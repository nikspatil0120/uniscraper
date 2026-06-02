# routers/export.py
# GET /scrapes/export/csv — download scrape results as a CSV file.

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

import database
from utils.csv_builder import build_csv

logger = logging.getLogger(__name__)
router = APIRouter(tags=["export"])


@router.get("/scrapes/export/csv")
async def export_csv(
    scrape_ids: Optional[str] = Query(
        default=None,
        description="Comma-separated list of scrape IDs to export",
    ),
    all: bool = Query(
        default=False,
        description="Set to true to export all scrape results",
    ),
):
    """
    Export scrape results as a CSV download.
    Either pass all=true or a comma-separated list of scrape_ids.
    """
    if not all and not scrape_ids:
        raise HTTPException(
            status_code=400,
            detail="Provide scrape_ids (comma-separated) or all=true",
        )

    col = database.scrape_results_collection

    if all:
        cursor = col.find({}, {"_id": 0})
        docs = await cursor.to_list(length=10_000)
    else:
        ids = [sid.strip() for sid in scrape_ids.split(",") if sid.strip()]
        cursor = col.find({"scrape_id": {"$in": ids}}, {"_id": 0})
        docs = await cursor.to_list(length=len(ids))

    if not docs:
        raise HTTPException(status_code=404, detail="No matching scrape results found")

    csv_string = build_csv(docs)
    filename = f"uniscraper_export_{date.today().isoformat()}.csv"

    # Prepend UTF-8 BOM (\ufeff) to make it Excel-compatible on Windows
    return StreamingResponse(
        iter(["\ufeff" + csv_string]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/scrapes/export/json")
async def export_json(
    scrape_ids: Optional[str] = Query(
        default=None,
        description="Comma-separated list of scrape IDs to export",
    ),
    all: bool = Query(
        default=False,
        description="Set to true to export all scrape results",
    ),
):
    """
    Export scrape results as a JSON download.
    Either pass all=true or a comma-separated list of scrape_ids.
    """
    if not all and not scrape_ids:
        raise HTTPException(
            status_code=400,
            detail="Provide scrape_ids (comma-separated) or all=true",
        )

    col = database.scrape_results_collection

    if all:
        cursor = col.find({}, {"_id": 0})
        docs = await cursor.to_list(length=10_000)
    else:
        ids = [sid.strip() for sid in scrape_ids.split(",") if sid.strip()]
        cursor = col.find({"scrape_id": {"$in": ids}}, {"_id": 0})
        docs = await cursor.to_list(length=len(ids))

    if not docs:
        raise HTTPException(status_code=404, detail="No matching scrape results found")

    import json
    json_string = json.dumps(docs, indent=2, default=str)
    filename = f"uniscraper_export_{date.today().isoformat()}.json"

    return StreamingResponse(
        iter([json_string]),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
