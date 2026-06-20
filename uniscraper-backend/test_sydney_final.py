"""
Final verification test with University of Sydney MBA
Tests all fixes after removing fake URL construction
"""
import asyncio
import httpx
import time

SYDNEY_URL = "https://www.sydney.edu.au/courses/courses/pc/master-of-business-administration.html"

async def main():
    print("="*80)
    print("FINAL VERIFICATION TEST - UNIVERSITY OF SYDNEY MBA")
    print("="*80)
    print(f"\nURL: {SYDNEY_URL}")
    print("\n✅ FIXES IMPLEMENTED:")
    print("1. Scoring boost: +150 for english-requirements pages")
    print("2. Budget increase: 6000 → 10000 chars for English")
    print("3. Duplicate detection: word count + first 200 chars")
    print("4. Model upgrade: flash-lite → flash")
    print("5. REMOVED fake URL construction (root cause of Tier 2 fallback)")
    print("\n" + "="*80)
    
    input("Press ENTER to start (make sure backend is restarted)...")
    
    # Clear Sydney cache
    print("\nClearing Sydney cache...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get('http://localhost:8000/api/v1/scrapes?limit=100')
            scrapes = resp.json()
            
            deleted_count = 0
            for scrape in scrapes:
                if 'sydney.edu.au' in scrape.get('url_requested', '').lower():
                    scrape_id = scrape.get('scrape_id')
                    try:
                        await client.delete(f'http://localhost:8000/api/v1/scrape/{scrape_id}')
                        deleted_count += 1
                    except:
                        pass
            
            print(f"Deleted {deleted_count} cached result(s)")
    except Exception as e:
        print(f"Cache clear failed (continuing): {e}")
    
    print(f"\nStarting Sydney scrape...")
    print("⏳ This should take 2-3 minutes without fake URL timeouts...\n")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        start = time.time()
        resp = await client.post(
            'http://localhost:8000/api/v1/scrape',
            json={"url": SYDNEY_URL}
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
            print(f"\n⏱️ Timeout after {time.time() - start:.1f}s")
            return
        
        elapsed = time.time() - start
        tier = result.get('tier_used')
        
        # Display results
        print("="*80)
        print("FINAL VERIFICATION RESULTS")
        print("="*80)
        
        print(f"\n📊 SCRAPE METADATA:")
        print(f"  Status:    {status}")
        print(f"  Tier:      {tier}")
        print(f"  Time:      {elapsed:.1f}s")
        print(f"  Pages:     {result.get('pages_fetched')}")
        
        # CRITICAL: Check Tier 1
        if tier != 1:
            print(f"\n❌ CRITICAL FAILURE: Using Tier {tier} instead of Tier 1")
            print("   This means Crawl4AI is still failing or disabled.")
            print("   Check backend console for Crawl4AI errors.")
            return
        
        print("\n✅ TIER 1 ACTIVE - All fixes are being applied!")
        
        # Check English requirements
        english = result.get('english_requirements') or {}
        english_count = sum(1 for v in english.values() if v is not None and v != "")
        
        print(f"\n🌍 ENGLISH REQUIREMENTS:")
        print(f"  IELTS:    {english.get('ielts')}")
        print(f"  TOEFL:    {english.get('toefl')}")
        print(f"  PTE:      {english.get('pte')}")
        print(f"  Duolingo: {english.get('duolingo')}")
        notes = english.get('notes', '')
        if notes:
            print(f"  Notes:    {notes[:100]}...")
        
        print(f"\n  Extracted: {english_count}/5 sub-fields")
        
        if english_count >= 2:
            print("  ✅ SUCCESS - At least 2 english sub-fields extracted!")
        elif english_count == 1:
            print("  ⚠️  PARTIAL - Only 1 sub-field (notes only?)")
        else:
            print("  ❌ FAILED - No english requirements extracted")
        
        # Check tuition
        tuition = result.get('tuition_fees') or {}
        tuition_count = sum(1 for v in tuition.values() if v is not None and v != "")
        
        print(f"\n💰 TUITION FEES:")
        print(f"  Domestic:      {tuition.get('domestic')}")
        print(f"  International: {tuition.get('international')}")
        print(f"  Currency:      {tuition.get('currency')}")
        print(f"\n  Extracted: {tuition_count}/4 sub-fields")
        
        if tuition_count >= 2:
            print("  ✅ GOOD - At least 2 tuition sub-fields extracted")
        else:
            print("  ⚠️  Needs improvement")
        
        # Overall assessment
        simple_fields = ['university_name', 'program_name', 'degree_level', 'program_duration',
                        'intake_months', 'application_deadlines', 'min_academic_requirement',
                        'accepted_qualifications', 'work_experience', 'other_requirements',
                        'other_fees', 'scholarships']
        non_null = sum(1 for f in simple_fields if result.get(f) is not None)
        total = non_null + (1 if english_count > 0 else 0) + (1 if tuition_count > 0 else 0)
        
        print(f"\n📈 OVERALL EXTRACTION:")
        print(f"  Total fields: {total}/15 ({total/15*100:.0f}%)")
        
        # Time comparison
        print(f"\n⏱️  SPEED:")
        print(f"  Completed in {elapsed:.1f}s")
        if elapsed < 150:
            print("  ✅ FAST - No 30s timeout delays!")
        else:
            print("  ⚠️  Still slow - check for other issues")
        
        # Backend log checklist
        print("\n" + "="*80)
        print("BACKEND CONSOLE VERIFICATION")
        print("="*80)
        print("\n✓ Check backend logs for:")
        print()
        print("1. [tier1_crawl4ai] Exhaustive BFS crawl starting...")
        print("   (Confirms Tier 1 is active)")
        print()
        print("2. [tier1_crawl4ai] Depth X — .../... OK (X words, X links)")
        print("   Should see ONLY real links being followed")
        print("   Should NOT see fake URLs like /entry-requirements or /english-requirements")
        print()
        print("3. [tier1_crawl4ai] DUPLICATE CONTENT: ... — skipping")
        print("   (If applicable, confirms duplicate detection working)")
        print()
        print("4. [ai_extractor] english_requirements - ALL PAGE SCORES:")
        print("   Should see score=260+ for english-requirements pages")
        print("   (Confirms +150 scoring boost working)")
        print()
        print("5. [ai_extractor] english_requirements: included X/Y pages, 9000-10000 chars")
        print("   (Confirms budget increase from 6000 to 10000)")
        print()
        print("6. sending: X chars to Gemini (gemini-2.5-flash)")
        print("   NOT: (gemini-2.5-flash-lite)")
        print("   (Confirms model upgrade)")
        print()
        print("="*80)
        
        # Final verdict
        print("\n" + "="*80)
        print("FINAL VERDICT")
        print("="*80)
        
        if tier == 1 and english_count >= 2 and elapsed < 150:
            print("\n🎉 ✅ ALL TESTS PASSED!")
            print("   ✓ Tier 1 active (Crawl4AI)")
            print("   ✓ English extraction improved (2+ fields)")
            print("   ✓ No fake URL timeouts")
            print("   ✓ All fixes working")
            print("\n   READY TO COMMIT AND PUSH TO GITHUB!")
            
        elif tier == 1 and english_count >= 1:
            print("\n⚠️  PARTIAL SUCCESS")
            print("   ✓ Tier 1 active")
            print("   ⚠️  English extraction partial (1 field)")
            print("   → Review backend logs for scoring details")
            print("   → May need additional prompt improvements")
            
        elif tier == 1 and elapsed < 150:
            print("\n⚠️  TIER 1 WORKING BUT EXTRACTION NEEDS WORK")
            print("   ✓ No fake URL timeouts (speed improved)")
            print("   ✓ Tier 1 active")
            print("   ⚠️  English extraction still 0/5")
            print("   → Check if Sydney page actually has IELTS scores")
            print("   → Review LLM prompt and extraction logic")
            
        else:
            print("\n❌ TESTS FAILED")
            print(f"   Tier: {tier} (expected: 1)")
            print(f"   English: {english_count}/5")
            print(f"   Time: {elapsed:.1f}s")
            print("   → Review backend console for errors")

if __name__ == "__main__":
    asyncio.run(main())
