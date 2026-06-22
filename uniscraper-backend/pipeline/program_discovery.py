# pipeline/program_discovery.py
# Discovers program pages on a university website.
#
# ARCHITECTURE — 5 stages:
#   Stage 1: Candidate Collection  (sitemap + SerpAPI + legacy BFS)
#   Stage 2: Cheap Pre-Filter      (string checks, no API calls)
#   Stage 3: Gemini Batch Classification  (title + ~200 words, 12-15 per call)
#   Stage 4: Sibling Expansion     (sitemap around confirmed pages, one pass)
#   Stage 5: Full extraction       (handled by orchestrator, not this file)
#
# Stage 3 output is for the DISCOVERY LIST UI ONLY (clickable cards).
# Stage 3 never substitutes for full Phase 1 extraction — that runs independently.

import asyncio
import json
import logging
import re
import time
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """Strip www., trailing slash, query params, and .html/.xml extensions for deduplication."""
    try:
        p = urlparse(url)
        netloc = p.netloc.lower().replace("www.", "")
        path = p.path.rstrip("/") or "/"
        # Strip common page extensions so .html and .xml versions of the same page dedup correctly
        for ext in (".html", ".htm", ".xml", ".aspx", ".php"):
            if path.endswith(ext):
                path = path[: -len(ext)]
                break
        return urlunparse((p.scheme.lower(), netloc, path, "", "", ""))
    except Exception:
        return url


async def _fetch_html(url: str, timeout: float = 5.0) -> tuple[str, int]:
    """
    Fetch HTML content from URL with aggressive timeout for discovery.
    
    For discovery, we want fast responses. Pages that don't load quickly
    are unlikely to be useful program pages.
    
    Returns: (html_content, status_code)
    - On success: (html, 200)
    - On timeout/error: ("", 0)
    """
    try:
        # Use granular timeouts: connect=3s, read=5s
        timeout_config = httpx.Timeout(
            connect=3.0,
            read=timeout,
            write=5.0,
            pool=5.0
        )
        
        async with httpx.AsyncClient(
            timeout=timeout_config, follow_redirects=True, headers=_HEADERS
        ) as client:
            r = await client.get(url)
            html = r.text
            
            # Log extraction details for debugging "no_content" failures
            text_length = len(html)
            word_count = len(html.split())
            
            if text_length == 0:
                logger.debug(f"[program_discovery] fetch returned empty HTML: {url}")
            
            return html, r.status_code
            
    except httpx.TimeoutException as e:
        logger.debug(f"[program_discovery] fetch timeout ({timeout}s): {url} - {type(e).__name__}")
        return "", 0
    except httpx.ConnectError as e:
        logger.debug(f"[program_discovery] fetch connection error: {url} - {e}")
        return "", 0
    except Exception as e:
        logger.debug(f"[program_discovery] fetch error {url}: {type(e).__name__}: {e}")
        return "", 0


def _get_title(html: str) -> str:
    try:
        tag = BeautifulSoup(html, "lxml").find("title")
        return tag.get_text(strip=True) if tag else ""
    except Exception:
        return ""


def _get_snippet(html: str, max_words: int = 200) -> str:
    """Extract first ~200 words of visible body text for classification."""
    try:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        body = soup.find("body")
        text = (body or soup).get_text(" ", strip=True)
        words = text.split()
        return " ".join(words[:max_words])
    except Exception:
        return ""


def _word_count(html: str) -> int:
    try:
        return len(BeautifulSoup(html, "lxml").get_text().split())
    except Exception:
        return 0


def _clean_program_name(title: str, university_name: str = "") -> str:
    name = title
    for sep in [" | ", " - ", " — ", " :: ", " · "]:
        if sep in name:
            parts = name.split(sep)
            if university_name:
                uni_lower = university_name.lower()
                parts = [p for p in parts if uni_lower not in p.lower()]
            if parts:
                name = parts[0].strip()
                break
    return name.strip() or title


def _is_soft_404(title: str) -> bool:
    return bool(re.search(
        r"(error 404|page not found|404 not found|403 forbidden|access denied|not available)",
        title, re.IGNORECASE,
    ))


# ── Degree level fallback (display-only, Gemini is the authority) ─────────────

_DEGREE_KEYWORDS = [
    # PhD / Research doctorates
    ("phd", "PhD"), ("ph.d", "PhD"), ("doctorate", "PhD"), ("doctoral", "PhD"),
    ("dphil", "PhD"), ("d.phil", "PhD"),
    # Professional doctorates → Doctoral tier
    ("doctor of", "Doctoral"), ("d.n.p", "Doctoral"), ("dnp", "Doctoral"),
    ("dpt", "Doctoral"), ("doctor of physical therapy", "Doctoral"),
    ("doctor of nursing", "Doctoral"), ("doctor of occupational", "Doctoral"),
    ("otd", "Doctoral"), ("edd", "Doctoral"), ("ed.d", "Doctoral"),
    ("dba", "Doctoral"), ("jd", "Doctoral"), ("pharmd", "Doctoral"),
    # Education Specialist — between Master's and Doctoral
    ("ed.s", "Doctoral"), ("eds in", "Doctoral"), ("education specialist", "Doctoral"),
    # MBA explicitly first so it matches before generic "master"
    ("mba", "MBA"), ("m.b.a", "MBA"),
    # Master's
    ("master of", "Master's"), ("master's", "Master's"), ("masters", "Master's"),
    ("msc", "Master's"), ("m.sc", "Master's"), ("meng", "Master's"), ("m.eng", "Master's"),
    ("mres", "Master's"), ("mphil", "Master's"), ("llm", "Master's"),
    ("mfa", "Master's"), ("mpa", "Master's"), ("mph", "Master's"),
    ("msw", "Master's"), ("msn", "Master's"), ("mse in", "Master's"),
    ("ms in", "Master's"), ("msa in", "Master's"),
    # Bare "ms " / "mse " / "msa " with trailing space — catches "MS Engineering"
    (" ms ", "Master's"), ("^ms ", "Master's"),
    ("mse ", "Master's"), ("msa ", "Master's"),
    # Short degree codes as standalone words (with boundary context)
    ("ma in", "Master's"), ("ma of", "Master's"),     # MA in Sociology
    ("mfa in", "Master's"), ("mpa in", "Master's"),   # MFA / MPA
    ("mph in", "Master's"), ("mm in", "Master's"),    # MPH / MM (Music)
    ("mfa", "Master's"), ("mpa", "Master's"),
    ("mm ", "Master's"),                               # Master of Music
    ("postgraduate", "Master's"), ("pgdip", "Master's"), ("pgcert", "Certificate"),
    ("pgce", "Certificate"),
    # Bachelor's
    ("bachelor of", "Bachelor's"), ("bachelor's", "Bachelor's"),
    ("undergraduate", "Bachelor's"), ("bsc", "Bachelor's"), ("beng", "Bachelor's"),
    # Other
    ("associate", "Associate's"), ("certificate", "Certificate"), ("diploma", "Diploma"),
]


def _fallback_degree_level(url: str, title: str) -> str:
    combined = (url + " " + title).lower()
    for kw, level in _DEGREE_KEYWORDS:
        if kw.startswith("^"):
            # Anchored check — match start of title only
            if title.lower().startswith(kw[1:]):
                return level
        elif kw in combined:
            return level
    return "Unspecified"


# ── Sitemap cache (per-process) ───────────────────────────────────────────────

_sitemap_cache: dict[str, list[str]] = {}


async def _load_all_sitemap_locs(domain: str) -> list[str]:
    """Load and cache all <loc> entries from domain's sitemap. Fetches all sub-sitemaps."""
    if domain in _sitemap_cache:
        return _sitemap_cache[domain]

    bases = [f"https://{domain}"]
    if not domain.startswith("www."):
        bases.append(f"https://www.{domain}")

    sitemap_paths = [
        "/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
        "/programs-sitemap.xml", "/page-sitemap.xml",
    ]

    all_locs: list[str] = []
    for b in bases:
        for path in sitemap_paths:
            try:
                html, status = await _fetch_html(f"{b}{path}", timeout=8.0)
                if status != 200 or not html:
                    continue
                locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", html)
                sub_maps = re.findall(
                    r"<sitemap>.*?<loc>\s*(.*?)\s*</loc>", html, re.DOTALL
                )

                async def fetch_sub(u: str) -> list[str]:
                    try:
                        sh, ss = await _fetch_html(u, timeout=8.0)
                        if ss == 200 and sh:
                            return re.findall(r"<loc>\s*(.*?)\s*</loc>", sh)
                    except Exception:
                        pass
                    return []

                if sub_maps:
                    sub_results = await asyncio.gather(*[fetch_sub(u) for u in sub_maps])
                    for sl in sub_results:
                        locs.extend(sl)

                if locs:
                    all_locs = locs
                    logger.info(
                        f"[program_discovery] Sitemap {b}{path}: "
                        f"{len(locs)} locs ({len(sub_maps)} sub-sitemaps)"
                    )
                    break
            except Exception:
                continue
        if all_locs:
            break

    _sitemap_cache[domain] = all_locs
    return all_locs


# ── Stage 1: Candidate Collection ────────────────────────────────────────────

# Index paths for legacy BFS fallback
_INDEX_PATHS = [
    "/programs", "/programs/index.html", "/programmes", "/study",
    "/courses", "/graduate-programs", "/postgraduate", "/degrees",
    "/academics", "/academics/programs", "/academics/graduate-school",
    "/study/programs", "/study/courses", "/study/masters/courses",
    "/find/postgraduate", "/graduate/programs",
    "/admissions-and-aid/graduate-admissions",
    "/future-students/programs", "/grad/programs",
    "/graduate-studies/programs",
]

# Sitemap path patterns that indicate program catalogue pages
_PROGRAM_SITEMAP_HINTS = [
    "/programs/", "/programme", "/courses/list/",
    "/study/masters/courses/", "/study/postgraduate/courses/",
    "/study/undergraduate/courses/", "/study/phd/",
    "/degrees/", "/graduate/courses/",
]

_EXCLUDE_SITEMAP_HINTS = [
    "funding", "news", "events", "scholarships", "fees",
    "student-funding", "opportunities",
]

# Non-program subdomains to skip when confirming pages
_NON_PROGRAM_SUBDOMAINS = [
    "studentnews.", "news.", "blog.", "blogs.", "events.",
    "alumni.", "giving.", "library.", "portal.", "login.",
    "careers.", "jobs.", "research.", "staff.", "intranet.",
    "sites.", "figshare.", "personalpages.",
]


def _calculate_simple_confidence(url: str) -> tuple[float, float]:
    """
    Simple heuristic scoring for URL prioritization.
    Returns (positive_score, negative_score) separately for better debugging.
    
    Final score = positive - negative
    Keeping them separate helps identify:
    - High positive, low negative = strong program candidate
    - High positive, high negative = ambiguous (e.g., /masters/funding/)
    - Low positive, high negative = likely not a program
    """
    positive = 0.0
    negative = 0.0
    url_lower = url.lower()
    
    # Positive signals - postgraduate paths
    if "/masters/" in url_lower or "/master/" in url_lower:
        positive += 10
    if "/postgraduate-research/" in url_lower or "/postgraduate/" in url_lower:
        positive += 10
    if "/graduate/" in url_lower:
        positive += 8
    if "/phd/" in url_lower or "/doctorate/" in url_lower:
        positive += 10
    
    # Positive signals - degree slugs
    postgrad_slugs = [
        "msc-", "ma-", "mba-", "llm-", "mphil-", "phd-",
        "pgce-", "pgdip-", "mres-", "med-", "meng-", "mfin-",
        # Additional MS variants common in US universities
        "ms-in-", "ms-by-", "msa-", "mse-", "msw-", "msn-", "mpa-",
        "/ms-", "-ms-",  # path segment matching
    ]
    for slug in postgrad_slugs:
        if slug in url_lower:
            positive += 5
            break

    # Mild positive for certificate pages — valid graduate programs, but
    # lower priority than degrees. Tier sort handles final ranking.
    # Using +1 (not -3) keeps certs discoverable for cert-only universities.
    if "certificate-in-" in url_lower or "cert-in-" in url_lower:
        positive += 1
    
    # Negative signals - undergraduate (check path segment, not raw substring)
    # Use path segment check to avoid false positives like "mba-" matching "ba-"
    if "/undergraduate/" in url_lower:
        negative += 10
    else:
        # Check the slug directly (strip extension, strip online- prefix)
        import re as _re2
        _path = url_lower.split("?")[0]
        _slug = _path.rstrip("/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
        for _pfx in ("online-", "on-campus-", "campus-"):
            if _slug.startswith(_pfx):
                _slug = _slug[len(_pfx):]
                break
        _UNDERGRAD_SCORE_RE = _re2.compile(
            r"^(bsc|ba|bfa|bme|bse|bsn|bba|bsba|bsrs|bsw|bsed|bas|"
            r"bsa|bgs|bsce|bsee|bsme|beng|barch|bbe|bmus|bm|bcom|"
            r"aas|aasn|ags|as[_-]|aa[_-])"
            r"([-_]|in-|$)",
            _re2.IGNORECASE,
        )
        if _UNDERGRAD_SCORE_RE.match(_slug):
            negative += 10
    
    # Negative signals - non-program pages
    non_program_hints = [
        "/research-areas/", "/funding/", "/scholarships/",
        "/admissions/", "/staff/", "/faculty/", "/news/",
        "/events/", "/blog/", "/about/"
    ]
    for hint in non_program_hints:
        if hint in url_lower:
            negative += 5
            break
    
    return (positive, negative)


async def collect_candidates(
    domain: str,
    university_name: str = "",
) -> list[str]:
    """
    Stage 1: Collect candidate URLs from sitemap, SerpAPI, and path-guessing.
    Does NOT decide which are programs — that's Stage 3's job.
    Returns up to 150 candidate URLs.
    """
    all_candidates: set[str] = set()

    # ── 1a: Sitemap-based discovery ───────────────────────────────────────────
    all_locs = await _load_all_sitemap_locs(domain)
    if all_locs:
        # Find parent directories containing program pages from sitemap index
        parent_dirs = _infer_parents_from_sitemap_index(domain, all_locs)
        for pdir in parent_dirs:
            ppath = urlparse(pdir).path
            matching = [
                loc.strip() for loc in all_locs
                if ppath.rstrip("/") in urlparse(loc.strip()).path
            ]
            for url in matching:
                all_candidates.add(url)
            logger.info(
                f"[program_discovery] Sitemap: {len(matching)} URLs under {ppath}"
            )

    # ── 1b: SerpAPI ───────────────────────────────────────────────────────────
    if settings.serpapi_key and settings.serpapi_enabled:
        try:
            from pipeline.serpapi_client import search_program_pages
            serp_urls = await search_program_pages(domain, university_name)
            domain_bare = domain.replace("www.", "")
            for url in serp_urls:
                parsed = urlparse(url)
                link_domain = parsed.netloc.replace("www.", "")
                # Skip non-domain and known non-program subdomains
                if link_domain != domain_bare and not link_domain.endswith("." + domain_bare):
                    continue
                if any(link_domain.startswith(prefix) for prefix in _NON_PROGRAM_SUBDOMAINS):
                    continue
                all_candidates.add(url)
        except Exception as e:
            logger.debug(f"[program_discovery] SerpAPI failed: {e}")

    logger.info(
        f"[program_discovery] Stage 1 collected {len(all_candidates)} candidates"
    )
    
    # Return all candidates (will be scored and sorted in main flow)
    return list(all_candidates)


def _infer_parents_from_sitemap_index(domain: str, all_locs: list[str]) -> list[str]:
    """
    Look at sub-sitemap URLs in the locs to infer program parent directories.
    Fast: reads sub-sitemap URLs directly without fetching their content.
    """
    from collections import Counter
    parent_counts: Counter = Counter()
    seen: set[str] = set()
    result: list[str] = []

    for loc in all_locs:
        loc = loc.strip()
        path = urlparse(loc).path.lower()

        # Skip funding/news sitemaps
        if any(excl in path for excl in _EXCLUDE_SITEMAP_HINTS):
            continue

        # Check if path contains a program hint
        for hint in _PROGRAM_SITEMAP_HINTS:
            if hint in path:
                # If this is a sitemap.xml file, its directory IS the parent dir
                parsed = urlparse(loc)
                if loc.endswith("sitemap.xml") or "sitemap" in loc.split("/")[-1]:
                    sitemap_dir = parsed.path.rsplit("/", 1)[0] + "/"
                    parent_url = f"{parsed.scheme}://{parsed.netloc}{sitemap_dir}"
                else:
                    # Extract parent up to the hint segment
                    idx = path.find(hint.lower())
                    parent_path = parsed.path[:idx + len(hint)]
                    parent_url = f"{parsed.scheme}://{parsed.netloc}{parent_path}"
                norm = _normalize_url(parent_url.rstrip("/"))
                if norm not in seen:
                    seen.add(norm)
                    parent_counts[parent_url] += 1
                break

    # Return all parents with >= 1 URL (sorted by count)
    result = [p for p, _ in parent_counts.most_common()]
    if result:
        logger.info(f"[program_discovery] Inferred {len(result)} parent dirs from sitemap")
    return result


# ── Stage 2: Cheap Pre-Filter ─────────────────────────────────────────────────

_OBVIOUS_JUNK = [
    ".pdf", ".doc", ".docx", ".jpg", ".png", ".zip", ".xml",
    "/news/", "/events/", "/staff/", "/faculty-directory/",
    "/contact", "/login", "/search", "/sitemap",
    "/privacy", "/cookie", "/accessibility", "/jobs/",
    "/about/leadership", "/donate", "#",
    "mailto:", "javascript:", "/blog/", "/press/",
    "/giving/", "/alumni/", "/library/",
    "/financial-aid", "/tuition", "/fees",
    "/scholarships", "/housing", "/campus-map",
    "/registrar", "/graduation",
]

# Subdomains that are never program pages
_NON_PROGRAM_SUBDOMAINS_ALL = [
    "studentnews.", "news.", "blog.", "blogs.", "events.",
    "alumni.", "giving.", "library.", "portal.", "login.",
    "careers.", "jobs.", "research.", "staff.", "intranet.",
    "sites.", "figshare.", "personalpages.", "media.", "press.",
]


def cheap_prefilter(url: str) -> bool:
    """Return True to KEEP (send to Gemini), False to DROP obvious junk."""
    url_lower = url.lower()
    # Drop obvious junk paths
    if any(j in url_lower for j in _OBVIOUS_JUNK):
        return False
    # Drop known non-program subdomains
    try:
        netloc = urlparse(url).netloc.lower()
        if any(netloc.startswith(sub) for sub in _NON_PROGRAM_SUBDOMAINS_ALL):
            return False
    except Exception:
        pass
    return True


# ── Stage 3: Gemini Batch Classification ──────────────────────────────────────

# Known degree prefixes that indicate a program page without needing verification
_DEGREE_PREFIXES = [
    "msc-", "ma-", "mba-", "llm-", "mphil-", "phd-",
    "pgce-", "pgdip-", "mres-", "med-", "mph-", "meng-", 
    "mfin-", "mpharm-", "mphys-", "msci-", "mla-", "mpa-",
    "engd-", "edd-", "dba-", "md-", "jd-"
]

# Known high-confidence URL patterns (university-specific)
# These are self-identifying program pages that don't need Gemini verification
_HIGH_CONFIDENCE_PATTERNS = [
    # Manchester (very structured, highly reliable)
    r"/study/masters/courses/list/\d+/[a-z-]+",
    r"/study/postgraduate-research/programmes/list/\d+/[a-z-]+",
    r"/study/masters/courses/\d+/[a-z-]+",
    r"/study/postgraduate-research/programme",
    r"/study/online-blended-learning/courses/[a-z-]+",
    
    # Generic patterns (common across universities)
    r"/programs?/[a-z-]+-(master|msc|ma|mba|phd|doctorate|mphil)",
    r"/graduate/programs?/[a-z-]+-m[as]",
    r"/academics/programs?/graduate/[a-z-]+-(ms|ma|phd)",
    r"/(msc|ma|mba|phd|mphil|llm|mres|med|mph|meng|mla)-[a-z-]+",
    r"/postgraduate/[a-z-]+(msc|ma|phd|mba|mphil)",
    r"/(doctoral|doctorate|phd)-program",
]


def _has_obvious_degree_slug(url: str) -> tuple[bool, str | None]:
    """
    Check if URL contains an obvious degree slug like msc-, phd-, etc.
    Returns (is_obvious, degree_level).
    
    Examples:
        "/masters/msc-robotics/" -> (True, "Master's")
        "/phd-bioinformatics/" -> (True, "PhD")
        "/masters/funding/" -> (False, None)
    """
    url_lower = url.lower()
    path = urlparse(url_lower).path
    
    # Extract slug parts
    parts = [p for p in path.split("/") if p]
    if not parts:
        return (False, None)
    
    # Check last part (slug) for degree prefix — strip extension first
    last_part = parts[-1]
    last_part = last_part.rsplit(".", 1)[0] if "." in last_part else last_part
    
    for prefix in _DEGREE_PREFIXES:
        if last_part.startswith(prefix):
            # Determine degree level from prefix
            if prefix in ["phd-", "engd-", "edd-", "dba-"]:
                return (True, "PhD")
            elif prefix in ["mphil-"]:
                return (True, "Doctoral")
            elif prefix in ["msc-", "ma-", "mba-", "llm-", "mres-", "med-", "mph-", 
                           "meng-", "mfin-", "mpharm-", "mphys-", "msci-", "mla-", "mpa-"]:
                return (True, "Master's")
            elif prefix in ["pgce-", "pgdip-"]:
                return (True, "Certificate")
            else:
                return (True, "Unspecified")
    
    return (False, None)

def _is_high_confidence_url(url: str) -> bool:
    """Check if URL matches known high-confidence program page patterns."""
    url_lower = url.lower()
    return any(re.search(pattern, url_lower) for pattern in _HIGH_CONFIDENCE_PATTERNS)


def _calculate_url_confidence(url: str, title: str = "") -> float:
    """
    Calculate confidence score (0.0-1.0) that a URL is a program page.
    Higher scores = more likely to be a real program page.
    
    Used to prioritize Gemini classification - classify high-confidence first.
    """
    score = 0.5  # base score
    url_lower = url.lower()
    title_lower = title.lower()
    
    # Boost for program-indicating path segments
    if "/masters/" in url_lower or "/postgraduate/" in url_lower:
        score += 0.2
    if "/graduate/" in url_lower or "/phd/" in url_lower:
        score += 0.2
    if "/programmes/" in url_lower or "/programs/" in url_lower:
        score += 0.1
    
    # Boost for degree indicators in URL
    degree_keywords = ["msc", "ma", "mba", "phd", "mphil", "llm", "mres"]
    if any(kw in url_lower for kw in degree_keywords):
        score += 0.15
    
    # Boost for title indicators
    if title_lower:
        if any(kw in title_lower for kw in ["msc", "ma", "mba", "phd", "master"]):
            score += 0.1
    
    # Penalty for likely non-program pages
    if any(term in url_lower for term in ["/news/", "/blog/", "/events/", "/about/"]):
        score -= 0.3
    if any(term in url_lower for term in ["/admissions/", "/apply/", "/fees/"]):
        score -= 0.2
    
    return max(0.0, min(1.0, score))  # clamp to [0, 1]


async def _auto_confirm_candidate(url: str, university_name: str) -> dict | None:
    """
    Fast-path auto-confirmation for obvious program pages.
    Returns program dict if auto-confirmed, None if needs Gemini.
    
    Two-tier approach:
    1. Obvious degree slug (msc-, phd-, etc.) -> Extract from URL, skip fetch entirely
    2. High-confidence pattern -> Fetch and validate with simple checks
    
    Criteria for tier 1 (slug-based):
    - URL has obvious degree prefix (msc-, phd-, ma-, etc.)
    - Skip network fetch entirely (200+ URLs saved!)
    
    Criteria for tier 2 (pattern-based):
    - URL matches high-confidence pattern
    - Page exists (200 status)
    - Has a title
    - Word count > 200 (substantive content)
    """
    # TIER 1: Check for obvious degree slug first (no fetch needed!)
    has_slug, degree_level = _has_obvious_degree_slug(url)
    if has_slug and degree_level:
        # Extract program name from URL slug
        path = urlparse(url.lower()).path
        parts = [p for p in path.split("/") if p]
        if parts:
            # Last part is the slug — strip file extension first
            slug = parts[-1]
            slug = slug.rsplit(".", 1)[0] if "." in slug else slug
            # Convert slug to readable name: "ma-in-sociology" -> "MA in Sociology"
            # Keep degree code uppercase, lowercase connectors
            words = slug.replace("-", " ").split()
            _UPPER_CODES = {
                "ma": "MA", "msc": "MSc", "ms": "MS", "mba": "MBA",
                "llm": "LLM", "mphil": "MPhil", "mres": "MRes", "meng": "MEng",
                "mph": "MPH", "mfa": "MFA", "mpa": "MPA", "med": "MEd",
                "phd": "PhD", "dba": "DBA", "edd": "EdD", "engd": "EngD",
                "pgce": "PGCE", "pgdip": "PGDip", "mpharm": "MPharm",
                "msci": "MSci", "mla": "MLA", "llb": "LLB",
            }
            _LOWER_WORDS = {"in", "of", "and", "for", "the", "a", "an", "with", "at"}
            formatted = []
            for i, w in enumerate(words):
                if w in _UPPER_CODES:
                    formatted.append(_UPPER_CODES[w])
                elif i > 0 and w in _LOWER_WORDS:
                    formatted.append(w)
                else:
                    formatted.append(w.capitalize())
            program_name = " ".join(formatted)

            logger.debug(f"[program_discovery] Auto-confirm (slug): {url} -> {program_name}")

            return {
                "program_name": program_name,
                "degree_level": degree_level,
                "url": url,
                "confidence": 0.98,
            }
    
    # TIER 2: High-confidence pattern (requires fetch)
    if not _is_high_confidence_url(url):
        return None
    
    html, status = await _fetch_html(url, timeout=4.0)
    if status != 200 or not html or _word_count(html) < 200:
        return None
    
    title = _get_title(html)
    if not title or _is_soft_404(title):
        return None
    
    # Auto-confirm with high confidence
    program_name = _clean_program_name(title, university_name)
    degree_level = _fallback_degree_level(url, title)
    
    return {
        "program_name": program_name,
        "degree_level": degree_level,
        "url": url,
        "confidence": 0.95,  # auto-confirmed from pattern + content
    }


_CLASSIFICATION_PROMPT = """\
You are validating university academic program pages.

For EACH page below, determine:
1. is_program: true ONLY if this page is specifically about ONE degree/academic program
   Examples of TRUE: "MSc Data Science", "BA English Literature", "PhD Chemistry"
   Examples of FALSE:
   - General admissions pages ("Applying to Graduate School")
   - Department homepages ("School of Engineering")
   - Blog posts or student stories ("Why I chose to study...")
   - News or events pages
   - Listing pages showing multiple programs
   - Financial aid, tuition, or fees pages
   - "Why study at Manchester?", "Campus tours", "Widening participation"
2. program_name: the specific program name if is_program=true, otherwise null
3. degree_level: one of "Bachelor's", "Master's", "PhD", "Doctoral", "Certificate",
   "Associate's", "Diploma", "MBA", "Unspecified" — based ONLY on what's stated
4. confidence: 0.0 to 1.0 — how confident you are this is an individual program page

RULES:
- A blog post about studying a degree is NOT a program page
- A page titled "Clearing" or "How to Apply" is NOT a program page  
- A page about ONE specific course/program with its own requirements IS a program page
- Do NOT invent program names
- Use "Unspecified" rather than guessing degree level

Return ONLY a JSON array, one object per page, same order as input. No markdown, no explanation.

Pages:
{pages_json}
"""


async def _call_gemini_classify(
    candidates: list[dict],  # [{"index": int, "url": str, "title": str, "snippet": str}]
) -> list[dict]:
    """
    Call Gemini to classify a batch of candidates.
    Uses shared rate limiting from ai_extractor to avoid conflicts.
    Returns list of classification results.
    """
    if not settings.gemini_api_key:
        return []

    pages_json = json.dumps(candidates, indent=2)
    prompt = _CLASSIFICATION_PROMPT.format(pages_json=pages_json)

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }

    # Import shared rate limiter from ai_extractor
    from pipeline.ai_extractor import _GEMINI_SEMAPHORE, _enforce_rpm_limit, _request_timestamps
    
    for attempt in range(3):
        try:
            # Use shared semaphore + rate limit enforcement
            async with _GEMINI_SEMAPHORE:
                rate_limit_check_start = time.time()
                
                # Enforce RPM limit before making request
                wait = _enforce_rpm_limit()
                
                # Log rate limiter state before every request
                now = time.monotonic()
                recent_calls = [t for t in _request_timestamps if now - t < 60.0]
                logger.info(
                    f"[program_discovery] Rate limiter check: {len(recent_calls)} calls in last 60s, "
                    f"wait={wait:.1f}s"
                )
                
                if wait > 0:
                    logger.info(f"[program_discovery] ⏱️  RATE LIMIT: Sleeping {wait:.1f}s before API call")
                    await asyncio.sleep(wait)
                    logger.info(f"[program_discovery] ⏱️  RATE LIMIT: Sleep complete, proceeding with API call")
                
                rate_limit_overhead = time.time() - rate_limit_check_start
                
                # Track this request in the shared rolling window
                _request_timestamps.append(time.monotonic())
                
                api_call_start = time.time()
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, json=payload)
                    
                    # Handle 403 Forbidden immediately - don't retry
                    if resp.status_code == 403:
                        logger.error(
                            f"[program_discovery] Gemini 403 Forbidden - Authentication failed. "
                            f"Check API key, billing, or API enablement. Aborting Gemini classification."
                        )
                        return []
                    
                    # Handle 429 with backoff
                    if resp.status_code == 429:
                        wait = 30 * (attempt + 1)
                        logger.warning(f"[program_discovery] Gemini 429, waiting {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    
                    resp.raise_for_status()
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    # Strip markdown fences if present
                    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()
                    results = json.loads(text)
                    
                    api_call_duration = time.time() - api_call_start
                    total_call_duration = time.time() - rate_limit_check_start
                    
                    logger.info(
                        f"[program_discovery] Gemini timing: "
                        f"rate_limit_overhead={rate_limit_overhead:.1f}s, "
                        f"api_call={api_call_duration:.1f}s, "
                        f"total={total_call_duration:.1f}s"
                    )
                    
                    if isinstance(results, list):
                        return results
                    return []
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.error(
                    f"[program_discovery] Gemini 403 Forbidden - Authentication failed. "
                    f"Check API key: {settings.gemini_api_key[:20]}... "
                    f"Aborting Gemini classification."
                )
                return []
            logger.warning(f"[program_discovery] Gemini HTTP error attempt {attempt+1}: {e}")
            await asyncio.sleep(5)
        except json.JSONDecodeError as e:
            logger.warning(f"[program_discovery] Gemini JSON parse error: {e}")
            return []
        except Exception as e:
            logger.warning(f"[program_discovery] Gemini classify attempt {attempt+1} failed: {e}")
            await asyncio.sleep(5)

    return []


async def gemini_classify_candidates(
    candidates: list[str],
    university_name: str = "",
    batch_size: int = 12,
    max_duration_seconds: float = 600.0,
    hard_cap: int = 0,  # Stop early once this many programs confirmed (0=no cap)
) -> tuple[list[dict], str]:
    """
    Stage 3: Fetch title + snippet for each candidate, then classify in batches.
    
    Fast-path optimization: Auto-confirm obvious program pages (high-confidence URL patterns)
    without calling Gemini. Only uncertain candidates go to Gemini for classification.
    
    Returns tuple of (programs_list, status):
        - programs_list: confirmed programs (confidence >= 0.75)
        - status: "success" if all processed, "partial" if hit time limit
    """
    start_time = time.time()
    logger.info(
        f"[program_discovery] Stage 3 START at t=0.0s: classifying {len(candidates)} candidates "
        f"in batches of {batch_size}, max_duration={max_duration_seconds}s"
    )
    
    # Quick Gemini availability check
    gemini_available = bool(settings.gemini_api_key)
    if gemini_available:
        logger.info(f"[program_discovery] Gemini API key present: {settings.gemini_api_key[:20]}...")
    else:
        logger.warning("[program_discovery] No Gemini API key - will rely on heuristics only")
    
    # Timing instrumentation with wall-clock tracking
    timings = {
        "auto_confirm_phase": 0.0,
        "candidate_fetch_phase": 0.0,
        "gemini_classify_phase": 0.0,
        "gemini_api_time": 0.0,
        "rate_limit_wait_time": 0.0,
    }
    phase_timestamps = {
        "start": start_time,
    }
    
    # Step 1: Try auto-confirmation for high-confidence URLs
    phase_start = time.time()
    auto_confirm_sem = asyncio.Semaphore(25)  # Increased from 10 to 25
    
    logger.info(f"[program_discovery] t={phase_start - start_time:.1f}s: Starting auto-confirm phase")
    logger.info(f"[program_discovery] Auto-confirm: {len(candidates)} URLs to check, concurrency={auto_confirm_sem._value}")
    
    fetch_times = []
    completed_count = 0
    pattern_matched = 0
    pattern_rejected = 0
    slug_confirmed = 0  # NEW: Track slug-based confirmations (no fetch)
    fetch_confirmed = 0  # NEW: Track pattern-based confirmations (with fetch)
    fetch_failed = 0
    
    async def try_auto_confirm(url: str) -> tuple[str, dict | None]:
        nonlocal completed_count, pattern_matched, pattern_rejected, slug_confirmed, fetch_confirmed, fetch_failed
        async with auto_confirm_sem:
            url_start = time.time()
            
            # Check if URL has obvious degree slug (no fetch needed)
            has_slug, _ = _has_obvious_degree_slug(url)
            
            # Track if URL matches high-confidence pattern
            if has_slug or _is_high_confidence_url(url):
                pattern_matched += 1
            else:
                pattern_rejected += 1
            
            result = await _auto_confirm_candidate(url, university_name)
            
            if result:
                # Track which tier succeeded
                if has_slug:
                    slug_confirmed += 1
                else:
                    fetch_confirmed += 1
            else:
                fetch_failed += 1
            
            url_duration = time.time() - url_start
            fetch_times.append(url_duration)
            
            completed_count += 1
            if completed_count % 50 == 0:
                elapsed = time.time() - phase_start
                throughput = completed_count / elapsed if elapsed > 0 else 0
                logger.info(
                    f"[program_discovery] Auto-confirm progress: {completed_count}/{len(candidates)} "
                    f"({throughput:.2f} urls/sec, pattern_match={pattern_matched}, slug_confirmed={slug_confirmed}, fetch_confirmed={fetch_confirmed})"
                )
            
            return (url, result)
    
    auto_results = await asyncio.gather(
        *[try_auto_confirm(u) for u in candidates],
        return_exceptions=True,
    )
    
    auto_confirmed: list[dict] = []
    needs_gemini: list[str] = []
    
    for result in auto_results:
        if isinstance(result, tuple):
            url, prog = result
            if prog:
                auto_confirmed.append(prog)
            else:
                needs_gemini.append(url)
        else:
            # Exception occurred, send to Gemini as fallback
            if isinstance(result, Exception):
                logger.debug(f"[program_discovery] Auto-confirm error: {result}")
    
    timings["auto_confirm_phase"] = time.time() - phase_start
    phase_timestamps["auto_confirm_end"] = time.time()
    wall_clock_elapsed = phase_timestamps["auto_confirm_end"] - start_time
    
    # Calculate auto-confirm statistics
    avg_fetch_time = sum(fetch_times) / len(fetch_times) if fetch_times else 0
    min_fetch_time = min(fetch_times) if fetch_times else 0
    max_fetch_time = max(fetch_times) if fetch_times else 0
    
    logger.info(
        f"[program_discovery] t={wall_clock_elapsed:.1f}s: Auto-confirm complete - "
        f"{len(auto_confirmed)} auto-confirmed ({slug_confirmed} from slug, {fetch_confirmed} from pattern+fetch), "
        f"{len(needs_gemini)} need Gemini "
        f"(phase took {timings['auto_confirm_phase']:.1f}s)"
    )
    logger.info(
        f"[program_discovery] Auto-confirm stats: "
        f"{len(candidates)} URLs checked, "
        f"pattern_matched={pattern_matched}, "
        f"pattern_rejected={pattern_rejected}, "
        f"slug_confirmed={slug_confirmed} (no fetch!), "
        f"fetch_confirmed={fetch_confirmed}, "
        f"fetch_failed={fetch_failed}"
    )
    logger.info(
        f"[program_discovery] Auto-confirm timing: "
        f"avg={avg_fetch_time:.2f}s/URL, "
        f"min={min_fetch_time:.2f}s, "
        f"max={max_fetch_time:.2f}s"
    )
    
    # Note: pattern_rejected URLs return immediately without fetching (negligible time cost)
    if pattern_rejected > 0:
        logger.info(
            f"[program_discovery] Auto-confirm efficiency: "
            f"{pattern_rejected} URLs ({(pattern_rejected / len(candidates)) * 100:.1f}%) "
            f"rejected by pattern match WITHOUT fetching (fast path)"
        )

    
    # Step 2: Fetch title + snippet for remaining candidates (parallel, lightweight)
    if not needs_gemini:
        elapsed = time.time() - start_time
        logger.info(
            f"[program_discovery] t={elapsed:.1f}s: All candidates auto-confirmed, "
            f"skipping Gemini (timings: {timings})"
        )
        return (auto_confirmed, "success")
    
    # Log first 20 URLs going to Gemini for analysis
    logger.info(f"[program_discovery] First 20 URLs needing Gemini classification:")
    for i, url in enumerate(needs_gemini[:20], 1):
        logger.info(f"  {i}. {url}")
    
    phase_start = time.time()
    logger.info(
        f"[program_discovery] t={phase_start - start_time:.1f}s: Starting candidate fetch phase "
        f"({len(needs_gemini)} candidates)"
    )
    fetch_sem = asyncio.Semaphore(15)  # Reduced from 30: high concurrency triggers rate limiting
    logger.info(f"[program_discovery] Candidate fetch: concurrency={fetch_sem._value}")
    
    candidate_fetch_times = []
    completed_candidates = 0
    failure_log = []  # Track first 50 failures with details
    from urllib.parse import urlparse

    async def fetch_candidate_info(url: str) -> dict | None:
        nonlocal completed_candidates
        async with fetch_sem:
            url_start = time.time()
            
            try:
                html, status = await _fetch_html(url, timeout=6.0)  # Reverted: timeout not the issue
                url_duration = time.time() - url_start
                candidate_fetch_times.append(url_duration)
                
                completed_candidates += 1
                if completed_candidates % 25 == 0:
                    elapsed = time.time() - phase_start
                    throughput = completed_candidates / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"[program_discovery] Candidate fetch progress: {completed_candidates}/{len(needs_gemini)} "
                        f"({throughput:.2f} urls/sec)"
                    )
                
                if status != 200 or not html or _word_count(html) < 50:
                    # Log failure details for first 50
                    if len(failure_log) < 50:
                        hostname = urlparse(url).netloc
                        reason = "no_content" if not html else f"short_content_{_word_count(html)}" if html else f"status_{status}"
                        failure_log.append({
                            "url": url,
                            "hostname": hostname,
                            "reason": reason,
                            "status": status,
                            "duration": url_duration
                        })
                    return None
                    
                title = _get_title(html)
                if _is_soft_404(title):
                    if len(failure_log) < 50:
                        hostname = urlparse(url).netloc
                        failure_log.append({
                            "url": url,
                            "hostname": hostname,
                            "reason": "soft_404",
                            "status": status,
                            "duration": url_duration
                        })
                    return None
                    
                snippet = _get_snippet(html, max_words=200)
                confidence = _calculate_url_confidence(url, title)
                return {
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                    "url_confidence": confidence,
                }
            except Exception as exc:
                url_duration = time.time() - url_start
                candidate_fetch_times.append(url_duration)
                
                # Log exception details for first 50 failures
                if len(failure_log) < 50:
                    hostname = urlparse(url).netloc
                    exc_type = type(exc).__name__
                    failure_log.append({
                        "url": url,
                        "hostname": hostname,
                        "reason": "exception",
                        "exception_type": exc_type,
                        "exception_msg": str(exc)[:100],
                        "duration": url_duration
                    })
                    logger.warning(
                        f"[program_discovery] Fetch exception: {hostname} - {exc_type}: {str(exc)[:100]}"
                    )
                
                completed_candidates += 1
                return None

    fetch_results = await asyncio.gather(
        *[fetch_candidate_info(u) for u in needs_gemini],
        return_exceptions=True,
    )
    fetched = [r for r in fetch_results if isinstance(r, dict) and r is not None]
    
    # Sort by confidence (highest first) to prioritize better candidates
    fetched.sort(key=lambda x: x.get("url_confidence", 0.5), reverse=True)
    
    timings["candidate_fetch_phase"] = time.time() - phase_start
    phase_timestamps["candidate_fetch_end"] = time.time()
    wall_clock_elapsed = phase_timestamps["candidate_fetch_end"] - start_time
    
    # Calculate candidate fetch statistics
    avg_candidate_time = sum(candidate_fetch_times) / len(candidate_fetch_times) if candidate_fetch_times else 0
    min_candidate_time = min(candidate_fetch_times) if candidate_fetch_times else 0
    max_candidate_time = max(candidate_fetch_times) if candidate_fetch_times else 0
    failed_fetches = len(needs_gemini) - len(fetched)
    
    # Log failure analysis
    if failure_log:
        logger.info(f"[program_discovery] Candidate fetch failure analysis (first {len(failure_log)} failures):")
        
        # Aggregate by hostname
        from collections import Counter
        hostname_failures = Counter(f["hostname"] for f in failure_log)
        logger.info(f"[program_discovery]   Failures by hostname:")
        for hostname, count in hostname_failures.most_common(10):
            logger.info(f"[program_discovery]     {hostname}: {count} failures")
        
        # Aggregate by failure reason
        reason_counts = Counter(f["reason"] for f in failure_log)
        logger.info(f"[program_discovery]   Failures by reason:")
        for reason, count in reason_counts.most_common():
            logger.info(f"[program_discovery]     {reason}: {count} failures")
        
        # Show exception types if any
        exception_types = Counter(f.get("exception_type") for f in failure_log if f.get("exception_type"))
        if exception_types:
            logger.info(f"[program_discovery]   Exception types:")
            for exc_type, count in exception_types.most_common():
                logger.info(f"[program_discovery]     {exc_type}: {count} occurrences")
        
        # Show sample of first 5 failures
        logger.info(f"[program_discovery]   Sample failures (first 5):")
        for i, fail in enumerate(failure_log[:5], 1):
            if fail.get("exception_type"):
                logger.info(
                    f"[program_discovery]     {i}. {fail['hostname']} - {fail['exception_type']}: "
                    f"{fail.get('exception_msg', 'N/A')[:80]} ({fail['duration']:.2f}s)"
                )
            else:
                logger.info(
                    f"[program_discovery]     {i}. {fail['hostname']} - {fail['reason']} "
                    f"(status={fail.get('status', 'N/A')}, {fail['duration']:.2f}s)"
                )
    
    logger.info(
        f"[program_discovery] t={wall_clock_elapsed:.1f}s: Candidate fetch complete - "
        f"{len(fetched)}/{len(needs_gemini)} candidates fetched "
        f"(phase took {timings['candidate_fetch_phase']:.1f}s)"
    )
    logger.info(
        f"[program_discovery] Candidate fetch stats: "
        f"{len(candidate_fetch_times)} requests, "
        f"{failed_fetches} failed, "
        f"avg={avg_candidate_time:.2f}s/URL, "
        f"min={min_candidate_time:.2f}s, "
        f"max={max_candidate_time:.2f}s"
    )

    if not fetched:
        elapsed = time.time() - start_time
        logger.info(
            f"[program_discovery] t={elapsed:.1f}s: No fetchable candidates for Gemini "
            f"(timings: {timings})"
        )
        return (auto_confirmed, "success")

    # Step 3: Classify in batches with time limit
    phase_start = time.time()
    phase_timestamps["gemini_phase_start"] = phase_start
    logger.info(
        f"[program_discovery] t={phase_start - start_time:.1f}s: Starting Gemini classification phase "
        f"({len(fetched)} candidates, {(len(fetched) + batch_size - 1) // batch_size} batches expected)"
    )
    
    confirmed_programs: list[dict] = []
    gemini_calls = 0
    candidates_processed = 0
    status = "success"  # assume success unless we hit time limit

    for i in range(0, len(fetched), batch_size):
        # Check time limit before each batch
        elapsed = time.time() - start_time
        if elapsed >= max_duration_seconds:
            logger.warning(
                f"[program_discovery] t={elapsed:.1f}s: Hit time limit ({max_duration_seconds}s) "
                f"after {gemini_calls} Gemini calls, {candidates_processed}/{len(fetched)} candidates processed"
            )
            status = "partial"
            break

        # Early-exit if hard cap reached
        total_so_far = len(auto_confirmed) + len(confirmed_programs)
        if hard_cap > 0 and total_so_far >= hard_cap:
            logger.info(
                f"[program_discovery] t={elapsed:.1f}s: Discovery cap reached "
                f"({total_so_far} >= {hard_cap}), skipping remaining Gemini batches"
            )
            status = "capped"
            break
        
        batch = fetched[i:i + batch_size]
        batch_input = [
            {"index": j, "url": c["url"], "title": c["title"], "snippet": c["snippet"][:500]}
            for j, c in enumerate(batch)
        ]

        gemini_calls += 1
        batch_wall_start = time.time()
        logger.info(
            f"[program_discovery] t={batch_wall_start - start_time:.1f}s: Starting Gemini batch {gemini_calls} "
            f"({len(batch)} candidates)"
        )
        
        batch_start = time.time()
        gemini_api_start = time.time()
        results = await _call_gemini_classify(batch_input)
        gemini_api_duration = time.time() - gemini_api_start
        batch_duration = time.time() - batch_start
        batch_wall_end = time.time()
        
        # Check if Gemini auth failed (returns empty list on 403)
        if results is None or (isinstance(results, list) and len(results) == 0 and len(batch) > 0):
            # If this is the first batch and we got nothing, Gemini likely failed
            if gemini_calls == 1:
                logger.error(
                    f"[program_discovery] Gemini returned no results on first batch. "
                    f"Likely auth failure. Skipping remaining Gemini classification."
                )
                gemini_available = False
                status = "partial"
                break
        
        timings["gemini_api_time"] += gemini_api_duration
        
        logger.info(
            f"[program_discovery] t={batch_wall_end - start_time:.1f}s: Gemini batch {gemini_calls} complete - "
            f"{len(batch)} candidates classified in {batch_duration:.1f}s "
            f"(API call: {gemini_api_duration:.1f}s, wall-clock: {batch_wall_end - batch_wall_start:.1f}s)"
        )

        for result in results:
            if not isinstance(result, dict):
                continue
            if not result.get("is_program"):
                continue
            confidence = float(result.get("confidence", 0))
            if confidence < 0.75:
                continue

            # Find matching candidate URL by index
            idx = result.get("index", -1)
            if 0 <= idx < len(batch):
                url = batch[idx]["url"]
                program_name = result.get("program_name") or _clean_program_name(
                    batch[idx]["title"], university_name
                )
                degree_level = result.get("degree_level") or _fallback_degree_level(
                    url, batch[idx]["title"]
                )
                confirmed_programs.append({
                    "program_name": program_name,
                    "degree_level": degree_level,
                    "url": url,
                    "confidence": confidence,
                })
        
        candidates_processed = i + len(batch)

    timings["gemini_classify_phase"] = time.time() - phase_start
    phase_timestamps["gemini_phase_end"] = time.time()
    elapsed = time.time() - start_time
    
    logger.info(
        f"[program_discovery] t={elapsed:.1f}s: Stage 3 classification complete - "
        f"{len(confirmed_programs)} confirmed programs from {gemini_calls} Gemini calls (status={status})"
    )
    
    # Log detailed timing breakdown with wall-clock analysis
    logger.info(
        f"[program_discovery] Stage 3 TIMING BREAKDOWN:"
    )
    logger.info(
        f"  Phase 1 - Auto-confirm:    {timings['auto_confirm_phase']:6.1f}s "
        f"(t=0.0 to t={phase_timestamps.get('auto_confirm_end', 0) - start_time:.1f}s)"
    )
    logger.info(
        f"  Phase 2 - Candidate fetch: {timings['candidate_fetch_phase']:6.1f}s "
        f"(t={phase_timestamps.get('auto_confirm_end', 0) - start_time:.1f}s "
        f"to t={phase_timestamps.get('candidate_fetch_end', 0) - start_time:.1f}s)"
    )
    logger.info(
        f"  Phase 3 - Gemini classify: {timings['gemini_classify_phase']:6.1f}s "
        f"(t={phase_timestamps.get('gemini_phase_start', 0) - start_time:.1f}s "
        f"to t={phase_timestamps.get('gemini_phase_end', 0) - start_time:.1f}s)"
    )
    logger.info(
        f"    └─ Gemini API time:      {timings['gemini_api_time']:6.1f}s "
        f"(actual API calls)"
    )
    logger.info(
        f"    └─ Overhead:             {timings['gemini_classify_phase'] - timings['gemini_api_time']:6.1f}s "
        f"({(timings['gemini_classify_phase'] - timings['gemini_api_time']) / timings['gemini_classify_phase'] * 100:.0f}% of phase)"
    )
    logger.info(
        f"  TOTAL WALL-CLOCK TIME:     {elapsed:6.1f}s"
    )
    
    # Calculate and log overhead
    accounted_time = (
        timings['auto_confirm_phase'] + 
        timings['candidate_fetch_phase'] + 
        timings['gemini_classify_phase']
    )
    overhead = elapsed - accounted_time
    
    logger.info(
        f"  Accounted time:            {accounted_time:6.1f}s"
    )
    logger.info(
        f"  Unaccounted overhead:      {overhead:6.1f}s ({overhead / elapsed * 100:.0f}% of total)"
    )
    
    if overhead > 5.0:
        logger.warning(
            f"[program_discovery] Stage 3: {overhead:.1f}s unaccounted overhead detected! "
            f"Check for sequential operations or hidden waits."
        )
    
    # Step 4: Combine auto-confirmed + Gemini-confirmed
    all_programs = auto_confirmed + confirmed_programs
    logger.info(
        f"[program_discovery] Stage 3 total: {len(all_programs)} programs "
        f"({len(auto_confirmed)} auto-confirmed + {len(confirmed_programs)} Gemini-confirmed)"
    )
    return (all_programs, status)


# ── Stage 4: Sibling Expansion ────────────────────────────────────────────────

async def sibling_expansion(
    confirmed_programs: list[dict],
    domain: str,
    university_name: str = "",
) -> list[dict]:
    """
    Stage 4: Given at least one confirmed program, find siblings from sitemap
    under the same parent directory. Runs one pass only — no recursive expansion.
    Returns additional confirmed programs to merge with Stage 3 results.
    """
    if not confirmed_programs:
        return []

    # Collect unique parent directories from confirmed programs
    all_locs = await _load_all_sitemap_locs(domain)
    if not all_locs:
        return []

    # Find parent dirs of confirmed programs
    seen_parents: set[str] = set()
    for prog in confirmed_programs:
        url = prog["url"]
        parsed = urlparse(url)
        parent_path = parsed.path.rsplit("/", 1)[0] + "/"
        parent_url = f"{parsed.scheme}://{parsed.netloc}{parent_path}"
        norm = _normalize_url(parent_url.rstrip("/"))
        seen_parents.add(norm)

    # Find sitemap locs under those parent dirs (excluding already-confirmed ones)
    confirmed_urls = {_normalize_url(p["url"]) for p in confirmed_programs}
    sibling_candidates: list[str] = []
    for loc in all_locs:
        loc = loc.strip()
        norm = _normalize_url(loc)
        if norm in confirmed_urls:
            continue
        loc_parent = _normalize_url(urlparse(loc).path.rsplit("/", 1)[0])
        if any(loc_parent.endswith(p.rstrip("/").split("://", 1)[-1].split("/", 1)[-1])
               for p in seen_parents):
            sibling_candidates.append(loc)

    sibling_candidates = [u for u in sibling_candidates if cheap_prefilter(u)]

    # Apply same graduate-only filter as Stage 2.5 (slug-based, not raw substring)
    _UNDERGRAD_SIBLING_RE = re.compile(
        r"^(bs|ba|bfa|bme|bse|bsn|bba|bsba|bsrs|bsw|bsed|bsph|bscs|bsis|"
        r"bsa|bgs|bsce|bsee|bsme|bsie|bsit|bscpe|bscp|bste|bas|"
        r"beng|bsc|llb|barch|bbe|bmus|bm|bcom|btech|bca|bdes|"
        r"aas|aasn|ags|as|aa|"
        r"minor|concentration|track|endorsement"
        r")([-_]|$|in-)",
        re.IGNORECASE,
    )

    def _is_grad_sibling(url: str) -> bool:
        url_lower = url.lower()
        path = urlparse(url_lower).path
        slug = path.rstrip("/").rsplit("/", 1)[-1]
        slug = slug.rsplit(".", 1)[0] if "." in slug else slug
        for prefix in ("online-", "on-campus-", "campus-", "part-time-", "full-time-"):
            if slug.startswith(prefix):
                slug = slug[len(prefix):]
                break
        if _UNDERGRAD_SIBLING_RE.match(slug):
            return False
        if any(s in url_lower for s in ["/undergraduate/", "/undergrad/", "/bachelor", "/minors/"]):
            return False
        return True

    sibling_candidates = [u for u in sibling_candidates if _is_grad_sibling(u)]

    # Also filter out certificate URLs from siblings — they score negative in Stage 1.5
    # and shouldn't be re-introduced via sibling expansion
    sibling_candidates = [
        u for u in sibling_candidates
        if not ("certificate-in-" in u.lower() or "cert-in-" in u.lower())
    ]

    # Cap sibling candidates to 2× remaining headroom
    from config import settings as _settings
    cap = _settings.max_programs_per_university
    remaining = max(0, cap - len(confirmed_programs))
    sibling_cap = remaining * 2
    if len(sibling_candidates) > sibling_cap:
        logger.info(
            f"[program_discovery] Stage 4: capping siblings {len(sibling_candidates)} → {sibling_cap} "
            f"({remaining} slots remaining toward cap {cap})"
        )
        sibling_candidates = sibling_candidates[:sibling_cap]

    logger.info(
        f"[program_discovery] Stage 4: {len(sibling_candidates)} sibling candidates"
    )

    if not sibling_candidates:
        return []

    # Classify siblings with the same Stage 2+3 pipeline
    filtered = [u for u in sibling_candidates if cheap_prefilter(u)][:sibling_cap]
    return await gemini_classify_candidates(
        filtered, university_name,
        hard_cap=_settings.max_programs_per_university,
    )


# ── Legacy BFS fallback ───────────────────────────────────────────────────────

async def _legacy_bfs_fallback(
    domain: str,
    university_name: str = "",
    max_pages: int = 30,
) -> list[str]:
    """
    Last-resort BFS when sitemap and SerpAPI return nothing.
    Returns raw candidate URLs (not classified).
    """
    logger.info(f"[program_discovery] Legacy BFS for {domain}")
    base = f"https://{domain}"
    bases = [base, f"https://www.{domain}"] if not domain.startswith("www.") else [base]

    index_pages: list[str] = []
    seen_paths: set[str] = set()
    sem = asyncio.Semaphore(5)

    async def check_index(path: str, b: str) -> str | None:
        async with sem:
            url = f"{b}{path}"
            html, status = await _fetch_html(url, timeout=6.0)
            min_words = 100 if any(s in path for s in ["/programs", "/courses"]) else 300
            if status == 200 and html and _word_count(html) > min_words:
                return url
            return None

    tasks = [check_index(p, b) for p in _INDEX_PATHS for b in bases]
    for r in await asyncio.gather(*tasks):
        if r:
            pk = urlparse(r).path
            if pk not in seen_paths:
                seen_paths.add(pk)
                index_pages.append(r)

    if not index_pages:
        return []

    candidates: set[str] = set()
    visited: set[str] = set(index_pages)
    queue: list[tuple[str, int]] = [(u, 0) for u in index_pages]
    pages_scanned = 0
    fetch_sem = asyncio.Semaphore(5)

    async def fetch_links(url: str, depth: int) -> list[str]:
        nonlocal pages_scanned
        async with fetch_sem:
            html, status = await _fetch_html(url)
            pages_scanned += 1
            if status != 200 or not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            links = []
            domain_bare = domain.replace("www.", "")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href or href.startswith("#"):
                    continue
                abs_url = urljoin(url, href)
                parsed = urlparse(abs_url)
                if not parsed.scheme.startswith("http"):
                    continue
                link_domain = parsed.netloc.replace("www.", "")
                if link_domain == domain_bare or link_domain.endswith("." + domain_bare):
                    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
                    if clean:
                        links.append(clean)
                        candidates.add(clean)
            return links

    while queue and pages_scanned < max_pages:
        wave = queue[:8]
        queue = queue[8:]
        for link_list in await asyncio.gather(*[fetch_links(u, d) for u, d in wave]):
            for link in link_list:
                if link not in visited:
                    visited.add(link)
                    queue.append((link, 1))

    logger.info(
        f"[program_discovery] Legacy BFS: {pages_scanned} pages, "
        f"{len(candidates)} candidates"
    )
    return list(candidates)


# ── Main entry point ──────────────────────────────────────────────────────────

async def discover_programs(
    domain: str,
    university_name: str = "",
    max_pages: int = 30,
    max_programs: int = 500,  # Increased default from 200 to 500
    skip_gemini_threshold: int = 0,  # If >0, skip Gemini when candidates < threshold
) -> list[dict]:
    """
    Discover university program pages using Gemini-based classification.

    Stage 1: Collect candidates (sitemap + SerpAPI + legacy BFS)
    Stage 2: Cheap string pre-filter
    Stage 3: Gemini batch classification (title + 200 words, 12/call)
    Stage 4: Sibling expansion around confirmed programs (one pass)

    Parameters:
        max_programs: Maximum programs to return (default 500)
        skip_gemini_threshold: If >0, skip Gemini when remaining candidates < threshold
                               Useful when Gemini finds very few programs relative to time cost

    Returns list of {"program_name", "degree_level", "url"} dicts.
    NOTE: This is for the discovery list UI only — degree_level/program_name
    here are provisional display labels. Full extraction runs independently.
    """
    logger.info(f"[program_discovery] Starting discovery for {domain}")

    # ── Stage 1: Collect candidates ───────────────────────────────────────────
    candidates = await collect_candidates(domain, university_name)

    # If sitemap + SerpAPI found nothing, fall back to legacy BFS
    if len(candidates) < 5:
        logger.info(
            f"[program_discovery] Only {len(candidates)} from sitemap+SerpAPI "
            f"— trying legacy BFS"
        )
        bfs_candidates = await _legacy_bfs_fallback(domain, university_name, max_pages)
        # Merge and deduplicate
        seen = {_normalize_url(u) for u in candidates}
        for u in bfs_candidates:
            if _normalize_url(u) not in seen:
                seen.add(_normalize_url(u))
                candidates.append(u)
        candidates = candidates[:150]

    logger.info(f"[program_discovery] Stage 1: {len(candidates)} candidates")

    # ── Stage 1.5: Score and prioritize candidates ────────────────────────────
    # Calculate confidence score for each candidate
    # Keep positive/negative scores separate for better debugging
    scored_candidates = []
    for url in candidates:
        positive, negative = _calculate_simple_confidence(url)
        net_score = positive - negative
        scored_candidates.append((url, net_score, positive, negative))
    
    # Sort by net score descending (highest confidence first)
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    
    # Log distribution for analysis
    positive_net = [(s, p, n) for _, s, p, n in scored_candidates if s > 0]
    zero_net = [(s, p, n) for _, s, p, n in scored_candidates if s == 0]
    negative_net = [(s, p, n) for _, s, p, n in scored_candidates if s < 0]
    
    logger.info(f"[program_discovery] Confidence distribution:")
    logger.info(f"  Positive net scores (likely programs): {len(positive_net)}")
    logger.info(f"  Zero net scores (unknown): {len(zero_net)}")
    logger.info(f"  Negative net scores (likely not programs): {len(negative_net)}")
    
    if positive_net:
        max_score = max(s for _, s, _, _ in scored_candidates)
        min_positive = min(s for s, _, _ in positive_net)
        logger.info(f"  Score range: {min_positive:.1f} to {max_score:.1f}")
        
        # Show top 10 for debugging with positive/negative breakdown
        logger.info(f"  Top 10 URLs by confidence:")
        for i, (url, net, pos, neg) in enumerate(scored_candidates[:10], 1):
            logger.info(f"    {i}. [net={net:+.1f}, pos={pos:.1f}, neg={neg:.1f}] {url}")
    
    # Extract URLs in priority order, keep only non-negative net scores
    candidates = [url for url, net, _, _ in scored_candidates if net >= 0]
    
    logger.info(f"[program_discovery] After scoring: {len(candidates)} candidates (removed {len(negative_net)} negative net scores)")

    # ── Stage 2: Cheap pre-filter ─────────────────────────────────────────────
    filtered = [u for u in candidates if cheap_prefilter(u)]
    logger.info(
        f"[program_discovery] Stage 2: {len(filtered)} after pre-filter "
        f"(dropped {len(candidates) - len(filtered)})"
    )

    if not filtered:
        logger.warning(f"[program_discovery] No candidates survived pre-filter for {domain}")
        return []

    # ── Stage 2.5: Graduate-only filter ──────────────────────────────────────
    # Client decision: restrict discovery to graduate programs only.
    # Drop Bachelor's, Associate's, Minors, and Concentrations before any
    # expensive fetch/Gemini work.
    #
    # FIX: Previous version used raw substring patterns like "/ba-" which are
    # UNSAFE — "/ba-" matches "mba-in-marketing" (false positive drops MBA).
    # "/bsc-" doesn't match "bs-in-accounting" (false negative keeps undergrad).
    # Solution: match against the LAST PATH SEGMENT (slug) with a regex that
    # requires the prefix to appear at the START of the slug.

    import re as _re

    _UNDERGRAD_SLUG_RE = _re.compile(
        r"^(bs|ba|bfa|bme|bse|bsn|bba|bsba|bsrs|bsw|bsed|bsph|bscs|bsis|"
        r"bsa|bgs|bsce|bsee|bsme|bsie|bsit|bscpe|bscp|bste|bas|"
        r"beng|bsc|llb|barch|bbe|bmus|bm|bcom|btech|bca|bdes|"
        r"aas|aasn|ags|as|aa|"
        r"minor|concentration|track|endorsement"
        r")([-_]|$|in-)",
        _re.IGNORECASE,
    )

    def _is_likely_graduate(url: str) -> bool:
        url_lower = url.lower()
        # Extract the last non-empty path segment (the slug), strip extension
        path = urlparse(url_lower).path
        slug = path.rstrip("/").rsplit("/", 1)[-1]
        slug = slug.rsplit(".", 1)[0] if "." in slug else slug

        # Strip common prefixes that obscure the degree code
        # e.g. "online-bsn-in-nursing" → "bsn-in-nursing"
        for prefix in ("online-", "on-campus-", "campus-", "part-time-", "full-time-"):
            if slug.startswith(prefix):
                slug = slug[len(prefix):]
                break

        # Drop if slug starts with an undergrad/minor prefix
        if _UNDERGRAD_SLUG_RE.match(slug):
            return False

        # Drop structural path segments that are always undergrad
        _UNDERGRAD_PATH_SEGMENTS = [
            "/undergraduate/", "/undergrad/", "/bachelor", "/associate/", "/minors/",
        ]
        if any(s in url_lower for s in _UNDERGRAD_PATH_SEGMENTS):
            return False

        return True

    grad_filtered = [u for u in filtered if _is_likely_graduate(u)]
    dropped_undergrad = len(filtered) - len(grad_filtered)
    logger.info(
        f"[program_discovery] Stage 2.5 graduate filter: {len(grad_filtered)} kept "
        f"({dropped_undergrad} likely-undergrad dropped)"
    )
    filtered = grad_filtered

    # ── Stage 2.6: Apply discovery cap before expensive stages ───────────────
    # Rank by the confidence score already computed. Taking the top N here
    # means Stage 3 (Gemini) and Stage 4 (siblings) work on a bounded pool.
    cap = settings.max_programs_per_university
    # Allow 2× headroom so attrition from Gemini filtering still lands ≥ cap
    candidate_cap = cap * 2
    if len(filtered) > candidate_cap:
        logger.info(
            f"[program_discovery] Capping candidates: {len(filtered)} → {candidate_cap} "
            f"(2× headroom over target {cap})"
        )
        # Re-score the filtered set (scores were computed pre-filter above)
        url_to_score = {
            url: net for url, net, _, _ in scored_candidates
        }
        filtered.sort(key=lambda u: url_to_score.get(u, 0.0), reverse=True)
        filtered = filtered[:candidate_cap]

    # ── Stage 3: Gemini classification ───────────────────────────────────────
    # Optional: Skip Gemini if remaining candidates are below threshold
    # Useful when Gemini finds very few programs relative to time cost
    if skip_gemini_threshold > 0 and len(filtered) < skip_gemini_threshold:
        logger.info(
            f"[program_discovery] Skipping Gemini: {len(filtered)} candidates < threshold {skip_gemini_threshold}. "
            f"Using heuristics only."
        )
        confirmed = []
        classification_status = "skipped"
    else:
        confirmed, classification_status = await gemini_classify_candidates(
            filtered, university_name, batch_size=15,
            hard_cap=settings.max_programs_per_university,
        )

    if not confirmed:
        logger.warning(
            f"[program_discovery] Gemini found 0 programs for {domain} "
            f"(no API key, skipped, or all filtered out)"
        )
        return []

    logger.info(f"[program_discovery] Stage 3: {len(confirmed)} programs confirmed")

    # ── Stage 4: Sibling expansion ────────────────────────────────────────────
    cap = settings.max_programs_per_university
    if len(confirmed) >= cap:
        logger.info(
            f"[program_discovery] Stage 4 skipped: already at cap "
            f"({len(confirmed)} >= {cap})"
        )
    else:
        siblings_result = await sibling_expansion(confirmed, domain, university_name)
        # sibling_expansion calls gemini_classify_candidates which returns (list, status)
        siblings = siblings_result[0] if isinstance(siblings_result, tuple) else siblings_result
        if siblings:
            logger.info(f"[program_discovery] Stage 4: {len(siblings)} additional siblings")
            confirmed = confirmed + siblings

    # ── Post-classification tier sort ────────────────────────────────────────
    # Sort confirmed programs by degree priority before applying the cap.
    # This ensures PhD/Doctoral/Master's programs are selected preferentially
    # over Certificates, regardless of the order Gemini confirmed them.
    # A university with 100 certificate pages should not crowd out its
    # flagship graduate programs from the final 40.
    #
    # Priority (lower = better).
    # For a study-abroad platform, Master's and PhD are equally valuable —
    # both are the primary target audience. Doctoral (MPhil, Ed.D, DPT etc.)
    # sits just below since those are niche/professional. Certificates last.
    _DEGREE_PRIORITY = {
        "PhD":         0,
        "Master's":    0,
        "MBA":         0,
        "Doctoral":    1,
        "Certificate": 2,
        "Diploma":     2,
        "Unspecified": 2,
        "Associate's": 3,
        "Bachelor's":  3,
    }

    confirmed.sort(key=lambda p: _DEGREE_PRIORITY.get(p.get("degree_level", "Unspecified"), 2))

    # Log tier breakdown before cap
    from collections import Counter as _Counter
    tier_counts = _Counter(p.get("degree_level", "Unspecified") for p in confirmed)
    logger.info(
        f"[program_discovery] Pre-cap tier breakdown ({len(confirmed)} total): "
        + ", ".join(f"{k}={v}" for k, v in sorted(tier_counts.items(), key=lambda x: _DEGREE_PRIORITY.get(x[0], 2)))
    )

    # Soft certificate cap: certificates can fill at most 25% of the final output.
    # If a university has 30 certs and 10 masters, we still surface the 10 masters
    # first and only fill remaining slots with certs — never the other way around.
    # Falls back gracefully: if there are NO masters/PhD programs, certs are fine.
    cap = settings.max_programs_per_university
    cert_soft_cap = max(5, cap // 4)  # 25% of cap, minimum 5
    degree_programs = [p for p in confirmed if _DEGREE_PRIORITY.get(p.get("degree_level", "Unspecified"), 2) < 2]
    cert_programs   = [p for p in confirmed if _DEGREE_PRIORITY.get(p.get("degree_level", "Unspecified"), 2) >= 2]

    if len(degree_programs) >= cap:
        # Enough degree programs to fill the cap — don't include any certs
        confirmed = degree_programs
        logger.info(f"[program_discovery] Tier sort: {len(degree_programs)} degree programs >= cap ({cap}), certs excluded")
    elif len(degree_programs) + cert_soft_cap < cap:
        # Not enough degree programs to fill even the cert-capped result — allow all certs
        confirmed = degree_programs + cert_programs
        logger.info(
            f"[program_discovery] Tier sort: {len(degree_programs)} degree programs + "
            f"{len(cert_programs)} certs (soft cap not limiting)"
        )
    else:
        # Mix: fill degree programs first, then fill remaining slots with certs
        remaining_slots = cap - len(degree_programs)
        certs_to_include = min(remaining_slots, cert_soft_cap, len(cert_programs))
        confirmed = degree_programs + cert_programs[:certs_to_include]
        logger.info(
            f"[program_discovery] Tier sort: {len(degree_programs)} degree programs + "
            f"{certs_to_include}/{len(cert_programs)} certs (soft cap={cert_soft_cap})"
        )

    # ── Deduplicate and cap ───────────────────────────────────────────────────
    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    final: list[dict] = []

    for prog in confirmed:
        norm_url = _normalize_url(prog["url"])
        norm_name = re.sub(r"\s+", " ", prog["program_name"].lower().strip())
        if norm_url in seen_urls or (norm_name and norm_name in seen_names):
            continue
        seen_urls.add(norm_url)
        if norm_name:
            seen_names.add(norm_name)
        # Strip confidence from final output (internal only)
        final.append({
            "program_name": prog["program_name"],
            "degree_level": prog["degree_level"],
            "url": prog["url"],
        })

    final = final[:settings.max_programs_per_university]
    logger.info(
        f"[program_discovery] Final: {len(final)} unique programs for {domain} "
        f"(target={settings.max_programs_per_university}, discovered={len(confirmed)} total, "
        f"classification_status={classification_status})"
    )
    return final

