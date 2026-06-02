# pipeline/merger.py
# merge_results(results, sources) -> dict
# Merges extracted field dicts from multiple sources into one canonical dict.
# First non-null value wins for scalars; lists are unioned; nested dicts merged independently.

import logging

logger = logging.getLogger(__name__)

# All scalar top-level fields (first non-null wins)
_SCALAR_FIELDS = [
    "university_name",
    "program_name",
    "degree_level",
    "program_duration",
    "application_deadlines",
    "min_academic_requirement",
    "accepted_qualifications",
    "other_fees",
    "scholarships",
    "work_experience",
    "other_requirements",
    "confidence_notes",
]

# List fields (union across all sources)
_LIST_FIELDS = ["intake_months"]

# Nested dict fields with their sub-keys
_NESTED_FIELDS = {
    "english_requirements": ["ielts", "toefl", "pte", "duolingo", "notes"],
    "tuition_fees": ["domestic", "international", "currency", "notes"],
}


def merge_results(results: list[dict], sources: list[str]) -> dict:
    """
    Merge a list of extracted field dicts (one per source page/PDF) into
    a single canonical dict. Sources is a parallel list of source URLs.

    Strategy:
    - Scalar fields: first non-null value wins (main page first)
    - List fields (intake_months): deduplicated union across all sources
    - Nested dicts (english_requirements, tuition_fees): sub-fields merged independently
    - field_sources: records which URL each field came from
    """
    if not results:
        merged = {k: None for k in _SCALAR_FIELDS}
        for lf in _LIST_FIELDS:
            merged[lf] = None
        for nf in _NESTED_FIELDS:
            merged[nf] = None
        merged["field_sources"] = {}
        return merged

    merged: dict = {}
    field_sources: dict[str, str] = {}

    # --- Scalar fields ---
    for field in _SCALAR_FIELDS:
        for result, source_url in zip(results, sources):
            value = result.get(field)
            if value is not None:
                merged[field] = value
                field_sources[field] = source_url
                break
        else:
            merged[field] = None

    # --- List fields ---
    for field in _LIST_FIELDS:
        seen_values: list[str] = []
        seen_set: set[str] = set()
        first_source = None
        for result, source_url in zip(results, sources):
            value = result.get(field)
            if value and isinstance(value, list):
                if first_source is None:
                    first_source = source_url
                for item in value:
                    item_str = str(item).strip()
                    if item_str and item_str not in seen_set:
                        seen_set.add(item_str)
                        seen_values.append(item_str)

        if seen_values:
            merged[field] = seen_values
            field_sources[field] = first_source
        else:
            merged[field] = None

    # --- Nested dict fields ---
    for nested_field, sub_keys in _NESTED_FIELDS.items():
        nested_merged: dict = {}
        any_found = False

        for sub_key in sub_keys:
            for result, source_url in zip(results, sources):
                parent = result.get(nested_field)
                if parent is None:
                    continue
                # Handle both dict and Pydantic model
                if hasattr(parent, "model_dump"):
                    parent = parent.model_dump()
                if not isinstance(parent, dict):
                    continue
                value = parent.get(sub_key)
                if value is not None:
                    nested_merged[sub_key] = value
                    field_sources[f"{nested_field}.{sub_key}"] = source_url
                    any_found = True
                    break
            else:
                nested_merged[sub_key] = None

        merged[nested_field] = nested_merged if any_found else None

    merged["field_sources"] = field_sources

    non_null = sum(1 for v in merged.values() if v is not None)
    logger.info(
        f"[merger] merged {len(results)} sources, {non_null} total fields found"
    )

    return merged
