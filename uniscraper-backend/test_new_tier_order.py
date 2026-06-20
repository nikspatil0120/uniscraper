"""
Test new tier order: Custom (Tier 1) → Firecrawl (Tier 2) → Crawl4AI (Tier 3)
"""
import asyncio
import httpx
import time

URL = "https://www.astate.edu/programs/mba-in-business-administration.html"

async def test_new_tier_order():
    print("="*80)
    print("TESTING NEW TIER ORDER")
    print("="*80)
    print(f"\nURL: {URL}")
    print("\nNew tier order:")
    print("  Tier 1: Custom (httpx + Playwright)")
    print("  Tier 2: Firecrawl")
    print("  Tier 3: Crawl4AI")
    print("\nExpected: Tier 1 (custom) should handle this site")
    print("Expected time: ~90-110s (faster than previous 141.6s)")
    print("\n" + "="*80)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Start scrape
        start = time.time()
        resp = await client.post(
            'http://localhost:8000/api/v1/scrape',
            json={"url": URL, "context_hint": "Test new tier order"}
        )
        data = resp.json()
        scrape_id = data['scrape_id']
        
        if data.get('status') == 'cached':
            print(f"\n⚠️  Cached: {data.get('message')}")
            print("Clear cache first to test fresh scrape")
            return
        
        print(f"\nScrape ID: {scrape_id}")
        print("Polling every 5s...")
        print("Watch backend logs to see which tier is used!\n")
        
        # Poll for completion
        poll_count = 0
        while time.time() - start < 240:
            await asyncio.sleep(5)
            poll_count += 1
            
            resp = await client.get(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
            result = resp.json()
            status = result.get('status')
            
            if poll_count % 3 == 0:  # Every 15s
                print(f"Poll #{poll_count}: {status} ({time.time() - start:.0f}s elapsed)")
            
            if status in ['success', 'partial', 'failed']:
                print(f"\n✓ {status.upper()}!\n")
                break
        
        if status not in ['success', 'partial', 'failed']:
            print(f"\nTimeout after {time.time() - start:.1f}s")
            return
        
        elapsed = time.time() - start
        
        # Display results
        print("="*80)
        print("RESULTS")
        print("="*80)
        
        tier = result.get('tier_used', '?')
        tier_name = {1: "Custom", 2: "Firecrawl", 3: "Crawl4AI"}.get(tier, "Unknown")
        
        print(f"\nTier used:  {tier} ({tier_name})")
        print(f"Time:       {elapsed:.1f}s")
        print(f"Pages:      {result.get('pages_fetched')}")
        print(f"Status:     {status}")
        
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
        
        print(f"\nFields:     {total}/15 ({total/15*100:.0f}%)")
        print(f"  Simple:   {non_null}/12")
        print(f"  English:  {english_count}/5")
        print(f"  Tuition:  {tuition_count}/4")
        
        print(f"\n💰 TUITION:")
        print(f"  Domestic:      {tuition.get('domestic')}")
        print(f"  International: {tuition.get('international')}")
        
        print("\n" + "="*80)
        print("COMPARISON TO PREVIOUS:")
        print("="*80)
        print("PREVIOUS (Tier 1 = Crawl4AI):")
        print("  Time:    141.6s")
        print("  Tier:    1 (Crawl4AI)")
        print("  Pages:   15")
        print("  Fields:  12/15")
        print()
        print("CURRENT (Tier 1 = Custom):")
        print(f"  Time:    {elapsed:.1f}s  ({(141.6-elapsed)/141.6*100:+.0f}% change)")
        print(f"  Tier:    {tier} ({tier_name})")
        print(f"  Pages:   {result.get('pages_fetched')}")
        print(f"  Fields:  {total}/15")
        
        if tier == 1:
            print("\n✅ SUCCESS: Tier 1 (custom) handled the site!")
            if elapsed < 141.6:
                print(f"✅ FASTER: {141.6-elapsed:.1f}s improvement")
        elif tier == 3:
            print("\n⚠️  WARNING: Fell back to Tier 3 (Crawl4AI)")
            print("   Investigate why Tier 1 (custom) failed")
        
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_new_tier_order())
