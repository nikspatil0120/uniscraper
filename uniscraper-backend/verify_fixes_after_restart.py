"""
Verification script to run AFTER restarting the backend server.
This will test if all English requirements fixes are working.
"""
import asyncio
import httpx
import time

# Test with Edinburgh - known to have English requirements pages
TEST_URL = "https://www.ed.ac.uk/studying/postgraduate/degrees/index.php?r=site/view&id=107"
UNIVERSITY_NAME = "Edinburgh"

async def main():
    print("="*80)
    print("ENGLISH REQUIREMENTS FIX - VERIFICATION TEST")
    print("="*80)
    print(f"\nUniversity: {UNIVERSITY_NAME}")
    print(f"URL: {TEST_URL}")
    print("\nPre-flight checks:")
    print("  [ ] Backend server restarted")
    print("  [ ] MongoDB cache cleared")
    print("  [ ] Config shows gemini-2.5-flash (not flash-lite)")
    print("\n" + "="*80)
    
    input("Press ENTER when ready to start test...")
    
    # Clear any existing cache for this university
    print("\nClearing cache...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get('http://localhost:8000/api/v1/scrapes?limit=100')
            scrapes = resp.json()
            
            deleted_count = 0
            for scrape in scrapes:
                url = scrape.get('url_requested', '').lower()
                if 'ed.ac.uk' in url and 'id=107' in url:
                    scrape_id = scrape.get('scrape_id')
                    try:
                        await client.delete(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
                        deleted_count += 1
                    except:
                        pass
            
            print(f"Deleted {deleted_count} cached result(s)")
    except Exception as e:
        print(f"Cache clear failed: {e}")
    
    print(f"\nStarting {UNIVERSITY_NAME} scrape...")
    print("⏳ Watch backend console for log messages...\n")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        start = time.time()
        resp = await client.post(
            'http://localhost:8000/api/v1/scrape',
            json={"url": TEST_URL}
        )
        data = resp.json()
        scrape_id = data['scrape_id']
        
        print(f"Scrape ID: {scrape_id}")
        print("Polling every 5s...\n")
        
        # Poll for completion
        poll_count = 0
        while time.time() - start < 300:
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
        print("VERIFICATION RESULTS")
        print("="*80)
        
        tier = result.get('tier_used')
        print(f"\nStatus:    {status}")
        print(f"Tier:      {tier}")
        print(f"Time:      {elapsed:.1f}s")
        print(f"Pages:     {result.get('pages_fetched')}")
        
        # CRITICAL: Check if Tier 1 was used
        if tier != 1:
            print(f"\n❌ FAILED: Using Tier {tier} instead of Tier 1 (Crawl4AI)")
            print("   This means the backend server wasn't restarted or Crawl4AI is disabled.")
            print("   Our fixes only work with Tier 1 (Crawl4AI).")
            return
        
        print("✅ PASS: Using Tier 1 (Crawl4AI) - fixes are active!")
        
        # Check English requirements
        english = result.get('english_requirements') or {}
        english_count = sum(1 for v in english.values() if v is not None and v != "")
        
        print(f"\n🌍 ENGLISH REQUIREMENTS:")
        print(f"  IELTS:    {english.get('ielts')}")
        print(f"  TOEFL:    {english.get('toefl')}")
        print(f"  PTE:      {english.get('pte')}")
        print(f"  Duolingo: {english.get('duolingo')}")
        print(f"  Notes:    {english.get('notes')}")
        print(f"\n  Extracted: {english_count}/5 sub-fields")
        
        if english_count >= 2:
            print("  ✅ PASS - At least 2 sub-fields extracted!")
        elif english_count == 1:
            print("  ⚠️  PARTIAL - Only 1 sub-field")
        else:
            print("  ❌ FAIL - No english requirements extracted")
        
        # Check tuition (baseline)
        tuition = result.get('tuition_fees') or {}
        tuition_count = sum(1 for v in tuition.values() if v is not None and v != "")
        
        print(f"\n💰 TUITION FEES:")
        print(f"  Domestic:      {tuition.get('domestic')}")
        print(f"  International: {tuition.get('international')}")
        print(f"  Extracted: {tuition_count}/4 sub-fields")
        
        # Overall assessment
        print("\n" + "="*80)
        print("BACKEND LOG VERIFICATION CHECKLIST")
        print("="*80)
        print("Go to your backend console and verify you see:")
        print()
        print("1. ✓ [tier1_crawl4ai] Exhaustive BFS crawl starting...")
        print("     (Confirms Tier 1 is active)")
        print()
        print("2. ✓ [tier1_crawl4ai] DUPLICATE CONTENT: ...skipping")
        print("     (Confirms duplicate detection is working)")
        print()
        print("3. ✓ [ai_extractor] english_requirements - ALL PAGE SCORES:")
        print("       #1 score=260+ (or similar high score for english pages)")
        print("     (Confirms +150 scoring boost is working)")
        print()
        print("4. ✓ [ai_extractor] english_requirements: included 2-3/X pages, 9000-10000 chars")
        print("     (Confirms budget increase from 6000 to 10000 is working)")
        print()
        print("5. ✓ sending: X chars to Gemini (gemini-2.5-flash)")
        print("     NOT: (gemini-2.5-flash-lite)")
        print("     (Confirms model upgrade is working)")
        print()
        print("="*80)
        
        if tier == 1 and english_count >= 2:
            print("\n🎉 VERIFICATION SUCCESSFUL!")
            print("   All fixes are working. Ready to commit and push to GitHub.")
        elif tier == 1 and english_count >= 1:
            print("\n⚠️  PARTIAL SUCCESS")
            print("   Tier 1 is active but extraction needs improvement.")
            print("   Check backend logs for scoring and budget details.")
        else:
            print("\n❌ VERIFICATION FAILED")
            print("   Review backend logs to diagnose the issue.")

if __name__ == "__main__":
    asyncio.run(main())
