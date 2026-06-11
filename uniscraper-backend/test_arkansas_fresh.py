"""
Test Arkansas State MBA with fresh scrape (no cache)
This will help us see if the bucket architecture improves extraction
"""
import httpx
import asyncio
import time
import json

URL = "https://www.astate.edu/programs/mba-in-business-administration.html"

async def test_arkansas():
    print("="*80)
    print("ARKANSAS STATE MBA - FRESH SCRAPE TEST")
    print("="*80)
    print(f"\nURL: {URL}")
    print("This will take ~90-120 seconds...")
    print("\nStarting scrape...\n")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Start scrape
        start = time.time()
        resp = await client.post(
            'http://localhost:8000/api/v1/scrape',
            json={
                "url": URL,
                "context_hint": "Fresh test of bucket architecture",
                "force_refresh": True  # Force bypass cache
            }
        )
        data = resp.json()
        scrape_id = data['scrape_id']
        
        if data.get('status') == 'cached':
            print("⚠️  Still using cache. Need to clear cache first.")
            print(f"Cached from: {data.get('message', 'earlier')}")
            return
        
        print(f"Scrape ID: {scrape_id}")
        print("Waiting for completion...\n")
        
        # Poll for completion
        while time.time() - start < 180:  # 3 min timeout
            await asyncio.sleep(5)
            resp = await client.get(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
            result = resp.json()
            
            status = result.get('status')
            if status in ['success', 'partial', 'failed']:
                elapsed = time.time() - start
                
                print("="*80)
                print("RESULTS")
                print("="*80)
                print(f"\nStatus: {status}")
                print(f"Time: {elapsed:.1f}s")
                print(f"Pages: {result.get('pages_fetched')}")
                print(f"Tier: {result.get('tier_used')}")
                
                print("\n--- TUITION FEES ---")
                tuition = result.get('tuition_fees', {})
                print(json.dumps(tuition, indent=2))
                
                print("\n--- ENGLISH REQUIREMENTS ---")
                english = result.get('english_requirements', {})
                print(json.dumps(english, indent=2))
                
                print("\n--- BASIC PROGRAM INFO ---")
                print(f"University: {result.get('university_name')}")
                print(f"Program: {result.get('program_name')}")
                print(f"Duration: {result.get('program_duration')}")
                print(f"Intake: {result.get('intake_months')}")
                
                # Count non-null fields
                all_fields = [
                    'university_name', 'program_name', 'degree_level', 'program_duration',
                    'intake_months', 'application_deadlines', 'min_academic_requirement',
                    'accepted_qualifications', 'work_experience', 'other_requirements',
                    'other_fees', 'scholarships'
                ]
                non_null = sum(1 for f in all_fields if result.get(f) is not None)
                english_count = sum(1 for v in english.values() if v is not None)
                tuition_count = sum(1 for v in tuition.values() if v is not None)
                
                total = non_null + (1 if english_count > 0 else 0) + (1 if tuition_count > 0 else 0)
                
                print(f"\n--- FIELD COUNT ---")
                print(f"Total: {total}/15 fields")
                print(f"Simple: {non_null}")
                print(f"English: {english_count}/5 sub-fields")
                print(f"Tuition: {tuition_count}/4 sub-fields")
                
                print("\n" + "="*80)
                print("CHECK BACKEND LOGS FOR:")
                print("- Score distributions for tuition_fees field")
                print("- Pages included in extraction")
                print("- Early exit behavior")
                print("="*80)
                
                return
        
        print("⏱  Timeout waiting for scrape to complete")

if __name__ == "__main__":
    asyncio.run(test_arkansas())
