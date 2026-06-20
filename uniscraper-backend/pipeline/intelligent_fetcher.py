# pipeline/intelligent_fetcher.py
#
# Master fetch orchestrator — three-tier waterfall.
#
# TIER 1 (Primary):    Custom    — httpx → Playwright fallback (fast, simple pages)
# TIER 2 (Fallback 1): Firecrawl — hosted API, handles Cloudflare + JavaScript
# TIER 3 (Fallback 2): Crawl4AI  — stealth Playwright with deep crawling (complex cases)
#
# Public functions:
#   fetch_page_intelligent(url)          — single page, best tier available
#   fetch_subpages_intelligent(url, n)   — main + sub-pages, best tier available
#   discover_programs_intelligent(...)   — Phase 2: find all program URLs

import asyncio
import logging

from config import settings

logger = logging.getLogger(__name__)

_MIN_WORDS = 200  # below this → try next tier


# ─────────────────────────────────────────────────────────────────────────────
# Single-page fetch
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_page_intelligent(url: str) -> dict:
    """
    Fetch one page, trying tiers in order until sufficient content is returned.

    Returns:
    {
        "content":    str,        # clean markdown or cleaned HTML
        "html":       str,        # raw HTML (may be empty for Firecrawl)
        "links":      list[str],  # internal links
        "word_count": int,
        "method":     str,        # "custom" | "firecrawl" | "crawl4ai"
        "tier":       int,        # 1, 2, or 3
        "url":        str,
        "error":      str | None,
    }
    """

    # ── TIER 1: Custom httpx + Playwright ────────────────────────────────────
    logger.info(f"[intelligent_fetcher] {url} — trying Tier 1 (custom)")
    try:
        from pipeline.tier1_custom import fetch_single_page
        r = await fetch_single_page(url)
        if r["markdown"] and r["word_count"] >= _MIN_WORDS:
            logger.info(
                f"[intelligent_fetcher] {url} — Tier 1 SUCCESS ({r['word_count']} words)"
            )
            return {
                "content": r["markdown"], "html": r["html"],
                "links": r["links"], "word_count": r["word_count"],
                "method": "custom", "tier": 1, "url": url, "error": None,
            }
        logger.warning(
            f"[intelligent_fetcher] {url} — Tier 1 insufficient "
            f"({r['word_count']} words), trying Tier 2"
        )
    except Exception as exc:
        logger.error(f"[intelligent_fetcher] {url} — Tier 1 exception: {exc}, trying Tier 2")

    # ── TIER 2: Firecrawl ─────────────────────────────────────────────────────
    if settings.firecrawl_enabled and settings.firecrawl_api_key:
        logger.info(f"[intelligent_fetcher] {url} — trying Tier 2 (Firecrawl)")
        try:
            from pipeline.tier2_firecrawl import fetch_single_page
            r = await fetch_single_page(url)
            if r["markdown"] and r["word_count"] >= _MIN_WORDS:
                logger.info(
                    f"[intelligent_fetcher] {url} — Tier 2 SUCCESS ({r['word_count']} words)"
                )
                return {
                    "content": r["markdown"], "html": r["html"],
                    "links": r["links"], "word_count": r["word_count"],
                    "method": "firecrawl", "tier": 2, "url": url, "error": None,
                }
            logger.warning(
                f"[intelligent_fetcher] {url} — Tier 2 insufficient "
                f"({r['word_count']} words), trying Tier 3"
            )
        except Exception as exc:
            logger.error(f"[intelligent_fetcher] {url} — Tier 2 exception: {exc}, trying Tier 3")

    # ── TIER 3: Crawl4AI (deep crawling fallback) ────────────────────────────
    if settings.crawl4ai_enabled:
        logger.info(f"[intelligent_fetcher] {url} — trying Tier 3 (Crawl4AI)")
        try:
            from pipeline.tier3_crawl4ai import fetch_single_page
            r = await fetch_single_page(url)
            if r["markdown"] and r["word_count"] >= _MIN_WORDS:
                logger.info(
                    f"[intelligent_fetcher] {url} — Tier 3 SUCCESS ({r['word_count']} words)"
                )
                return {
                    "content": r["markdown"], "html": r["html"],
                    "links": r["links"], "word_count": r["word_count"],
                    "method": "crawl4ai", "tier": 3, "url": url, "error": None,
                }
            logger.warning(
                f"[intelligent_fetcher] {url} — Tier 3 insufficient "
                f"({r['word_count']} words)"
            )
        except Exception as exc:
            logger.error(f"[intelligent_fetcher] {url} — Tier 3 exception: {exc}")

    # ── All tiers failed ──────────────────────────────────────────────────────
    logger.error(f"[intelligent_fetcher] {url} — all tiers failed")
    return {
        "content": "", "html": "", "links": [], "word_count": 0,
        "method": "all_failed", "tier": 0, "url": url, "error": "All tiers failed",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Multi-page fetch (main + sub-pages)
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_subpages_intelligent(url: str, max_pages: int = 50) -> list[dict]:
    """
    Fetch main page + admission-relevant sub-pages using the best available tier.
    
    Exhaustive crawling: visits ALL relevant pages up to max_pages and max_depth.
    Information is often buried 2-3 levels deep (international fees, IELTS scores).

    Returns list of dicts, each with keys:
        url, content, html, word_count, method, tier, page_type, depth
    First item is the main page.
    """

    # ── TIER 1: Custom httpx + Playwright with BFS ───────────────────────────
    logger.info(f"[intelligent_fetcher] subpages {url} — trying Tier 1 (custom)")
    try:
        from pipeline.tier1_custom import deep_crawl_program_page, fetch_single_page
        from utils.page_classifier import classify_page
        
        pages = await deep_crawl_program_page(url, max_pages)
        
        if not pages:
            # Deep crawl returned nothing — try single page as Tier 1 minimum
            logger.warning(
                f"[intelligent_fetcher] Tier 1 deep crawl returned no pages "
                f"— trying single fetch"
            )
            try:
                single = await fetch_single_page(url)
                if single.get("word_count", 0) >= _MIN_WORDS:
                    pages = [{
                        "url": url,
                        "content": single.get("markdown", ""),
                        "markdown": single.get("markdown", ""),
                        "html": single.get("html", ""),
                        "word_count": single["word_count"],
                        "method": "custom",
                        "tier": 1,
                        "page_type": classify_page(url, single.get("markdown", "")),
                        "depth": 0,
                    }]
                    logger.info(
                        f"[intelligent_fetcher] Single fetch fallback succeeded "
                        f"({pages[0]['word_count']} words)"
                    )
            except Exception as e:
                logger.warning(f"[intelligent_fetcher] Single fetch also failed: {e}")

        # ── Tier 1 success: any valid main page is enough to proceed ─────
        if len(pages) >= 1 and pages[0]["word_count"] >= _MIN_WORDS:
            logger.info(
                f"[intelligent_fetcher] Tier 1 SUCCESS — "
                f"{len(pages)} pages (depths: {sorted(set(p.get('depth', 0) for p in pages))})"
            )
            return [
                {
                    **p,
                    "content": p.get("markdown", ""),
                    "page_type": p.get("page_type", classify_page(p["url"], p.get("markdown", ""))),
                }
                for p in pages
            ]
            
        reason = f"{pages[0]['word_count']} words" if pages else "no pages"
        logger.warning(
            f"[intelligent_fetcher] subpages {url} — "
            f"Tier 1 insufficient ({reason}), trying Tier 2"
        )
    except Exception as exc:
        logger.warning(f"[intelligent_fetcher] Tier 1 deep crawl failed: {exc}")

    # ── TIER 2: Firecrawl exhaustive crawl ────────────────────────────────────
    if settings.firecrawl_enabled and settings.firecrawl_api_key:
        logger.info(f"[intelligent_fetcher] subpages {url} — trying Tier 2 (Firecrawl)")
        try:
            from pipeline.tier2_firecrawl import crawl_program_subpages
            from utils.page_classifier import classify_page
            pages = await crawl_program_subpages(url, max_pages)
            if len(pages) >= 1 and pages[0].get("word_count", 0) >= _MIN_WORDS:
                max_depth = max(p.get("depth", 0) for p in pages) if pages else 0
                logger.info(
                    f"[intelligent_fetcher] Tier 2 SUCCESS — "
                    f"{len(pages)} pages (max depth: {max_depth})"
                )
                return [
                    {
                        **p,
                        "content": p.get("markdown", ""),
                        "page_type": classify_page(p["url"], p.get("markdown", "")),
                    }
                    for p in pages
                ]
            logger.warning(
                f"[intelligent_fetcher] subpages {url} — Tier 2 insufficient, trying Tier 3"
            )
        except Exception as exc:
            logger.warning(f"[intelligent_fetcher] Tier 2 crawl failed: {exc}")

    # ── TIER 3: Crawl4AI deep crawling ───────────────────────────────────────
    if settings.crawl4ai_enabled:
        logger.info(f"[intelligent_fetcher] subpages {url} — trying Tier 3 (Crawl4AI)")
        try:
            from pipeline.tier3_crawl4ai import deep_crawl_program_page, fetch_single_page
            from utils.page_classifier import classify_page
            
            pages = await deep_crawl_program_page(url, max_pages)
            
            if not pages:
                # Try single page fallback
                logger.warning(
                    f"[intelligent_fetcher] Tier 3 deep crawl returned no pages "
                    f"— trying single fetch"
                )
                try:
                    single = await fetch_single_page(url)
                    if single.get("word_count", 0) >= _MIN_WORDS:
                        pages = [{
                            "url": url,
                            "content": single.get("markdown", ""),
                            "markdown": single.get("markdown", ""),
                            "html": single.get("html", ""),
                            "word_count": single["word_count"],
                            "method": "crawl4ai",
                            "tier": 3,
                            "page_type": classify_page(url, single.get("markdown", "")),
                            "depth": 0,
                        }]
                except Exception as e:
                    logger.warning(f"[intelligent_fetcher] Tier 3 single fetch failed: {e}")

            if len(pages) >= 1 and pages[0]["word_count"] >= _MIN_WORDS:
                logger.info(
                    f"[intelligent_fetcher] Tier 3 SUCCESS — "
                    f"{len(pages)} pages (depths: {sorted(set(p.get('depth', 0) for p in pages))})"
                )
                return [
                    {
                        **p,
                        "content": p.get("markdown", ""),
                        "page_type": p.get("page_type", classify_page(p["url"], p.get("markdown", ""))),
                    }
                    for p in pages
                ]
                
            logger.warning(f"[intelligent_fetcher] Tier 3 insufficient")
        except Exception as exc:
            logger.warning(f"[intelligent_fetcher] Tier 3 crawl failed: {exc}")

    logger.error(f"[intelligent_fetcher] all subpage tiers failed for {url}")
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Program discovery
# ─────────────────────────────────────────────────────────────────────────────

async def discover_programs_intelligent(
    university_name: str,
    country: str,
    university_domain: str,
) -> list[dict]:
    """
    Phase 2: Discover all program URLs at a university.
    Tries Firecrawl /map first (fastest), then fallback to Tier 1 custom, then Tier 3 Crawl4AI.
    Returns list of {url, program_name, degree_level} dicts.
    """

    # Firecrawl map is best — one API call returns a full sitemap
    if settings.firecrawl_enabled and settings.firecrawl_api_key:
        try:
            from pipeline.tier2_firecrawl import map_university_programs
            urls = await map_university_programs(f"https://{university_domain}")
            if urls:
                logger.info(
                    f"[intelligent_fetcher] discover {university_domain} — "
                    f"Firecrawl map: {len(urls)} URLs"
                )
                return [{"url": u, "program_name": None, "degree_level": None} for u in urls]
        except Exception as exc:
            logger.warning(f"[intelligent_fetcher] Firecrawl map failed: {exc}")

    # Custom fetcher discovery as Tier 1 fallback
    try:
        from pipeline.tier1_custom import discover_university_programs
        urls = await discover_university_programs(university_domain, max_urls=50)
        if urls:
            logger.info(
                f"[intelligent_fetcher] discover {university_domain} — "
                f"Tier 1 custom: {len(urls)} URLs"
            )
            return [{"url": u, "program_name": None, "degree_level": None} for u in urls]
    except Exception as exc:
        logger.warning(f"[intelligent_fetcher] Tier 1 custom discover failed: {exc}")

    # Crawl4AI deep crawl as Tier 3 fallback
    if settings.crawl4ai_enabled:
        try:
            from pipeline.tier3_crawl4ai import discover_university_programs
            urls = await discover_university_programs(university_domain, max_urls=50)
            if urls:
                logger.info(
                    f"[intelligent_fetcher] discover {university_domain} — "
                    f"Tier 3 Crawl4AI: {len(urls)} URLs"
                )
                return [{"url": u, "program_name": None, "degree_level": None} for u in urls]
        except Exception as exc:
            logger.warning(f"[intelligent_fetcher] Tier 3 Crawl4AI discover failed: {exc}")

    logger.error(f"[intelligent_fetcher] all discovery tiers failed for {university_domain}")
    return []
