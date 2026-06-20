#!/usr/bin/env python3
"""
Check what content we're actually getting from Arkansas State's tuition page
"""
import asyncio
from pipeline.fetcher import fetch_page

async def check_arkansas_page():
    """Fetch Arkansas State page and check for breakdown table"""
    url = "https://www.astate.edu/admissions-and-aid/tuition-and-fees/estimate-your-costs.html"
    
    print("=" * 80)
    print(f"FETCHING: {url}")
    print("=" * 80)
    
    result = await fetch_page(url)
    
    if not result.get("error") and result.get("html"):
        content = result["html"]
        
        # Check for key phrases that should be in the breakdown
        keywords = [
            "Tuition",
            "Books",
            "Room & Board",
            "Room and Board",
            "Transportation",
            "Personal",
            "Graduate Non-Resident",
            "Resident",
            "Non-Resident",
            "Total",
            "$",
        ]
        
        print("\n1. KEYWORD DETECTION:")
        for kw in keywords:
            count = content.count(kw)
            if count > 0:
                print(f"   ✅ '{kw}': {count} occurrences")
            else:
                print(f"   ❌ '{kw}': not found")
        
        # Look for table-like patterns
        print("\n2. CHECKING FOR TABLE PATTERNS:")
        if "<table" in content.lower():
            print("   ✅ HTML table detected")
        else:
            print("   ❌ No HTML table found")
        
        # Extract snippets around tuition mentions
        print("\n3. CONTENT SNIPPETS (around 'Graduate Non-Resident'):")
        idx = content.find("Graduate Non-Resident")
        if idx != -1:
            snippet = content[max(0, idx-200):min(len(content), idx+500)]
            print(f"\n{snippet}\n")
        else:
            print("   ❌ 'Graduate Non-Resident' not found in content")
        
        # Save full content for manual inspection
        with open("arkansas_page_content.txt", "w", encoding="utf-8") as f:
            f.write(content)
        print("\n4. Full content saved to: arkansas_page_content.txt")
        print(f"   Content length: {len(content)} characters")
        
    else:
        print(f"❌ Failed to fetch: {result.get('error', 'Unknown error')}")
    
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(check_arkansas_page())
