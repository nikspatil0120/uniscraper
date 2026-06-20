"""
Test Manchester with new Tier 1 (custom fetcher)
"""
import asyncio
import httpx
import time

URL = "https://www.manchester.ac.uk/study/masters/courses/list/21573/msc-advanced-computer-science/"

async def test():
    print("="*80)
    print("MANCHESTER - TESTING TIER 1 CUSTOM")
    print("="*80)
    print(f"\nURL: {URL}")
    print("\nExpected: Tier 1 (custom httpx + Playwright) should handle this")
    print("\n" + "="*80)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        start = time.time()
        resp = await client.post(
            'http://localhost:8000/api/v1/scrape',
            json={"url": URL, "context_hint": "Test Tier 1 custom"}
        )
        data = resp.json()
        scrape_id = data['scrape_id']
        
        if data.get('status') == 'cached':
            print(f"\n⚠️  Cached: {data.get('message')}")
            return
        
        print(f"\nScrape ID: {scrape_id}")
        print("Watch backend logs for [tier1_custom] messages!\n")
        
        poll_count = 0
        while time.time() - start < 120:
            await asyncio.sleep(5)
            poll_count += 1
            
            resp = await client.get(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
            result = resp.json()
            status = result.get('status')
            
            if poll_count % 2 == 0:
                print(f"Poll #{poll_count}: {status}")
            
            if status in ['success', 'partial', 'failed']:
                print(f"\n✓ {status.upper()}!\n")
                break
        
        elapsed = time.time() - start
        tier = result.get('tier_used', '?')
        tier_name = {1: "Custom", 2: "Firecrawl", 3: "Crawl4AI"}.get(tier, "Unknown")
        
        print("="*80)
        print("RESULTS")
        print("="*80)
        print(f"\nTier:   {tier} ({tier_name})")
        print(f"Time:   {elapsed:.1f}s")
        print(f"Pages:  {result.get('pages_fetched')}")
        print(f"Status: {status}")
        
        if tier == 1:
            print("\n✅ SUCCESS: Tier 1 (custom) worked!")
        else:
            print(f"\n⚠️  Used Tier {tier} ({tier_name}) instead")
            print("Check backend logs for why Tier 1 failed")
        
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test())
