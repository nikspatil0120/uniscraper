# utils/text_cleaner.py
# clean_html(html)          — strip noise tags, extract main content, return plain text
# clean_text_content(text)  — deep-clean plain text, prioritise admission-relevant sections
# truncate_text(text, max)  — smart truncation that keeps relevant sections first
# combine_texts(parts)      — join multiple page texts with section headers

import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── HTML stripping ────────────────────────────────────────────────────────────

_JUNK_LINE_RE = re.compile(r"^[\W\d]+$")


def clean_html(html: str) -> str:
    """
    Parse HTML, strip noise elements, extract main content area,
    return clean readable text suitable for further processing.
    Uses a word-count based approach to find the best content container.
    """
    soup = BeautifulSoup(html, "lxml")

    # ── Step 1: Remove noise tags entirely ───────────────────────────────────
    for tag in soup.find_all([
        "script", "style", "noscript", "nav", "footer", 
        "header", "aside", "iframe", "svg", "form", 
        "button", "meta", "link", "figure", "picture"
    ]):
        tag.decompose()

    # ── Step 2: Try content selectors in order, use first that gives > 200 words ──
    selectors = [
        "main", "article", '[role="main"]',
        ".main-content", "#main-content",
        ".content", "#content", "#main",
        ".page-content", ".content-wrapper",
        ".programme-content", "#content-inner",
        ".col-content", ".entry-content",
        "section.content", "div.content",
        "section", "div#wrapper",
    ]

    best_text = ""
    matched_selector = None
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n")
            words = len(text.split())
            if words > 200:
                best_text = text
                matched_selector = selector
                logger.debug(f"[text_cleaner] Matched selector '{selector}' with {words} words")
                break

    # ── Step 3: If no selector worked, fall back to full body ────────────────
    if len(best_text.split()) < 200:
        logger.warning(f"[text_cleaner] No selector found >200 words, using body fallback")
        body = soup.find("body")
        if body:
            best_text = body.get_text(separator="\n")
        else:
            best_text = soup.get_text(separator="\n")

    # ── Step 4: Clean the text ────────────────────────────────────────────────
    lines = []
    for line in best_text.split("\n"):
        line = line.strip()
        # Skip very short lines
        if len(line) < 3:
            continue
        # Skip lines that are just numbers/punctuation
        if line.replace(".", "").replace(",", "").replace("-", "").replace(" ", "").isdigit():
            continue
        lines.append(line)

    # Collapse multiple blank lines
    result = []
    blank_count = 0
    for line in lines:
        if not line:
            blank_count += 1
            if blank_count <= 1:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)

    final_text = "\n".join(result)
    logger.debug(f"[text_cleaner] Final output: {len(final_text)} chars, {len(final_text.split())} words")
    return final_text


# ── Plain-text deep cleaner ───────────────────────────────────────────────────

# Patterns for junk lines to drop entirely
_COOKIE_RE = re.compile(
    r"(cookie|privacy policy|accept all|we use cookies|gdpr|consent|"
    r"accessibility|skip to (main|content|navigation)|back to top|"
    r"share this|print this|email this|follow us|subscribe|newsletter|"
    r"all rights reserved|copyright ©|terms of use|site map|sitemap)",
    re.IGNORECASE,
)

# Keywords that signal admission-relevant content — lines/paragraphs containing
# these are kept even if they'd otherwise be trimmed
_RELEVANT_KW_RE = re.compile(
    r"(admission|admissions|requirement|eligibility|tuition|fee|ielts|toefl|"
    r"pte|duolingo|english|intake|deadline|scholarship|gpa|grade|degree|"
    r"programme|program|apply|application|entry|qualification|academic|"
    r"international|domestic|cost|stipend|funding|fellowship|gre|gmat|"
    r"language|proficiency|band|score|minimum|maximum|credit|semester|"
    r"duration|full.time|part.time|campus|start date|closing date)",
    re.IGNORECASE,
)

# Repeated navigation-style short phrases (≤5 words, all title-case or all caps)
_NAV_LINE_RE = re.compile(r"^([A-Z][a-z]+ ?){1,5}$|^[A-Z\s]{3,40}$")


def clean_text_content(text: str) -> str:
    """
    Deep-clean plain text extracted from a web page.

    - Removes cookie/privacy/accessibility boilerplate
    - Removes repeated navigation items
    - Removes lines shorter than 4 chars
    - Collapses excessive whitespace and blank lines
    - Deduplicates identical consecutive lines
    - Preserves lines containing admission-relevant keywords
    """
    lines = text.splitlines()
    cleaned: list[str] = []
    seen: set[str] = set()
    blank_run = 0

    for raw_line in lines:
        line = raw_line.strip()

        # Always drop empty / very short lines (but allow one blank separator)
        if len(line) < 4:
            blank_run += 1
            if blank_run == 1:
                cleaned.append("")
            continue
        blank_run = 0

        # Drop junk-only lines (punctuation / digits only)
        if _JUNK_LINE_RE.match(line):
            continue

        # Drop cookie/privacy/accessibility boilerplate
        if _COOKIE_RE.search(line) and not _RELEVANT_KW_RE.search(line):
            continue

        # Drop repeated navigation-style lines (unless admission-relevant)
        if _NAV_LINE_RE.match(line) and len(line) < 50 and not _RELEVANT_KW_RE.search(line):
            continue

        # Deduplicate identical consecutive lines
        if line in seen and not _RELEVANT_KW_RE.search(line):
            continue
        seen.add(line)

        cleaned.append(line)

    # Collapse 3+ consecutive blank lines → 1
    result: list[str] = []
    blanks = 0
    for line in cleaned:
        if line == "":
            blanks += 1
            if blanks <= 1:
                result.append(line)
        else:
            blanks = 0
            result.append(line)

    return "\n".join(result).strip()


# ── Smart truncation ──────────────────────────────────────────────────────────

# High-priority keywords — paragraphs containing these are kept first
_HIGH_PRIORITY_KW = re.compile(
    r"(tuition|fee|cost|£|€|\$|USD|GBP|CAD|AUD|"
    r"international\s+fee|domestic\s+fee|home\s+fee|overseas\s+fee|"
    r"per\s+year|per\s+annum|annually|"
    r"IELTS|TOEFL|PTE|duolingo|english\s+language|"
    r"deadline|closing\s+date|apply\s+by|"
    r"duration|full.time|part.time|"
    r"GPA|grade\s+point|first.class|2:1|upper\s+second|"
    r"international\s+student|domestic\s+student|home\s+student|"
    r"overall\s+score)",
    re.IGNORECASE,
)

# Medium-priority keywords
_MED_PRIORITY_KW = re.compile(
    r"(admission|requirement|eligibility|intake|scholarship|"
    r"entry|qualification|academic|international|domestic|"
    r"programme|program|apply|application)",
    re.IGNORECASE,
)


def truncate_text(text: str, max_chars: int = 12000) -> str:
    """
    Truncate text to max_chars, prioritising admission-relevant paragraphs.

    Scoring:
    - High-priority keywords (fees, scores, deadlines, duration): +3 each
    - Medium-priority keywords (admission, requirements): +1 each
    - Paragraphs are sorted by score, then re-ordered by original position.
    """
    if len(text) <= max_chars:
        return text

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    scored: list[tuple[int, int, str]] = []
    for idx, para in enumerate(paragraphs):
        score = (
            len(_HIGH_PRIORITY_KW.findall(para)) * 3
            + len(_MED_PRIORITY_KW.findall(para)) * 1
        )
        scored.append((score, idx, para))

    # Sort: high-score first, then by original order for ties
    scored.sort(key=lambda x: (-x[0], x[1]))

    budget = max_chars - 80
    selected: list[tuple[int, str]] = []
    used = 0
    for score, idx, para in scored:
        cost = len(para) + 2
        if used + cost <= budget:
            selected.append((idx, para))
            used += cost
        if used >= budget:
            break

    if not selected:
        return text[:8000] + "\n\n[...content truncated...]\n\n" + text[-4000:]

    # Re-sort by original order so text reads naturally
    selected.sort(key=lambda x: x[0])
    result = "\n\n".join(p for _, p in selected)

    if len(result) < len(text) * 0.9:
        result += "\n\n[...content truncated for token efficiency...]"

    return result


# ── Multi-source combiner ─────────────────────────────────────────────────────

def combine_texts(parts: list[tuple[str, str]]) -> str:
    """
    Combine multiple (label, text) pairs into one string with clear section headers.
    Each part is already cleaned plain text.

    Args:
        parts: list of (source_label, cleaned_text) tuples

    Returns:
        Single combined string ready for LLM input.
    """
    sections: list[str] = []
    for label, text in parts:
        if text and text.strip():
            sections.append(f"=== SOURCE: {label} ===\n{text.strip()}")
    return "\n\n".join(sections)
