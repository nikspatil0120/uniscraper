# pipeline/tier1_crawl4ai.py
#
# Tier 1 — Primary intelligent fetcher using Crawl4AI.
# Uses stealth Playwright (patchright) + fit_markdown for LLM-ready output.
#
# Public functions:
#   fetch_single_page(url)                  — single page fetch
#   deep_crawl_program_page(url, max_pages) — BFS main page + sub-pages
#   discover_university_programs(domain)    — Phase 2: find all program URLs

import asyncio
import logging
import hashlib
import re

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from utils.page_classifier import classify_page

logger = logging.getLogger(__name__)

# ── Shared browser config ─────────────────────────────────────────────────────
BROWSER_CONFIG = BrowserConfig(
    browser_type="chromium",
    headless=True,
    verbose=False,
    enable_stealth=True,            # patchright — hides automation flags from Cloudflare
    extra_args=["--no-sandbox"],
    ignore_https_errors=True,
)

# ── Admission-relevant URL patterns ───────────────────────────────────────────
_ADMISSION_INCLUDE = [
    "*admission*", "*admissions*",
    "*fees*", "*fee*", "*tuition*", "*cost*", "*costs*", "*funding*", "*finance*",
    "*requirement*", "*requirements*", "*eligibility*", "*eligib*",
    "*english*", "*language*", "*ielts*", "*toefl*",
    "*apply*", "*application*", "*entry*",
    "*scholarships*", "*scholarship*",
]
_ADMISSION_EXCLUDE = [
    "*login*", "*sign-in*", "*portal*", "*staff*", "*faculty*",
    "*news*", "*blog*", "*events*", "*calendar*", "*alumni*",
    "*donate*", "*giving*", "*contact*", "*about*",
    "*cookie*", "*privacy*", "*visa*", "*immigration*",
    "*undergraduate*", "*ug/*", "*ug-*",
]

# ── Program discovery patterns (Phase 2) ─────────────────────────────────────
_PROGRAM_INCLUDE = [
    "*programme*", "*programs*", "*courses*",
    "*postgraduate*", "*graduate*",
    "*masters*", "*msc*", "*mba*",
    "*phd*", "*doctorate*",
    "*taught*", "*study*",
]
_PROGRAM_EXCLUDE = [
    "*login*", "*staff*", "*alumni*",
    "*news*", "*events*", "*research*",
    "*about*", "*contact*", "*donate*",
]


def _extract_markdown(result) -> str:
    """
    Safely extract markdown from a crawl result.
    
    Crawl4AI markdown hierarchy:
    - raw_markdown: Full unfiltered markdown (always populated)
    - fit_markdown: Filtered markdown (only when using PruningContentFilter/BM25)
    
    For our use case, we want raw_markdown since we're not using content filters.
    """
    if not result.markdown:
        return ""
    
    # Try raw_markdown first (always available)
    if hasattr(result.markdown, "raw_markdown") and result.markdown.raw_markdown:
        return result.markdown.raw_markdown
    
    # Fallback to fit_markdown (only populated with filters)
    if hasattr(result.markdown, "fit_markdown") and result.markdown.fit_markdown:
        return result.markdown.fit_markdown
    
    # Last resort: convert to string
    return str(result.markdown) if result.markdown else ""


# ─────────────────────────────────────────────────────────────────────────────
# Single-page fetch
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_single_page(url: str) -> dict:
    """
    Fetch one page with Crawl4AI stealth Playwright.

    Returns:
    {
        "markdown":   str | None,
        "html":       str | None,
        "links":      list[str],   # internal links
        "word_count": int,
        "method":     "crawl4ai",
        "tier":       1,
        "error":      str | None,
    }
    Never raises.
    """
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        remove_overlay_elements=True,
        remove_consent_popups=True,
        process_iframes=True,
        wait_until="networkidle",
        page_timeout=30000,
        # Execute JavaScript to handle dynamic content
        js_code="await new Promise(r => setTimeout(r, 2000));",  # Wait 2s for JS rendering
    )

    try:
        async with AsyncWebCrawler(config=BROWSER_CONFIG) as crawler:
            result = await crawler.arun(url=url, config=run_config)

        if result.success:
            markdown = _extract_markdown(result)
            word_count = len(markdown.split()) if markdown else 0

            links: list[str] = []
            if result.links:
                for link in result.links.get("internal", []):
                    href = link.get("href", "") if isinstance(link, dict) else str(link)
                    if href and href.startswith("http"):
                        links.append(href)

            logger.info(
                f"[tier1_crawl4ai] {url} — success, {word_count} words, "
                f"{len(links)} internal links"
            )
            return {
                "markdown":   markdown,
                "html":       result.html or "",
                "links":      links,
                "word_count": word_count,
                "method":     "crawl4ai",
                "tier":       1,
                "error":      None,
            }
        else:
            err = getattr(result, "error_message", "unknown error") or "unknown error"
            logger.warning(f"[tier1_crawl4ai] {url} — failed: {err}")
            return {
                "markdown": None, "html": None, "links": [],
                "word_count": 0, "method": "crawl4ai", "tier": 1, "error": err,
            }

    except Exception as exc:
        logger.error(f"[tier1_crawl4ai] {url} — {type(exc).__name__}: {exc}")
        return {
            "markdown": None, "html": None, "links": [],
            "word_count": 0, "method": "crawl4ai", "tier": 1, "error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Deep crawl — main page + relevant sub-pages
# ─────────────────────────────────────────────────────────────────────────────

def _score_and_filter_links(
    candidate_urls: set[str],
    base_url: str,
    visited: set[str],
) -> dict[str, int]:
    """
    Score and filter candidate URLs for relevance to program admission information.
    Returns dict of {clean_url: score} for URLs worth crawling.
    
    Extracted as helper for reuse in BFS crawling.
    """
    HIGH_VALUE_KEYWORDS = [
        "entry-requirement", "entry_requirement", "admission", "requirement",
        "english", "language", "ielts", "toefl",
        "fee", "tuition", "cost", "funding", "scholarship", "finance",
        "how-to-apply", "apply", "application", "deadline",
        "overview", "about", "programme", "program", "course",
        "structure", "modules", "curriculum",
    ]
    SKIP_PATTERNS = [
        "login", "logout", "signin", "signup", "register", "cart", "shop",
        "news", "event", "blog", "staff", "contact", "sitemap", "search",
        "privacy", "cookie", "legal", "accessibility", "alumni", "donate",
        "mailto:", "javascript:", "#", ".pdf", ".doc", ".zip",
        "/find/", "/find?", "study-with-us", "graduate-courses",
        "in_c=", "?in_c", "courses/list",
    ]
    
    base_domain = urlparse(base_url).netloc
    base_path = urlparse(base_url).path.rstrip("/")
    
    scored_links = {}
    for abs_url in candidate_urls:
        parsed = urlparse(abs_url)
        
        # Same domain only
        if parsed.netloc != base_domain:
            continue
        # Must be under the base program path (program-specific only)
        if not parsed.path.startswith(base_path):
            continue
        # Skip noise
        if any(skip in abs_url.lower() for skip in SKIP_PATTERNS):
            continue
        # Skip already visited
        clean_url = abs_url.rstrip("/")
        if clean_url in visited or clean_url == base_url.rstrip("/"):
            continue
        
        # Score by keyword relevance
        url_lower = abs_url.lower()
        score = sum(2 for kw in HIGH_VALUE_KEYWORDS if kw in url_lower)
        
        if score > 0:
            scored_links[clean_url] = score
    
    return scored_links


async def deep_crawl_program_page(url: str, max_pages: int = 50) -> list[dict]:
    """
    Exhaustive BFS crawl of a university program page and ALL relevant sub-pages.
    
    Strategy:
    1. Start with the main page (depth 0)
    2. Extract and score all links from fetched pages
    3. Fetch the highest-scoring unvisited links in waves (breadth-first)
    4. Continue until max_pages reached or max_depth exceeded
    5. Return all pages as a flat list
    
    This ensures we discover information buried 2-3 levels deep (e.g.,
    international fees, specific IELTS scores in nested pages).
    """
    from config import settings
    
    logger.info(f"[tier1_crawl4ai] Exhaustive BFS crawl starting: {url} (max={max_pages}, depth={settings.max_depth})")
    
    browser_cfg = BrowserConfig(
        browser_type="chromium",
        headless=True,
        verbose=False,
        enable_stealth=True,
        extra_args=["--no-sandbox"],
        ignore_https_errors=True,
    )
    run_cfg = CrawlerRunConfig(
        page_timeout=60000,
        wait_until="domcontentloaded",
        word_count_threshold=settings.min_page_words,
        cache_mode=CacheMode.BYPASS,
        remove_overlay_elements=True,
        remove_consent_popups=True,
        process_iframes=True,
        js_code="await new Promise(r => setTimeout(r, 3000));",
    )
    
    pages = []
    visited = set()
    content_hashes = set()  # Track content hashes to detect duplicates
    queue = [(url, 0)]  # (url, depth)
    visited.add(url.rstrip("/"))
    
    semaphore = asyncio.Semaphore(settings.max_concurrent_fetches)
    
    async def fetch_page_with_links(fetch_url: str, depth: int) -> dict | None:
        """Fetch a single page and extract its links."""
        async with semaphore:
            try:
                async with AsyncWebCrawler(config=browser_cfg) as crawler:
                    result = await crawler.arun(url=fetch_url, config=run_cfg)
                
                if not result.success:
                    logger.debug(f"[tier1_crawl4ai] Depth {depth} — {fetch_url} failed: {result.error_message}")
                    return None
                
                markdown = _extract_markdown(result)
                wc = len(markdown.split())
                
                if wc < settings.min_page_words:
                    logger.debug(f"[tier1_crawl4ai] Depth {depth} — {fetch_url} too short ({wc} words)")
                    return None
                
                # Check for duplicate content (e.g., Cambridge returning same template)
                content_hash = hashlib.md5(markdown.encode('utf-8')).hexdigest()
                if content_hash in content_hashes:
                    logger.debug(f"[tier1_crawl4ai] Depth {depth} — {fetch_url} duplicate content (hash: {content_hash[:8]}), skipping")
                    return None
                content_hashes.add(content_hash)
                
                # Extract links for next wave
                extracted_links = set()
                
                # Source A: HTML links
                if result.html:
                    soup = BeautifulSoup(result.html, "lxml")
                    for a in soup.find_all("a", href=True):
                        abs_url = urljoin(fetch_url, a["href"].strip())
                        extracted_links.add(abs_url)
                
                # Source B: markdown links
                for match in re.finditer(r'\[([^\]]*)\]\((https?://[^\)]+)\)', markdown):
                    extracted_links.add(match.group(2))
                for match in re.finditer(r'(?<!\()https?://[^\s\)>]+', markdown):
                    extracted_links.add(match.group(0).rstrip(".,)"))
                
                # Source C: construct known sub-page patterns
                base_domain = urlparse(fetch_url).netloc
                base_path = urlparse(fetch_url).path.rstrip("/")
                KNOWN_SUFFIXES = [
                    "/entry-requirements", "/fees", "/how-to-apply",
                    "/application", "/english-requirements", "/english-language",
                    "/scholarships", "/funding", "/overview", "/about",
                    "/structure", "/modules", "/curriculum",
                ]
                for suffix in KNOWN_SUFFIXES:
                    extracted_links.add(f"https://{base_domain}{base_path}{suffix}")
                
                logger.info(f"[tier1_crawl4ai] Depth {depth} — {fetch_url} OK ({wc} words, {len(extracted_links)} links)")
                
                return {
                    "url": fetch_url,
                    "markdown": markdown,
                    "html": result.html or "",
                    "word_count": wc,
                    "method": "crawl4ai",
                    "tier": 1,
                    "page_type": classify_page(fetch_url, markdown),
                    "depth": depth,
                    "links": extracted_links,
                }
                
            except Exception as e:
                logger.debug(f"[tier1_crawl4ai] Depth {depth} — {fetch_url} exception: {e}")
                return None
    
    # ── BFS wave-based crawling ───────────────────────────────────────────────
    current_depth = 0
    
    while queue and len(pages) < max_pages:
        # Group URLs by depth to process in waves
        current_wave = []
        next_queue = []
        
        for fetch_url, depth in queue:
            if depth == current_depth:
                current_wave.append((fetch_url, depth))
            else:
                next_queue.append((fetch_url, depth))
        
        if not current_wave:
            # Move to next depth
            current_depth += 1
            queue = next_queue
            if current_depth > settings.max_depth:
                logger.info(f"[tier1_crawl4ai] Max depth {settings.max_depth} reached, stopping")
                break
            continue
        
        logger.info(f"[tier1_crawl4ai] Processing wave at depth {current_depth} — {len(current_wave)} URLs")
        
        # Fetch all URLs in current wave in parallel
        wave_results = await asyncio.gather(
            *[fetch_page_with_links(u, d) for u, d in current_wave]
        )
        
        # Process results and queue next level
        new_candidates = set()
        
        for result in wave_results:
            if result is None:
                continue
            
            # Add to pages list
            result_copy = {k: v for k, v in result.items() if k != "links"}
            pages.append(result_copy)
            
            # Collect links for next depth
            if result["depth"] < settings.max_depth:
                new_candidates.update(result["links"])
        
        # Score and filter candidates for next wave
        if new_candidates and len(pages) < max_pages:
            scored = _score_and_filter_links(new_candidates, url, visited)
            
            # Sort by score and add top candidates to queue
            remaining_slots = max_pages - len(pages)
            top_candidates = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:remaining_slots]
            
            for candidate_url, score in top_candidates:
                visited.add(candidate_url.rstrip("/"))
                next_queue.append((candidate_url, current_depth + 1))
                logger.debug(f"[tier1_crawl4ai] Queued depth {current_depth + 1}: {candidate_url} (score={score})")
        
        queue = next_queue
    
    logger.info(
        f"[tier1_crawl4ai] BFS crawl complete — "
        f"{len(pages)} pages fetched (max depth reached: {max(p.get('depth', 0) for p in pages) if pages else 0})"
    )
    
    return pages


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Discover all program URLs on a university website
# ─────────────────────────────────────────────────────────────────────────────

async def discover_university_programs(
    university_domain: str,
    max_urls: int = 100,
) -> list[str]:
    """
    Phase 2: Discover program URLs at a university.
    TEMPORARY: Return empty list to force fallback to other methods.
    TODO: Implement without broken BFSDeepCrawlStrategy
    """
    logger.info(f"[tier1_crawl4ai] discover_university_programs {university_domain} — DISABLED")
    return []
