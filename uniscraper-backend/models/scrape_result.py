# models/scrape_result.py
# Canonical Pydantic output schema for a completed scrape.
# All 20+ fields are typed. Most are Optional[str] = None.
# Required fields: scrape_id, status, created_at, source_urls.
# Includes nested sub-models: EnglishRequirements, TuitionFees.
# field_sources tracks which URL each extracted field came from.

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class EnglishRequirements(BaseModel):
    """Nested model for English language test score requirements."""
    ielts: Optional[str] = None
    toefl: Optional[str] = None
    pte: Optional[str] = None
    duolingo: Optional[str] = None
    notes: Optional[str] = None


class TuitionFees(BaseModel):
    """Nested model for tuition fee breakdown."""
    domestic: Optional[str] = None
    international: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None


class ScrapeResult(BaseModel):
    """Full output schema for a university program scrape."""

    # Required fields
    scrape_id: str
    status: str  # "processing" | "success" | "partial" | "failed"
    created_at: datetime
    source_urls: List[str]

    # University / program identity
    university_name: Optional[str] = None
    program_name: Optional[str] = None
    degree_level: Optional[str] = None
    program_duration: Optional[str] = None

    # Intake and deadlines
    intake_months: Optional[List[str]] = None
    application_deadlines: Optional[str] = None

    # Academic requirements
    min_academic_requirement: Optional[str] = None
    accepted_qualifications: Optional[str] = None

    # Language requirements
    english_requirements: Optional[EnglishRequirements] = None

    # Fees
    tuition_fees: Optional[TuitionFees] = None
    other_fees: Optional[str] = None

    # Funding and extras
    scholarships: Optional[str] = None
    work_experience: Optional[str] = None
    other_requirements: Optional[str] = None

    # Metadata
    confidence_notes: Optional[str] = None
    field_sources: Optional[Dict[str, str]] = None  # field_name -> source_url
