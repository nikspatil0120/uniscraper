#!/usr/bin/env python
# scripts/seed_test_data.py
# Inserts 8 realistic mock scrape documents into MongoDB.
# Used to populate the History page during frontend development.
#
# Usage:
#   python scripts/seed_test_data.py

import asyncio
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database


def _dt(days_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


MOCK_DOCS = [
    # ── UK ──────────────────────────────────────────────────────────────────
    {
        "scrape_id": str(uuid.uuid4()),
        "status": "success",
        "created_at": _dt(1),
        "url_requested": "https://www.ed.ac.uk/studying/postgraduate/degrees/artificial-intelligence",
        "source_urls": [
            "https://www.ed.ac.uk/studying/postgraduate/degrees/artificial-intelligence",
            "https://www.ed.ac.uk/studying/postgraduate/fees",
        ],
        "university_name": "University of Edinburgh",
        "program_name": "MSc Artificial Intelligence",
        "degree_level": "Masters",
        "program_duration": "1 year full-time",
        "intake_months": ["September"],
        "application_deadlines": "Rolling admissions; early application advised",
        "min_academic_requirement": "UK 2:1 Honours degree or international equivalent",
        "accepted_qualifications": "Bachelor's degree in Computer Science, Mathematics, or related field",
        "english_requirements": {
            "ielts": "6.5 overall, minimum 6.0 in each component",
            "toefl": "92 overall, minimum 20 in each section",
            "pte": "61 overall",
            "duolingo": None,
            "notes": "IELTS Academic only; General Training not accepted",
        },
        "tuition_fees": {
            "domestic": "£13,100 per year",
            "international": "£34,800 per year",
            "currency": "GBP",
            "notes": "Fees for 2024/25 entry",
        },
        "other_fees": "£200 application fee for international students",
        "scholarships": "Edinburgh Global Research Scholarships available; Postgraduate Excellence Scholarships",
        "work_experience": None,
        "other_requirements": "Personal statement, two academic references, CV",
        "confidence_notes": None,
        "field_sources": {
            "university_name": "https://www.ed.ac.uk/studying/postgraduate/degrees/artificial-intelligence",
            "tuition_fees": "https://www.ed.ac.uk/studying/postgraduate/fees",
        },
    },
    {
        "scrape_id": str(uuid.uuid4()),
        "status": "success",
        "created_at": _dt(3),
        "url_requested": "https://www.manchester.ac.uk/study/masters/courses/list/01251/mba/",
        "source_urls": [
            "https://www.manchester.ac.uk/study/masters/courses/list/01251/mba/",
        ],
        "university_name": "University of Manchester",
        "program_name": "MBA (Master of Business Administration)",
        "degree_level": "Masters",
        "program_duration": "12 months full-time",
        "intake_months": ["September"],
        "application_deadlines": "Round 1: November 1; Round 2: January 15; Round 3: March 15",
        "min_academic_requirement": "UK 2:1 Honours degree or equivalent",
        "accepted_qualifications": "Any undergraduate degree; work experience required",
        "english_requirements": {
            "ielts": "7.0 overall, minimum 6.5 in each component",
            "toefl": "100 overall, minimum 22 in each section",
            "pte": "65 overall",
            "duolingo": None,
            "notes": None,
        },
        "tuition_fees": {
            "domestic": "£42,000 total",
            "international": "£42,000 total",
            "currency": "GBP",
            "notes": "Same fee for all students regardless of domicile",
        },
        "other_fees": "£75 application fee",
        "scholarships": "Alliance MBS Scholarships up to £10,000; Women in Business Scholarship",
        "work_experience": "Minimum 3 years post-graduation professional work experience required",
        "other_requirements": "GMAT or GRE score required; two professional references",
        "confidence_notes": None,
        "field_sources": {},
    },

    # ── USA ─────────────────────────────────────────────────────────────────
    {
        "scrape_id": str(uuid.uuid4()),
        "status": "success",
        "created_at": _dt(5),
        "url_requested": "https://www.eecs.mit.edu/academics/graduate-programs/",
        "source_urls": [
            "https://www.eecs.mit.edu/academics/graduate-programs/",
            "https://gradadmissions.mit.edu/costs-funding",
        ],
        "university_name": "Massachusetts Institute of Technology (MIT)",
        "program_name": "MEng Computer Science and Engineering",
        "degree_level": "Masters",
        "program_duration": "1 year (for MIT undergraduates); 2 years for external applicants",
        "intake_months": ["September"],
        "application_deadlines": "December 15 for September entry",
        "min_academic_requirement": "GPA 3.5/4.0 or higher strongly preferred",
        "accepted_qualifications": "Bachelor's degree in Computer Science, Electrical Engineering, or closely related field",
        "english_requirements": {
            "ielts": None,
            "toefl": "90 minimum (iBT)",
            "pte": None,
            "duolingo": None,
            "notes": "TOEFL required for non-native English speakers",
        },
        "tuition_fees": {
            "domestic": "USD 59,750 per year",
            "international": "USD 59,750 per year",
            "currency": "USD",
            "notes": "Tuition 2024–25; most students receive full funding through RA/TA positions",
        },
        "other_fees": "USD 340 student activity fee per semester",
        "scholarships": "Research Assistantships and Teaching Assistantships available covering full tuition + stipend",
        "work_experience": None,
        "other_requirements": "GRE General Test; three letters of recommendation; statement of objectives",
        "confidence_notes": None,
        "field_sources": {},
    },
    {
        "scrape_id": str(uuid.uuid4()),
        "status": "success",
        "created_at": _dt(7),
        "url_requested": "https://datascience.columbia.edu/education/programs/ms-in-data-science/",
        "source_urls": [
            "https://datascience.columbia.edu/education/programs/ms-in-data-science/",
        ],
        "university_name": "Columbia University",
        "program_name": "MS in Data Science",
        "degree_level": "Masters",
        "program_duration": "3 semesters (1.5 years) full-time",
        "intake_months": ["September", "January"],
        "application_deadlines": "Fall: February 15; Spring: October 1",
        "min_academic_requirement": "GPA 3.3/4.0 recommended",
        "accepted_qualifications": "Bachelor's degree; strong background in mathematics and programming",
        "english_requirements": {
            "ielts": "7.0 overall",
            "toefl": "101 iBT",
            "pte": None,
            "duolingo": "120",
            "notes": "Duolingo accepted for 2024 entry",
        },
        "tuition_fees": {
            "domestic": "USD 2,376 per credit (30 credits total)",
            "international": "USD 2,376 per credit (30 credits total)",
            "currency": "USD",
            "notes": "Approximately USD 71,280 total tuition",
        },
        "other_fees": "USD 2,218 student services fee per semester",
        "scholarships": "Merit scholarships available; limited departmental fellowships",
        "work_experience": None,
        "other_requirements": "GRE required; two letters of recommendation; personal statement",
        "confidence_notes": None,
        "field_sources": {},
    },

    # ── Canada ───────────────────────────────────────────────────────────────
    {
        "scrape_id": str(uuid.uuid4()),
        "status": "success",
        "created_at": _dt(10),
        "url_requested": "https://www.cs.ubc.ca/students/grad/prospective",
        "source_urls": [
            "https://www.cs.ubc.ca/students/grad/prospective",
            "https://www.grad.ubc.ca/prospective-students/tuition-fees-cost-living",
        ],
        "university_name": "University of British Columbia (UBC)",
        "program_name": "MSc Computer Science",
        "degree_level": "Masters",
        "program_duration": "2 years",
        "intake_months": ["September"],
        "application_deadlines": "December 15 for September entry",
        "min_academic_requirement": "B+ average (76%) in last two years of undergraduate study",
        "accepted_qualifications": "Bachelor's degree in Computer Science or related discipline",
        "english_requirements": {
            "ielts": "6.5 overall, no band below 6.0",
            "toefl": "90 iBT overall, minimum 22 in each section",
            "pte": None,
            "duolingo": None,
            "notes": None,
        },
        "tuition_fees": {
            "domestic": "CAD 5,515 per year",
            "international": "CAD 9,695 per year",
            "currency": "CAD",
            "notes": "2024/25 fees; most MSc students receive a minimum funding package of CAD 22,000/year",
        },
        "other_fees": "CAD 1,000 student fees per year",
        "scholarships": "Four Year Doctoral Fellowship; International Tuition Award; NSERC scholarships",
        "work_experience": None,
        "other_requirements": "Three academic references; statement of interest; CV",
        "confidence_notes": None,
        "field_sources": {},
    },
    {
        "scrape_id": str(uuid.uuid4()),
        "status": "partial",
        "created_at": _dt(14),
        "url_requested": "https://www.rotman.utoronto.ca/Degrees/MBA",
        "source_urls": [
            "https://www.rotman.utoronto.ca/Degrees/MBA",
        ],
        "university_name": "University of Toronto — Rotman School of Management",
        "program_name": "MBA",
        "degree_level": "Masters",
        "program_duration": "2 years full-time",
        "intake_months": ["September"],
        "application_deadlines": None,
        "min_academic_requirement": "B average (3.0/4.0 GPA) in final two years",
        "accepted_qualifications": "Any undergraduate degree",
        "english_requirements": {
            "ielts": "7.0 overall",
            "toefl": "100 iBT",
            "pte": None,
            "duolingo": None,
            "notes": None,
        },
        "tuition_fees": None,
        "other_fees": None,
        "scholarships": "Rotman Merit Scholarships; Forté Fellowship for women",
        "work_experience": "Minimum 2 years professional work experience required",
        "other_requirements": "GMAT or GRE; two professional references; essays",
        "confidence_notes": "Tuition fees not found on scraped page — check rotman.utoronto.ca/fees directly",
        "field_sources": {},
    },

    # ── Australia ────────────────────────────────────────────────────────────
    {
        "scrape_id": str(uuid.uuid4()),
        "status": "success",
        "created_at": _dt(18),
        "url_requested": "https://study.unimelb.edu.au/find/courses/graduate/master-of-information-technology/",
        "source_urls": [
            "https://study.unimelb.edu.au/find/courses/graduate/master-of-information-technology/",
        ],
        "university_name": "University of Melbourne",
        "program_name": "Master of Information Technology",
        "degree_level": "Masters",
        "program_duration": "2 years full-time",
        "intake_months": ["February", "July"],
        "application_deadlines": "Semester 1 (Feb): October 31; Semester 2 (Jul): April 30",
        "min_academic_requirement": "Bachelor's degree with H2B (70%) average or equivalent",
        "accepted_qualifications": "Bachelor's degree in IT, Computer Science, Engineering, or related field",
        "english_requirements": {
            "ielts": "6.5 overall, minimum 6.0 in each band",
            "toefl": "79 iBT overall, minimum 13 in each section",
            "pte": "58 overall, minimum 50 in each communicative skill",
            "duolingo": None,
            "notes": None,
        },
        "tuition_fees": {
            "domestic": "AUD 16,512 per year (Commonwealth Supported Place)",
            "international": "AUD 47,008 per year",
            "currency": "AUD",
            "notes": "2024 fees; subject to annual increase",
        },
        "other_fees": "AUD 326 student services and amenities fee per year",
        "scholarships": "Melbourne Research Scholarship; Graduate Access Melbourne bursary",
        "work_experience": None,
        "other_requirements": "Academic transcripts; English proficiency evidence; CV",
        "confidence_notes": None,
        "field_sources": {},
    },
    {
        "scrape_id": str(uuid.uuid4()),
        "status": "failed",
        "created_at": _dt(22),
        "url_requested": "https://programsandcourses.anu.edu.au/program/MSCCO",
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
        "field_sources": {},
        "error": "Connection timeout after 30s — site may be blocking automated requests",
    },
]


async def seed():
    print("Connecting to MongoDB...")
    ok = await database.ping()
    if not ok:
        print("✗ Could not connect to MongoDB. Check MONGODB_URI in .env")
        sys.exit(1)

    col = database.scrape_results_collection

    # Remove any existing seed data to avoid duplicates on re-run
    existing_ids = [doc["scrape_id"] for doc in MOCK_DOCS]
    await col.delete_many({"scrape_id": {"$in": existing_ids}})

    result = await col.insert_many(MOCK_DOCS)
    count = len(result.inserted_ids)

    print(f"✓ Inserted {count} mock scrape documents")
    print("  Breakdown:")
    for doc in MOCK_DOCS:
        name = doc.get("university_name") or "(failed)"
        prog = doc.get("program_name") or ""
        print(f"    [{doc['status']:8}] {name} — {prog}")

    print("\nSeed complete. Open /history in the dashboard to verify.")


if __name__ == "__main__":
    asyncio.run(seed())
