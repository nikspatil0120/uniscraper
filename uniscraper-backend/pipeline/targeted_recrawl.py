# pipeline/targeted_recrawl.py
# Targeted recrawl — fetch specific pages suggested by gap analysis.
#
# Strategy:
#   1. Check if suggested page types already exist in discovered URLs
#   2. Generate candidate URLs for missing page types
#   3. Attempt to fetch each candidate (HTTP HEAD first for efficiency)
#   4. Return successful pages with content
#
# NOTE: These are speculative URLs — many will 404.
# We use httpx-only and discard thin pages immediately.
# Playwright is NOT attempted here: it adds 10-30s per failed URL
# and speculative URLs are almost always empty if httpx gets < 100 words.

import asyncio
import logging
import re
from urllib.parse import urlparse

import httpx

from pipeline.fetcher import fetch_page
from utils.text_cleaner import clean_html
from utils.page_classifier import classify_page

logger = logging.getLogger(__name__)


async def targeted_recrawl(
    base_url: str,
    suggested_page_types: list[str],
    existing_pages: list[dict],
    max_new_pages: int = 5,
) -> list[dict]:
    """
    Fetch pages suggested by gap analysis.
    
    Args:
        base_url: The original program URL
        suggested_page_types: Page types suggested by gap analyzer
        existing_pages: Already-fetched pages (to avoid duplicates)
        max_new_pages: Maximum number of new pages to fetch
    
    Returns:
        List of successfully fetched pages:
        [
            {
                "url": str,
                "content": str,  # Clean markdown/text
                "page_type": str,
                "word_count": int,
                "method": str,
                "tier": int,
            }
        ]
    """
    if not suggested_page_types:
        logger.info("[targeted_recrawl] No page types suggested, skipping")
        return []
    
    logger.info(
        f"[targeted_recrawl] Searching for: {', '.join(suggested_page_types)}"
    )
    
    # Check if we already have pages matching the suggested types
    existing_urls = {p.get("url", "").rstrip("/").lower() for p in existing_pages}
    existing_types = {p.get("page_type", "").lower() for p in existing_pages}
    
    # Filter out page types we already have
    needed_types = []
    for pt in suggested_page_types:
        if pt.lower() not in existing_types:
            # Also check if URL path contains this type
            if not any(pt.lower() in url for url in existing_urls):
                needed_types.append(pt)
    
    if not needed_types:
        logger.info("[targeted_recrawl] All suggested page types already scraped")
        return []
    
    logger.info(f"[targeted_recrawl] Need to fetch: {', '.join(needed_types)}")
    
    # Generate candidate URLs
    from pipeline.gap_analyzer import build_candidate_urls
    
    candidates = build_candidate_urls(base_url, needed_types)
    logger.info(f"[targeted_recrawl] Generated {len(candidates)} candidate URLs")
    
    # Filter out URLs we already fetched
    candidates = [
        url for url in candidates
        if url.rstrip("/").lower() not in existing_urls
    ]
    
    if not candidates:
        logger.info("[targeted_recrawl] All candidates already fetched")
        return []
    
    logger.info(f"[targeted_recrawl] Trying {len(candidates)} new URLs")
    
    # Fetch candidates in parallel (with limit)
    fetched_pages = []
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
    
    async def try_fetch(url: str) -> dict | None:
        async with semaphore:
            try:
                # Quick HEAD request first to check if page exists
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    head_resp = await client.head(url)
                    if head_resp.status_code >= 400:
                        logger.debug(f"[targeted_recrawl] {url} returned {head_resp.status_code}")
                        return None
                
                # Page exists, fetch full content via httpx only
                # NOTE: We deliberately skip Playwright here.
                # These are speculative URLs — if httpx gets < 100 words the page
                # is almost certainly a 404/error page. Playwright would also fail
                # and wastes 10-30 extra seconds per URL.
                logger.info(f"[targeted_recrawl] Fetching {url}")
                result = await fetch_page(url, force_httpx=True)
                
                if result.get("error"):
                    logger.debug(f"[targeted_recrawl] {url} fetch error: {result['error']}")
                    return None
                
                html = result.get("html", "")
                word_count = result.get("word_count", 0) or len(html.split())
                
                # Thin content check — if httpx got < 100 words, it's almost
                # certainly a 404/empty page. Skip immediately, don't try Playwright.
                if word_count < 100:
                    logger.debug(
                        f"[targeted_recrawl] {url} — thin ({word_count} words), skipping"
                    )
                    return None
                
                # Clean and classify
                content = clean_html(html) if html else ""
                content_words = len(content.split())
                
                if content_words < 50:
                    logger.debug(f"[targeted_recrawl] {url} too thin after cleaning ({content_words} words)")
                    return None
                
                page_type = classify_page(url, content)
                
                logger.info(
                    f"[targeted_recrawl] ✅ {url} ({page_type}, {content_words} words)"
                )
                
                return {
                    "url": result.get("final_url", url),
                    "content": content,
                    "page_type": page_type,
                    "word_count": content_words,
                    "method": result.get("method_used", "httpx"),
                    "tier": 1,
                    "html": html,
                }
                
            except Exception as exc:
                logger.debug(f"[targeted_recrawl] {url} exception: {exc}")
                return None
    
    # Try all candidates
    tasks = [try_fetch(url) for url in candidates[:15]]  # Limit to 15 attempts
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, dict) and result is not None:
            fetched_pages.append(result)
            if len(fetched_pages) >= max_new_pages:
                break
    
    logger.info(
        f"[targeted_recrawl] Successfully fetched {len(fetched_pages)} new pages"
    )
    
    return fetched_pages


async def check_existing_pages_for_content(
    existing_pages: list[dict],
    missing_fields: list[str],
) -> dict[str, str]:
    """
    Re-scan existing pages to see if missing content is actually there
    but was missed in first extraction pass.
    
    This is a lightweight check before doing expensive recrawls.
    
    Returns:
        {
            "field_name": "url_where_found",
            ...
        }
    """
    field_keywords = {
        "tuition_fees": ["tuition", "fee", "cost", "$", "£", "€", "USD", "GBP"],
        "english_requirements": ["IELTS", "TOEFL", "PTE", "Duolingo", "English language"],
        "application_deadlines": ["deadline", "closing date", "apply by", "submission"],
        "min_academic_requirement": ["GPA", "grade", "academic requirement", "qualification"],
    }
    
    found_in = {}
    
    for field in missing_fields:
        keywords = field_keywords.get(field, [])
        if not keywords:
            continue
        
        for page in existing_pages:
            content = page.get("content", "").lower()
            
            # Check if multiple keywords appear in this page
            matches = sum(1 for kw in keywords if kw.lower() in content)
            
            if matches >= 2:  # At least 2 keywords found
                found_in[field] = page.get("url", "unknown")
                logger.info(
                    f"[targeted_recrawl] Field '{field}' likely in already-fetched "
                    f"{page.get('url', '')}"
                )
                break
    
    return found_in
