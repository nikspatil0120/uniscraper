"""
Comprehensive test script for bucket-based architecture.

Tests multiple universities to validate:
1. Threshold appropriateness (is 80 correct?)
2. Information completeness (more fields extracted?)
3. Speed consistency (is early exit working?)
4. Robustness (diverse university structures)

Universities to test:
- Arkansas State (US, credit-hour based)
- Melbourne (AU, different structure)
- Edinburgh (UK, traditional)
- McGill (CA, bilingual)
- Harvard MBA (US, prestigious)
- Manchester (UK, large)
"""
import asyncio
import time
from datetime import datetime
import httpx

API_BASE = "http://localhost:8000/api/v1"

TEST_UNIVERSITIES = [
    {
        "name": "Arkansas State MBA",
        "url": "https://www.astate.edu/programs/mba-in-business-administration.html",
        "expected": "US format, credit-hour based tuition"
    },
    {
        "name": "Melbourne MBA", 
        "url": "https://www.monash.edu/study/courses/find-a-course/2025/business-analytics-b6024",
        "expected": "AU format, complex site structure"
    },
    {
        "name": "Edinburgh MSc",
        "url": "https://www.ed.ac.uk/studying/postgraduate/degrees/index.php?r=site/view&id=108",
        "expected": "UK format, traditional structure"
    },
    {
        "name": "McGill MBA",
        "url": "https://www.mcgill.ca/desautels/programs/mba/mba-program",
        "expected": "CA format, bilingual content"
    },
]


async def start_scrape(url: str, name: str) -> str:
    """Start a scrape and return scrape_id"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{API_BASE}/scrape",
            json={"url": url, "context_hint": f"Test scrape for {name}"}
        )
        data = response.json()
        
        if data.get("status") == "cached":
            print(f"  ⚠️  Using cached result from {data.get('message', 'earlier')}")
        
        return data["scrape_id"]


async def wait_for_completion(scrape_id: str, timeout: int = 300) -> dict:
    """Poll for scrape completion"""
    start = time.time()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        while time.time() - start < timeout:
            try:
                response = await client.get(f"{API_BASE}/scrape/{scrape_id}")
                result = response.json()
                
                status = result.get("status")
                if status in ["success", "partial", "failed"]:
                    return result
                
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"    Error polling: {e}")
                await asyncio.sleep(5)
    
    return {"status": "timeout"}


def analyze_result(result: dict, university_name: str):
    """Analyze and print key metrics"""
    status = result.get("status", "unknown")
    elapsed = result.get("elapsed_seconds", 0)
    pages = result.get("pages_fetched", 0)
    tier = result.get("tier_used", "?")
    
    # Count non-null fields
    fields_to_check = [
        "university_name", "program_name", "degree_level", "program_duration",
        "intake_months", "application_deadlines", "min_academic_requirement",
        "accepted_qualifications", "work_experience", "other_requirements",
        "other_fees", "scholarships"
    ]
    
    non_null_simple = sum(1 for f in fields_to_check if result.get(f) is not None)
    
    # Check structured fields
    english = result.get("english_requirements") or {}
    english_fields = sum(1 for v in english.values() if v is not None)
    
    tuition = result.get("tuition_fees") or {}
    tuition_fields = sum(1 for v in tuition.values() if v is not None)
    
    total_fields = non_null_simple + (1 if english_fields > 0 else 0) + (1 if tuition_fields > 0 else 0)
    
    print(f"\n{'='*80}")
    print(f"📊 {university_name}")
    print(f"{'='*80}")
    print(f"Status:         {status}")
    print(f"Time:           {elapsed:.1f}s")
    print(f"Pages:          {pages}")
    print(f"Tier:           {tier}")
    print(f"Fields:         {total_fields}/15 non-null")
    print(f"  - Simple:     {non_null_simple}")
    print(f"  - English:    {english_fields}/5 sub-fields")
    print(f"  - Tuition:    {tuition_fields}/4 sub-fields")
    
    # Show critical fields
    print(f"\n🎓 PROGRAM:")
    print(f"  University:   {result.get('university_name', 'NOT FOUND')}")
    print(f"  Program:      {result.get('program_name', 'NOT FOUND')}")
    print(f"  Duration:     {result.get('program_duration', 'NOT FOUND')}")
    print(f"  Intake:       {result.get('intake_months', 'NOT FOUND')}")
    
    print(f"\n💰 TUITION:")
    print(f"  Domestic:     {tuition.get('domestic', 'NOT FOUND')}")
    print(f"  International:{tuition.get('international', 'NOT FOUND')}")
    print(f"  Currency:     {tuition.get('currency', 'NOT FOUND')}")
    print(f"  Notes:        {tuition.get('notes', 'NOT FOUND')}")
    
    print(f"\n🌍 ENGLISH:")
    print(f"  IELTS:        {english.get('ielts', 'NOT FOUND')}")
    print(f"  TOEFL:        {english.get('toefl', 'NOT FOUND')}")
    print(f"  PTE:          {english.get('pte', 'NOT FOUND')}")
    
    print(f"\n📅 ADMISSION:")
    print(f"  Deadlines:    {result.get('application_deadlines', 'NOT FOUND')}")
    print(f"  Min Academic: {result.get('min_academic_requirement', 'NOT FOUND')}")
    print(f"  Scholarships: {result.get('scholarships', 'NOT FOUND')}")
    
    return {
        "name": university_name,
        "status": status,
        "elapsed": elapsed,
        "pages": pages,
        "tier": tier,
        "total_fields": total_fields,
        "simple_fields": non_null_simple,
        "english_fields": english_fields,
        "tuition_fields": tuition_fields,
    }


async def run_tests():
    """Run all tests and generate report"""
    print("\n" + "="*80)
    print("🧪 BUCKET ARCHITECTURE VALIDATION TEST")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing {len(TEST_UNIVERSITIES)} universities")
    print("="*80)
    
    results = []
    
    for i, uni in enumerate(TEST_UNIVERSITIES, 1):
        print(f"\n[{i}/{len(TEST_UNIVERSITIES)}] 🎯 Testing: {uni['name']}")
        print(f"  URL: {uni['url']}")
        print(f"  Expected: {uni['expected']}")
        
        try:
            # Start scrape
            scrape_id = await start_scrape(uni['url'], uni['name'])
            print(f"  Scrape ID: {scrape_id}")
            print(f"  Waiting for completion...")
            
            # Wait for result
            result = await wait_for_completion(scrape_id)
            
            # Analyze
            metrics = analyze_result(result, uni['name'])
            results.append(metrics)
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append({
                "name": uni['name'],
                "status": "error",
                "error": str(e)
            })
    
    # Generate summary report
    print("\n" + "="*80)
    print("📈 SUMMARY REPORT")
    print("="*80)
    
    print("\n| University | Status | Time | Pages | Fields | English | Tuition |")
    print("|------------|--------|------|-------|--------|---------|---------|")
    
    for r in results:
        if r.get("status") == "error":
            print(f"| {r['name'][:20]:20s} | ERROR  | -    | -     | -      | -       | -       |")
        else:
            print(
                f"| {r['name'][:20]:20s} | "
                f"{r['status']:7s} | "
                f"{r['elapsed']:4.0f}s | "
                f"{r['pages']:5d} | "
                f"{r['total_fields']:2d}/15  | "
                f"{r['english_fields']:1d}/5     | "
                f"{r['tuition_fields']:1d}/4     |"
            )
    
    # Calculate averages
    valid_results = [r for r in results if r.get("status") != "error"]
    if valid_results:
        avg_time = sum(r['elapsed'] for r in valid_results) / len(valid_results)
        avg_pages = sum(r['pages'] for r in valid_results) / len(valid_results)
        avg_fields = sum(r['total_fields'] for r in valid_results) / len(valid_results)
        
        print("\n📊 AVERAGES:")
        print(f"  Time:   {avg_time:.1f}s")
        print(f"  Pages:  {avg_pages:.1f}")
        print(f"  Fields: {avg_fields:.1f}/15 ({avg_fields/15*100:.0f}%)")
    
    # Success rate
    success_count = sum(1 for r in results if r.get("status") in ["success", "partial"])
    success_rate = success_count / len(results) * 100 if results else 0
    
    print(f"\n✅ Success Rate: {success_count}/{len(results)} ({success_rate:.0f}%)")
    
    print("\n" + "="*80)
    print("🏁 TEST COMPLETE")
    print("="*80)
    print("\n💡 NEXT STEPS:")
    print("1. Check backend logs for score distributions")
    print("2. Look for pattern: 'score distribution: >=200:X | >=150:Y | >=100:Z | >=80:W'")
    print("3. Analyze if threshold=80 is appropriate or needs adjustment")
    print("4. Compare field counts before/after bucket architecture")
    print("\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
