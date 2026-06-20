# utils/text_cleaner.py
# clean_html(html)          — strip noise tags, extract main content, return plain text
# clean_text_content(text)  — deep-clean plain text, prioritise admission-relevant sections
# truncate_text(text, max)  — smart truncation that keeps relevant sections first
# combine_texts(parts)      — join multiple page texts with section headers

import re
from bs4 import BeautifulSoup

# ── HTML stripping ────────────────────────────────────────────────────────────

_REMOVE_TAGS = [
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", "iframe", "svg", "form", "meta", "link",
    # NOTE: do NOT remove "button" — accordion toggles wrap section headings
    # NOTE: do NOT remove divs with hidden/aria-hidden — they contain accordion content
]

_CONTENT_SELECTORS = [
    "main", "article", '[role="main"]',
    ".main-content", "#main-content", ".content", "#content", "body",
]

_JUNK_LINE_RE = re.compile(r"^[\W\d]+$")


def clean_html(html: str) -> str:
    """
    Parse HTML, strip noise elements, extract main content area,
    return clean readable text suitable for further processing.
    Explicitly reveals accordion/hidden content so scores in collapsed
    sections are not lost.
    """
    soup = BeautifulSoup(html, "lxml")

    # ── Reveal hidden accordion / tab content before stripping ───────────────
    # Many university sites hide IELTS/fee tables inside collapsed accordions.
    # Remove the `hidden` attribute so get_text() captures the content.
    for tag in soup.find_all(attrs={"hidden": True}):
        del tag["hidden"]
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        del tag["aria-hidden"]
    # Also remove display:none inline styles
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        del tag["style"]

    for tag_name in _REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove button tags but keep their text (accordion headings)
    for btn in soup.find_all("button"):
        btn.replace_with(btn.get_text(separator=" "))

    # ── Special handling for tables to preserve structure ────────────────────
    # Convert tables to formatted text before general text extraction
    # This helps LLMs understand cost breakdowns and data in tabular format
    for table in soup.find_all("table"):
        table_text = _table_to_text(table)
        table.replace_with(f"\n\n{table_text}\n\n")

    content_el = None
    for selector in _CONTENT_SELECTORS:
        content_el = soup.select_one(selector)
        if content_el:
            break

    raw_text = content_el.get_text(separator="\n") if content_el else soup.get_text(separator="\n")
    return clean_text_content(raw_text)


def _table_to_text(table) -> str:
    """
    Convert HTML table to readable plain text format.
    Preserves column structure with pipe separators.
    
    Example output:
    | Tuition & Fees | Books | Room & Board | Total |
    | 7,556 | 1,250 | 13,190 | 28,356 |
    """
    rows = []
    
    # Get all rows from thead and tbody
    for row in table.find_all("tr"):
        cells = []
        for cell in row.find_all(["th", "td"]):
            # Get cell text and clean it
            cell_text = cell.get_text(separator=" ", strip=True)
            # Collapse multiple spaces
            cell_text = " ".join(cell_text.split())
            cells.append(cell_text)
        
        if cells:  # Only add non-empty rows
            # Join cells with pipe separator
            rows.append("| " + " | ".join(cells) + " |")
    
    return "\n".join(rows) if rows else ""


# ── Markdown noise stripping ─────────────────────────────────────────────────

# Melbourne and similar sites embed large SVG logos as data: URIs in markdown.
# Pattern: [![alt text](data:image/...very long...)](url)
# The SVG blob can span multiple lines and be 10-50KB.
# We need to strip these before any text processing.

# Matches the inner image part: ![alt](data:...)
_DATA_URI_IMG_RE = re.compile(
    r'!\[[^\]]*\]\(data:[^)]{20,}\)',
    re.DOTALL,
)

# Matches linked images wrapping data URIs: [![alt](data:...)](url)
_LINKED_DATA_URI_RE = re.compile(
    r'\[!\[[^\]]*\]\(data:[^\)]{20,}\)\]\([^\)]*\)',
    re.DOTALL,
)

# URL-encoded SVG blobs appearing directly in text/links (%3csvg...)
_ENCODED_SVG_RE = re.compile(
    r'%3[cC]svg[A-Za-z0-9%._~:/?#\[\]@!$&\'()*+,;=\-]{30,}',
    re.DOTALL,
)

# Bare data: URIs (in case they appear outside markdown image syntax)
_DATA_URI_BARE_RE = re.compile(
    r'data:image/[^\s\)"\'>]{20,}',
    re.DOTALL,
)


def strip_markdown_noise(text: str) -> str:
    """
    Remove noise from Firecrawl/Crawl4AI markdown before sending to the LLM:
      - Linked data: URI images: [![alt](data:image/...)](url)
      - Inline data: URI images: ![alt](data:image/...)
      - URL-encoded SVG blobs in links/text
      - Bare data: URI references
    Leaves all real text, links, and tables intact.
    """
    # The Melbourne SVG blob is a single-line URL-encoded string inside
    # a markdown image link. Strip any markdown link/image whose URL starts
    # with data: — match up to the closing paren of the URL.
    # Use a non-greedy match to handle cases where multiple appear on one line.
    text = re.sub(r'!\[[^\]]*\]\(data:[^)]*\)', '', text)
    # Also strip linked images with data URIs: [![...](data:...)](url)
    text = re.sub(r'\[!\[[^\]]*\]\(data:[^)]*\)\]\([^)]*\)', '', text)
    # Strip any remaining bare data: URIs (fallback)
    text = re.sub(r'data:image/\S{10,}', '[image]', text)
    # Strip URL-encoded SVG fragments (%3csvg or %3Csvg) and everything after
    # them until whitespace — these appear as part of longer URL strings
    text = re.sub(r'%3[cC]svg\S{20,}', '', text)
    # Collapse blank lines created by stripping
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


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

    - Strips inline data: URI images and SVG blobs (Firecrawl/Crawl4AI noise)
    - Removes cookie/privacy/accessibility boilerplate
    - Removes repeated navigation items
    - Removes lines shorter than 4 chars
    - Collapses excessive whitespace and blank lines
    - Deduplicates identical consecutive lines
    - Preserves lines containing admission-relevant keywords
    """
    # Strip data URI images / SVG blobs first — they inflate word counts massively
    text = strip_markdown_noise(text)
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
    r"IELTS|TOEFL|PTE|duolingo|english\s+language|"
    r"deadline|closing\s+date|apply\s+by|"
    r"duration|full.time|part.time|"
    r"GPA|grade\s+point|first.class|2:1|upper\s+second|"
    r"international\s+student|domestic\s+student|home\s+student|"
    r"per\s+year|per\s+annum|annually|overall\s+score)",
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
