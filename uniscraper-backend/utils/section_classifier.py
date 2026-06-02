# utils/section_classifier.py
# Classify text content into semantic sections to prevent context contamination
# This helps separate admission requirements from curriculum/progression rules

import re
from typing import Dict, List

# Section classification patterns
ADMISSION_PATTERNS = [
    r"admission\s+requirements?",
    r"entry\s+requirements?", 
    r"eligibility",
    r"how\s+to\s+apply",
    r"application\s+process",
    r"minimum\s+requirements?",
    r"academic\s+requirements?",
]

FEE_PATTERNS = [
    r"tuition\s+fees?",
    r"fees?\s+and\s+funding",
    r"cost\s+of\s+study",
    r"financial\s+information",
    r"fees?\s+structure",
]

ENGLISH_PATTERNS = [
    r"english\s+language\s+requirements?",
    r"language\s+proficiency",
    r"ielts|toefl|pte|duolingo",
    r"english\s+proficiency",
]

CURRICULUM_PATTERNS = [
    r"curriculum",
    r"course\s+structure",
    r"modules?",
    r"subjects?",
    r"year\s+\d+",
    r"semester\s+\d+",
    r"progression",
    r"academic\s+plan",
]

SCHOLARSHIP_PATTERNS = [
    r"scholarships?",
    r"financial\s+aid",
    r"bursaries",
    r"funding\s+opportunities",
]

def classify_text_sections(text: str, source_url: str = "") -> Dict[str, str]:
    """
    Classify text into semantic sections to prevent context contamination.
    Returns dict with section labels as keys and relevant text as values.
    """
    sections = {
        "admissions": "",
        "fees": "",
        "english": "",
        "curriculum": "",
        "scholarships": "",
        "other": ""
    }
    
    # Split into paragraphs for classification
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    for para in paragraphs:
        para_lower = para.lower()
        classified = False
        
        # Check admission patterns
        if any(re.search(pattern, para_lower) for pattern in ADMISSION_PATTERNS):
            sections["admissions"] += para + "\n\n"
            classified = True
        
        # Check fee patterns
        elif any(re.search(pattern, para_lower) for pattern in FEE_PATTERNS):
            sections["fees"] += para + "\n\n"
            classified = True
            
        # Check English patterns
        elif any(re.search(pattern, para_lower) for pattern in ENGLISH_PATTERNS):
            sections["english"] += para + "\n\n"
            classified = True
            
        # Check scholarship patterns
        elif any(re.search(pattern, para_lower) for pattern in SCHOLARSHIP_PATTERNS):
            sections["scholarships"] += para + "\n\n"
            classified = True
            
        # Check curriculum patterns (lower priority for admission extraction)
        elif any(re.search(pattern, para_lower) for pattern in CURRICULUM_PATTERNS):
            sections["curriculum"] += para + "\n\n"
            classified = True
        
        # Unclassified goes to other
        if not classified:
            sections["other"] += para + "\n\n"
    
    # Clean up sections
    for key in sections:
        sections[key] = sections[key].strip()
    
    return sections

def get_admission_focused_text(sections: Dict[str, str]) -> str:
    """
    Combine sections in priority order for admission-focused extraction.
    Excludes curriculum-heavy content that causes confusion.
    """
    # Priority order: admissions first, then supporting info, avoid curriculum
    priority_sections = [
        sections["admissions"],
        sections["english"], 
        sections["fees"],
        sections["scholarships"],
        sections["other"][:2000],  # Limited other content
        # Note: curriculum section excluded to prevent confusion
    ]
    
    combined = []
    for section in priority_sections:
        if section:
            combined.append(section)
    
    return "\n\n".join(combined)