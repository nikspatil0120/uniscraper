#!/usr/bin/env python3
"""
Test the gap detection and targeted recrawl system.

This simulates a scenario where first pass misses critical fields,
then gap analysis suggests additional pages to fetch.
"""
import asyncio
from pipeline.gap_analyzer import analyze_missing_fields, build_candidate_urls
from pipeline.targeted_recrawl import check_existing_pages_for_content


async def test_gap_detection():
    print("=" * 80)
    print("TEST 1: Gap Detection with Missing Fields")
    print("=" * 80)
    
    # Simulated first-pass extraction with missing fields
    extracted_data = {
        "university_name": "Example University",
        "program_name": "Master of Science in Computer Science",
        "degree_level": "Master's",
        "program_duration": "2 years",
        "tuition_fees": None,  # MISSING
        "english_requirements": None,  # MISSING
        "application_deadlines": "Rolling admissions",
        "min_academic_requirement": None,  # MISSING
    }
    
    # Simulated pages from first pass
    pages_data = [
        {
            "url": "https://example.com/programs/cs/overview",
            "page_type": "overview",
            "content": "Master of Science in Computer Science is a 2-year program...",
            "word_count": 500,
        },
        {
            "url": "https://example.com/programs/cs/curriculum",
            "page_type": "curriculum",
            "content": "The curriculum includes advanced algorithms, machine learning...",
            "word_count": 800,
        },
    ]
    
    base_url = "https://example.com/programs/cs"
    
    # Run gap analysis
    gap_analysis = await analyze_missing_fields(extracted_data, pages_data, base_url)
    
    print(f"\n📊 Gap Analysis Results:")
    print(f"   Needs recrawl: {gap_analysis['needs_recrawl']}")
    print(f"   Missing fields: {gap_analysis['missing_fields']}")
    print(f"   Suggested page types: {gap_analysis['suggested_page_types']}")
    print(f"   Reasoning: {gap_analysis['reasoning']}")
    
    # Generate candidate URLs
    if gap_analysis["needs_recrawl"]:
        print(f"\n🔗 Candidate URLs:")
        candidates = build_candidate_urls(base_url, gap_analysis["suggested_page_types"])
        for i, url in enumerate(candidates[:10], 1):
            print(f"   {i}. {url}")
    
    print("\n" + "=" * 80)
    print("TEST 2: No Missing Fields")
    print("=" * 80)
    
    # All fields present
    complete_data = {
        "university_name": "Example University",
        "program_name": "Master of Science in Computer Science",
        "tuition_fees": {"international": "$30,000", "currency": "USD"},
        "english_requirements": {"ielts": "6.5", "toefl": "90"},
        "application_deadlines": "January 15, 2027",
        "min_academic_requirement": "Bachelor's degree with 3.0 GPA",
    }
    
    gap_analysis2 = await analyze_missing_fields(complete_data, pages_data, base_url)
    
    print(f"\n📊 Gap Analysis Results:")
    print(f"   Needs recrawl: {gap_analysis2['needs_recrawl']}")
    print(f"   Missing fields: {gap_analysis2['missing_fields']}")
    print(f"   Reasoning: {gap_analysis2['reasoning']}")
    
    print("\n" + "=" * 80)
    print("TEST 3: Check Existing Pages for Content")
    print("=" * 80)
    
    # Simulated pages that might contain the missing data
    pages_with_content = [
        {
            "url": "https://example.com/programs/cs/overview",
            "content": "Program overview with general information...",
        },
        {
            "url": "https://example.com/admissions/requirements",
            "content": "IELTS 6.5 overall, TOEFL iBT 90. Minimum GPA 3.0 required.",
        },
        {
            "url": "https://example.com/fees",
            "content": "Tuition fees for international students: $30,000 per year. Domestic: $15,000.",
        },
    ]
    
    missing_fields = ["tuition_fees", "english_requirements", "min_academic_requirement"]
    found_in = await check_existing_pages_for_content(pages_with_content, missing_fields)
    
    print(f"\n🔍 Content Found in Existing Pages:")
    for field, url in found_in.items():
        print(f"   ✅ {field}: {url}")
    
    not_found = [f for f in missing_fields if f not in found_in]
    if not_found:
        print(f"\n   ❌ Still missing: {', '.join(not_found)}")
    
    print("\n" + "=" * 80)
    print("✅ All tests complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_gap_detection())
