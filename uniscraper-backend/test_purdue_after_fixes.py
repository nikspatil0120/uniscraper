"""
Test Purdue discovery after critical fixes:
1. Removed overly broad /graduate/ filter
2. Increased SerpAPI: 10 -> 30 results per query
3. Expanded queries: 2 -> 6 targeted searches

Expected improvements:
- Before: 19 candidates -> 11 programs
- After:  100-150 candidates -> 50-100+ programs
"""

import asyncio
import logging

from pipeline.program_discovery import discover_programs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

async def main():
    print("=" * 80)
    print("PURDUE DISCOVERY TEST - After Critical Fixes")
    print("=" * 80)
    print()
    print("Testing fixes:")
    print("1. ✅ Removed /graduate/ filter (was blocking /graduate/programs/...)")
    print("2. ✅ Increased SerpAPI: 10 -> 30 results per query")
    print("3. ✅ Expanded queries: 2 -> 6 targeted searches")
    print("4. ✅ Firecrawl fallback for 202/403/429 status codes")
    print()
    print("Expected improvements:")
    print("- Candidates: 19 -> 100-150+")
    print("- Programs:   11 -> 50-100+")
    print()
    print("=" * 80)
    print()
    
    result = await discover_programs(
        domain="purdue.edu",
        university_name="Purdue University",
        max_programs=500,
    )
    
    # Handle both list and dict return types
    if isinstance(result, list):
        programs = result
        timings = {}
    else:
        programs = result.get("programs", [])
        timings = result.get("timings", {})
    
    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total programs discovered: {len(programs)}")
    print()
    
    # Analyze degree distribution
    from collections import Counter
    degree_counts = Counter(p["degree_level"] for p in programs)
    
    print("Degree Distribution:")
    for degree, count in degree_counts.most_common():
        print(f"  {degree}: {count}")
    print()
    
    # Show first 20 programs
    print("First 20 Programs:")
    for i, prog in enumerate(programs[:20], 1):
        print(f"  {i}. {prog['program_name'][:50]:50} | {prog['degree_level']:12} | {prog.get('confidence', 0):.2f}")
    
    if len(programs) > 20:
        print(f"  ... and {len(programs) - 20} more")
    print()
    
    # Check for catalog pages
    catalog_urls = [p["url"] for p in programs if "catalog.purdue.edu" in p["url"]]
    if catalog_urls:
        print(f"✅ Found {len(catalog_urls)} programs from catalog.purdue.edu")
        print("   (Firecrawl fallback working!)")
    else:
        print("⚠️  No catalog.purdue.edu programs found")
        print("   (Check if Firecrawl fallback triggered)")
    print()
    
    # Check for /graduate/ URLs
    graduate_urls = [p["url"] for p in programs if "/graduate/" in p["url"]]
    if graduate_urls:
        print(f"✅ Found {len(graduate_urls)} programs with /graduate/ in URL")
        print("   (Filter fix working!)")
        print("   Examples:")
        for url in graduate_urls[:3]:
            print(f"     {url}")
    else:
        print("⚠️  No /graduate/ URLs found")
        print("   (May be normal if Purdue doesn't use /graduate/ paths)")
    print()
    
    print("=" * 80)
    print()
    
    # Performance metrics
    if timings:
        print("Performance Metrics:")
        total_time = timings.get("total_duration", 0)
        print(f"  Total time: {total_time:.1f}s")
        
        if "auto_confirm_phase" in timings:
            print(f"  Auto-confirm: {timings['auto_confirm_phase']:.1f}s")
        if "gemini_classify_phase" in timings:
            print(f"  Gemini classify: {timings['gemini_classify_phase']:.1f}s")
        print()
    
    print("Check backend logs for:")
    print("  1. [serpapi_client] query='...' returned X URLs")
    print("     (Should see 6 queries with ~20-30 results each)")
    print("  2. [serpapi_client] program_pages total: X unique URLs")
    print("     (Should be ~100-150, up from 19)")
    print("  3. [program_discovery] HTTPX 202 detected... trying Firecrawl")
    print("     (If catalog.purdue.edu pages are fetched)")
    print("  4. [program_discovery] Processing: .../graduate/programs/...")
    print("     (Should NOT see filtered as junk)")
    print()

if __name__ == "__main__":
    asyncio.run(main())
