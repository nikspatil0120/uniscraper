# pipeline/tier1_custom.py
#
# TIER 1 (Primary): Custom httpx + Playwright fallback with BFS deep crawling
# Fast, reliable, handles simple pages. Falls back to Playwright for JS-rendered content.
# Now includes exhaustive BFS crawling like the other tiers.

import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse
import hashlib

from pipeline.fetcher import fetch_page
from utils.text_cleaner import clean_html
from pipeline.link_extractor import extract_relevant_links
from utils.page_classifier import classify_page
from config import settings

logger = logging.getLogger(__name__)

_MIN_WORDS = 50


# ─────────────────────────────────────────────────────────────────────────────
# Single page fetch
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_single_page(url: str) -> dict:
    """
    Fetch a single page using httpx only (no Playwright fallback).
    
    Playwright is not used here because:
    - BFS crawls speculative/linked URLs — many are 404/thin pages
    - Playwright adds 10-30s per failed URL with no benefit
    - The main program page already used Playwright if needed via intelligent_fetcher
    
    Returns:
    {
        "markdown": str,    # cleaned HTML (we call it markdown for consistency)
        "html": str,        # raw HTML
        "links": list[str], # internal links
        "word_count": int,
        "url": str,
        "error": str | None,
    }
    """
    logger.info(f"[tier1_custom] Fetching {url}")
    
    try:
        result = await fetch_page(url, force_httpx=True)
        
        if not result.get("html"):
            return {
                "markdown": "",
                "html": "",
                "links": [],
                "word_count": 0,
                "url": url,
                "error": result.get("error") or "No HTML returned",
            }
        
        html = result["html"]
        cleaned = clean_html(html)
        links = extract_relevant_links(html, url)
        word_count = len(cleaned.split())
        
        logger.info(
            f"[tier1_custom] {url} — success, {word_count} words, "
            f"method={result.get('method_used')}"
        )
        
        return {
            "markdown": cleaned,
            "html": html,
            "links": links,
            "word_count": word_count,
            "url": result.get("final_url", url),
            "error": None,
        }
        
    except Exception as e:
        logger.error(f"[tier1_custom] {url} — error: {e}")
        return {
            "markdown": "",
            "html": "",
            "links": [],
            "word_count": 0,
            "url": url,
            "error": str(e),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Deep BFS crawling for program pages
# ─────────────────────────────────────────────────────────────────────────────

async def deep_crawl_program_page(
    start_url: str,
    max_pages: int = 20,
    max_depth: int = 4,
) -> list[dict]:
    """
    Exhaustive BFS crawl using custom fetcher.
    
    Discovers pages 2-3 levels deep (e.g., /admissions-and-aid/tuition-and-fees).
    Early exit when all critical pages (fees, english, entry) are found.
    
    Returns list of dicts:
    [
        {
            "url": str,
            "content": str,        # cleaned HTML
            "markdown": str,       # same as content (for consistency)
            "html": str,           # raw HTML
            "word_count": int,
            "method": str,         # "httpx" or "playwright"
            "tier": 1,
            "depth": int,
            "page_type": str,
        },
        ...
    ]
    """
    logger.info(
        f"[tier1_custom] Exhaustive BFS crawl starting: {start_url} "
        f"(max={max_pages}, depth={max_depth})"
    )
    
    visited = set()
    content_hashes = set()  # Deduplicate by content hash
    pages_data = []
    
    # BFS queue: (url, depth)
    queue = [(start_url, 0)]
    visited.add(start_url)

    # Pre-compute a "normalised program stem" so we can block year-variant
    # copies of the start URL (e.g. /2024/program/CADAN when start is /2026/…)
    # Pattern: any URL whose path matches /YYYY/<same-tail-as-start>
    _year_variant_pattern = None
    _start_parsed = urlparse(start_url)
    _start_path = _start_parsed.path.rstrip("/")
    _year_match = re.match(r'^(/\d{4})(/.+)$', _start_path)
    if _year_match:
        _program_tail = re.escape(_year_match.group(2))  # e.g. /program/CADAN
        _year_variant_pattern = re.compile(
            r'^/\d{4}' + _program_tail + r'(/.*)?$'
        )
    
    # Track critical pages for early exit
    critical_pages_found = {
        "fees": False,
        "english": False,
        "entry": False,
    }
    
    while queue and len(pages_data) < max_pages:
        # Process wave at current depth
        current_depth = queue[0][1]
        wave = [item for item in queue if item[1] == current_depth]
        queue = [item for item in queue if item[1] != current_depth]
        
        if not wave:
            break
        
        logger.info(
            f"[tier1_custom] Processing wave at depth {current_depth} — {len(wave)} URLs"
        )
        
        # Fetch wave concurrently
        tasks = [fetch_single_page(url) for url, _ in wave]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for (url, depth), result in zip(wave, results):
            if isinstance(result, Exception):
                logger.warning(f"[tier1_custom] {url} — exception: {result}")
                continue
            
            # Skip thin pages (redirected to 404, error pages, etc.)
            # Don't attempt Playwright — if httpx got < _MIN_WORDS, it's a dead end.
            if not result.get("markdown") or result["word_count"] < _MIN_WORDS:
                logger.debug(f"[tier1_custom] {url} — insufficient content ({result['word_count']} words), skipping")
                continue
            
            # Content deduplication
            content_hash = hashlib.md5(result["markdown"].encode()).hexdigest()
            if content_hash in content_hashes:
                logger.debug(f"[tier1_custom] {url} — duplicate content (hash={content_hash[:8]})")
                continue
            content_hashes.add(content_hash)
            
            # Classify page
            page_type = classify_page(url, result["markdown"])
            
            # Check for critical pages
            url_lower = url.lower()
            if any(x in url_lower for x in ["tuition", "fees", "cost", "bursar"]):
                critical_pages_found["fees"] = True
            if any(x in url_lower for x in ["english", "ielts", "toefl", "language"]):
                critical_pages_found["english"] = True
            if any(x in url_lower for x in ["entry", "admission", "requirement", "apply"]):
                critical_pages_found["entry"] = True
            
            # Store page data
            page_data = {
                "url": url,
                "content": result["markdown"],
                "markdown": result["markdown"],
                "html": result.get("html", ""),
                "word_count": result["word_count"],
                "method": "custom",
                "tier": 1,
                "depth": depth,
                "page_type": page_type,
            }
            pages_data.append(page_data)
            
            logger.info(
                f"[tier1_custom] Depth {depth} — {url} OK "
                f"({result['word_count']} words, {len(result.get('links', []))} links)"
            )
            
            # Add links to queue if we haven't hit max depth
            if depth < max_depth and len(pages_data) < max_pages:
                for link in result.get("links", []):
                    if link not in visited:
                        link_path = urlparse(link).path

                        # ── SKIP 1: individual course catalogue pages ─────────
                        # e.g. /2024/course/COMP6730, /2025/course/STAT7055
                        if re.search(r'/\d{4}/course/', link):
                            logger.debug(f"[tier1_custom] Skipping course catalogue URL: {link}")
                            continue

                        # ── SKIP 2: year-variant copies of the start program ──
                        # e.g. /2024/program/CADAN when start is /2026/program/CADAN
                        # These are identical content from other catalogue years.
                        if _year_variant_pattern and _year_variant_pattern.match(link_path):
                            # Allow the start URL's own year — block all others
                            if not link.rstrip("/").endswith(start_url.rstrip("/").split("://", 1)[-1].split("/", 1)[-1]):
                                logger.debug(f"[tier1_custom] Skipping year-variant URL: {link}")
                                continue

                        # ── SKIP 3: semester navigation pages ─────────────────
                        if any(pat in link for pat in [
                            "/First%20Semester/", "/Second%20Semester/",
                            "/Semester/", "/semester/",
                        ]):
                            logger.debug(f"[tier1_custom] Skipping semester nav URL: {link}")
                            continue

                        # ─────────────────────────────────────────────────────
                        visited.add(link)
                        queue.append((link, depth + 1))
        
        # Early exit check
        all_critical_found = all(critical_pages_found.values())
        if all_critical_found and len(pages_data) >= 15:
            logger.info(
                f"[tier1_custom] Early exit at depth {current_depth} — "
                f"all critical pages found ({len(pages_data)} pages total)"
            )
            break
    
    logger.info(
        f"[tier1_custom] BFS crawl complete — {len(pages_data)} pages fetched "
        f"(max depth reached: {max(p['depth'] for p in pages_data) if pages_data else 0})"
    )
    
    return pages_data


# ─────────────────────────────────────────────────────────────────────────────
# Program discovery (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

async def discover_university_programs(
    university_domain: str,
    max_urls: int = 50,
) -> list[str]:
    """
    Discover program URLs at a university using custom fetcher.
    
    Not as sophisticated as Firecrawl /map or Crawl4AI, but works as fallback.
    Starts from common entry points (/programs, /study, /courses) and crawls.
    
    Returns list of program URLs.
    """
    logger.info(f"[tier1_custom] Discovering programs at {university_domain}")
    
    # Common entry points for program listings
    entry_points = [
        f"https://{university_domain}/programs",
        f"https://{university_domain}/study",
        f"https://{university_domain}/courses",
        f"https://{university_domain}/postgraduate",
        f"https://{university_domain}/graduate",
    ]
    
    program_urls = set()
    visited = set()
    
    for entry_url in entry_points:
        if len(program_urls) >= max_urls:
            break
        
        try:
            result = await fetch_single_page(entry_url)
            if not result.get("links"):
                continue
            
            # Look for program-like URLs
            for link in result["links"]:
                if len(program_urls) >= max_urls:
                    break
                
                link_lower = link.lower()
                if any(x in link_lower for x in ["/program/", "/course/", "/msc-", "/mba-", "/master"]):
                    if link not in visited:
                        program_urls.add(link)
                        visited.add(link)
        
        except Exception as e:
            logger.warning(f"[tier1_custom] {entry_url} — failed: {e}")
            continue
    
    logger.info(f"[tier1_custom] Discovered {len(program_urls)} program URLs")
    return list(program_urls)
