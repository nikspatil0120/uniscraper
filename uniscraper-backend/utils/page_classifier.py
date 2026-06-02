# utils/page_classifier.py
# Classify pages by type to enable field-specific extraction routing

import re
from typing import Dict, List
from urllib.parse import urlparse

# URL pattern classification
URL_PATTERNS = {
    "admissions": [
        r"admission", r"apply", r"entry", r"requirements", r"eligibility",
        r"how-to-apply", r"application"
    ],
    "english_requirements": [
        r"english", r"language", r"ielts", r"toefl", r"proficiency"
    ],
    "tuition": [
        r"fees?", r"tuition", r"cost", r"funding", r"financial", r"price"
    ],
    "scholarships": [
        r"scholarship", r"bursary", r"financial-aid", r"funding"
    ],
    "programme_overview": [
        r"programme", r"program", r"course", r"curriculum", r"overview",
        r"about", r"structure"
    ],
    "curriculum": [
        r"curriculum", r"modules?", r"subjects?", r"syllabus", r"courses?"
    ]
}

# Content pattern classification (fallback for unclear URLs)
CONTENT_PATTERNS = {
    "admissions": [
        r"admission\s+requirements?", r"how\s+to\s+apply", r"entry\s+requirements?",
        r"eligibility", r"application\s+process", r"minimum\s+requirements?"
    ],
    "english_requirements": [
        r"english\s+language\s+requirements?", r"ielts", r"toefl", r"pte",
        r"language\s+proficiency", r"english\s+proficiency"
    ],
    "tuition": [
        r"tuition\s+fees?", r"fees?\s+and\s+funding", r"cost\s+of\s+study",
        r"financial\s+information", r"fees?\s+structure"
    ],
    "scholarships": [
        r"scholarships?", r"financial\s+aid", r"bursaries",
        r"funding\s+opportunities", r"grants?"
    ],
    "programme_overview": [
        r"programme\s+overview", r"about\s+the\s+programme", r"degree\s+structure",
        r"programme\s+duration", r"intake", r"start\s+date"
    ]
}

def classify_page_by_url(url: str) -> str:
    """Classify page type based on URL patterns."""
    url_lower = url.lower()
    
    for page_type, patterns in URL_PATTERNS.items():
        if any(re.search(pattern, url_lower) for pattern in patterns):
            return page_type
    
    return "other"

def classify_page_by_content(content: str, url: str = "") -> str:
    """Classify page type based on content patterns."""
    content_lower = content.lower()
    
    # Score each page type
    scores = {}
    for page_type, patterns in CONTENT_PATTERNS.items():
        score = sum(len(re.findall(pattern, content_lower)) for pattern in patterns)
        scores[page_type] = score
    
    # Return highest scoring type (if score > 0)
    if scores and max(scores.values()) > 0:
        return max(scores, key=scores.get)
    
    # Fallback to URL classification
    return classify_page_by_url(url)

def classify_page(url: str, content: str) -> str:
    """
    Classify a page into one of the standard types.
    Uses both URL and content analysis.
    """
    # Try URL first (faster)
    url_type = classify_page_by_url(url)
    if url_type != "other":
        return url_type
    
    # Fallback to content analysis
    return classify_page_by_content(content, url)

# Field to page type routing
FIELD_TO_PAGE_TYPES = {
    "english_requirements": ["english_requirements", "admissions"],
    "tuition_fees": ["tuition", "admissions"],
    "scholarships": ["scholarships", "tuition", "admissions"],
    "application_deadlines": ["admissions"],
    "min_academic_requirement": ["admissions"],
    "accepted_qualifications": ["admissions"],
    "program_duration": ["programme_overview", "admissions"],
    "intake_months": ["programme_overview", "admissions"],
    "degree_level": ["programme_overview"],
    "other_requirements": ["admissions"],
    "work_experience": ["admissions"]
}