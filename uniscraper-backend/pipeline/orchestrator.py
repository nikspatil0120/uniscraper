# pipeline/orchestrator.py
# run_scrape(scrape_id, url, context_hint) — main pipeline coordinator.
#
# ARCHITECTURE: ONE Gemini call per university.
#   1. Fetch main page
#   2. Extract sub-page links + fetch sub-pages concurrently
#   3. Extract PDFs from main page
#   4. Clean + combine ALL text into one string
#   5. Single Gemini extraction call
#   6. Save to MongoDB

import asyncio
import logging
import time
from datetime import datetime, timezone

from config import settings
import database
from pipeline.fetcher import fetch_page
from pipeline.link_extractor import extract_relevant_links
from pipeline.pdf_extractor import extract_pdfs_from_page
from pipeline.ai_extractor import extract_fields
from utils.text_cleaner import clean_html, clean_text_content, combine_texts, truncate_text
from utils.page_classifier import classify_page

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _determine_status(result: dict) -> str:
    """
    success:  university_name present AND ≥8 other non-null fields
    partial:  university_name OR program_name present, but <8 other fields
    failed:   neither university_name nor program_name found
    """
    has_uni = result.get("university_name") is not None
    has_prog = result.get("program_name") is not None

    if not has_uni and not has_prog:
        return "failed"

    meta_keys = {"scrape_id", "status", "created_at", "source_urls",
                 "field_sources", "confidence_notes"}
    other_non_null = sum(
        1 for k, v in result.items()
        if k not in meta_keys and v is not None
    )

    if has_uni and other_non_null >= 8:
        return "success"
    return "partial"


async def run_scrape_delayed(scrape_id: str, url: str, context_hint: str, delay_seconds: float) -> None:
    """Wrapper that sleeps before running — used by batch to stagger requests."""
    if delay_seconds > 0:
        logger.info(f"[orchestrator] {scrape_id} — waiting {delay_seconds:.0f}s before start (batch stagger)")
        await asyncio.sleep(delay_seconds)
    await run_scrape(scrape_id, url, context_hint)


async def run_scrape(scrape_id: str, url: str, context_hint: str = "") -> None:
    """
    Full scraping pipeline. Runs as a FastAPI BackgroundTask.
    Makes exactly ONE Gemini API call per scrape.
    Never raises — all exceptions are caught and written to MongoDB.
    """
    start_time = time.monotonic()
    col = database.scrape_results_collection

    async def update_progress(step: str):
        """Helper to update progress in database"""
        await col.update_one(
            {"scrape_id": scrape_id},
            {"$set": {"current_step": step, "last_updated": _utcnow()}},
        )

    try:
        # ── STEP 1: Mark as running ───────────────────────────────────────────
        await col.update_one(
            {"scrape_id": scrape_id},
            {"$set": {"status": "running", "started_at": _utcnow(), "current_step": "Fetching page"}},
        )

        # ── STEP 2: Fetch main page ───────────────────────────────────────────
        await update_progress("Fetching page")
        logger.info(f"[orchestrator] {scrape_id} — fetching {url}")
        fetch_result = await fetch_page(url)

        if fetch_result["html"] is None:
            await col.update_one(
                {"scrape_id": scrape_id},
                {"$set": {
                    "status": "failed",
                    "error": fetch_result.get("error", "Failed to fetch page"),
                    "completed_at": _utcnow(),
                }},
            )
            logger.error(f"[orchestrator] {scrape_id} — fetch failed: {fetch_result.get('error')}")
            return

        main_html = fetch_result["html"]
        final_url = fetch_result.get("final_url", url)
        logger.info(f"[orchestrator] {scrape_id} — main page: "
                    f"{fetch_result['word_count']} words via {fetch_result['method_used']}")

        # ── STEP 3: Extract sub-page links ────────────────────────────────────
        await update_progress("Detecting content type")
        sub_urls = extract_relevant_links(main_html, final_url)
        logger.info(f"[orchestrator] {scrape_id} — {len(sub_urls)} sub-pages found")

        # ── STEP 4: Extract PDFs ──────────────────────────────────────────────
        await update_progress("Following sub-pages")
        pdf_results = await extract_pdfs_from_page(main_html, final_url)
        logger.info(f"[orchestrator] {scrape_id} — {len(pdf_results)} PDFs found")

        # ── STEP 5: Clean main page first ────────────────────────────────────────
        try:
            main_clean = clean_html(main_html)
            if not main_clean or len(main_clean) < 100:
                logger.warning(f"[orchestrator] {scrape_id} — main page cleaning produced minimal content ({len(main_clean)} chars), using raw HTML")
                main_clean = main_html  # Fallback to raw HTML if cleaning produces nothing
        except Exception as e:
            logger.error(f"[orchestrator] {scrape_id} — failed to clean main HTML: {e}")
            main_clean = main_html  # Fallback to raw HTML if cleaning fails
        
        # ── STEP 6: Fetch sub-pages concurrently (OPTIMIZED) ─────────────────────
        max_concurrent = max(1, min(len(sub_urls), 3))  # At least 1 to avoid range(0,0,0)
        
        async def fetch_with_classification(url):
            result = await fetch_page(url)
            if result.get("html"):
                try:
                    clean_content = clean_html(result["html"])
                    # Fallback to raw HTML if cleaning produces minimal content
                    if not clean_content or len(clean_content) < 100:
                        logger.warning(f"[orchestrator] {scrape_id} — sub-page {url} cleaning produced minimal content, using raw HTML")
                        clean_content = result["html"]
                    page_type = classify_page(url, clean_content)
                    return url, result["html"], clean_content, page_type
                except Exception as e:
                    logger.error(f"[orchestrator] {scrape_id} — error cleaning sub-page {url}: {e}")
                    # Fallback to raw HTML
                    return url, result["html"], result["html"], "other"
            return url, None, None, "other"
        
        # Process in batches to control concurrency
        sub_results = []
        for i in range(0, len(sub_urls), max_concurrent):
            batch = sub_urls[i:i + max_concurrent]
            batch_tasks = [fetch_with_classification(url) for url in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            sub_results.extend(batch_results)

        # ── STEP 7: Process results and build text parts ─────────────────────────
        text_parts: list[tuple[str, str]] = []  # (label, cleaned_text)
        
        # Ensure main page content is never empty
        main_content_to_use = main_clean if main_clean and len(main_clean) >= 100 else main_html
        if main_content_to_use == main_html:
            logger.warning(f"[orchestrator] {scrape_id} — using raw main HTML due to insufficient cleaned content")
        
        text_parts.append(("MAIN PAGE", main_content_to_use))
        
        sub_pages: list[tuple[str, str]] = []
        pages_data = [{"url": final_url, "content": main_content_to_use, "page_type": "programme_overview"}]
        
        for result in sub_results:
            if isinstance(result, Exception):
                logger.warning(f"[orchestrator] {scrape_id} — sub-page error: {result}")
                continue
            
            sub_url, sub_html, sub_clean, page_type = result
            if sub_html and sub_clean:
                sub_pages.append((sub_url, sub_html))
                pages_data.append({"url": sub_url, "content": sub_clean, "page_type": page_type})
                label = f"{sub_url.split('/')[-1] or sub_url.split('/')[-2] or sub_url} ({page_type})"
                text_parts.append((label.upper(), sub_clean))
        # ── STEP 8: Process PDFs ─────────────────────────────────────────────────
        await update_progress("Extracting PDFs")
        pdf_count = 0
        for pdf_r in pdf_results:
            if pdf_r.get("text"):
                pdf_clean = clean_text_content(pdf_r["text"])
                label = pdf_r["url"].split("/")[-1] or "PDF"
                text_parts.append((f"PDF: {label}", pdf_clean))
                pdf_count += 1

        combined = combine_texts(text_parts)
        
        # Safety check: if combined_text is empty, fall back to raw main page HTML
        if not combined or not combined.strip():
            logger.warning(f"[orchestrator] {scrape_id} — combined_text is empty, falling back to raw main page HTML")
            combined = main_html
            # Also update pages_data to use raw HTML
            pages_data[0]["content"] = main_html

        # Debug summary
        print(f"\n[DEBUG] Scrape {scrape_id[:8]}...")
        print(f"[DEBUG]   Main page raw:  {len(main_html):,} chars")
        print(f"[DEBUG]   Main page clean: {len(main_clean):,} chars")
        print(f"[DEBUG]   Main page used:  {len(main_content_to_use):,} chars ({'raw' if main_content_to_use == main_html else 'cleaned'})")
        print(f"[DEBUG]   Sub-pages:      {len(sub_pages)}")
        print(f"[DEBUG]   PDFs processed: {pdf_count}")
        print(f"[DEBUG]   Combined text:  {len(combined):,} chars")
        logger.info(f"[orchestrator] {scrape_id} — combined {len(text_parts)} sources, "
                    f"{len(combined):,} chars total")

        all_source_urls = [final_url] + [u for u, _ in sub_pages] + \
                          [r["url"] for r in pdf_results if r.get("text")]

        # ── STEP 9: Single LLM extraction call ───────────────────────────────
        await update_progress("Running AI extraction")
        logger.info(f"[orchestrator] {scrape_id} — starting extraction")
        extracted = await extract_fields(combined, final_url, context_hint, pages_data)

        # Pull internal metadata key before saving
        llm_model_used = extracted.pop("_model_used", fetch_result.get("method_used", "unknown"))

        # ── STEP 9b: Build field_sources attribution ──────────────────────────
        # For each non-null field, record which page URL it most likely came from
        # based on the same relevance scoring used during extraction.
        from pipeline.ai_extractor import calculate_page_relevance_score

        field_sources: dict[str, str] = {}

        FIELD_TO_GROUP = {
            "university_name": "program_duration",
            "program_name": "program_duration",
            "degree_level": "program_duration",
            "program_duration": "program_duration",
            "intake_months": "intake_months",
            "application_deadlines": "application_deadlines",
            "min_academic_requirement": "application_deadlines",
            "accepted_qualifications": "application_deadlines",
            "work_experience": "application_deadlines",
            "other_requirements": "application_deadlines",
            "english_requirements": "english_requirements",
            "tuition_fees": "tuition_fees",
            "other_fees": "tuition_fees",
            "scholarships": "tuition_fees",
        }

        def _best_source_url(group: str) -> str:
            best_url, best_score = final_url, -1
            for page in pages_data:
                score = calculate_page_relevance_score(page, group)
                if score > best_score:
                    best_score, best_url = score, page["url"]
            return best_url

        for field, group in FIELD_TO_GROUP.items():
            value = extracted.get(field)
            if value is None:
                continue
            source = _best_source_url(group)
            field_sources[field] = source
            # Dot-notation for nested sub-fields
            if isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    if sub_val is not None:
                        field_sources[f"{field}.{sub_key}"] = source

        extracted["field_sources"] = field_sources
        logger.info(f"[orchestrator] {scrape_id} — field_sources: {list(field_sources.keys())}")

        # ── STEP 9: Determine status ──────────────────────────────────────────
        await update_progress("Saving results")
        status = _determine_status(extracted)

        # ── STEP 9: Save to MongoDB ───────────────────────────────────────────
        elapsed = time.monotonic() - start_time
        update_doc = {
            **extracted,
            "status": status,
            "source_urls": all_source_urls,
            "completed_at": _utcnow(),
            "method_used": fetch_result.get("method_used"),
            "llm_model": llm_model_used,
            "elapsed_seconds": round(elapsed, 2),
        }
        # Don't store entirely-null nested dicts
        if update_doc.get("english_requirements") is None:
            update_doc.pop("english_requirements", None)
        if update_doc.get("tuition_fees") is None:
            update_doc.pop("tuition_fees", None)
        # Ensure field_sources is always present (even if empty)
        if "field_sources" not in update_doc or update_doc["field_sources"] is None:
            update_doc["field_sources"] = {}

        await col.update_one(
            {"scrape_id": scrape_id},
            {"$set": update_doc},
        )
        # Clear progress step on completion
        await col.update_one(
            {"scrape_id": scrape_id},
            {"$unset": {"current_step": "", "last_updated": ""}},
        )

        # ── STEP 10: Log completion ───────────────────────────────────────────
        non_null = sum(1 for v in extracted.values() if v is not None)
        print(f"[DEBUG]   Status: {status} | Fields: {non_null} | Time: {elapsed:.1f}s\n")
        logger.info(f"[orchestrator] {scrape_id} — {status}, "
                    f"{len(all_source_urls)} sources, {elapsed:.1f}s, {non_null} fields")

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        logger.exception(f"[orchestrator] {scrape_id} — unhandled exception: {exc}")
        try:
            await col.update_one(
                {"scrape_id": scrape_id},
                {"$set": {
                    "status": "failed",
                    "error": str(exc),
                    "completed_at": _utcnow(),
                    "elapsed_seconds": round(elapsed, 2),
                }},
            )
        except Exception as db_exc:
            logger.error(f"[orchestrator] {scrape_id} — MongoDB update failed: {db_exc}")
