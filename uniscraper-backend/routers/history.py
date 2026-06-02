# routers/history.py
# GET /scrapes — paginated, filterable list of past scrape results.
# Returns lightweight summary objects (not full documents).

import math
import logging
from typing import Optional

from fastapi import APIRouter, Query

import database

logger = logging.getLogger(__name__)
router = APIRouter(tags=["history"])

# Fields returned in the list view (keeps response payload small)
_SUMMARY_PROJECTION = {
    "_id": 0,
    "scrape_id": 1,
    "university_name": 1,
    "program_name": 1,
    "degree_level": 1,
    "status": 1,
    "created_at": 1,
    "source_urls": 1,
}


@router.get("/scrapes")
async def list_scrapes(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(default=20, ge=1, le=100, description="Results per page"),
    search: Optional[str] = Query(default=None, description="Search university or program name"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
):
    """
    Return a paginated list of scrape results, newest first.
    Supports optional full-text search on university_name / program_name
    and filtering by status.
    """
    query_filter: dict = {}

    if search:
        query_filter["$or"] = [
            {"university_name": {"$regex": search, "$options": "i"}},
            {"program_name": {"$regex": search, "$options": "i"}},
        ]

    if status:
        query_filter["status"] = status

    col = database.scrape_results_collection
    total = await col.count_documents(query_filter)

    skip = (page - 1) * limit
    cursor = (
        col.find(query_filter, _SUMMARY_PROJECTION)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)

    # Replace source_urls list with a count to keep the payload lean
    for item in items:
        urls = item.get("source_urls") or []
        item["source_count"] = len(urls)
        item.pop("source_urls", None)

    pages = math.ceil(total / limit) if total > 0 else 1

    return {
        "data": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }
