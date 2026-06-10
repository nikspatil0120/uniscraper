# pipeline/orchestrator.py
# run_scrape(scrape_id, url, context_hint) — main pipeline coordinator.
#
# FETCH STRATEGY — three-tier waterfall via intelligent_fetcher:
#   Tier 1: Crawl4AI  (stealth Playwright + fit_markdown)
#   Tier 2: Firecrawl (hosted API — handles Cloudflare)
#   Tier 3: Custom    (httpx → Playwright, guaranteed fallback)
#
# After fetching, the pipeline is unchanged:
#   → PDF extraction → single Gemini call → MongoDB save

import asyncio
import logging
import time
from datetime import datetime, timezone

from config import settings
import database
from pipeline.intelligent_fetcher import fetch_subpages_intelligent
from pipeline.pdf_extractor import extract_pdfs_from_page
from pipeline.ai_extractor import extract_fields
from utils.text_cleaner import clean_text_content, combine_texts
from utils.page_classifier import classify_page

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _determine_status(result: dict) -> str:
    has_uni = result.get("university_name") is not None
    has_prog = result.get("program_name") is not None
    if not has_uni and not has_prog:
        return "failed"
    meta_keys = {"scrape_id", "status", "created_at", "source_urls",
                 "field_sources", "confidence_notes"}
    other_non_null = sum(1 for k, v in result.items() if k not in meta_keys and v is not None)
    if has_uni and other_non_null >= 8:
        return "success"
    return "partial"


async def run_scrape_delayed(scrape_id: str, url: str, context_hint: str, delay_seconds: float) -> None:
    if delay_seconds > 0:
        logger.info(f"[orchestrator] {scrape_id} — waiting {delay_seconds:.0f}s (batch stagger)")
        await asyncio.sleep(delay_seconds)
    await run_scrape(scrape_id, url, context_hint)


async def run_scrape(scrape_id: str, url: str, context_hint: str = "") -> None:
    """
    Full scraping pipeline. Runs as a FastAPI BackgroundTask.
    Never raises — all exceptions are caught and written to MongoDB.
    """
    start_time = time.monotonic()
    col = database.scrape_results_collection

    try:
        # ── STEP 1: Mark as running ───────────────────────────────────────────
        await col.update_one(
            {"scrape_id": scrape_id},
            {"$set": {"status": "running", "started_at": _utcnow()}},
        )

        # ── STEP 2: Fetch all pages via intelligent three-tier waterfall ──────
        logger.info(f"[orchestrator] {scrape_id} — fetching {url}")

        all_pages = await fetch_subpages_intelligent(
            url, max_pages=settings.max_subpages
        )

        if not all_pages:
            await col.update_one(
                {"scrape_id": scrape_id},
                {"$set": {
                    "status": "failed",
                    "error": "All fetch tiers failed — no content retrieved",
                    "completed_at": _utcnow(),
                }},
            )
            logger.error(f"[orchestrator] {scrape_id} — all tiers failed for {url}")
            return

        main_page = all_pages[0]
        tier_used = main_page.get("tier", 3)
        method_used = main_page.get("method", "unknown")
        final_url = main_page.get("url", url)

        logger.info(
            f"[orchestrator] {scrape_id} — fetched {len(all_pages)} pages via "
            f"Tier {tier_used} ({method_used})"
        )
        print(f"\n[FETCH] Tier {tier_used} ({method_used}) — "
              f"{len(all_pages)} pages, main={main_page.get('word_count', 0)} words")

        # ── STEP 3: Build pages_data and text_parts ───────────────────────────
        pages_data: list[dict] = []
        text_parts: list[tuple[str, str]] = []

        for page in all_pages:
            content = page.get("content") or page.get("markdown") or ""
            if not content or len(content.split()) < 30:
                logger.warning(
                    f"[orchestrator] skipping thin page "
                    f"{page.get('url', '')[-60:]} ({len(content.split())} words)"
                )
                continue

            page_url = page.get("url", url)
            page_type = page.get("page_type") or classify_page(page_url, content)

            pages_data.append({
                "url":        page_url,
                "content":    content,
                "page_type":  page_type,
                "word_count": len(content.split()),
                "method":     page.get("method", method_used),
                "tier":       page.get("tier", tier_used),
            })

            is_main = (page_url == final_url or page == all_pages[0])
            label = "MAIN PAGE" if is_main else (
                f"{page_url.split('/')[-1] or page_url.split('/')[-2] or page_url} ({page_type})"
            ).upper()
            text_parts.append((label, content))

        if not pages_data:
            await col.update_one(
                {"scrape_id": scrape_id},
                {"$set": {
                    "status": "failed",
                    "error": "All fetched pages were too thin to process",
                    "completed_at": _utcnow(),
                }},
            )
            return

        # ── STEP 4: Extract PDFs from main page HTML ──────────────────────────
        pdf_count = 0
        main_html = main_page.get("html", "")
        if main_html:
            try:
                pdf_results = await database_safe_pdf_extract(main_html, final_url)
                for pdf_r in pdf_results:
                    if pdf_r.get("text"):
                        pdf_clean = clean_text_content(pdf_r["text"])
                        label = pdf_r["url"].split("/")[-1] or "PDF"
                        text_parts.append((f"PDF: {label}", pdf_clean))
                        pdf_count += 1
            except Exception as pdf_exc:
                logger.warning(f"[orchestrator] {scrape_id} — PDF extraction failed: {pdf_exc}")

        # ── STEP 5: Combine all text ──────────────────────────────────────────
        combined = combine_texts(text_parts)

        print(f"[DEBUG] Scrape {scrape_id[:8]}...")
        print(f"[DEBUG]   Tier:           {tier_used} ({method_used})")
        print(f"[DEBUG]   Pages:          {len(pages_data)}")
        print(f"[DEBUG]   PDFs:           {pdf_count}")
        print(f"[DEBUG]   Combined text:  {len(combined):,} chars")
        logger.info(
            f"[orchestrator] {scrape_id} — combined {len(text_parts)} sources, "
            f"{len(combined):,} chars, tier={tier_used}"
        )

        all_source_urls = [p["url"] for p in pages_data]

        # ── STEP 6: LLM extraction ────────────────────────────────────────────
        # Tiers 1 & 2 return clean markdown — skip clean_html() inside ai_extractor
        content_format = "markdown" if tier_used in (1, 2) else "html"

        logger.info(f"[orchestrator] {scrape_id} — starting extraction (format={content_format})")
        extracted = await extract_fields(
            combined, final_url, context_hint, pages_data,
            content_format=content_format,
        )

        llm_model_used = extracted.pop("_model_used", method_used)

        # ── STEP 7: Build field_sources attribution ───────────────────────────
        from pipeline.ai_extractor import calculate_page_relevance_score

        FIELD_TO_GROUP = {
            "university_name":          "program_duration",
            "program_name":             "program_duration",
            "degree_level":             "program_duration",
            "program_duration":         "program_duration",
            "intake_months":            "intake_months",
            "application_deadlines":    "application_deadlines",
            "min_academic_requirement": "application_deadlines",
            "accepted_qualifications":  "application_deadlines",
            "work_experience":          "application_deadlines",
            "other_requirements":       "application_deadlines",
            "english_requirements":     "english_requirements",
            "tuition_fees":             "tuition_fees",
            "other_fees":               "tuition_fees",
            "scholarships":             "tuition_fees",
        }

        def _best_source_url(group: str) -> str:
            best_url, best_score = final_url, -1
            for page in pages_data:
                score = calculate_page_relevance_score(page, group)
                if score > best_score:
                    best_score, best_url = score, page["url"]
            return best_url

        field_sources: dict[str, str] = {}
        for field, group in FIELD_TO_GROUP.items():
            value = extracted.get(field)
            if value is None:
                continue
            source = _best_source_url(group)
            field_sources[field] = source
            if isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    if sub_val is not None:
                        field_sources[f"{field}.{sub_key}"] = source

        extracted["field_sources"] = field_sources

        # ── STEP 8: Save to MongoDB ───────────────────────────────────────────
        status = _determine_status(extracted)
        elapsed = time.monotonic() - start_time

        update_doc = {
            **extracted,
            "status":          status,
            "source_urls":     all_source_urls,
            "completed_at":    _utcnow(),
            "method_used":     method_used,
            "tier_used":       tier_used,
            "pages_fetched":   len(pages_data),
            "llm_model":       llm_model_used,
            "elapsed_seconds": round(elapsed, 2),
        }
        if update_doc.get("english_requirements") is None:
            update_doc.pop("english_requirements", None)
        if update_doc.get("tuition_fees") is None:
            update_doc.pop("tuition_fees", None)
        if "field_sources" not in update_doc or update_doc["field_sources"] is None:
            update_doc["field_sources"] = {}

        await col.update_one({"scrape_id": scrape_id}, {"$set": update_doc})

        non_null = sum(1 for v in extracted.values() if v is not None)
        print(
            f"[DEBUG]   Status: {status} | Fields: {non_null} | "
            f"Tier: {tier_used} | Time: {elapsed:.1f}s\n"
        )
        logger.info(
            f"[orchestrator] {scrape_id} — {status}, {len(all_source_urls)} sources, "
            f"tier={tier_used}, {elapsed:.1f}s, {non_null} fields"
        )

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


async def database_safe_pdf_extract(html: str, url: str) -> list[dict]:
    """Wrapper so PDF import errors don't crash the whole pipeline."""
    try:
        from pipeline.pdf_extractor import extract_pdfs_from_page
        return await extract_pdfs_from_page(html, url)
    except Exception as exc:
        logger.warning(f"[orchestrator] PDF extractor error: {exc}")
        return []
