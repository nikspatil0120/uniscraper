import httpx
import time
import asyncio

async def test():
    url = "https://www.ed.ac.uk/studying/postgraduate/degrees/index.php?r=site/view&id=107"
    
    print("Testing Edinburgh MBA...")
    print(f"URL: {url}\n")
    
    async with httpx.AsyncClient(timeout=300) as client:
        # Start scrape
        resp = await client.post('http://localhost:8000/api/v1/scrape', json={'url': url})
        data = resp.json()
        scrape_id = data['scrape_id']
        
        print(f"Scrape ID: {scrape_id}")
        if data.get('status') == 'cached':
            print(f"CACHED: {data.get('message')}")
            scrape_id = data.get('cached_from', scrape_id)
        
        print("Polling...\n")
        
        # Poll
        start = time.time()
        while time.time() - start < 300:
            await asyncio.sleep(5)
            resp = await client.get(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
            result = resp.json()
            status = result.get('status')
            
            if status in ['success', 'partial', 'failed']:
                break
        
        elapsed = time.time() - start
        tier = result.get('tier_used')
        
        print("\nRESULTS:")
        print(f"Status: {status}")
        print(f"Tier: {tier}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Pages: {result.get('pages_fetched')}")
        
        english = result.get('english_requirements') or {}
        english_count = sum(1 for v in english.values() if v)
        
        tuition = result.get('tuition_fees') or {}
        tuition_count = sum(1 for v in tuition.values() if v)
        
        print(f"\nEnglish: {english_count}/5")
        for k, v in english.items():
            if v:
                print(f"  {k}: {str(v)[:80]}")
        
        print(f"\nTuition: {tuition_count}/4")
        for k, v in tuition.items():
            if v:
                print(f"  {k}: {str(v)[:80]}")
        
        if tier == 1:
            print("\n✅ Tier 1 active")
        else:
            print(f"\n❌ Tier {tier} (expected 1)")
        
        if english_count >= 2:
            print("✅ English improved (2+ fields)")
        else:
            print(f"❌ English still needs work ({english_count}/5)")

asyncio.run(test())
