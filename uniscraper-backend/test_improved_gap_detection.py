#!/usr/bin/env python3
"""
Test improved gap detection logic that checks critical sub-fields.
"""
import asyncio
from pipeline.gap_analyzer import analyze_missing_fields


async def test_anu_scenario():
    """Test with ANU-like data where english_requirements has only notes"""
    print("=" * 80)
    print("TEST: ANU Scenario - English requirements with notes but no scores")
    print("=" * 80)
    
    # ANU-like extraction result
    extracted_data = {
        "university_name": "Australian National University",
        "program_name": "Graduate Certificate of Applied Data Analytics",
        "tuition_fees": {
            "domestic": "AUD 4,330",
            "international": None,
            "currency": "AUD",
            "notes": "CSP fees for domestic students"
        },
        "english_requirements": {
            "ielts": None,
            "toefl": None,
            "pte": None,
            "duolingo": None,
            "notes": "All applicants must meet the University's English Language Admission Requirements."
        },
        "application_deadlines": "Not accepting 2026 admissions",
        "min_academic_requirement": "Bachelor degree with minimum GPA 4.0/7.0",
    }
    
    pages_data = [
        {"url": "https://anu.edu.au/program/overview", "page_type": "overview"},
        {"url": "https://anu.edu.au/program/admissions", "page_type": "admissions"},
    ]
    
    base_url = "https://anu.edu.au/program"
    
    gap_analysis = await analyze_missing_fields(extracted_data, pages_data, base_url)
    
    print(f"\n📊 Gap Analysis Results:")
    print(f"   Needs recrawl: {gap_analysis['needs_recrawl']}")
    print(f"   Missing fields: {gap_analysis['missing_fields']}")
    print(f"   Suggested page types: {gap_analysis['suggested_page_types']}")
    print(f"   Reasoning: {gap_analysis['reasoning']}")
    
    # Verify english_requirements is detected as missing
    if "english_requirements" in gap_analysis["missing_fields"]:
        print("\n✅ SUCCESS: Detected missing english_requirements (notes present, but no scores)")
    else:
        print("\n❌ FAILED: Should have detected missing english_requirements")
    
    print("\n" + "=" * 80)


async def test_complete_scenario():
    """Test with complete data - should not trigger recrawl"""
    print("\nTEST: Complete Data - Should NOT trigger recrawl")
    print("=" * 80)
    
    extracted_data = {
        "university_name": "Test University",
        "tuition_fees": {
            "domestic": "$10,000",
            "international": "$20,000",
            "currency": "USD"
        },
        "english_requirements": {
            "ielts": "6.5 overall",
            "toefl": "90 iBT",
            "pte": None,
            "duolingo": None,
            "notes": "Additional requirements..."
        },
        "application_deadlines": "January 15, 2027",
        "min_academic_requirement": "Bachelor degree",
    }
    
    pages_data = [{"url": "https://test.edu/program", "page_type": "overview"}]
    base_url = "https://test.edu/program"
    
    gap_analysis = await analyze_missing_fields(extracted_data, pages_data, base_url)
    
    print(f"\n📊 Gap Analysis Results:")
    print(f"   Needs recrawl: {gap_analysis['needs_recrawl']}")
    print(f"   Missing fields: {gap_analysis['missing_fields']}")
    
    if not gap_analysis["needs_recrawl"]:
        print("\n✅ SUCCESS: Correctly skipped recrawl (has IELTS and TOEFL)")
    else:
        print("\n❌ FAILED: Should not have triggered recrawl")
    
    print("\n" + "=" * 80)


async def test_only_notes_scenario():
    """Test with ONLY notes field filled - should trigger"""
    print("\nTEST: Only Notes - Should trigger recrawl")
    print("=" * 80)
    
    extracted_data = {
        "tuition_fees": {
            "domestic": "$10,000",
            "international": "$20,000",
        },
        "english_requirements": {
            "ielts": None,
            "toefl": None,
            "pte": None,
            "duolingo": None,
            "notes": "Contact admissions for requirements"
        },
        "application_deadlines": None,
        "min_academic_requirement": "Bachelor degree",
    }
    
    pages_data = []
    base_url = "https://test.edu"
    
    gap_analysis = await analyze_missing_fields(extracted_data, pages_data, base_url)
    
    print(f"\n📊 Gap Analysis Results:")
    print(f"   Missing: {gap_analysis['missing_fields']}")
    
    if "english_requirements" in gap_analysis["missing_fields"]:
        print("\n✅ SUCCESS: Correctly detected missing scores (only notes present)")
    else:
        print("\n❌ FAILED: Should detect missing english scores")
    
    print("\n" + "=" * 80)


async def main():
    await test_anu_scenario()
    await test_complete_scenario()
    await test_only_notes_scenario()
    print("\n✅ All tests complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
