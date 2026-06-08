# routers/scrape.py
# POST /scrape  — start a scrape, return immediately with scrape_id
# GET  /scrape/{scrape_id} — poll for result

import uuid
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException

import database
from models.scrape_request import ScrapeRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scrape"])

_CACHE_TTL_HOURS = 24


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/scrape", status_code=202)
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Start a new scrape. Returns immediately with scrape_id and status="processing".
    If the same URL was successfully scraped within the last 24 hours, returns
    the cached result immediately instead of re-scraping.
    """
    url_str = str(request.url)

    # ── Cache check: same URL, success/partial, within 24h ───────────────────
    cutoff = _utcnow() - timedelta(hours=_CACHE_TTL_HOURS)
    existing = await database.scrape_results_collection.find_one(
        {
            "url_requested": url_str,
            "status": {"$in": ["success", "partial"]},
            "created_at": {"$gte": cutoff},
        },
        sort=[("created_at", -1)],  # Most recent first
    )
    if existing:
        cached_id = existing["scrape_id"]
        logger.info(f"[scrape] cache hit for {url_str} -> {cached_id}")
        return {
            "scrape_id": cached_id,
            "status": "cached",
            "cached_from": cached_id,
            "message": f"Returning cached result from {existing['created_at'].strftime('%Y-%m-%d %H:%M UTC')}",
        }

    # ── No cache hit — run fresh scrape ──────────────────────────────────────
    scrape_id = str(uuid.uuid4())

    initial_doc = {
        "scrape_id": scrape_id,
        "status": "processing",
        "created_at": _utcnow(),
        "url_requested": url_str,
        "context_hint": request.context_hint,
        "source_urls": [],
        "university_name": None,
        "program_name": None,
        "degree_level": None,
        "program_duration": None,
        "intake_months": None,
        "application_deadlines": None,
        "min_academic_requirement": None,
        "accepted_qualifications": None,
        "english_requirements": None,
        "tuition_fees": None,
        "other_fees": None,
        "scholarships": None,
        "work_experience": None,
        "other_requirements": None,
        "confidence_notes": None,
        "field_sources": None,
    }

    await database.scrape_results_collection.insert_one(initial_doc)
    logger.info(f"[scrape] queued {scrape_id} for {url_str}")

    # Defer importing the orchestration pipeline (which pulls in heavy deps like Playwright)
    # until we actually enqueue a background scrape. This lets the FastAPI app start in
    # development without installing all native dependencies.
    from pipeline.orchestrator import run_scrape

    background_tasks.add_task(run_scrape, scrape_id, url_str, request.context_hint or "")

    return {"scrape_id": scrape_id, "status": "processing"}


@router.get("/scrape/{scrape_id}")
async def get_scrape(scrape_id: str):
    """
    Retrieve a scrape result by ID.
    Returns the full document. Status will be "processing" until the pipeline finishes.
    """
    doc = await database.scrape_results_collection.find_one({"scrape_id": scrape_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="Scrape not found")

    doc.pop("_id", None)
    return doc


@router.delete("/scrape/{scrape_id}", status_code=204)
async def delete_scrape(scrape_id: str):
    """Delete a scrape result by ID."""
    result = await database.scrape_results_collection.delete_one({"scrape_id": scrape_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Scrape not found")
