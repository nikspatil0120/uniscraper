#!/usr/bin/env python
# scripts/test_single_url.py
# Development utility: run the full pipeline on one or more URLs.
# ONE Gemini call per URL. Configurable delay between URLs.
# Skips MongoDB entirely.
#
# Usage:
#   python scripts/test_single_url.py <url> [context_hint]
#   python scripts/test_single_url.py <url1> <url2> <url3>   (batch mode)

import asyncio
import json
import sys
import time
from pathlib import Path

# Reconfigure stdout/stderr to UTF-8 to prevent encoding crashes on Windows
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from pipeline.fetcher import fetch_page
from pipeline.link_extractor import extract_relevant_links
from pipeline.pdf_extractor import extract_pdfs_from_page
from pipeline.ai_extractor import extract_fields
from utils.text_cleaner import clean_html, clean_text_content, combine_texts


def _truncate(value, max_len: int = 60) -> str:
    if value is None:
        return "-"
    s = str(value)
    return s[:max_len] + "..." if len(s) > max_len else s


def _print_summary_table(result: dict) -> None:
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

    print("=" * 80)


async def scrape_one(url: str, context_hint: str = "") -> dict:
    """Run the full pipeline for a single URL. Returns the extracted result dict."""
    print(f"\n{'='*70}")
    print(f"[SCRAPING] {url}")
    print(f"{'='*70}")
    t0 = time.monotonic()

    # ── 1. Fetch main page ────────────────────────────────────────────────────
    print("  [1/4] Fetching main page...")
    fetch_result = await fetch_page(url)
    if fetch_result["html"] is None:
        print(f"  [-] Fetch failed: {fetch_result['error']}")
        return {"university_name": None, "confidence_notes": f"Fetch failed: {fetch_result['error']}"}

    main_html = fetch_result["html"]
    final_url = fetch_result.get("final_url", url)
    print(f"       [+] {fetch_result['method_used']}, {fetch_result['word_count']} words, "
          f"{len(main_html):,} chars raw")

    # ── 2. Extract sub-page links + fetch ────────────────────────────────────
    print("  [2/4] Finding & fetching sub-pages...")
    sub_urls = extract_relevant_links(main_html, final_url)
    print(f"       Found {len(sub_urls)} relevant links")

    sub_pages: list[tuple[str, str]] = []
    for sub_url in sub_urls:
        r = await fetch_page(sub_url)
        if r.get("html"):
            sub_pages.append((sub_url, r["html"]))
            label = sub_url.split("/")[-1] or sub_url
            print(f"       [+] {label[:60]} ({r['word_count']} words)")
        else:
            print(f"       [-] {sub_url[:60]} - {r.get('error', 'failed')}")

    # ── 3. Extract PDFs ───────────────────────────────────────────────────────
    print("  [3/4] Extracting PDFs...")
    pdf_results = await extract_pdfs_from_page(main_html, final_url)
    pdf_texts = [(r["url"].split("/")[-1], clean_text_content(r["text"]))
                 for r in pdf_results if r.get("text")]
    print(f"       [+] {len(pdf_texts)} PDFs with text")

    # ── 4. Combine all text → single Gemini call ──────────────────────────────
    print("  [4/4] Combining text → single Gemini extraction...")

    text_parts: list[tuple[str, str]] = []
    text_parts.append(("MAIN PAGE", clean_html(main_html)))
    for sub_url, sub_html in sub_pages:
        label = sub_url.split("/")[-1] or sub_url.split("/")[-2] or "SUBPAGE"
        text_parts.append((label.upper(), clean_html(sub_html)))
    for label, pdf_text in pdf_texts:
        text_parts.append((f"PDF: {label}", pdf_text))

    combined = combine_texts(text_parts)
    result = await extract_fields(combined, final_url, context_hint)

    elapsed = time.monotonic() - t0
    non_null = sum(1 for v in result.values() if v is not None)

    _print_summary_table(result)
    print(f"\n[JSON] Full JSON:\n{json.dumps(result, indent=2, default=str)}")
    print(f"\n[TIME] {elapsed:.1f}s | {len(sub_pages)} sub-pages | "
          f"{len(pdf_texts)} PDFs | {non_null} fields extracted\n")

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
            print(f"\n[WAIT] Waiting {delay}s before next scrape (rate-limit protection)...")
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
