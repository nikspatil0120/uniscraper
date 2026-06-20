# pipeline/gap_analyzer.py
# AI-assisted gap detection and targeted recrawl planner.
#
# Gemini's role:
#   1. Identify which critical fields are missing
#   2. Suggest page types where the data is likely located
#   3. NEVER invent, estimate, or hallucinate data
#
# This keeps extraction grounded in actual university content.

import json
import logging
import re
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

# Critical fields that should trigger recrawl if missing
CRITICAL_FIELDS = [
    "tuition_fees",
    "english_requirements",
    "application_deadlines",
    "min_academic_requirement",
]

# Map field names to suggested page types to search for
FIELD_TO_PAGE_TYPES = {
    "tuition_fees": [
        "fees",
        "tuition-and-fees",
        "tuition-fees",
        "cost-of-attendance",
        "costs",
        "tuition",
        "graduate-tuition",
        "postgraduate-fees",
        "programme-costs",
    ],
    "english_requirements": [
        "english-language-requirements",
        "language-requirements",
        "english-requirements",
        "ielts",
        "toefl",
        "language-proficiency",
        "international-applicants",
        "international-students",
        "entry-requirements",
    ],
    "application_deadlines": [
        "application-deadlines",
        "deadlines",
        "key-dates",
        "important-dates",
        "how-to-apply",
        "apply",
        "admissions",
        "application-process",
    ],
    "min_academic_requirement": [
        "entry-requirements",
        "admission-requirements",
        "admissions-requirements",
        "requirements",
        "eligibility",
        "academic-requirements",
        "how-to-apply",
    ],
    "intake_months": [
        "intake",
        "start-dates",
        "when-to-start",
        "key-dates",
        "admissions",
    ],
    "scholarships": [
        "scholarships",
        "funding",
        "financial-aid",
        "financial-support",
        "bursaries",
        "grants",
    ],
    "program_duration": [
        "overview",
        "programme-overview",
        "course-details",
        "about",
    ],
}

GAP_ANALYSIS_PROMPT = """You are a university admissions analyst helping to identify missing information.

STRICT RULES:
- You are NOT allowed to invent, estimate, or guess any values
- You may ONLY identify what information is missing
- Your role is to suggest where missing information might be found
- NEVER provide actual IELTS scores, tuition fees, deadlines, or requirements

TASK:
Review the extracted data and the pages that were scraped.
Identify which critical fields are missing and suggest where they might be located.

EXTRACTED DATA:
{extracted_json}

PAGES SCRAPED:
{pages_info}

ANALYSIS:
1. Which critical fields are missing from the extraction?
2. Based on the pages already scraped, what page types are missing?
3. Where is this information most likely to be found?

Common examples:
- IELTS scores → "english-language-requirements" or "international-applicants"
- Tuition fees → "tuition-and-fees" or "cost-of-attendance"
- Deadlines → "application-deadlines" or "how-to-apply"
- Entry requirements → "entry-requirements" or "admissions"

Return ONLY valid JSON in this exact format:
{{
  "needs_recrawl": true or false,
  "missing_fields": ["field1", "field2"],
  "suggested_page_types": ["page-type-1", "page-type-2"],
  "reasoning": "Brief explanation of what's missing and where to look"
}}

If all critical fields are present, return:
{{
  "needs_recrawl": false,
  "missing_fields": [],
  "suggested_page_types": [],
  "reasoning": "All critical fields extracted successfully"
}}
"""


async def analyze_missing_fields(
    extracted_data: dict,
    pages_data: list[dict],
    base_url: str,
) -> dict:
    """
    Analyze extraction results to identify missing critical fields
    and suggest where to find them.
    
    Args:
        extracted_data: The extracted field values from first pass
        pages_data: List of pages that were already scraped
        base_url: Base URL for the program (for URL construction)
    
    Returns:
        {
            "needs_recrawl": bool,
            "missing_fields": list[str],
            "suggested_page_types": list[str],
            "reasoning": str
        }
    """
    # Check which critical fields are missing
    missing_critical = []
    for field in CRITICAL_FIELDS:
        value = extracted_data.get(field)
        
        # Check if field is completely missing or empty
        if value is None:
            missing_critical.append(field)
            continue
        
        # For nested objects (english_requirements, tuition_fees), check critical sub-fields
        if isinstance(value, dict):
            if field == "english_requirements":
                # Check if at least one test score is present (not just notes)
                test_scores = [value.get("ielts"), value.get("toefl"), value.get("pte"), value.get("duolingo")]
                if not any(test_scores):  # All test scores are None
                    missing_critical.append(field)
            
            elif field == "tuition_fees":
                # Check if at least one fee amount is present (not just notes)
                fee_amounts = [value.get("domestic"), value.get("international")]
                if not any(fee_amounts):  # Both fees are None
                    missing_critical.append(field)
            
            else:
                # For other dicts, check if all values are None
                if not any(v for v in value.values() if v is not None):
                    missing_critical.append(field)
    
    if not missing_critical:
        logger.info("[gap_analyzer] All critical fields present, no recrawl needed")
        return {
            "needs_recrawl": False,
            "missing_fields": [],
            "suggested_page_types": [],
            "reasoning": "All critical fields extracted successfully"
        }
    
    logger.info(f"[gap_analyzer] Missing critical fields: {missing_critical}")
    
    # Get already-scraped page types
    scraped_page_types = set()
    for page in pages_data:
        page_url = page.get("url", "")
        # Extract page type from URL path
        path_parts = page_url.rstrip("/").split("/")
        if path_parts:
            last_part = path_parts[-1].lower()
            scraped_page_types.add(last_part)
        
        # Also check classified page_type
        if page.get("page_type"):
            scraped_page_types.add(page["page_type"].lower())
    
    # Build suggested page types based on missing fields
    suggested = []
    for field in missing_critical:
        page_types = FIELD_TO_PAGE_TYPES.get(field, [])
        for pt in page_types:
            # Only suggest if we haven't already scraped a similar page
            if not any(pt in scraped for scraped in scraped_page_types):
                if pt not in suggested:
                    suggested.append(pt)
    
    # If using Gemini API, get AI reasoning (optional enhancement)
    reasoning = _build_simple_reasoning(missing_critical, suggested)
    
    result = {
        "needs_recrawl": len(suggested) > 0,
        "missing_fields": missing_critical,
        "suggested_page_types": suggested[:5],  # Limit to top 5 suggestions
        "reasoning": reasoning
    }
    
    logger.info(f"[gap_analyzer] Suggested page types: {result['suggested_page_types']}")
    return result


def _build_simple_reasoning(missing_fields: list[str], suggested_types: list[str]) -> str:
    """Build a simple reasoning string without calling LLM."""
    if not missing_fields:
        return "All critical fields extracted successfully"
    
    field_str = ", ".join(missing_fields)
    type_str = ", ".join(suggested_types[:3])
    
    return (
        f"Missing {len(missing_fields)} critical field(s): {field_str}. "
        f"Suggested pages to crawl: {type_str}"
    )


async def analyze_missing_fields_with_ai(
    extracted_data: dict,
    pages_data: list[dict],
) -> Optional[dict]:
    """
    Use Gemini to analyze missing fields and suggest page types.
    This is an optional enhancement over the rule-based approach.
    
    Returns None if API call fails, falling back to rule-based analysis.
    """
    if not settings.gemini_api_key:
        logger.warning("[gap_analyzer] No Gemini API key, skipping AI analysis")
        return None
    
    # Prepare extracted data summary
    extracted_json = json.dumps({
        k: v for k, v in extracted_data.items()
        if k in CRITICAL_FIELDS or k in ["university_name", "program_name"]
    }, indent=2)
    
    # Prepare pages info
    pages_info = "\n".join([
        f"- {page.get('url', 'unknown')} ({page.get('page_type', 'unknown')})"
        for page in pages_data[:10]  # Limit to first 10 pages
    ])
    
    prompt = GAP_ANALYSIS_PROMPT.format(
        extracted_json=extracted_json,
        pages_info=pages_info
    )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash-exp:generateContent?key={settings.gemini_api_key}"
            )
            
            response = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 500,
                    }
                }
            )
            
            if response.status_code != 200:
                logger.warning(f"[gap_analyzer] Gemini API error: {response.status_code}")
                return None
            
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Extract JSON from response
            text = re.sub(r"```(?:json)?\s*", "", text).strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                logger.info(f"[gap_analyzer] AI analysis complete: {result.get('reasoning', '')}")
                return result
            
            return None
            
    except Exception as exc:
        logger.warning(f"[gap_analyzer] AI analysis failed: {exc}")
        return None


# ── URL Construction helpers ──────────────────────────────────────────────────

def build_candidate_urls(base_url: str, page_types: list[str]) -> list[str]:
    """
    Generate candidate URLs for suggested page types.
    
    Example:
        base_url = "https://example.com/programs/mba"
        page_types = ["fees", "english-requirements"]
        
        Returns:
            [
                "https://example.com/programs/mba/fees",
                "https://example.com/programs/mba/fees/",
                "https://example.com/fees",
                "https://example.com/programs/mba/english-requirements",
                ...
            ]
    """
    from urllib.parse import urljoin, urlparse
    
    parsed = urlparse(base_url)
    base_path = parsed.path.rstrip("/")
    domain = f"{parsed.scheme}://{parsed.netloc}"
    
    candidates = []
    
    for page_type in page_types:
        # Try variations at different path levels
        # 1. Append to current path
        candidates.append(urljoin(base_url, page_type))
        candidates.append(urljoin(base_url + "/", page_type))
        
        # 2. At parent level (go up one directory)
        if "/" in base_path:
            parent_path = "/".join(base_path.split("/")[:-1])
            candidates.append(f"{domain}{parent_path}/{page_type}")
        
        # 3. At domain root
        candidates.append(f"{domain}/{page_type}")
        
        # 4. Common variations
        if not page_type.endswith(".html"):
            candidates.append(urljoin(base_url, f"{page_type}.html"))
    
    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for url in candidates:
        normalized = url.rstrip("/")
        if normalized not in seen:
            seen.add(normalized)
            unique_candidates.append(url)
    
    return unique_candidates[:20]  # Limit to 20 candidates
