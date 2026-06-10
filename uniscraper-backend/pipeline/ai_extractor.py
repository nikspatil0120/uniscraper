# pipeline/ai_extractor.py
# extract_fields(combined_text, primary_url, context_hint) -> dict
#
# Hybrid extraction: regex pre-extraction → Gemini call (with Ollama fallback) → regex fallbacks.
# Model routing:
#   PRIMARY  — Gemini 2.5 Flash  (best quality, cloud)
#   FALLBACK — Qwen2.5:7b via Ollama  (local, no quota, used on 429/503)

import asyncio
import json
import logging
import random
import re
import time

import httpx

from config import settings
from prompts.extraction_prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils.text_cleaner import clean_html, clean_text_content, truncate_text
from utils.section_classifier import classify_text_sections, get_admission_focused_text
from utils.field_validators import validate_extraction_result
from utils.page_classifier import classify_page, FIELD_TO_PAGE_TYPES
from pipeline.regex_extractor import (
    extract_regex_hints,
    extract_regex_hints_from_sections,
    apply_regex_fallbacks,
    format_hints_for_prompt,
)

logger = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={api_key}"
)

_OLLAMA_URL = "http://localhost:11434/api/chat"
_OLLAMA_MODEL = "qwen2.5:1.5b"  # Fast on CPU (~10-15s), good enough for fallback

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"  # Best Groq model for structured extraction

# ── Gemini rate-limit controls ────────────────────────────────────────────────
# Free tier: 10 RPM, ~4M TPM for Flash. We target max 3 RPM to stay safe.
_GEMINI_SEMAPHORE = asyncio.Semaphore(1)   # Only ONE Gemini call at a time globally
_MIN_CALL_GAP = 20.0                        # 20s between calls = max 3 RPM
_POST_SUCCESS_COOLDOWN = 10.0               # Extra cooldown after every success
_last_call_time: float = 0.0

# Retry delays: 30s → 60s → 120s → 180s → 240s  (aggressive backoff)
_RETRY_DELAYS = [30, 60, 120, 180, 240]
_MAX_RETRIES = len(_RETRY_DELAYS)

# ── Request rate tracker ──────────────────────────────────────────────────────
_MAX_RPM = 3                                # Hard cap: 3 requests per minute
_request_timestamps: list[float] = []       # Rolling window of recent call times


def _enforce_rpm_limit() -> float:
    """
    Returns how many seconds to sleep to stay under _MAX_RPM.
    Prunes timestamps older than 60s from the rolling window.
    """
    now = time.monotonic()
    # Drop timestamps older than 60 seconds
    cutoff = now - 60.0
    while _request_timestamps and _request_timestamps[0] < cutoff:
        _request_timestamps.pop(0)

    if len(_request_timestamps) >= _MAX_RPM:
        # Oldest request in window — sleep until it falls out of the 60s window
        oldest = _request_timestamps[0]
        wait = (oldest + 60.0) - now
        return max(0.0, wait)
    return 0.0

_EXPECTED_KEYS = [
    "university_name", "program_name", "degree_level", "program_duration",
    "intake_months", "application_deadlines", "min_academic_requirement",
    "accepted_qualifications", "english_requirements", "tuition_fees",
    "other_fees", "scholarships", "work_experience", "other_requirements",
    "confidence_notes",
]

_NULL_RESULT = {k: None for k in _EXPECTED_KEYS}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _looks_like_html(text: str) -> bool:
    return bool(re.search(r"<[a-zA-Z][^>]{0,100}>", text))


def _extract_json_from_text(raw: str) -> dict | None:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _parse_llm_response(raw: str) -> dict:
    # Temporary debug for Oxford issues
    if len(raw) < 100:
        print(f"[DEBUG] Very short response ({len(raw)} chars): {raw}")
    elif "ox.ac.uk" in raw or len(raw) > 3000:
        print(f"[DEBUG] Large response ({len(raw)} chars), first 300: {raw[:300]}")
    
    try:
        result = json.loads(raw.strip())
        if isinstance(result, dict):
            for key in _EXPECTED_KEYS:
                if key not in result:
                    result[key] = None
            return result
    except json.JSONDecodeError as e:
        if len(raw) > 1000:  # Only log for substantial responses
            print(f"[DEBUG] JSON error on {len(raw)} char response: {e}")
            print(f"[DEBUG] Response end: ...{raw[-200:]}")

    logger.warning("[ai_extractor] primary JSON parse failed, trying regex extraction")
    result = _extract_json_from_text(raw)
    if result:
        for key in _EXPECTED_KEYS:
            if key not in result:
                result[key] = None
        return result

    logger.error("[ai_extractor] could not parse LLM response as JSON")
    failed = dict(_NULL_RESULT)
    failed["confidence_notes"] = "LLM returned unparseable response"
    return failed


def _safe_fallback(reason: str) -> dict:
    result = dict(_NULL_RESULT)
    result["confidence_notes"] = reason
    return result


# ── API call ──────────────────────────────────────────────────────────────────

async def _call_gemini(user_prompt: str, model: str | None = None) -> str:
    global _last_call_time

    async with _GEMINI_SEMAPHORE:  # Only one Gemini call at a time globally
        # ── RPM rate limiter ──────────────────────────────────────────────────
        rpm_wait = _enforce_rpm_limit()
        if rpm_wait > 0:
            print(f"[rate-limit] RPM cap reached — waiting {rpm_wait:.1f}s")
            await asyncio.sleep(rpm_wait)

        # ── Minimum gap between calls ─────────────────────────────────────────
        now = time.monotonic()
        gap_wait = _MIN_CALL_GAP - (now - _last_call_time)
        if gap_wait > 0:
            await asyncio.sleep(gap_wait)

        _last_call_time = time.monotonic()
        _request_timestamps.append(_last_call_time)

        use_model = model or settings.llm_model
        url = _GEMINI_URL.format(
            model=use_model,
            api_key=settings.gemini_api_key,
        )
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        # ── Post-success cooldown ─────────────────────────────────────────────
        await asyncio.sleep(_POST_SUCCESS_COOLDOWN)

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini response structure: {e} — {str(data)[:300]}")


# ── Ollama (local) caller ─────────────────────────────────────────────────────

async def _call_ollama(user_prompt: str) -> str:
    """
    Call local Ollama with Qwen2.5:7b.
    No rate limiting — runs locally.
    Truncates to 6k chars to keep CPU inference under ~45s.
    """
    MAX_LOCAL_CHARS = 6000
    if len(user_prompt) > MAX_LOCAL_CHARS:
        # Always truncate from the end — the page text is at the bottom
        user_prompt = user_prompt[:MAX_LOCAL_CHARS] + "\n--- END COMBINED PAGE TEXT ---"

    payload = {
        "model": _OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 2000,  # Enough for the JSON schema
        },
    }

    async with httpx.AsyncClient(timeout=45.0) as client:  # 1.5b runs in ~10-15s on CPU
        response = await client.post(_OLLAMA_URL, json=payload)
        response.raise_for_status()
        data = response.json()

    try:
        return data["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Ollama response structure: {e} — {str(data)[:300]}")


async def _is_ollama_available() -> bool:
    """Quick health check — returns True if Ollama is running locally."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            return r.status_code == 200
    except Exception:
        return False


# ── Groq caller ───────────────────────────────────────────────────────────────

async def _call_groq(user_prompt: str) -> str:
    """
    Call Groq API (OpenAI-compatible) with llama-3.3-70b-versatile.
    Fast cloud inference, separate quota from Gemini.
    Truncates to 12k chars — Groq has generous context but we keep it focused.
    """
    MAX_GROQ_CHARS = 12000
    if len(user_prompt) > MAX_GROQ_CHARS:
        user_prompt = user_prompt[:MAX_GROQ_CHARS] + "\n--- END COMBINED PAGE TEXT ---"

    payload = {
        "model": _GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(_GROQ_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Groq response structure: {e} — {str(data)[:300]}")


# ── Public entry point ────────────────────────────────────────────────────────

def calculate_page_relevance_score(page_data: dict, field_group: str) -> int:
    """
    Calculate relevance score for a page based on field group.
    Uses page_type + URL + content keywords with proper negative weights.
    """
    url = page_data.get("url", "").lower()
    page_type = page_data.get("page_type", "other")
    content = page_data.get("content", "").lower()

    score = 50  # base

    # ── LAYER 1: Page type match ──────────────────────────────────────────────
    PAGE_TYPE_SCORES = {
        "english_requirements": {
            "english_requirements": +80, "admissions": +20, "programme_overview": +30,
            "tuition": -20, "scholarships": -20, "curriculum": -30,
        },
        "tuition_fees": {
            "tuition": +80, "programme_overview": +60,  # main page often has the actual fee
            "admissions": +10,
            "english_requirements": -20, "curriculum": -30,
        },
        "application_deadlines": {
            "admissions": +80, "programme_overview": +40,
            "tuition": -10, "english_requirements": -10,
        },
        "program_duration": {
            "programme_overview": +80, "admissions": +20,
            "tuition": -10, "english_requirements": -20,
        },
        "intake_months": {
            "programme_overview": +80, "admissions": +30,
            "tuition": -10, "english_requirements": -20,
        },
    }
    if field_group in PAGE_TYPE_SCORES:
        score += PAGE_TYPE_SCORES[field_group].get(page_type, 0)

    # ── LAYER 2: URL signals ──────────────────────────────────────────────────
    # Positive: specialized sub-pages
    if any(t in url for t in ["language", "english", "ielts", "toefl"]):
        if field_group == "english_requirements":
            score += 40
        else:
            score -= 20
    if any(t in url for t in ["fee", "tuition", "cost", "funding"]):
        if field_group == "tuition_fees":
            score += 40
        else:
            score -= 10
    if any(t in url for t in ["admission", "apply", "entry", "requirement"]):
        if field_group in ("application_deadlines", "program_duration"):
            score += 20
    # Negative: generic university-wide pages
    if any(t in url for t in ["visa", "immigration", "cas", "undergraduate"]):
        score -= 30

    # ── LAYER 3: Content keyword density ─────────────────────────────────────
    FIELD_KEYWORDS = {
        "english_requirements": ["ielts", "toefl", "pte", "duolingo", "english language requirement", "language proficiency"],
        "tuition_fees":         ["tuition fee", "course fee", "£", "$", "aud", "per year", "per annum", "annual fee", "indicative fee"],
        "application_deadlines":["deadline", "closing date", "apply by", "applications close", "applications due", "due date", "key dates", "key application", "applications open"],
        "program_duration":     ["12 months", "24 months", "full-time", "part-time", "duration", "programme length"],
        "intake_months":        ["september intake", "january intake", "october intake", "march intake", "july intake",
                                 "february intake", "start date", "intake", "commence", "commencement",
                                 "march, july", "march and july", "semester 1", "semester 2"],
    }
    if field_group in FIELD_KEYWORDS:
        hits = sum(1 for kw in FIELD_KEYWORDS[field_group] if kw in content)
        score += hits * 20

    return max(0, score)


def build_field_specific_context(pages_data: list, field_group: str, max_chars: int = 5000) -> str:
    """
    Return the most relevant pages for a field group, sorted by score.
    Hard cap: max_chars total. Each page is included in full unless it alone
    exceeds the cap, in which case it is truncated.
    """
    if not pages_data:
        return ""

    scored = sorted(
        [(calculate_page_relevance_score(p, field_group), p) for p in pages_data],
        key=lambda x: x[0],
        reverse=True,
    )

    parts = []
    used = 0
    for score, page_data in scored:
        content = page_data.get("content", "")
        url     = page_data.get("url", "")
        ptype   = page_data.get("page_type", "other")
        header  = f"\n--- {ptype.upper()} (score:{score}) | {url} ---\n"

        available = max_chars - used
        if available <= 500:
            break

        if len(header) + len(content) <= available:
            parts.append(header + content)
            used += len(header) + len(content)
        else:
            # truncate to fit
            keep = available - len(header) - 30
            if keep > 500:
                parts.append(header + content[:keep] + "\n...[truncated]")
                used = max_chars
            break

        if len(parts) >= 3:
            break

    result = "\n".join(parts)
    top_url = scored[0][1].get("url", "")[-50:] if scored else ""
    print(f"[RELEVANCE] {field_group}: {len(parts)} pages, {len(result)} chars  (top: {top_url})")
    return result


async def extract_fields(
    combined_text: str,
    primary_url: str,
    context_hint: str = "",
    pages_data: list = None,
    content_format: str = "html",   # "markdown" (Tier 1/2) or "html" (Tier 3)
) -> dict:
    """
    Hybrid extraction pipeline:
      1. Regex pre-extraction (fast, deterministic)
      2. Smart truncation (keeps relevant paragraphs)
      3. Single Gemini call with regex hints injected into prompt
      4. Regex fallback (fills nulls the LLM missed)

    content_format="markdown": content is already clean fit_markdown from Crawl4AI
      or Firecrawl — skip the clean_html() step (it would corrupt markdown tables).
    content_format="html": legacy path — run clean_html() first.

    Returns dict with all _EXPECTED_KEYS (None where not found).
    """
    # ── Step 1: Clean text ────────────────────────────────────────────────────
    raw_chars = len(combined_text)

    if content_format == "markdown":
        # Already clean — just normalise whitespace, don't strip structure
        cleaned = clean_text_content(combined_text)
        print(f"[AI] Markdown input (Tier 1/2) — skipping clean_html()")
    elif _looks_like_html(combined_text):
        cleaned = clean_html(combined_text)
    else:
        cleaned = clean_text_content(combined_text)

    clean_chars = len(cleaned)

    # ── Step 2: Field-specific context building ──────────────────────────────
    if pages_data:
        # Each field gets its own ranked page selection — 4000 chars each
        # admission_context gets extra budget since it covers intake + deadlines
        program_context  = build_field_specific_context(pages_data, "program_duration",      3000)
        english_context  = build_field_specific_context(pages_data, "english_requirements",  3000)
        fees_context     = build_field_specific_context(pages_data, "tuition_fees",          3000)
        admission_context= build_field_specific_context(pages_data, "application_deadlines", 3000)
        intake_context   = build_field_specific_context(pages_data, "intake_months",         2000)

        # Deduplicate: if intake top page == admission top page, skip the repeat
        intake_section = ""
        if intake_context and intake_context.strip() != admission_context.strip():
            intake_section = "=== INTAKE & DATES ===\n" + intake_context

        extraction_text = "\n\n".join(filter(None, [
            "=== PROGRAM INFORMATION ===\n"  + program_context,
            "=== ENGLISH REQUIREMENTS ===\n" + english_context,
            "=== FEES INFORMATION ===\n"     + fees_context,
            "=== ADMISSION DETAILS ===\n"    + admission_context,
            intake_section,
        ])).strip()

        print(f"[ROUTING] Built targeted context: {len(extraction_text)} chars")
    else:
        sections = classify_text_sections(cleaned, primary_url)
        admission_focused = get_admission_focused_text(sections)
        extraction_text = admission_focused if admission_focused else cleaned
        print(f"[SECTION] Using section classification: {len(extraction_text)} chars")

    # ── Step 3: Page-aware regex pre-extraction ──────────────────────────────
    # Extract section headers for context-aware regex
    section_headers = []
    if "===" in extraction_text:
        section_headers = [line.strip() for line in extraction_text.split('\n') 
                          if line.strip().startswith('===') and line.strip().endswith('===')]
    
    hints = extract_regex_hints_from_sections(extraction_text, section_headers)
    hints_block = format_hints_for_prompt(hints)

    found_hints = [k for k, v in hints.items() if v]
    if found_hints:
        print(f"[REGEX] Pre-extracted: {', '.join(found_hints)}")

    # ── Step 4: Smart truncation ──────────────────────────────────────────────
    truncated = truncate_text(extraction_text, settings.llm_context_limit)
    final_chars = len(truncated)

    print(f"[AI] Raw: {raw_chars:,} -> cleaned: {clean_chars:,} -> "
          f"section-focused: {len(extraction_text):,} -> sending: {final_chars:,} chars to Gemini ({settings.llm_model})")
    logger.info(f"[ai_extractor] {primary_url} — "
                f"raw={raw_chars} clean={clean_chars} focused={len(extraction_text)} sending={final_chars}")

    # ── Step 5: Build prompt with regex hints ─────────────────────────────────
    user_prompt = USER_PROMPT_TEMPLATE.format(
        source_url=primary_url,
        context_hint=context_hint or "Extract all available program information",
        regex_hints=hints_block,
        page_text=truncated,
    )

    # ── Step 6: Hybrid LLM call — Gemini primary, Ollama fallback ────────────
    raw_response = None
    model_used = settings.llm_model
    active_model = settings.llm_model
    consecutive_429s = 0

    for attempt in range(_MAX_RETRIES):
        try:
            raw_response = await _call_gemini(user_prompt, model=active_model)
            model_used = active_model
            logger.info(f"[ai_extractor] Gemini succeeded (attempt {attempt + 1}, model={active_model})")
            break

        except httpx.HTTPStatusError as e:
            status = e.response.status_code

            if status == 429:
                consecutive_429s += 1

            if (status == 429 or status >= 500) and attempt < _MAX_RETRIES - 1:
                # After 2 consecutive 429s, try Groq first (fast cloud, separate quota)
                if consecutive_429s >= 2:
                    logger.warning(f"[ai_extractor] {consecutive_429s} consecutive 429s — trying Groq fallback")
                    print(f"[ai_extractor] Gemini rate-limited ({consecutive_429s}x) - trying Groq/{_GROQ_MODEL}")
                    if settings.groq_api_key:
                        try:
                            raw_response = await _call_groq(user_prompt)
                            model_used = f"groq/{_GROQ_MODEL}"
                            logger.info("[ai_extractor] Groq fallback succeeded")
                            print("[ai_extractor] Groq extraction complete")
                            break
                        except Exception as groq_err:
                            logger.warning(f"[ai_extractor] Groq fallback failed: {type(groq_err).__name__}: {groq_err}")
                            print(f"[ai_extractor] Groq error ({type(groq_err).__name__}) - trying Ollama")
                    else:
                        print("[ai_extractor] No GROQ_API_KEY set — skipping Groq fallback")

                    # Groq failed or not configured — try Ollama next
                    print(f"[ai_extractor] Trying Ollama/{_OLLAMA_MODEL} as secondary fallback")
                    try:
                        if await _is_ollama_available():
                            raw_response = await _call_ollama(user_prompt)
                            model_used = f"ollama/{_OLLAMA_MODEL}"
                            logger.info("[ai_extractor] Ollama fallback succeeded")
                            print("[ai_extractor] Ollama extraction complete")
                            break
                        else:
                            print("[ai_extractor] Ollama not running - falling back to flash-lite")
                    except Exception as ollama_err:
                        logger.warning(f"[ai_extractor] Ollama fallback failed: {type(ollama_err).__name__}: {ollama_err}")
                        print(f"[ai_extractor] Ollama error ({type(ollama_err).__name__}) - falling back to flash-lite")

                # Final cloud fallback: flash-lite (higher RPM limit)
                if status == 429 and attempt >= 1 and active_model == settings.llm_model:
                    active_model = "gemini-2.5-flash-lite"
                    print(f"[ai_extractor] Switching to flash-lite as final fallback")

                delay = _RETRY_DELAYS[attempt] + random.uniform(0, 2)
                print(f"[ai_extractor] HTTP {status} - retry {attempt + 1}/{_MAX_RETRIES} in {delay:.0f}s...")
                logger.warning(f"[ai_extractor] {primary_url} — HTTP {status}, retry {attempt + 1} in {delay:.1f}s...")
                await asyncio.sleep(delay)

            else:
                logger.error(f"[ai_extractor] HTTP {status} after {attempt + 1} attempts")
                fallback = _safe_fallback(f"Gemini extraction failed (HTTP {status})")
                validated_fallback = validate_extraction_result(fallback, extraction_text)
                r = apply_regex_fallbacks(validated_fallback, hints, extraction_text)
                r["_model_used"] = "failed"
                return r

        except (httpx.TimeoutException, httpx.RequestError) as e:
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt] + random.uniform(0, 2)
                logger.warning(f"[ai_extractor] network error: {e}, retry in {delay:.1f}s...")
                await asyncio.sleep(delay)
            else:
                fallback = _safe_fallback("Gemini extraction failed due to network error")
                validated_fallback = validate_extraction_result(fallback, extraction_text)
                r = apply_regex_fallbacks(validated_fallback, hints, extraction_text)
                r["_model_used"] = "failed"
                return r

        except ValueError as e:
            logger.error(f"[ai_extractor] unexpected response: {e}")
            fallback = _safe_fallback("Gemini returned unexpected response structure")
            r = apply_regex_fallbacks(fallback, hints, cleaned)
            r["_model_used"] = "failed"
            return r

    if raw_response is None:
        fallback = _safe_fallback("Gemini extraction failed after all retries")
        validated_fallback = validate_extraction_result(fallback, extraction_text)
        r = apply_regex_fallbacks(validated_fallback, hints, extraction_text)
        r["_model_used"] = "failed"
        return r

    # ── Step 7: Parse LLM response ────────────────────────────────────────────
    result = _parse_llm_response(raw_response)

    # ── Step 8: Apply validation rules ────────────────────────────────────────
    result = validate_extraction_result(result, extraction_text)

    # ── Step 9: Regex fallbacks — fill any nulls the LLM missed ──────────────
    result = apply_regex_fallbacks(result, hints, extraction_text)

    non_null = sum(1 for v in result.values() if v is not None)
    status_str = "success" if non_null > 4 else "sparse"
    print(f"[AI] Extraction {status_str} - {non_null} non-null fields (model: {model_used})")
    logger.info(f"[ai_extractor] {primary_url} — {non_null} non-null fields extracted (model: {model_used})")

    result["_model_used"] = model_used  # internal key, stripped before saving
    return result
