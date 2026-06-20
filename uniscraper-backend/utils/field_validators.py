# utils/field_validators.py
# Validate extracted fields for semantic correctness
# Catches common extraction errors like mixing curriculum with admission requirements

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def validate_program_duration(duration: str, degree_level: str) -> tuple[str, Optional[str]]:
    """
    Validate program duration makes sense for the degree level.
    Returns (validated_duration, confidence_note)
    """
    if not duration:
        return duration, None
    
    # Handle case where duration might not be a string
    if not isinstance(duration, str):
        duration = str(duration)
        
    duration_lower = duration.lower()
    
    # Extract numeric duration
    years_match = re.search(r'(\d+(?:\.\d+)?)\s*years?', duration_lower)
    months_match = re.search(r'(\d+)\s*months?', duration_lower)
    
    if years_match:
        years = float(years_match.group(1))
    elif months_match:
        years = float(months_match.group(1)) / 12
    else:
        return duration, "Duration format unclear - could not extract numeric value"
    
    # Validation rules by degree level
    if degree_level and "undergraduate" in degree_level.lower():
        if years < 2.5:
            return duration, f"Duration of {years} years seems short for undergraduate degree - may be partial program or misclassified curriculum requirement"
        elif years > 6:
            return duration, f"Duration of {years} years seems long for undergraduate degree"
    
    elif degree_level and any(level in degree_level.lower() for level in ["phd", "doctor", "doctorate", "dphil"]):
        if years < 2:
            logger.warning(f"[validator] Nulling duration '{duration}' — {years} years is too short for PhD (min 2)")
            return None, f"Duration of {years} years is implausible for a PhD — likely hallucinated"
        elif years > 10:
            return duration, f"Duration of {years} years seems very long for a PhD"

    elif degree_level and any(level in degree_level.lower() for level in ["master", "postgraduate", "msc", "ma ", "meng", "mres"]):
        if years < 0.5:
            return duration, f"Duration of {years} years seems very short for master's degree"
        elif years > 3:
            return duration, f"Duration of {years} years seems long for master's degree"
    
    return duration, None

def validate_gpa_requirement(gpa: str, context_text: str = "") -> tuple[str, Optional[str]]:
    """
    Validate GPA requirement isn't confused with internal progression requirements.
    Returns (validated_gpa, confidence_note)
    """
    if not gpa:
        return gpa, None
    
    # Handle case where gpa might not be a string
    if not isinstance(gpa, str):
        gpa = str(gpa)
    
    gpa_lower = gpa.lower()
    
    # Handle context_text being non-string
    if not isinstance(context_text, str):
        context_text = str(context_text) if context_text else ""
    context_lower = context_text.lower()
    
    # Red flags that suggest this is NOT an admission requirement
    internal_flags = [
        "in-program", "internal", "progression", "dissertation", 
        "thesis", "honours", "graduation", "maintain", "continue"
    ]
    
    admission_flags = [
        "admission", "entry", "minimum", "required", "eligibility", "apply"
    ]
    
    # Check context for red flags
    internal_score = sum(1 for flag in internal_flags if flag in context_lower)
    admission_score = sum(1 for flag in admission_flags if flag in context_lower)
    
    if internal_score > admission_score:
        return gpa, f"GPA requirement may be for internal progression rather than admission - found in context with: {', '.join([f for f in internal_flags if f in context_lower])}"
    
    return gpa, None

def validate_english_requirements(english_req: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[str]]:
    """
    Validate English requirements are reasonable and complete.
    Returns (validated_requirements, confidence_note)
    """
    if not english_req:
        return english_req, None
    
    issues = []
    
    # Check IELTS scores
    ielts = english_req.get("ielts", "")
    if ielts:
        ielts_match = re.search(r'(\d+\.?\d*)', ielts)
        if ielts_match:
            score = float(ielts_match.group(1))
            if score < 4.0 or score > 9.0:
                issues.append(f"IELTS score {score} outside normal range (4.0-9.0)")
    
    # Check TOEFL scores  
    toefl = english_req.get("toefl", "")
    if toefl:
        toefl_match = re.search(r'(\d+)', toefl)
        if toefl_match:
            score = int(toefl_match.group(1))
            if score < 30 or score > 120:
                issues.append(f"TOEFL score {score} outside normal iBT range (30-120)")
    
    confidence_note = "; ".join(issues) if issues else None
    return english_req, confidence_note

def validate_extraction_result(result: Dict[str, Any], source_text: str = "") -> Dict[str, Any]:
    """
    Apply all validation rules to an extraction result.
    Updates confidence_notes with validation warnings.
    """
    validation_notes = []
    
    # Validate duration
    if result.get("program_duration"):
        validated_duration, duration_note = validate_program_duration(
            result["program_duration"], 
            result.get("degree_level", "")
        )
        result["program_duration"] = validated_duration
        if duration_note:
            validation_notes.append(f"Duration: {duration_note}")
    
    # Validate GPA
    if result.get("min_academic_requirement"):
        validated_gpa, gpa_note = validate_gpa_requirement(
            result["min_academic_requirement"],
            source_text
        )
        result["min_academic_requirement"] = validated_gpa
        if gpa_note:
            validation_notes.append(f"Academic requirement: {gpa_note}")
    
    # Validate English requirements
    if result.get("english_requirements"):
        validated_english, english_note = validate_english_requirements(
            result["english_requirements"]
        )
        result["english_requirements"] = validated_english
        if english_note:
            validation_notes.append(f"English requirements: {english_note}")
    
    # Append validation notes to existing confidence notes
    if validation_notes:
        existing_notes = result.get("confidence_notes", "")
        validation_text = "Validation warnings: " + "; ".join(validation_notes)
        
        if existing_notes:
            result["confidence_notes"] = f"{existing_notes}. {validation_text}"
        else:
            result["confidence_notes"] = validation_text
    
    return result