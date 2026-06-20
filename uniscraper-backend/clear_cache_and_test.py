"""
Clear Arkansas State cache and run fresh scrape
"""
import asyncio
import motor.motor_asyncio
from datetime import datetime
import time
import httpx

MONGODB_URI = "mongodb+srv://s7sankalp:sankalp123@scraper.4cvnc.mongodb.net/?retryWrites=true&w=majority&appName=scraper"
DATABASE_NAME = "uniscraper"
COLLECTION_NAME = "scrape_results"

ARKANSAS_URL = "https://www.astate.edu/programs/mba-in-business-administration.html"

async def main():
    # Connect to MongoDB
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]
    
    print("="*80)
    print("CLEARING CACHE AND TESTING ARKANSAS STATE MBA")
    print("="*80)
    
    # Delete existing Arkansas State scrapes
    print(f"\n1. Deleting cached results for: {ARKANSAS_URL}")
    result = await collection.delete_many({"url_requested": ARKANSAS_URL})
    print(f"   Deleted {result.deleted_count} cached result(s)")
    
    # Start fresh scrape
    print(f"\n2. Starting fresh scrape...")
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        start = time.time()
        resp = await http_client.post(
            'http://localhost:8000/api/v1/scrape',
            json={
                "url": ARKANSAS_URL,
                "context_hint": "Fresh test with bucket architecture - post optimization"
            }
        )
        data = resp.json()
        scrape_id = data['scrape_id']
        
        if data.get('status') == 'cached':
            print(f"   ⚠️  Still cached (shouldn't happen)")
            return
        
        print(f"   Scrape ID: {scrape_id}")
        print(f"   Status: {data.get('status')}")
        print(f"\n3. Waiting for completion (polling every 5s)...")
        
        # Poll for completion
        poll_count = 0
        while time.time() - start < 240:  # 4 min timeout
            await asyncio.sleep(5)
            poll_count += 1
            
            resp = await http_client.get(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
            result = resp.json()
            status = result.get('status')
            
            print(f"   Poll #{poll_count}: status={status}", end="")
            if status in ['success', 'partial', 'failed']:
                print(" ✓")
                break
            print()
        
        if status not in ['success', 'partial', 'failed']:
            print(f"\n   ⏱  Timeout after {time.time() - start:.1f}s")
            return
        
        elapsed = time.time() - start
        
        # Display results
        print("\n" + "="*80)
        print("RESULTS - ARKANSAS STATE MBA (FRESH WITH BUCKET ARCHITECTURE)")
        print("="*80)
        
        print(f"\nStatus:         {status}")
        print(f"Time:           {elapsed:.1f}s")
        print(f"Pages:          {result.get('pages_fetched')}")
        print(f"Tier:           {result.get('tier_used')}")
        
        # Count fields
        simple_fields = [
            'university_name', 'program_name', 'degree_level', 'program_duration',
            'intake_months', 'application_deadlines', 'min_academic_requirement',
            'accepted_qualifications', 'work_experience', 'other_requirements',
            'other_fees', 'scholarships'
        ]
        non_null_simple = sum(1 for f in simple_fields if result.get(f) is not None)
        
        english = result.get('english_requirements') or {}
        english_count = sum(1 for v in english.values() if v is not None)
        
        tuition = result.get('tuition_fees') or {}
        tuition_count = sum(1 for v in tuition.values() if v is not None)
        
        total = non_null_simple + (1 if english_count > 0 else 0) + (1 if tuition_count > 0 else 0)
        
        print(f"\nFields:         {total}/15 non-null")
        print(f"  - Simple:     {non_null_simple}")
        print(f"  - English:    {english_count}/5 sub-fields")
        print(f"  - Tuition:    {tuition_count}/4 sub-fields")
        
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
        
        print("\n" + "="*80)
        print("COMPARISON TO OLD SCRAPE:")
        print("="*80)
        print("OLD (before bucket architecture):")
        print("  Time:    281.5s")
        print("  Pages:   50")
        print("  Fields:  11/15")
        print("  Tuition: null/null (USD, notes='$30')")
        print()
        print("NEW (with bucket architecture):")
        print(f"  Time:    {elapsed:.1f}s  ({((281.5-elapsed)/281.5*100):.0f}% faster)")
        print(f"  Pages:   {result.get('pages_fetched')}")
        print(f"  Fields:  {total}/15")
        print(f"  Tuition: {tuition.get('domestic')}/{tuition.get('international')}")
        
        print("\n" + "="*80)
        print("CHECK BACKEND LOGS FOR:")
        print("  - tuition_fees score distribution")
        print("  - Pages with score >= 80")
        print("  - Early exit behavior")
        print("="*80 + "\n")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
