"""
Simple Arkansas State MBA fresh scrape test
"""
import asyncio
import httpx
import time
import json

URL = "https://www.astate.edu/programs/mba-in-business-administration.html"

async def main():
    print("="*80)
    print("ARKANSAS STATE MBA - FRESH SCRAPE TEST")
    print("="*80)
    print(f"\nURL: {URL}")
    print("Expected: ~90-120s, ~20 pages, improved tuition extraction\n")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Start scrape
        start = time.time()
        resp = await client.post(
            'http://localhost:8000/api/v1/scrape',
            json={"url": URL, "context_hint": "Fresh test with bucket architecture"}
        )
        data = resp.json()
        scrape_id = data['scrape_id']
        
        if data.get('status') == 'cached':
            print(f"⚠️  Still cached: {data.get('message')}")
            return
        
        print(f"Scrape ID: {scrape_id}")
        print("Polling every 5s...\n")
        
        # Poll for completion
        poll_count = 0
        while time.time() - start < 240:
            await asyncio.sleep(5)
            poll_count += 1
            
            resp = await client.get(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
            result = resp.json()
            status = result.get('status')
            
            print(f"Poll #{poll_count}: {status}", end="")
            if status in ['success', 'partial', 'failed']:
                print(" ✓\n")
                break
            print()
        
        if status not in ['success', 'partial', 'failed']:
            print(f"\nTimeout after {time.time() - start:.1f}s")
            return
        
        elapsed = time.time() - start
        
        # Display results
        print("="*80)
        print("RESULTS")
        print("="*80)
        
        print(f"\nStatus:    {status}")
        print(f"Time:      {elapsed:.1f}s")
        print(f"Pages:     {result.get('pages_fetched')}")
        print(f"Tier:      {result.get('tier_used')}")
        
        # Count fields
        simple = ['university_name', 'program_name', 'degree_level', 'program_duration',
                  'intake_months', 'application_deadlines', 'min_academic_requirement',
                  'accepted_qualifications', 'work_experience', 'other_requirements',
                  'other_fees', 'scholarships']
        non_null = sum(1 for f in simple if result.get(f) is not None)
        
        english = result.get('english_requirements') or {}
        english_count = sum(1 for v in english.values() if v is not None)
        
        tuition = result.get('tuition_fees') or {}
        tuition_count = sum(1 for v in tuition.values() if v is not None)
        
        total = non_null + (1 if english_count > 0 else 0) + (1 if tuition_count > 0 else 0)
        
        print(f"\nFields:    {total}/15 ({total/15*100:.0f}%)")
        print(f"  Simple:  {non_null}/12")
        print(f"  English: {english_count}/5")
        print(f"  Tuition: {tuition_count}/4")
        
        print(f"\n💰 TUITION:")
        print(f"  Domestic:      {tuition.get('domestic')}")
        print(f"  International: {tuition.get('international')}")
        print(f"  Currency:      {tuition.get('currency')}")
        print(f"  Notes:         {tuition.get('notes')}")
        
        print(f"\n🌍 ENGLISH:")
        print(f"  IELTS: {english.get('ielts')}")
        print(f"  TOEFL: {english.get('toefl')}")
        print(f"  PTE:   {english.get('pte')}")
        
        print(f"\n📚 PROGRAM:")
        print(f"  University: {result.get('university_name')}")
        print(f"  Program:    {result.get('program_name')}")
        print(f"  Duration:   {result.get('program_duration')}")
        print(f"  Intake:     {result.get('intake_months')}")
        print(f"  Deadlines:  {result.get('application_deadlines')}")
        
        print("\n" + "="*80)
        print("COMPARISON:")
        print("="*80)
        print("OLD (cached, pre-optimization):")
        print("  Time:    281.5s")
        print("  Pages:   50")
        print("  Fields:  11/15 (73%)")
        print("  Tuition: null/null (notes='$30')")
        print()
        print("NEW (fresh, with bucket architecture):")
        print(f"  Time:    {elapsed:.1f}s  ({((281.5-elapsed)/281.5*100):.0f}% faster)")
        print(f"  Pages:   {result.get('pages_fetched')} ({((50-result.get('pages_fetched'))/50*100):.0f}% reduction)")
        print(f"  Fields:  {total}/15 ({total/15*100:.0f}%)")
        print(f"  Tuition: {tuition.get('domestic')}/{tuition.get('international')}")
        
        if total >= 11:
            print("\n✅ Field count maintained or improved!")
        else:
            print(f"\n⚠️  Field count decreased ({total} vs 11)")
        
        print("\n" + "="*80)
        print("Check backend logs for score distributions!")
        print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
