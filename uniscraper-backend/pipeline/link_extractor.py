# pipeline/link_extractor.py
# extract_relevant_links(html: str, base_url: str) -> list[str]
# Finds, scores, and returns the most admission-relevant internal links.

import logging

from bs4 import BeautifulSoup

from config import settings
from utils.url_utils import normalize_url, is_same_domain, is_pdf_url, score_url_relevance

logger = logging.getLogger(__name__)


def extract_relevant_links(html: str, base_url: str) -> list[str]:
    """
    Parse all <a href> tags from the page, filter to same-domain non-PDF links,
    score each by admission-relevance keywords, and return the top N URLs.

    Returns a plain list of URL strings (not dicts) sorted by score descending.
    Deduplicates by normalized lowercase URL (strips query params, trailing slashes).
    """
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()  # lowercase normalized keys for dedup
    scored: list[tuple[int, str]] = []  # (score, url)

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        if not href:
            continue

        normalized = normalize_url(href, base_url)
        if normalized is None:
            continue

        # Skip anchor links (fragment-only after normalization)
        if "#" in normalized:
            continue

        # Same domain only
        if not is_same_domain(normalized, base_url):
            continue

        # PDFs are handled by pdf_extractor
        if is_pdf_url(normalized):
            continue

        # Skip self-links
        base_stripped = base_url.rstrip("/").lower()
        norm_stripped = normalized.rstrip("/").lower()
        if norm_stripped == base_stripped:
            continue

        # Deduplicate — use lowercase key so /Page and /page are treated as one
        dedup_key = norm_stripped
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        link_text = a_tag.get_text(strip=True)
        score = score_url_relevance(normalized, link_text)

        # Only keep links with positive relevance
        if score >= 1:
            scored.append((score, normalized))

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    top_n = settings.max_subpages

    # Final dedup pass — belt-and-suspenders in case any duplicates slipped through
    final_seen: set[str] = set()
    results: list[str] = []
    for _, url in scored:
        key = url.rstrip("/").lower()
        if key not in final_seen:
            final_seen.add(key)
            results.append(url)
        if len(results) >= top_n:
            break

    logger.info(
        f"[link_extractor] found {len(results)} relevant links from {base_url} "
        f"(scored {len(scored)} candidates)"
    )
    return results
