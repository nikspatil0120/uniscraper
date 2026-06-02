# utils/csv_builder.py
# build_csv(docs: list[dict]) -> str
# Flattens MongoDB scrape documents into a CSV string.
# Nested english_requirements and tuition_fees are expanded into flat columns.

import csv
from io import StringIO
from datetime import datetime

HEADERS = [
    "scrape_id",
    "university_name",
    "program_name",
    "degree_level",
    "program_duration",
    "intake_months",
    "application_deadlines",
    "min_academic_requirement",
    "accepted_qualifications",
    "english_ielts",
    "english_toefl",
    "english_pte",
    "english_duolingo",
    "english_notes",
    "tuition_international",
    "tuition_domestic",
    "tuition_currency",
    "tuition_notes",
    "other_fees",
    "scholarships",
    "work_experience",
    "other_requirements",
    "confidence_notes",
    "status",
    "source_urls",
    "created_at",
]


def _safe(value) -> str:
    """Convert any value to a safe CSV string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def build_csv(docs: list[dict]) -> str:
    """
    Convert a list of MongoDB scrape result dicts into a CSV string.
    Each document becomes one row. Nested sub-documents are flattened.
    Returns the complete CSV as a string (including header row).
    """
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=HEADERS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()

    for doc in docs:
        # Extract nested english_requirements
        eng = doc.get("english_requirements") or {}
        if hasattr(eng, "model_dump"):
            eng = eng.model_dump()

        # Extract nested tuition_fees
        fees = doc.get("tuition_fees") or {}
        if hasattr(fees, "model_dump"):
            fees = fees.model_dump()

        # source_urls: join with " | "
        source_urls = doc.get("source_urls") or []
        if isinstance(source_urls, list):
            source_urls_str = " | ".join(str(u) for u in source_urls)
        else:
            source_urls_str = str(source_urls)

        row = {
            "scrape_id":                _safe(doc.get("scrape_id")),
            "university_name":          _safe(doc.get("university_name")),
            "program_name":             _safe(doc.get("program_name")),
            "degree_level":             _safe(doc.get("degree_level")),
            "program_duration":         _safe(doc.get("program_duration")),
            "intake_months":            _safe(doc.get("intake_months")),
            "application_deadlines":    _safe(doc.get("application_deadlines")),
            "min_academic_requirement": _safe(doc.get("min_academic_requirement")),
            "accepted_qualifications":  _safe(doc.get("accepted_qualifications")),
            "english_ielts":            _safe(eng.get("ielts")),
            "english_toefl":            _safe(eng.get("toefl")),
            "english_pte":              _safe(eng.get("pte")),
            "english_duolingo":         _safe(eng.get("duolingo")),
            "english_notes":            _safe(eng.get("notes")),
            "tuition_international":    _safe(fees.get("international")),
            "tuition_domestic":         _safe(fees.get("domestic")),
            "tuition_currency":         _safe(fees.get("currency")),
            "tuition_notes":            _safe(fees.get("notes")),
            "other_fees":               _safe(doc.get("other_fees")),
            "scholarships":             _safe(doc.get("scholarships")),
            "work_experience":          _safe(doc.get("work_experience")),
            "other_requirements":       _safe(doc.get("other_requirements")),
            "confidence_notes":         _safe(doc.get("confidence_notes")),
            "status":                   _safe(doc.get("status")),
            "source_urls":              source_urls_str,
            "created_at":               _safe(doc.get("created_at")),
        }
        writer.writerow(row)

    return output.getvalue()
