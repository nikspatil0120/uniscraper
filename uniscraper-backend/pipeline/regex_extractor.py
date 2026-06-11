# pipeline/regex_extractor.py
# Hybrid regex pre-extraction layer.
# Runs BEFORE the LLM call and extracts high-confidence values for:
#   - IELTS / TOEFL / PTE / Duolingo scores
#   - Tuition fees (with currency)
#   - Program duration
#   - Application deadlines
#   - GPA / grade requirements
#
# Results are passed to the LLM prompt as "known values" so the LLM
# can confirm/enrich rather than miss them entirely.
# Also used as a post-LLM fallback: if LLM returns null for a field
# that regex found, the regex value is used instead.

import re
import logging

logger = logging.getLogger(__name__)

# ── IELTS ─────────────────────────────────────────────────────────────────────
# Matches: "IELTS 6.5", "IELTS: 7.0 overall", "IELTS score of 6.5",
#          "minimum IELTS 6.5", "IELTS Academic 7.0"
_IELTS_OVERALL = re.compile(
    r"IELTS\b[^.]{0,60}?(\d\.\d)\s*(?:overall|minimum|or\s+above|and\s+above)?",
    re.IGNORECASE,
)
# Band/component scores: "no band below 6.0", "minimum 6.0 in each"
_IELTS_BAND = re.compile(
    r"(?:no\s+(?:band|component|skill)\s+(?:below|less\s+than)|"
    r"minimum\s+(?:of\s+)?|at\s+least\s+)(\d\.\d)"
    r"(?:\s+in\s+(?:each|any|all|writing|reading|listening|speaking))?",
    re.IGNORECASE,
)

# ── TOEFL ─────────────────────────────────────────────────────────────────────
_TOEFL_OVERALL = re.compile(
    r"TOEFL\b[^.]{0,100}?(\d{2,3})\s*(?:overall|minimum|iBT|or\s+above)?[^.]{0,50}",
    re.IGNORECASE,
)

# ── PTE ───────────────────────────────────────────────────────────────────────
_PTE_OVERALL = re.compile(
    r"PTE\b[^.]{0,60}?(\d{2,3})\s*(?:overall|minimum|or\s+above)?",
    re.IGNORECASE,
)

# ── Duolingo ──────────────────────────────────────────────────────────────────
_DUOLINGO = re.compile(
    r"Duolingo\b[^.]{0,60}?(\d{3})\s*(?:overall|minimum|or\s+above)?",
    re.IGNORECASE,
)

# ── Tuition fees ──────────────────────────────────────────────────────────────
# Matches: "£28,500 per year", "£28500/year", "GBP 28,500", "28,500 per annum"
# Also: "CAD 32,000", "AUD 45,000", "USD 59,750", "€15,000"
# US format: "$590 per credit hour", "$530/credit hour"
_FEE_PATTERN = re.compile(
    r"(?:"
    r"(£|€|\$|USD|GBP|CAD|AUD|NZD|SGD|HKD|CHF|SEK|NOK|DKK|JPY|CNY|INR)\s*"
    r"([\d,]+(?:\.\d{1,2})?)"
    r"|"
    r"([\d,]+(?:\.\d{1,2})?)\s*(£|€|\$|USD|GBP|CAD|AUD|NZD|SGD|HKD)"
    r")"
    r"(?:\s*(?:per\s+(?:year|annum|semester|credit(?:\s+hour)?|module)|/year|/credit|p\.a\.|annually))?",
    re.IGNORECASE,
)
# Context window around fee mentions — expanded for US universities
_FEE_CONTEXT = re.compile(
    r"(?:tuition|fee|cost|charge|rate|price|credit\s+hour)[^\n]{0,250}",
    re.IGNORECASE,
)
# Domestic/home fee context — look for UK/Home/domestic labels near fee amounts
_DOMESTIC_FEE_CONTEXT = re.compile(
    r"(?:UK|home|domestic|resident|in-state|home\s+student|UK\s+student|home\s+fee|arkansas\s+resident)"
    r"[^\n]{0,200}",
    re.IGNORECASE,
)
# International fee context — expanded for US universities
_INTERNATIONAL_FEE_CONTEXT = re.compile(
    r"(?:international|overseas|non-EU|non-UK|non-resident|out-of-state|foreign\s+student)"
    r"[^\n]{0,200}",
    re.IGNORECASE,
)

# ── Program duration ──────────────────────────────────────────────────────────
_DURATION = re.compile(
    r"(?:"
    r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(year|month|semester|term)s?"
    r"|"
    r"(\d+(?:\.\d+)?)\s*(year|month|semester|term)s?"
    r"|"
    r"(one|two|three|four|five|six|twelve|eighteen|twenty.four)\s*(year|month|semester|term)s?"
    r")"
    r"(?:\s*(?:full.time|part.time|of\s+study|programme|program|course))?",
    re.IGNORECASE,
)

# ── GPA / grade requirements ──────────────────────────────────────────────────
_GPA = re.compile(
    r"(?:GPA|grade\s+point\s+average)[^.]{0,60}?(\d\.\d+)\s*(?:/\s*4\.0|out\s+of\s+4)?",
    re.IGNORECASE,
)
_UK_GRADE = re.compile(
    r"(?:first.class|2:1|upper\s+second|2:2|lower\s+second|third.class)"
    r"(?:\s+honours)?(?:\s+degree)?(?:[^.]{0,40}?(\d+)%)?",
    re.IGNORECASE,
)

# ── Deadlines ─────────────────────────────────────────────────────────────────
_DEADLINE = re.compile(
    r"(?:deadline|closing\s+date|apply\s+by|applications?\s+(?:close|due|by))"
    r"[^.]{0,120}?"
    r"(?:"
    r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
    r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*\d{0,4})"
    r"|"
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{0,4})"
    r")",
    re.IGNORECASE,
)


def _extract_toefl_from_table(text: str) -> str | None:
    """Extract TOEFL requirements from table-formatted text."""
    # Look for Band B TOEFL requirements specifically
    band_b_match = re.search(
        r'Band B[^|]*\|[^|]*\|[^|]*\|[^|]*\|([^|]+)\|([^|]+)\|',
        text, re.IGNORECASE | re.DOTALL
    )
    if band_b_match:
        before_jan = band_b_match.group(1).strip()
        after_jan = band_b_match.group(2).strip()
        if before_jan and after_jan:
            return f"TOEFL iBT: {before_jan} (before Jan 2026) or {after_jan} (after Jan 2026)"
        elif before_jan:
            return f"TOEFL iBT: {before_jan}"
        elif after_jan:
            return f"TOEFL iBT: {after_jan}"
    
    # Fallback to original regex
    return None


def _first_match(pattern: re.Pattern, text: str) -> str | None:
    """Return the full match string of the first hit, or None."""
    m = pattern.search(text)
    return m.group(0).strip() if m else None
def _all_matches(pattern: re.Pattern, text: str, max_results: int = 3) -> list[str]:
    """Return up to max_results unique match strings."""
    seen: set[str] = set()
    results: list[str] = []
    for m in pattern.finditer(text):
        val = m.group(0).strip()
        if val not in seen:
            seen.add(val)
            results.append(val)
        if len(results) >= max_results:
            break
    return results


def _all_deadline_matches(text: str, max_results: int = 3) -> list[str]:
    """Extract just the date portion from deadline matches (not the full context)."""
    seen: set[str] = set()
    results: list[str] = []
    for m in _DEADLINE.finditer(text):
        # Groups 1 and 2 are the actual date captures
        date = (m.group(1) or m.group(2) or "").strip()
        if date and date not in seen:
            seen.add(date)
            results.append(date)
        if len(results) >= max_results:
            break
    return results


def extract_regex_hints_from_sections(text: str, section_headers: list = None) -> dict:
    """
    Run regex patterns against text with section awareness.
    Prioritizes program-specific sections over generic university policies.
    """
    hints: dict = {}
    
    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text) if text else ""
    
    # If we have section headers, try to extract from program-specific sections first
    if section_headers:
        program_sections = []
        generic_sections = []
        
        for header in section_headers:
            # Ensure header is a string
            if not isinstance(header, str):
                continue
            if any(term in header.lower() for term in ["program", "course", "admission", "requirement"]):
                program_sections.append(header)
            else:
                generic_sections.append(header)
        
        # Extract from program sections first, then generic if needed
        for section_group in [program_sections, generic_sections]:
            if section_group:
                section_text = "\n".join([text[text.find(header):text.find(header)+2000] 
                                        for header in section_group if header in text])
                if section_text:
                    section_hints = extract_regex_hints(section_text)
                    # Only use hints we haven't found yet
                    for key, value in section_hints.items():
                        if value and not hints.get(key):
                            hints[key] = value
    
    # Fallback to full text extraction if no section-specific hints found
    if not any(hints.values()):
        hints = extract_regex_hints(text)
    
    return hints


def extract_regex_hints(text: str) -> dict:
    """
    Run all regex patterns against the combined text.
    Returns a dict of field -> extracted string (or None).
    These are used as:
      1. Hints injected into the LLM prompt
      2. Fallback values if LLM returns null for a field
    """
    hints: dict = {}

    # ── IELTS ─────────────────────────────────────────────────────────────────
    ielts_matches = _all_matches(_IELTS_OVERALL, text)
    band_matches = _all_matches(_IELTS_BAND, text)
    if ielts_matches:
        ielts_str = ielts_matches[0]
        # Try to find the band score in the same sentence
        if band_matches:
            ielts_str += f", no band below {band_matches[0].split()[-1]}"
        hints["ielts"] = ielts_str
    else:
        hints["ielts"] = None

    # ── TOEFL ─────────────────────────────────────────────────────────────────
    # Try table extraction first for Trinity-style requirements
    toefl_table = _extract_toefl_from_table(text)
    if not toefl_table:
        toefl_table = _first_match(_TOEFL_OVERALL, text)
    hints["toefl"] = toefl_table

    # ── PTE ───────────────────────────────────────────────────────────────────
    pte = _first_match(_PTE_OVERALL, text)
    hints["pte"] = pte

    # ── Duolingo ──────────────────────────────────────────────────────────────
    duolingo = _first_match(_DUOLINGO, text)
    hints["duolingo"] = duolingo

    # ── Tuition fees ──────────────────────────────────────────────────────────
    # Find fee contexts first, then extract amounts from those contexts
    fee_contexts = _all_matches(_FEE_CONTEXT, text, max_results=8)
    fee_amounts: list[str] = []
    for ctx in fee_contexts:
        for m in _FEE_PATTERN.finditer(ctx):
            val = m.group(0).strip()
            if val not in fee_amounts:
                fee_amounts.append(val)

    # Also scan full text for fee amounts
    if not fee_amounts:
        fee_amounts = _all_matches(_FEE_PATTERN, text, max_results=4)

    hints["fee_amounts"] = fee_amounts if fee_amounts else None

    # Try to separately identify domestic vs international fee amounts
    domestic_fee = None
    international_fee = None

    for ctx in _all_matches(_DOMESTIC_FEE_CONTEXT, text, max_results=3):
        m = _FEE_PATTERN.search(ctx)
        if m:
            domestic_fee = m.group(0).strip()
            break

    for ctx in _all_matches(_INTERNATIONAL_FEE_CONTEXT, text, max_results=3):
        m = _FEE_PATTERN.search(ctx)
        if m:
            international_fee = m.group(0).strip()
            break

    hints["domestic_fee"] = domestic_fee
    hints["international_fee"] = international_fee

    # ── Duration ──────────────────────────────────────────────────────────────
    duration = _first_match(_DURATION, text)
    hints["duration"] = duration

    # ── GPA ───────────────────────────────────────────────────────────────────
    gpa = _first_match(_GPA, text)
    uk_grade = _first_match(_UK_GRADE, text)
    hints["gpa"] = gpa or uk_grade

    # ── Deadlines ─────────────────────────────────────────────────────────────
    deadlines = _all_deadline_matches(text, max_results=3)
    hints["deadlines"] = deadlines if deadlines else None

    # Log what was found
    found = {k: v for k, v in hints.items() if v}
    if found:
        logger.info(f"[regex_extractor] found hints: {list(found.keys())}")
    else:
        logger.info("[regex_extractor] no regex hints found")

    return hints


def apply_regex_fallbacks(result: dict, hints: dict, text: str) -> dict:
    """
    Post-LLM validation: if LLM returned null for a field that regex found,
    fill it in with the regex value.
    Also validates that fee currency+amount are consistent.
    """
    eng = result.get("english_requirements") or {}
    fees = result.get("tuition_fees") or {}

    # IELTS fallback
    if not eng.get("ielts") and hints.get("ielts"):
        logger.info(f"[regex_extractor] IELTS fallback: {hints['ielts']}")
        if isinstance(eng, dict):
            eng["ielts"] = hints["ielts"]
        else:
            eng = {"ielts": hints["ielts"], "toefl": None, "pte": None,
                   "duolingo": None, "notes": None}
        result["english_requirements"] = eng

    # TOEFL fallback with validation
    if not eng.get("toefl") and hints.get("toefl"):
        toefl_value = hints["toefl"]
        # Validation: TOEFL should be at least 10 characters and contain a number
        if len(toefl_value) >= 10 and re.search(r'\d{2,3}', toefl_value):
            logger.info(f"[regex_extractor] TOEFL fallback: {toefl_value}")
            if isinstance(eng, dict):
                eng["toefl"] = toefl_value
            result["english_requirements"] = eng
        else:
            logger.warning(f"[regex_extractor] TOEFL validation failed: '{toefl_value}' (too short or malformed)")
            # Discard the truncated/malformed extraction
            hints["toefl"] = None

    # PTE fallback
    if not eng.get("pte") and hints.get("pte"):
        if isinstance(eng, dict):
            eng["pte"] = hints["pte"]
        result["english_requirements"] = eng

    # Duration fallback
    if not result.get("program_duration") and hints.get("duration"):
        logger.info(f"[regex_extractor] duration fallback: {hints['duration']}")
        result["program_duration"] = hints["duration"]

    # GPA fallback
    if not result.get("min_academic_requirement") and hints.get("gpa"):
        logger.info(f"[regex_extractor] GPA fallback: {hints['gpa']}")
        result["min_academic_requirement"] = hints["gpa"]

    # Deadline fallback
    if not result.get("application_deadlines") and hints.get("deadlines"):
        logger.info(f"[regex_extractor] deadline fallback: {hints['deadlines']}")
        result["application_deadlines"] = "; ".join(hints["deadlines"])

    # Fee fallback: if we have fee amounts but LLM missed them
    if hints.get("fee_amounts"):
        has_fee_data = (
            fees.get("domestic") or fees.get("international") or fees.get("notes")
        )
        if not has_fee_data:
            logger.info(f"[regex_extractor] fee fallback: {hints['fee_amounts']}")
            amounts = hints["fee_amounts"]
            if not isinstance(fees, dict):
                fees = {"domestic": None, "international": None,
                        "currency": None, "notes": None}
            # Use targeted domestic/international if found
            if hints.get("domestic_fee") and not fees.get("domestic"):
                fees["domestic"] = hints["domestic_fee"]
            if hints.get("international_fee") and not fees.get("international"):
                fees["international"] = hints["international_fee"]
            # If still no split, put all amounts in notes
            if not fees.get("domestic") and not fees.get("international"):
                fees["notes"] = "; ".join(amounts)
            result["tuition_fees"] = fees

    # Apply targeted domestic/international even if LLM got some fee data
    if isinstance(fees, dict):
        if hints.get("domestic_fee") and not fees.get("domestic"):
            fees["domestic"] = hints["domestic_fee"]
            result["tuition_fees"] = fees
        if hints.get("international_fee") and not fees.get("international"):
            fees["international"] = hints["international_fee"]
            result["tuition_fees"] = fees

    # Fee currency fallback: if we have amounts but no currency
    if isinstance(fees, dict) and not fees.get("currency") and hints.get("fee_amounts"):
        for amount in hints["fee_amounts"]:
            for symbol, code in [("£", "GBP"), ("€", "EUR"), ("CAD", "CAD"),
                                  ("AUD", "AUD"), ("SGD", "SGD"), ("$", "USD")]:
                if symbol in amount:
                    fees["currency"] = code
                    result["tuition_fees"] = fees
                    break

    return result


def format_hints_for_prompt(hints: dict) -> str:
    """
    Format regex hints as a structured block to inject into the LLM prompt.
    This tells the LLM what values were already found so it can confirm/enrich.
    """
    lines = ["REGEX PRE-EXTRACTION (values found in page text — use these as anchors):"]
    found_any = False

    if hints.get("ielts"):
        lines.append(f"  - IELTS score found: {hints['ielts']}")
        found_any = True
    if hints.get("toefl"):
        lines.append(f"  - TOEFL score found: {hints['toefl']}")
        found_any = True
    if hints.get("pte"):
        lines.append(f"  - PTE score found: {hints['pte']}")
        found_any = True
    if hints.get("duolingo"):
        lines.append(f"  - Duolingo score found: {hints['duolingo']}")
        found_any = True
    if hints.get("fee_amounts"):
        lines.append(f"  - Fee amounts found: {', '.join(hints['fee_amounts'])}")
        found_any = True
    if hints.get("domestic_fee"):
        lines.append(f"  - Domestic/Home fee found: {hints['domestic_fee']}")
        found_any = True
    if hints.get("international_fee"):
        lines.append(f"  - International fee found: {hints['international_fee']}")
        found_any = True
    if hints.get("duration"):
        lines.append(f"  - Duration found: {hints['duration']}")
        found_any = True
    if hints.get("gpa"):
        lines.append(f"  - Grade/GPA found: {hints['gpa']}")
        found_any = True
    if hints.get("deadlines"):
        lines.append(f"  - Deadlines found: {'; '.join(hints['deadlines'])}")
        found_any = True

    if not found_any:
        return ""

    lines.append("Use these as starting points. Extract full context from the text.")
    return "\n".join(lines)
