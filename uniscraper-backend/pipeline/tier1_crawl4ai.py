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
    """Safely extract fit_markdown from a crawl result."""
    if not result.markdown:
        return ""
    if hasattr(result.markdown, "fit_markdown"):
        return result.markdown.fit_markdown or ""
    return str(result.markdown)


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

async def deep_crawl_program_page(url: str, max_pages: int = 15) -> list[dict]:
    """
    Crawl a university program page and all relevant sub-pages.
    Replaces BFSDeepCrawlStrategy (broken in current Crawl4AI version —
    CrawlResultContainer never exposes the actual CrawlResult content).
    
    Strategy:
    1. Fetch the main page with Crawl4AI single fetch
    2. Extract all internal links
    3. Score and rank links by keyword relevance  
    4. Fetch top N sub-pages in parallel
    5. Return all pages as a flat list
    """
    logger.info(f"[tier1_crawl4ai] deep_crawl_program_page called with URL: {url}")
    pages = []
    
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
        word_count_threshold=30,
        cache_mode=CacheMode.BYPASS,
        remove_overlay_elements=True,
        remove_consent_popups=True,
        process_iframes=True,
    )

    # ── Step 1: Fetch main page ──────────────────────────────────────────────
    try:
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
            
        if not result.success:
            logger.warning(f"[tier1_crawl4ai] Main page fetch failed: {result.error_message}")
            return []

        logger.info(f"[tier1_crawl4ai] Main page fetch succeeded")
        markdown = _extract_markdown(result)
        logger.info(f"[tier1_crawl4ai] Extracted markdown length: {len(markdown)}")
        
        if len(markdown.split()) >= 30:
            pages.append({
                "url": url,
                "markdown": markdown,
                "html": result.html or "",
                "word_count": len(markdown.split()),
                "method": "crawl4ai",
                "tier": 1,
                "page_type": classify_page(url, markdown),
            })
            logger.info(f"[tier1_crawl4ai] Main page: {len(markdown.split())} words")
            
        main_html = result.html or ""

    except Exception as e:
        logger.warning(f"[tier1_crawl4ai] Main page exception: {e}")
        return []

    if not main_html:
        return pages

    # ── Step 2: Extract and score internal links ─────────────────────────────
    import re
    
    HIGH_VALUE_KEYWORDS = [
        "entry-requirement", "entry_requirement", "admission", "requirement",
        "english", "language", "ielts", "toefl",
        "fee", "tuition", "cost", "funding", "scholarship", "finance",
        "how-to-apply", "apply", "application", "deadline",
        "overview", "about", "programme", "program", "course",
    ]
    # Pages that are generic site nav — penalise heavily
    NAV_PENALTY_PATTERNS = [
        "/find/", "/find?", "study-with-us", "graduate-courses",
        "in_c=hcta", "in_c=", "?in_c", "courses/list", "/search",
        "/sitemap", "/home", "/index",
    ]
    SKIP_PATTERNS = [
        "login", "logout", "signin", "signup", "register", "cart", "shop",
        "news", "event", "blog", "staff", "contact", "sitemap", "search",
        "privacy", "cookie", "legal", "accessibility", "alumni", "donate",
        "mailto:", "javascript:", "#", ".pdf", ".doc", ".zip",
    ]

    base_domain = urlparse(url).netloc
    # Base path — sub-pages should START with this path (program-specific only)
    base_path = urlparse(url).path.rstrip("/")
    
    candidate_urls = set()

    # Source A: raw HTML links
    if main_html:
        soup = BeautifulSoup(main_html, "lxml")
        for a in soup.find_all("a", href=True):
            abs_url = urljoin(url, a["href"].strip())
            candidate_urls.add(abs_url)

    # Source B: markdown links — catches JS-rendered links HTML misses
    # Markdown format: [text](url)
    for match in re.finditer(r'\[([^\]]*)\]\((https?://[^\)]+)\)', markdown):
        candidate_urls.add(match.group(2))
    # Also plain URLs in markdown
    for match in re.finditer(r'(?<!\()https?://[^\s\)>]+', markdown):
        candidate_urls.add(match.group(0).rstrip(".,)"))

    # Source C: construct known sub-page URLs directly
    # Many university sites follow predictable patterns
    KNOWN_SUBPAGE_SUFFIXES = [
        "/entry-requirements/", "/entry-requirements",
        "/fees/", "/fees", 
        "/how-to-apply/", "/how-to-apply",
        "/application/", "/application",
        "/english-requirements/", "/english-language/",
        "/scholarships/", "/funding/",
        "/overview/", "/about/",
    ]
    for suffix in KNOWN_SUBPAGE_SUFFIXES:
        candidate_urls.add(f"https://{base_domain}{base_path}{suffix}")

    scored_links = {}
    for abs_url in candidate_urls:
        parsed = urlparse(abs_url)
        
        # Same domain only
        if parsed.netloc != base_domain:
            continue
        # Must be under the base program path OR a known relevant sub-path
        # (prevents generic /find/ and /study-with-us/ from sneaking in)
        if not parsed.path.startswith(base_path):
            continue
        # Skip noise
        if any(skip in abs_url.lower() for skip in SKIP_PATTERNS):
            continue
        # Skip already visited / same as main
        clean_url = abs_url.rstrip("/")
        if clean_url == url.rstrip("/") or clean_url in scored_links:
            continue
        
        # Apply nav penalty — these are generic pages, not program-specific
        if any(pat in abs_url.lower() for pat in NAV_PENALTY_PATTERNS):
            continue  # skip entirely — they're never useful
        
        # Score by keyword relevance
        url_lower = abs_url.lower()
        score = sum(2 for kw in HIGH_VALUE_KEYWORDS if kw in url_lower)  # URL match = 2pts
                
        if score > 0:
            scored_links[clean_url] = score

    # Pick top sub-pages by score
    top_subpages = sorted(scored_links, key=scored_links.get, reverse=True)[:max_pages - 1]
    
    logger.info(
        f"[tier1_crawl4ai] Found {len(scored_links)} scored links "
        f"(from {len(candidate_urls)} candidates), "
        f"fetching top {len(top_subpages)}: {top_subpages}"
    )

    if not top_subpages:
        return pages

    # ── Step 3: Fetch sub-pages in parallel (max 4 concurrent) ───────────────
    semaphore = asyncio.Semaphore(4)

    async def fetch_subpage(suburl: str) -> dict | None:
        async with semaphore:
            try:
                async with AsyncWebCrawler(config=browser_cfg) as crawler:
                    result = await crawler.arun(url=suburl, config=run_cfg)
                    
                if not result.success:
                    return None

                markdown = _extract_markdown(result)
                
                wc = len(markdown.split())
                if wc < 30:
                    return None

                return {
                    "url": suburl,
                    "markdown": markdown,
                    "html": result.html or "",
                    "word_count": wc,
                    "method": "crawl4ai",
                    "tier": 1,
                    "page_type": classify_page(suburl, markdown),
                }
            except Exception as e:
                logger.debug(f"[tier1_crawl4ai] Sub-page {suburl} failed: {e}")
                return None

    sub_results = await asyncio.gather(*[fetch_subpage(u) for u in top_subpages])
    
    for r in sub_results:
        if r is not None:
            pages.append(r)
            logger.info(f"[tier1_crawl4ai] Sub-page OK: {r['url']} ({r['word_count']} words)")

    logger.info(
        f"[tier1_crawl4ai] deep_crawl {url} — "
        f"{len(pages)} valid pages total"
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
