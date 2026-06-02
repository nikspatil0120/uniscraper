#!/usr/bin/env python
# scripts/validate_universities.py
# Breadth validation: run the full pipeline on 9 universities and produce
# a structured report showing field coverage per university.
#
# Usage:
#   python scripts/validate_universities.py
#   python scripts/validate_universities.py --delay 10   (seconds between scrapes)

import asyncio
import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from pipeline.fetcher import fetch_page
from pipeline.link_extractor import extract_relevant_links
from pipeline.pdf_extractor import extract_pdfs_from_page
from pipeline.ai_extractor import extract_fields
from utils.text_cleaner import clean_html, clean_text_content, combine_texts

# ── Test universities ─────────────────────────────────────────────────────────

UNIVERSITIES = [
    {
        "name": "Oxford",
        "url": "https://www.ox.ac.uk/admissions/undergraduate/courses/course-listing/computer-science",
    },
    {
        "name": "Manchester",
        "url": "https://www.manchester.ac.uk/study/masters/courses/list/21573/msc-advanced-computer-science/",
    },
    {
        "name": "Harvard GSAS",
        "url": "https://gsas.harvard.edu/program/applied-physics",
    },
    {
        "name": "NUS",
        "url": "https://www.comp.nus.edu.sg/programmes/pg/mcomp/admissions/",
    },
    {
        "name": "Melbourne",
        "url": "https://study.unimelb.edu.au/find/courses/graduate/master-of-computer-science/",
    },
    {
        "name": "Toronto Rotman",
        "url": "https://www.rotman.utoronto.ca/Degrees/MBA/FullTimeMBA/Admissions",
    },
    {
        "name": "Trinity Dublin",
        "url": "https://www.tcd.ie/courses/postgraduate/az/course.php?id=DPCOM-DPTCS-1F09",
    },
    {
        "name": "UBC",
        "url": "https://www.cs.ubc.ca/students/grad/admissions",
    },
    {
        "name": "ANU",
        "url": "https://programsandcourses.anu.edu.au/program/MCOMP",
    },
]

# Fields to check for coverage
TRACKED_FIELDS = [
    "university_name",
    "program_name",
    "degree_level",
    "program_duration",
    "intake_months",
    "application_deadlines",
    "min_academic_requirement",
    "english_requirements.ielts",
    "tuition_fees.international",
    "tuition_fees.domestic",
    "scholarships",
    "other_requirements",
]


def _get_nested(result: dict, field: str):
    """Get a potentially nested field like 'english_requirements.ielts'."""
    parts = field.split(".")
    val = result
    for p in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
    return val


async def scrape_one(uni: dict) -> dict:
    """Run the full pipeline for one university. Returns result + metadata."""
    t0 = time.monotonic()
    url = uni["url"]

    try:
        # Fetch
        fetch_result = await fetch_page(url)
        if not fetch_result["html"]:
            return {"name": uni["name"], "url": url, "error": "Fetch failed",
                    "elapsed": 0, "result": {}}

        main_html = fetch_result["html"]
        final_url = fetch_result.get("final_url", url)

        # Sub-pages + PDFs
        sub_urls = extract_relevant_links(main_html, final_url)
        pdf_results = await extract_pdfs_from_page(main_html, final_url)

        sub_fetch_tasks = [fetch_page(u) for u in sub_urls]
        sub_outcomes = await asyncio.gather(*sub_fetch_tasks, return_exceptions=True)

        text_parts = [("MAIN PAGE", clean_html(main_html))]
        for sub_url, outcome in zip(sub_urls, sub_outcomes):
            if not isinstance(outcome, Exception) and outcome.get("html"):
                label = sub_url.split("/")[-1] or "SUBPAGE"
                text_parts.append((label.upper(), clean_html(outcome["html"])))

        for pdf_r in pdf_results:
            if pdf_r.get("text"):
                text_parts.append((f"PDF", clean_text_content(pdf_r["text"])))

        combined = combine_texts(text_parts)

        # Extract
        result = await extract_fields(combined, final_url)
        elapsed = time.monotonic() - t0

        return {
            "name": uni["name"],
            "url": url,
            "error": None,
            "elapsed": round(elapsed, 1),
            "sources": len(text_parts),
            "result": result,
        }

    except Exception as e:
        return {"name": uni["name"], "url": url, "error": str(e),
                "elapsed": round(time.monotonic() - t0, 1), "result": {}}


def _coverage(result: dict) -> tuple[int, int, list[str]]:
    """Return (found, total, missing_fields)."""
    found = 0
    missing = []
    for field in TRACKED_FIELDS:
        val = _get_nested(result, field)
        if val is not None and val != "" and val != []:
            found += 1
        else:
            missing.append(field)
    return found, len(TRACKED_FIELDS), missing


def _print_report(results: list[dict]):
    """Print a formatted validation report table."""
    print("\n" + "=" * 100)
    print("UNISCRAPER VALIDATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model: {settings.llm_model}")
    print("=" * 100)

    print(f"\n{'University':<18} {'Status':<10} {'Coverage':<12} {'Time':<8} {'Missing Fields'}")
    print("-" * 100)

    total_found = 0
    total_possible = 0

    for r in results:
        if r.get("error"):
            print(f"  {r['name']:<16} {'ERROR':<10} {'—':<12} {r['elapsed']:<8.1f}s  {r['error'][:50]}")
            continue

        found, total, missing = _coverage(r["result"])
        pct = int(found / total * 100)
        total_found += found
        total_possible += total

        status = "✓" if pct >= 75 else "~" if pct >= 50 else "✗"
        missing_short = ", ".join(f.split(".")[-1] for f in missing[:4])
        if len(missing) > 4:
            missing_short += f" +{len(missing)-4} more"

        print(f"  {r['name']:<16} {status:<10} {found}/{total} ({pct}%)  {r['elapsed']:<6.1f}s  {missing_short}")

    overall_pct = int(total_found / total_possible * 100) if total_possible else 0
    print("-" * 100)
    print(f"  {'OVERALL':<16} {'':10} {total_found}/{total_possible} ({overall_pct}%)")
    print("=" * 100)

    # Detailed results
    print("\n\nDETAILED RESULTS\n")
    for r in results:
        if r.get("error"):
            continue
        print(f"── {r['name']} ({r['url'][:60]})")
        res = r["result"]
        for field in TRACKED_FIELDS:
            val = _get_nested(res, field)
            label = field.split(".")[-1]
            if val:
                val_str = str(val)[:70] + ("..." if len(str(val)) > 70 else "")
                print(f"   ✓ {label:<30} {val_str}")
            else:
                print(f"   ✗ {label:<30} —")
        print()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=int, default=settings.scrape_delay_seconds,
                        help="Seconds between scrapes")
    parser.add_argument("--save", action="store_true",
                        help="Save JSON report to tests/validation/results/")
    args = parser.parse_args()

    print(f"Running validation on {len(UNIVERSITIES)} universities")
    print(f"Model: {settings.llm_model} | Delay: {args.delay}s between scrapes\n")

    results = []
    for i, uni in enumerate(UNIVERSITIES):
        if i > 0:
            print(f"\n⏳  Waiting {args.delay}s before next scrape...")
            await asyncio.sleep(args.delay)

        print(f"[{i+1}/{len(UNIVERSITIES)}] {uni['name']} — {uni['url'][:60]}")
        r = await scrape_one(uni)
        results.append(r)

        if r.get("error"):
            print(f"  ✗ Error: {r['error']}")
        else:
            found, total, _ = _coverage(r["result"])
            print(f"  ✓ {found}/{total} fields in {r['elapsed']}s")

    _print_report(results)

    if args.save:
        out_dir = Path(__file__).parent.parent / "tests" / "validation" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = out_dir / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(fname, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nReport saved to: {fname}")


if __name__ == "__main__":
    asyncio.run(main())
