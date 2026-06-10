# pipeline/tier2_firecrawl.py
#
# Tier 2 — First fallback using Firecrawl API.
# Handles Cloudflare protection, bot-detection, and sites that block Crawl4AI.
# Requires FIRECRAWL_API_KEY in .env.
#
# Public functions:
#   fetch_single_page(url)             — single page scrape
#   crawl_program_subpages(url, n)     — crawl main + sub-pages
#   map_university_programs(url)       — Phase 2: discover all program URLs

import logging

from config import settings

logger = logging.getLogger(__name__)

_ADMISSION_INCLUDE = [
    "*admission*", "*admissions*",
    "*fees*", "*fee*", "*tuition*", "*cost*", "*costs*", "*funding*", "*finance*",
    "*requirement*", "*requirements*", "*eligibility*",
    "*english*", "*language*", "*ielts*", "*apply*", "*application*", "*entry*",
    "*scholarships*", "*scholarship*",
]
_ADMISSION_EXCLUDE = [
    "*login*", "*staff*", "*news*", "*events*",
    "*alumni*", "*research*", "*donate*",
]


def _get_client():
    """Return a V1FirecrawlApp client if key is configured, else None."""
    if not settings.firecrawl_api_key:
        logger.warning("[tier2_firecrawl] No FIRECRAWL_API_KEY configured")
        return None
    from firecrawl import V1FirecrawlApp
    return V1FirecrawlApp(api_key=settings.firecrawl_api_key)


# ─────────────────────────────────────────────────────────────────────────────
# Single-page fetch
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_single_page(url: str) -> dict:
    """
    Scrape one page via Firecrawl API.
    Handles Cloudflare, JS rendering, anti-bot automatically.

    Returns standardised dict:
    {
        "markdown":   str | None,
        "html":       str | None,
        "links":      list[str],
        "word_count": int,
        "method":     "firecrawl",
        "tier":       2,
        "error":      str | None,
    }
    Never raises.
    """
    client = _get_client()
    if not client:
        return {
            "markdown": None, "html": None, "links": [],
            "word_count": 0, "method": "firecrawl", "tier": 2,
            "error": "No FIRECRAWL_API_KEY configured",
        }

    try:
        # V1FirecrawlApp uses synchronous calls — wrap in executor for async compat
        import asyncio
        loop = asyncio.get_event_loop()

        def _scrape():
            return client.scrape_url(
                url,
                formats=["markdown", "html", "links"],
                only_main_content=True,
                wait_for=2000,
            )

        result = await loop.run_in_executor(None, _scrape)

        # V1 returns a V1ScrapeResponse object (Pydantic model)
        markdown = getattr(result, "markdown", None) or ""
        html = getattr(result, "html", None) or ""
        links_raw = getattr(result, "links", None) or []

        # Normalise links to plain strings
        links = []
        for lnk in links_raw:
            if isinstance(lnk, str):
                links.append(lnk)
            elif isinstance(lnk, dict):
                links.append(lnk.get("url", lnk.get("href", "")))
        links = [l for l in links if l]

        word_count = len(markdown.split()) if markdown else 0

        logger.info(f"[tier2_firecrawl] {url} — success, {word_count} words")
        return {
            "markdown":   markdown,
            "html":       html,
            "links":      links,
            "word_count": word_count,
            "method":     "firecrawl",
            "tier":       2,
            "error":      None,
        }

    except Exception as exc:
        logger.error(f"[tier2_firecrawl] {url} — {type(exc).__name__}: {exc}")
        return {
            "markdown": None, "html": None, "links": [],
            "word_count": 0, "method": "firecrawl", "tier": 2,
            "error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Crawl main + sub-pages
# ─────────────────────────────────────────────────────────────────────────────

async def crawl_program_subpages(url: str, max_pages: int = 10) -> list[dict]:
    """
    Use Firecrawl scrape endpoint to fetch main page + admission-relevant sub-pages.
    Scrapes each sub-page individually using constructed URLs (avoids crawl_url
    which triggers Cloudflare with multiple requests).
    Returns list of {url, markdown, html, word_count, method, tier} dicts.
    """
    client = _get_client()
    if not client:
        return []

    import asyncio
    from urllib.parse import urlparse

    base_domain = urlparse(url).netloc
    base_path = urlparse(url).path.rstrip("/")

    # Always scrape the main page first
    main = await fetch_single_page(url)
    if main["word_count"] < 50:
        return []

    pages = [{
        "url": url,
        "markdown": main["markdown"],
        "html": main["html"],
        "word_count": main["word_count"],
        "method": "firecrawl",
        "tier": 2,
    }]

    # Construct known sub-page URLs — covers the most common university patterns
    KNOWN_SUBPAGE_SUFFIXES = [
        "/entry-requirements",
        "/fees",
        "/how-to-apply",
        "/application",
        "/english-requirements",
        "/english-language-requirements",
        "/scholarships",
        "/funding",
        "/overview",
        "/admissions",
    ]
    candidate_urls = [
        f"https://{base_domain}{base_path}{suffix}"
        for suffix in KNOWN_SUBPAGE_SUFFIXES
    ]

    # Also extract any links from main page markdown that look relevant
    import re
    HIGH_VALUE_KEYWORDS = [
        "entry-requirement", "fees", "tuition", "how-to-apply",
        "application", "english", "scholarship", "funding", "admission",
    ]
    for match in re.finditer(r'\[([^\]]*)\]\((https?://[^\)]+)\)', main["markdown"] or ""):
        link_url = match.group(2)
        if base_domain in link_url and any(kw in link_url.lower() for kw in HIGH_VALUE_KEYWORDS):
            clean = link_url.rstrip("/")
            if clean not in candidate_urls and clean != url.rstrip("/"):
                candidate_urls.append(clean)

    # Deduplicate, cap at max_pages-1 remaining slots
    seen = {url.rstrip("/")}
    unique_candidates = []
    for u in candidate_urls:
        clean = u.rstrip("/")
        if clean not in seen:
            seen.add(clean)
            unique_candidates.append(u)
    unique_candidates = unique_candidates[: max_pages - 1]

    logger.info(
        f"[tier2_firecrawl] scraping {len(unique_candidates)} candidate sub-pages for {url}"
    )

    # Scrape each sub-page individually with concurrency limit
    semaphore = asyncio.Semaphore(3)

    async def scrape_subpage(suburl: str) -> dict | None:
        async with semaphore:
            result = await fetch_single_page(suburl)
            if result["word_count"] >= 50:
                logger.info(f"[tier2_firecrawl] page OK: {suburl} ({result['word_count']} words)")
                return {
                    "url": suburl,
                    "markdown": result["markdown"],
                    "html": result["html"],
                    "word_count": result["word_count"],
                    "method": "firecrawl",
                    "tier": 2,
                }
            return None

    sub_results = await asyncio.gather(
        *[scrape_subpage(u) for u in unique_candidates],
        return_exceptions=True,
    )
    for r in sub_results:
        if isinstance(r, dict):
            pages.append(r)

    # ── Second pass: add university-wide English requirements if not found ────
    english_found = any(
        "english" in p["url"].lower() or "language" in p["url"].lower()
        for p in pages
    )
    if not english_found:
        from urllib.parse import urlparse as _urlparse
        base = f"https://{_urlparse(url).netloc}"
        candidate_english_urls = [
            f"{base}/english-language-requirements",
            f"{base}/study/english-language-requirements",
            f"{base}/admissions/english-language",
            f"{base}/find/english-language-requirements",
            f"{base}/information-for/international-students/english-language-requirements",
        ]
        for eng_url in candidate_english_urls:
            r = await fetch_single_page(eng_url)
            if r["word_count"] >= 100:
                pages.append({
                    "url": eng_url, "markdown": r["markdown"],
                    "html": r["html"], "word_count": r["word_count"],
                    "method": "firecrawl", "tier": 2,
                })
                logger.info(
                    f"[tier2_firecrawl] Added English req page: {eng_url} "
                    f"({r['word_count']} words)"
                )
                break  # found one, stop

    logger.info(f"[tier2_firecrawl] crawl {url} — {len(pages)} usable pages total")
    return pages


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Discover program URLs via Firecrawl /map
# ─────────────────────────────────────────────────────────────────────────────

async def map_university_programs(university_url: str) -> list[str]:
    """
    Phase 2: Use Firecrawl /map to get all URLs on a university site,
    then filter to program/course pages.
    Returns list of URL strings.
    """
    client = _get_client()
    if not client:
        return []

    try:
        import asyncio
        loop = asyncio.get_event_loop()

        def _map():
            return client.map_url(
                university_url,
                search="postgraduate programme masters phd",
                limit=100,
            )

        result = await loop.run_in_executor(None, _map)

        # v4: result is MapResponse with .links
        urls = getattr(result, "links", None) or []
        if not urls and isinstance(result, dict):
            urls = result.get("links", [])

        # Filter to likely program pages
        _PROGRAM_KW = [
            "programme", "program", "course", "masters",
            "msc", "mba", "phd", "postgraduate", "graduate", "taught", "study",
        ]
        filtered = [u for u in urls if any(kw in u.lower() for kw in _PROGRAM_KW)]

        logger.info(
            f"[tier2_firecrawl] map {university_url} — "
            f"{len(filtered)} program URLs from {len(urls)} total"
        )
        return filtered

    except Exception as exc:
        logger.error(
            f"[tier2_firecrawl] map {university_url} — {type(exc).__name__}: {exc}"
        )
        return []
