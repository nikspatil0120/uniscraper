# utils/url_utils.py
# URL helper functions used throughout the pipeline.
# is_same_domain, normalize_url, is_pdf_url, score_url_relevance

import re
from urllib.parse import urlparse, urljoin


def _strip_www(netloc: str) -> str:
    """Remove leading 'www.' from a netloc for domain comparison."""
    return netloc.lower().removeprefix("www.")


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Return True if both URLs share the same domain (ignoring www. prefix).
    """
    try:
        return _strip_www(urlparse(url1).netloc) == _strip_www(urlparse(url2).netloc)
    except Exception:
        return False


def normalize_url(url: str, base_url: str) -> str | None:
    """
    Resolve a potentially relative URL against base_url.
    Returns an absolute URL string, or None if the URL should be skipped.
    """
    if not url:
        return None

    url = url.strip()

    # Skip non-navigable schemes
    lower = url.lower()
    if lower.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None

    # Already absolute
    if lower.startswith("http://") or lower.startswith("https://"):
        result = url
    elif lower.startswith("//"):
        # Protocol-relative — inherit scheme from base
        scheme = urlparse(base_url).scheme or "https"
        result = f"{scheme}:{url}"
    elif lower.startswith("/"):
        # Root-relative
        parsed_base = urlparse(base_url)
        result = f"{parsed_base.scheme}://{parsed_base.netloc}{url}"
    elif lower.startswith("#"):
        # Anchor-only link — skip
        return None
    else:
        # Relative path — resolve against base
        result = urljoin(base_url, url)

    # Strip fragment
    if "#" in result:
        result = result.split("#")[0]

    # Strip query parameters — they don't change page content for our purposes
    if "?" in result:
        result = result.split("?")[0]

    # Strip trailing slash (but keep bare domain intact)
    parsed = urlparse(result)
    if parsed.path not in ("", "/"):
        result = result.rstrip("/")

    return result if result else None


def is_pdf_url(url: str) -> bool:
    """
    Return True if the URL points to a PDF file.
    Checks path extension, /pdf/ path segment, and format= query param.
    """
    lower = url.lower()
    return (
        lower.endswith(".pdf")
        or "/pdf/" in lower
        or "format=pdf" in lower
    )


# Keyword scoring tables - Updated with improved weights
_HIGH_PRIORITY = {
    "tuition": 5, "fees": 5, "fee": 5, "cost": 4, "costs": 4,
    "english": 4, "requirements": 4, "requirement": 4,
    "admissions": 3, "admission": 3, "apply": 2, "application": 2,
    "visa": 1,
}
_LANGUAGE_KEYWORDS = {
    "ielts": 4, "toefl": 4, "pte": 4, "duolingo": 3,
    "language": 3, "proficiency": 3,
}
_POSITIVE_KEYWORDS = {
    "eligibility": 3, "entry": 2, "program": 1, "programme": 1,
    "course": 1, "study": 1, "international": 2, "overseas": 2,
    "global": 1, "deadline": 3, "deadlines": 3,
}
_NEGATIVE_KEYWORDS = {
    "news": -3, "blog": -3, "event": -2, "events": -2,
    "alumni": -2, "donate": -3, "contact": -1, "login": -3,
    "portal": -2, "staff": -2, "faculty": -2, "research": -2,
    "about": -1, "history": -2, "campus": -1,
}


def score_url_relevance(url: str, link_text: str) -> int:
    """
    Score a URL + link text pair by admission-relevance keywords.
    Higher score = more likely to contain useful admission data.
    
    Scoring system:
    - tuition/fees: +5 (highest priority)
    - english/requirements: +4  
    - admissions: +3
    - apply: +2
    - visa: +1
    - negative keywords: -1 to -3
    """
    combined = (url + " " + link_text).lower()
    # Tokenise loosely — split on non-alphanumeric chars
    tokens = set(re.split(r"[^a-z0-9]+", combined))

    score = 0
    
    # Check all keyword categories
    all_keywords = {**_HIGH_PRIORITY, **_LANGUAGE_KEYWORDS, **_POSITIVE_KEYWORDS, **_NEGATIVE_KEYWORDS}
    
    for keyword, weight in all_keywords.items():
        if keyword in tokens or keyword in combined:
            score += weight

    # Bonus for multiple relevant keywords
    relevant_count = sum(1 for kw in _HIGH_PRIORITY.keys() | _LANGUAGE_KEYWORDS.keys() 
                        if kw in tokens or kw in combined)
    if relevant_count >= 2:
        score += 1  # Bonus for pages with multiple relevant topics

    return max(0, score)  # Don't return negative scores


