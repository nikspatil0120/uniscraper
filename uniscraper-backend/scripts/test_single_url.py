#!/usr/bin/env python
# scripts/test_single_url.py
# Development utility: run the full three-tier pipeline on one or more URLs.
# Skips MongoDB entirely. Shows which tier was used.
#
# Usage:
#   python scripts/test_single_url.py <url> [context_hint]
#   python scripts/test_single_url.py <url1> <url2> <url3>   (batch mode)

import asyncio
import json
import sys
import time
from pathlib import Path

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from pipeline.intelligent_fetcher import fetch_subpages_intelligent
from pipeline.pdf_extractor import extract_pdfs_from_page
from pipeline.ai_extractor import extract_fields
from utils.text_cleaner import clean_text_content, combine_texts
from utils.page_classifier import classify_page


def _truncate(value, max_len: int = 60) -> str:
    if value is None:
        return "-"
    s = str(value)
    return s[:max_len] + "..." if len(s) > max_len else s


def _tier_label(tier: int, method: str) -> str:
    labels = {1: "Crawl4AI", 2: "Firecrawl", 3: "Custom (httpx/Playwright)"}
    return f"Tier {tier} — {labels.get(tier, method)} ({method})"


def _print_summary_table(result: dict, tier: int = 0, method: str = "") -> None:
    fields = [
        "university_name", "program_name", "degree_level", "program_duration",
        "intake_months", "application_deadlines", "min_academic_requirement",
        "accepted_qualifications", "other_fees", "scholarships",
        "work_experience", "other_requirements", "confidence_notes",
    ]
    nested = {
        "english_requirements": ["ielts", "toefl", "pte", "duolingo", "notes"],
        "tuition_fees": ["domestic", "international", "currency", "notes"],
    }

    print("\n" + "=" * 80)
    print(f"  {'FIELD':<35} {'VALUE (first 60 chars)'}")
    print("=" * 80)

    for field in fields:
        value = result.get(field)
        marker = "+" if value is not None else " "
        print(f"  {marker} {field:<33} {_truncate(value)}")

    for parent_key, sub_keys in nested.items():
        parent = result.get(parent_key) or {}
        if isinstance(parent, dict):
            for sub_key in sub_keys:
                value = parent.get(sub_key)
                full_key = f"{parent_key}.{sub_key}"
                marker = "+" if value is not None else " "
                print(f"  {marker} {full_key:<33} {_truncate(value)}")

    if tier:
        print("-" * 80)
        print(f"  {'Tier used':<35} {_tier_label(tier, method)}")
    print("=" * 80)


async def scrape_one(url: str, context_hint: str = "") -> dict:
    print(f"\n{'='*70}")
    print(f"[SCRAPING] {url}")
    print(f"{'='*70}")
    t0 = time.monotonic()

    # ── 1. Fetch all pages via intelligent three-tier waterfall ───────────────
    print("  [1/3] Fetching pages (three-tier waterfall)...")
    all_pages = await fetch_subpages_intelligent(
        url, max_pages=settings.max_subpages + 1
    )

    if not all_pages:
        print("  [-] All fetch tiers failed")
        return {"university_name": None, "confidence_notes": "All fetch tiers failed"}

    main_page = all_pages[0]
    tier_used = main_page.get("tier", 3)
    method_used = main_page.get("method", "unknown")
    final_url = main_page.get("url", url)

    print(f"       [+] {_tier_label(tier_used, method_used)}")
    print(f"       [+] {len(all_pages)} pages | main: {main_page.get('word_count', 0)} words")
    for p in all_pages[1:]:
        label = p.get("url", "")[-60:]
        print(f"       [+] sub: {label} ({p.get('word_count', 0)} words, {p.get('page_type', '?')})")

    # ── 2. Build pages_data and text_parts ────────────────────────────────────
    print("  [2/3] Building extraction context...")
    pages_data = []
    text_parts = []

    for i, page in enumerate(all_pages):
        content = page.get("content") or page.get("markdown") or ""
        if not content or len(content.split()) < 30:
            continue
        page_url = page.get("url", url)
        page_type = page.get("page_type") or classify_page(page_url, content)
        pages_data.append({
            "url": page_url, "content": content,
            "page_type": page_type, "word_count": len(content.split()),
        })
        label = "MAIN PAGE" if i == 0 else (
            f"{page_url.split('/')[-1] or page_url} ({page_type})"
        ).upper()
        text_parts.append((label, content))

    # PDFs
    main_html = main_page.get("html", "")
    pdf_count = 0
    if main_html:
        try:
            from pipeline.pdf_extractor import extract_pdfs_from_page
            pdf_results = await extract_pdfs_from_page(main_html, final_url)
            for r in pdf_results:
                if r.get("text"):
                    pdf_clean = clean_text_content(r["text"])
                    text_parts.append((f"PDF: {r['url'].split('/')[-1]}", pdf_clean))
                    pdf_count += 1
        except Exception:
            pass
    print(f"       [+] {len(pages_data)} pages, {pdf_count} PDFs")

    combined = combine_texts(text_parts)
    print(f"       [+] {len(combined):,} chars combined")

    # ── 3. Single LLM extraction ──────────────────────────────────────────────
    print("  [3/3] Running LLM extraction (single Gemini call)...")
    content_format = "markdown" if tier_used in (1, 2) else "html"
    result = await extract_fields(
        combined, final_url, context_hint, pages_data,
        content_format=content_format,
    )

    elapsed = time.monotonic() - t0
    non_null = sum(1 for v in result.values() if v is not None)

    _print_summary_table(result, tier=tier_used, method=method_used)
    print(f"\n[JSON] Full JSON:\n{json.dumps(result, indent=2, default=str)}")
    print(
        f"\n[TIME] {elapsed:.1f}s | {len(all_pages)} pages | {pdf_count} PDFs | "
        f"{_tier_label(tier_used, method_used)} | {non_null} fields extracted\n"
    )

    return result


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_single_url.py <url> [url2 url3 ...]")
        sys.exit(1)

    urls = sys.argv[1:]
    delay = settings.scrape_delay_seconds

    results = []
    for i, url in enumerate(urls):
        if i > 0:
            print(f"\n[WAIT] Waiting {delay}s before next scrape...")
            await asyncio.sleep(delay)
        result = await scrape_one(url)
        results.append(result)

    if len(urls) > 1:
        print(f"\n{'='*70}")
        print(f"BATCH SUMMARY — {len(urls)} URLs")
        print(f"{'='*70}")
        for url, result in zip(urls, results):
            uni = result.get("university_name") or "—"
            prog = result.get("program_name") or "—"
            non_null = sum(1 for v in result.values() if v is not None)
            print(f"  {uni} | {prog} | {non_null} fields | {url[:50]}")


if __name__ == "__main__":
    asyncio.run(main())
