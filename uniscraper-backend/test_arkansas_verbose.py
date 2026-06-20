"""
Test Arkansas State with verbose logging to see what's happening
"""
import asyncio
import httpx
import time

ARKANSAS_URL = "https://www.astate.edu/programs/mba"

async def main():
    print("="*80)
    print("ARKANSAS STATE - VERBOSE TEST")
    print("="*80)
    print(f"URL: {ARKANSAS_URL}\n")
    
    # Delete cache first
    print("Clearing Arkansas cache...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get('http://localhost:8000/api/v1/scrapes?limit=100')
            scrapes = resp.json()
            
            deleted_count = 0
            for scrape in scrapes:
                if 'astate.edu' in scrape.get('url_requested', '').lower():
                    scrape_id = scrape.get('scrape_id')
                    try:
                        await client.delete(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
                        deleted_count += 1
                    except:
                        pass
            
            print(f"Deleted {deleted_count} cached result(s)\n")
    except Exception as e:
        print(f"Cache clear failed: {e}\n")
    
    print("Starting scrape (watch backend console for logs)...\n")
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        start = time.time()
        resp = await client.post(
            'http://localhost:8000/api/v1/scrape',
            json={"url": ARKANSAS_URL}
        )
        data = resp.json()
        scrape_id = data['scrape_id']
        
        print(f"Scrape ID: {scrape_id}")
        print("Polling...\n")
        
        while time.time() - start < 240:
            await asyncio.sleep(5)
            resp = await client.get(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
            result = resp.json()
            status = result.get('status')
            
            if status in ['success', 'partial', 'failed']:
                break
        
        elapsed = time.time() - start
        
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)
        print(f"Status: {status}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Pages: {result.get('pages_fetched')}")
        
        # English requirements
        english = result.get('english_requirements') or {}
        english_count = sum(1 for v in english.values() if v is not None and v != "")
        
        print(f"\nEnglish: {english_count}/5")
        for k, v in english.items():
            if v:
                print(f"  {k}: {v}")
        
        # Tuition
        tuition = result.get('tuition_fees') or {}
        tuition_count = sum(1 for v in tuition.values() if v is not None and v != "")
        
        print(f"\nTuition: {tuition_count}/4")
        for k, v in tuition.items():
            if v:
                print(f"  {k}: {v}")
        
        print("\n" + "="*80)
        print("CHECK BACKEND CONSOLE FOR:")
        print("="*80)
        print("1. 'DUPLICATE CONTENT' warnings")
        print("2. 'english_requirements - ALL PAGE SCORES'")
        print("3. English pages with score 260+ (150 boost)")
        print("4. 'sending X chars to Gemini (gemini-2.5-flash)'")
        print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
