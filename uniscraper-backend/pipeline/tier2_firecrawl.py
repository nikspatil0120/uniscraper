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
                only_main_content=False,  # Changed to False to get full content, not just fragments
                wait_for=2000,
                timeout=60000,  # 60s — default 35s is too short for heavy JS sites like Imperial
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

async def crawl_program_subpages(url: str, max_pages: int = 50) -> list[dict]:
    """
    Exhaustive multi-level crawl using Firecrawl scrape endpoint.
    
    Strategy:
    1. Scrape main page
    2. Extract and score all relevant links from main page
    3. Scrape all high-value sub-pages in parallel (depth 1)
    4. Extract links from depth-1 pages and score them
    5. Scrape depth-2 pages if budget allows
    6. Continue until max_pages reached or no more relevant links
    
    This handles cases where critical info (international fees, IELTS) is
    buried 2-3 levels deep in the site structure.
    
    Includes content deduplication to handle sites that return identical
    content for different URLs.
    """
    from config import settings
    
    client = _get_client()
    if not client:
        return []

    import asyncio
    import hashlib
    from urllib.parse import urlparse

    base_domain = urlparse(url).netloc
    base_path = urlparse(url).path.rstrip("/")

    logger.info(f"[tier2_firecrawl] Exhaustive crawl starting: {url} (max={max_pages}, depth={settings.max_depth})")

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
        "depth": 0,
    }]
    
    visited = {url.rstrip("/")}
    content_hashes = set()  # Track content hashes for deduplication
    
    # Add main page hash
    if main["markdown"]:
        main_hash = hashlib.md5(main["markdown"].encode('utf-8')).hexdigest()
        content_hashes.add(main_hash)
    
    current_depth_pages = [main]
    
    # ── Multi-level crawling with depth tracking ──────────────────────────────
    for depth in range(1, settings.max_depth + 1):
        if len(pages) >= max_pages:
            break
        
        # Extract candidates from current depth pages
        all_candidates = set()
        
        for page in current_depth_pages:
            # Source A: Construct known sub-page patterns
            if depth == 1:  # Only from main page
                KNOWN_SUFFIXES = [
                    "/entry-requirements", "/fees", "/how-to-apply",
                    "/application", "/english-requirements", "/english-language-requirements",
                    "/scholarships", "/funding", "/overview", "/admissions",
                    "/structure", "/modules", "/curriculum",
                    "/international-students", "/international",
                ]
                for suffix in KNOWN_SUFFIXES:
                    all_candidates.add(f"https://{base_domain}{base_path}{suffix}")
            
            # Source B: Extract from markdown links
            import re
            page_md = page.get("markdown", "")
            if isinstance(page_md, str):
                HIGH_VALUE_KEYWORDS = [
                    "entry-requirement", "fees", "tuition", "how-to-apply",
                    "application", "english", "scholarship", "funding", "admission",
                    "structure", "module", "curriculum", "international",
                ]
                for match in re.finditer(r'\[([^\]]*)\]\((https?://[^\)]+)\)', page_md):
                    link_url = match.group(2).split("#")[0]  # strip fragments
                    if base_domain in link_url and any(kw in link_url.lower() for kw in HIGH_VALUE_KEYWORDS):
                        all_candidates.add(link_url)
        
        # Score and filter candidates
        scored = {}
        for candidate in all_candidates:
            clean = candidate.rstrip("/")
            # Strip fragment identifiers — /fees/#nav is the same page as /fees
            if "#" in clean:
                clean = clean.split("#")[0].rstrip("/")
            if clean in visited:
                continue
            
            parsed = urlparse(candidate)
            if parsed.netloc != base_domain:
                continue
            if not parsed.path.startswith(base_path):
                continue
            
            # Skip noise
            SKIP_PATTERNS = [
                "login", "staff", "news", "event", "alumni", "donate",
                "privacy", "cookie", "visa", "undergraduate",
            ]
            if any(skip in candidate.lower() for skip in SKIP_PATTERNS):
                continue
            
            # Score by URL keywords
            HIGH_VALUE_KEYWORDS = [
                "entry-requirement", "fees", "tuition", "english", "ielts",
                "how-to-apply", "admission", "scholarship", "funding",
                "international", "structure", "curriculum",
            ]
            score = sum(3 for kw in HIGH_VALUE_KEYWORDS if kw in candidate.lower())
            
            if score > 0:
                scored[clean] = score
        
        if not scored:
            logger.info(f"[tier2_firecrawl] No more candidates at depth {depth}, stopping")
            break
        
        # Select top candidates for this depth
        remaining_slots = max_pages - len(pages)
        top_candidates = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:remaining_slots]
        
        logger.info(f"[tier2_firecrawl] Depth {depth} — scraping {len(top_candidates)} candidates")
        
        # Scrape in parallel
        semaphore = asyncio.Semaphore(settings.max_concurrent_fetches)
        
        async def scrape_candidate(candidate_url: str, score: int) -> dict | None:
            async with semaphore:
                result = await fetch_single_page(candidate_url)
                if result["word_count"] >= 50:
                    md = result["markdown"] or ""
                    # Drop soft-404 pages — Firecrawl returns HTTP 200 for these
                    md_lower = md.lower()
                    if any(sig in md_lower[:500] for sig in [
                        "page not found", "we can't find", "doesn't exist",
                        "no longer available", "404",
                    ]):
                        logger.debug(f"[tier2_firecrawl] {candidate_url} — soft-404, skipping")
                        return None
                    # Check for duplicate content
                    if md:
                        content_hash = hashlib.md5(md.encode('utf-8')).hexdigest()
                        if content_hash in content_hashes:
                            logger.debug(f"[tier2_firecrawl] Depth {depth} — {candidate_url} duplicate content (hash: {content_hash[:8]}), skipping")
                            return None
                        content_hashes.add(content_hash)
                    visited.add(candidate_url.rstrip("/"))
                    logger.info(f"[tier2_firecrawl] Depth {depth} — {candidate_url} OK ({result['word_count']} words, score={score})")
                    return {
                        "url": candidate_url,
                        "markdown": result["markdown"],
                        "html": result["html"],
                        "word_count": result["word_count"],
                        "method": "firecrawl",
                        "tier": 2,
                        "depth": depth,
                    }
                return None
        
        depth_results = await asyncio.gather(
            *[scrape_candidate(u, s) for u, s in top_candidates],
            return_exceptions=True,
        )
        
        current_depth_pages = []
        for r in depth_results:
            if isinstance(r, dict):
                pages.append(r)
                current_depth_pages.append(r)
        
        if not current_depth_pages:
            logger.info(f"[tier2_firecrawl] No valid pages at depth {depth}, stopping")
            break

    # ── Second pass: Add university-wide English requirements if missing ──────
    english_found = any(
        "english" in p["url"].lower() or "language" in p["url"].lower()
        for p in pages
    )
    if not english_found and len(pages) < max_pages:
        base = f"https://{urlparse(url).netloc}"
        candidate_english_urls = [
            f"{base}/english-language-requirements",
            f"{base}/study/english-language-requirements",
            f"{base}/admissions/english-language",
            f"{base}/find/english-language-requirements",
            f"{base}/information-for/international-students/english-language-requirements",
            f"{base}/info/english-language-requirements",
            f"{base}/information-for/international-students/english",
            f"{base}/study-with-us/english-language-requirements",
        ]
        for eng_url in candidate_english_urls:
            if eng_url.rstrip("/") in visited:
                continue
            r = await fetch_single_page(eng_url)
            # Check it's not a soft-404
            md_lower = (r.get("markdown") or "").lower()
            is_404 = any(sig in md_lower[:500] for sig in [
                "page not found", "we can't find", "doesn't exist", "no longer available"
            ])
            if r["word_count"] >= 100 and not is_404:
                pages.append({
                    "url": eng_url, "markdown": r["markdown"],
                    "html": r["html"], "word_count": r["word_count"],
                    "method": "firecrawl", "tier": 2, "depth": 99,
                })
                logger.info(
                    f"[tier2_firecrawl] Added university-wide English page: {eng_url} "
                    f"({r['word_count']} words)"
                )
                break

    # ── Third pass: Try to get international fees via Firecrawl actions ───────
    # Some sites (e.g. Melbourne) show domestic/international fees behind a JS tab.
    # Re-fetch the fees page with a click action to switch to "International students".
    int_fees_found = any(
        "international" in (p.get("markdown") or "").lower()[:2000]
        and any(kw in (p.get("markdown") or "").lower() for kw in ["aud", "$", "fee"])
        for p in pages
        if "fee" in p.get("url", "").lower()
    )
    fees_page = next(
        (p for p in pages if p.get("url", "").rstrip("/").endswith("/fees")), None
    )
    if not int_fees_found and fees_page and len(pages) < max_pages:
        try:
            loop = asyncio.get_event_loop()

            def _scrape_intl():
                return client.scrape_url(
                    fees_page["url"],
                    formats=["markdown"],
                    only_main_content=False,
                    wait_for=3000,
                    timeout=60000,
                    actions=[
                        {"type": "click", "selector": "[data-tab='international'], button[aria-label*='International'], label[for*='international'], [data-audience='international']"},
                        {"type": "wait", "milliseconds": 2000},
                    ],
                )

            intl_result = await loop.run_in_executor(None, _scrape_intl)
            intl_md = getattr(intl_result, "markdown", None) or ""
            intl_wc = len(intl_md.split())
            # Only add if it actually has different content
            if intl_wc >= 100:
                intl_hash = hashlib.md5(intl_md.encode("utf-8")).hexdigest()
                if intl_hash not in content_hashes:
                    content_hashes.add(intl_hash)
                    pages.append({
                        "url": fees_page["url"] + "?view=international",
                        "markdown": intl_md,
                        "html": "",
                        "word_count": intl_wc,
                        "method": "firecrawl",
                        "tier": 2,
                        "depth": 99,
                    })
                    logger.info(
                        f"[tier2_firecrawl] Added international fees view: "
                        f"{intl_wc} words"
                    )
        except Exception as exc:
            logger.debug(f"[tier2_firecrawl] International fees action failed: {exc}")

    max_depth_reached = max(p.get("depth", 0) for p in pages) if pages else 0
    logger.info(
        f"[tier2_firecrawl] Exhaustive crawl complete — "
        f"{len(pages)} pages (max depth: {max_depth_reached})"
    )
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
