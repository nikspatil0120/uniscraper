# routers/batch.py
# POST /scrapes/batch — queue multiple URLs as independent scrapes
# GET  /batch/{batch_id} — check batch progress

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

import database
from models.batch_request import BatchRequest
from pipeline.orchestrator import run_scrape_delayed

logger = logging.getLogger(__name__)
router = APIRouter(tags=["batch"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/scrapes/batch", status_code=202)
async def start_batch(request: BatchRequest, background_tasks: BackgroundTasks):
    """
    Queue a batch of URLs. Each URL is staggered 25s apart to stay under
    Gemini's 3 RPM rate limit. Returns batch_id and individual scrape_ids.
    """
    batch_id = str(uuid.uuid4())
    scrape_ids: list[str] = []
    now = _utcnow()

    # Create one scrape document per URL
    initial_docs = []
    for url in request.urls:
        url_str = str(url)
        scrape_id = str(uuid.uuid4())
        scrape_ids.append(scrape_id)
        initial_docs.append({
            "scrape_id": scrape_id,
            "batch_id": batch_id,
            "status": "processing",
            "created_at": now,
            "url_requested": url_str,
            "context_hint": None,
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
        })

    await database.scrape_results_collection.insert_many(initial_docs)

    # Create the batch job tracking document
    await database.batch_jobs_collection.insert_one({
        "batch_id": batch_id,
        "scrape_ids": scrape_ids,
        "total": len(scrape_ids),
        "created_at": now,
        "status": "processing",
    })

    # Stagger each scrape 25s apart — safely under 3 RPM
    for i, (scrape_id, url) in enumerate(zip(scrape_ids, request.urls)):
        delay = i * 25.0  # 0s, 25s, 50s, 75s ...
        background_tasks.add_task(
            run_scrape_delayed, scrape_id, str(url), "", delay
        )

    logger.info(f"[batch] queued batch {batch_id} — {len(scrape_ids)} URLs, 25s stagger")

    return {
        "batch_id": batch_id,
        "scrape_ids": scrape_ids,
        "total": len(scrape_ids),
        "status": "processing",
        "estimated_seconds": len(scrape_ids) * 25,
    }


@router.get("/batch/{batch_id}")
async def get_batch(batch_id: str):
    """
    Return the current status of a batch job, including per-scrape progress.
    """
    batch_doc = await database.batch_jobs_collection.find_one({"batch_id": batch_id})
    if batch_doc is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    scrape_ids: list[str] = batch_doc.get("scrape_ids", [])

    # Fetch status of all individual scrapes
    cursor = database.scrape_results_collection.find(
        {"scrape_id": {"$in": scrape_ids}},
        {
            "_id": 0,
            "scrape_id": 1,
            "status": 1,
            "university_name": 1,
            "program_name": 1,
            "url_requested": 1,
            "created_at": 1,
        },
    )
    scrapes = await cursor.to_list(length=len(scrape_ids))

    # Tally counts
    processing_count = sum(1 for s in scrapes if s.get("status") in ("processing", "running"))
    success_count = sum(1 for s in scrapes if s.get("status") == "success")
    partial_count = sum(1 for s in scrapes if s.get("status") == "partial")
    failed_count = sum(1 for s in scrapes if s.get("status") == "failed")
    completed = len(scrapes) - processing_count

    # Update batch status if all done
    batch_status = "processing" if processing_count > 0 else "complete"
    if batch_status == "complete" and batch_doc.get("status") != "complete":
        await database.batch_jobs_collection.update_one(
            {"batch_id": batch_id},
            {"$set": {"status": "complete"}},
        )

    return {
        "batch_id": batch_id,
        "total": batch_doc.get("total", len(scrape_ids)),
        "completed": completed,
        "processing": processing_count,
        "success_count": success_count,
        "partial_count": partial_count,
        "failed_count": failed_count,
        "status": batch_status,
        "scrapes": scrapes,
    }
