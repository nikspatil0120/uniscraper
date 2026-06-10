# pipeline/intelligent_fetcher.py
#
# Master fetch orchestrator — three-tier waterfall.
#
# TIER 1 (Primary):    Crawl4AI  — stealth Playwright, fit_markdown
# TIER 2 (Fallback 1): Firecrawl — hosted API, handles Cloudflare
# TIER 3 (Fallback 2): Custom    — httpx → Playwright + clean_html (always works)
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
        "method":     str,        # "crawl4ai" | "firecrawl" | "httpx" | "playwright"
        "tier":       int,        # 1, 2, or 3
        "url":        str,
        "error":      str | None,
    }
    """

    # ── TIER 1: Crawl4AI ─────────────────────────────────────────────────────
    if settings.crawl4ai_enabled:
        logger.info(f"[intelligent_fetcher] {url} — trying Tier 1 (Crawl4AI)")
        try:
            from pipeline.tier1_crawl4ai import fetch_single_page
            r = await fetch_single_page(url)
            if r["markdown"] and r["word_count"] >= _MIN_WORDS:
                logger.info(
                    f"[intelligent_fetcher] {url} — Tier 1 SUCCESS ({r['word_count']} words)"
                )
                return {
                    "content": r["markdown"], "html": r["html"],
                    "links": r["links"], "word_count": r["word_count"],
                    "method": "crawl4ai", "tier": 1, "url": url, "error": None,
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

    # ── TIER 3: Custom pipeline (guaranteed fallback) ─────────────────────────
    logger.info(f"[intelligent_fetcher] {url} — trying Tier 3 (custom pipeline)")
    try:
        from pipeline.fetcher import fetch_page
        from utils.text_cleaner import clean_html
        from pipeline.link_extractor import extract_relevant_links

        fetch_result = await fetch_page(url)
        html = fetch_result.get("html") or ""
        cleaned = clean_html(html) if html else ""
        links = extract_relevant_links(html, url) if html else []
        word_count = len(cleaned.split())
        method = fetch_result.get("method_used", "httpx")

        logger.info(
            f"[intelligent_fetcher] {url} — Tier 3 result: {word_count} words, "
            f"method={method}"
        )
        return {
            "content": cleaned, "html": html, "links": links,
            "word_count": word_count, "method": method, "tier": 3,
            "url": fetch_result.get("final_url", url),
            "error": fetch_result.get("error"),
        }
    except Exception as exc:
        logger.error(f"[intelligent_fetcher] {url} — Tier 3 also failed: {exc}")
        return {
            "content": "", "html": "", "links": [], "word_count": 0,
            "method": "all_failed", "tier": 0, "url": url, "error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Multi-page fetch (main + sub-pages)
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_subpages_intelligent(url: str, max_pages: int = 15) -> list[dict]:
    """
    Fetch main page + admission-relevant sub-pages using the best available tier.

    Returns list of dicts, each with keys:
        url, content, html, word_count, method, tier, page_type
    First item is the main page.
    """

    # ── TIER 1: Crawl4AI deep crawl ──────────────────────────────────────────
    if settings.crawl4ai_enabled:
        try:
            from pipeline.tier1_crawl4ai import deep_crawl_program_page, fetch_single_page
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
                            "method": "crawl4ai",
                            "tier": 1,
                            "page_type": classify_page(url, single.get("markdown", "")),
                        }]
                        logger.info(
                            f"[intelligent_fetcher] Single fetch fallback succeeded "
                            f"({pages[0]['word_count']} words)"
                        )
                except Exception as e:
                    logger.warning(f"[intelligent_fetcher] Single fetch also failed: {e}")

            # ── Tier 1 success check — changed from >= 2 to >= 1 ───────────────────
            if len(pages) >= 1 and pages[0]["word_count"] >= _MIN_WORDS:
                logger.info(
                    f"[intelligent_fetcher] Tier 1 sufficient — "
                    f"{len(pages)} pages, passing to extractor"
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

    # ── TIER 2: Firecrawl crawl ───────────────────────────────────────────────
    if settings.firecrawl_enabled and settings.firecrawl_api_key:
        try:
            from pipeline.tier2_firecrawl import crawl_program_subpages
            from utils.page_classifier import classify_page
            pages = await crawl_program_subpages(url, max_pages)
            if len(pages) >= 1 and pages[0].get("word_count", 0) >= _MIN_WORDS:
                logger.info(
                    f"[intelligent_fetcher] subpages {url} — "
                    f"Tier 2 crawl: {len(pages)} pages"
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

    # ── TIER 3: Manual sub-page fetching ─────────────────────────────────────
    logger.info(f"[intelligent_fetcher] subpages {url} — Tier 3 manual fetch")
    try:
        from pipeline.fetcher import fetch_page
        from utils.text_cleaner import clean_html
        from pipeline.link_extractor import extract_relevant_links
        from utils.page_classifier import classify_page

        main_result = await fetch_page(url)
        main_html = main_result.get("html") or ""
        if not main_html:
            return []

        main_clean = clean_html(main_html)
        sub_urls = extract_relevant_links(main_html, url)
        method = main_result.get("method_used", "httpx")

        pages = [{
            "url": main_result.get("final_url", url),
            "content": main_clean,
            "html": main_html,
            "markdown": main_clean,
            "word_count": len(main_clean.split()),
            "method": method,
            "tier": 3,
            "page_type": classify_page(url, main_clean),
        }]

        sub_results = await asyncio.gather(
            *[fetch_page(u) for u in sub_urls[:max_pages - 1]],
            return_exceptions=True,
        )
        for sub_url, res in zip(sub_urls, sub_results):
            if isinstance(res, Exception) or not res.get("html"):
                continue
            sub_clean = clean_html(res["html"])
            if len(sub_clean.split()) < 50:
                continue
            pages.append({
                "url": sub_url,
                "content": sub_clean,
                "html": res["html"],
                "markdown": sub_clean,
                "word_count": len(sub_clean.split()),
                "method": res.get("method_used", "httpx"),
                "tier": 3,
                "page_type": classify_page(sub_url, sub_clean),
            })

        logger.info(
            f"[intelligent_fetcher] subpages {url} — Tier 3 manual: {len(pages)} pages"
        )
        return pages

    except Exception as exc:
        logger.error(f"[intelligent_fetcher] all subpage tiers failed for {url}: {exc}")
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
    Tries Firecrawl /map first (fastest), then Crawl4AI deep crawl.
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

    # Crawl4AI deep crawl as fallback
    if settings.crawl4ai_enabled:
        try:
            from pipeline.tier1_crawl4ai import discover_university_programs
            urls = await discover_university_programs(university_domain, max_urls=50)
            if urls:
                logger.info(
                    f"[intelligent_fetcher] discover {university_domain} — "
                    f"Crawl4AI: {len(urls)} URLs"
                )
                return [{"url": u, "program_name": None, "degree_level": None} for u in urls]
        except Exception as exc:
            logger.warning(f"[intelligent_fetcher] Crawl4AI discover failed: {exc}")

    logger.error(f"[intelligent_fetcher] all discovery tiers failed for {university_domain}")
    return []
