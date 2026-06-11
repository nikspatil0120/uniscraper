"""
Test script to diagnose tuition extraction issues.
Tests Arkansas State MBA to see:
1. What pages are being discovered
2. What relevance scores they get for tuition_fees field
3. What content is being sent to the LLM
4. What the LLM extracts
"""
import asyncio
import sys
from pipeline.intelligent_fetcher import fetch_subpages_intelligent
from pipeline.ai_extractor import extract_fields, calculate_page_relevance_score, build_field_specific_context
from utils.page_classifier import classify_page
from config import settings

async def test_arkansas_state():
    url = "https://www.astate.edu/programs/mba-in-business-administration.html"
    
    print("=" * 80)
    print("ARKANSAS STATE MBA TUITION EXTRACTION TEST")
    print("=" * 80)
    
    # Step 1: Fetch all pages
    print("\n[1] Fetching pages...")
    all_pages = await fetch_subpages_intelligent(url, max_pages=settings.max_subpages)
    
    if not all_pages:
        print("ERROR: No pages fetched!")
        return
    
    print(f"\n✓ Fetched {len(all_pages)} pages")
    
    # Step 2: Build pages_data structure
    pages_data = []
    for page in all_pages:
        content = page.get("content") or page.get("markdown") or ""
        if not content or len(content.split()) < 30:
            continue
        
        page_url = page.get("url", url)
        page_type = page.get("page_type") or classify_page(page_url, content)
        
        pages_data.append({
            "url": page_url,
            "content": content,
            "page_type": page_type,
            "word_count": len(content.split()),
        })
    
    print(f"✓ {len(pages_data)} pages have sufficient content")
    
    # Step 3: Check tuition page discovery
    print("\n" + "=" * 80)
    print("[2] TUITION PAGE DISCOVERY")
    print("=" * 80)
    
    tuition_pages = [p for p in pages_data if any(kw in p['url'].lower() for kw in ['tuition', 'fees', 'cost'])]
    
    if tuition_pages:
        print(f"\n✓ Found {len(tuition_pages)} tuition-related page(s):")
        for p in tuition_pages:
            print(f"\n  URL: {p['url']}")
            print(f"  Type: {p['page_type']}")
            print(f"  Words: {p['word_count']}")
            print(f"  Preview: {p['content'][:200]}...")
    else:
        print("\n✗ NO tuition-related pages discovered!")
    
    # Step 4: Calculate relevance scores
    print("\n" + "=" * 80)
    print("[3] RELEVANCE SCORING FOR TUITION_FEES")
    print("=" * 80)
    
    scored_pages = []
    for page in pages_data:
        score = calculate_page_relevance_score(page, "tuition_fees")
        scored_pages.append((score, page))
    
    scored_pages.sort(key=lambda x: x[0], reverse=True)
    
    print("\nTop 5 pages by relevance score:")
    for i, (score, page) in enumerate(scored_pages[:5], 1):
        url_short = page['url'][-60:]
        print(f"{i}. Score: {score:3d} | {url_short}")
        print(f"   Type: {page['page_type']} | Words: {page['word_count']}")
    
    # Step 5: Build field-specific context
    print("\n" + "=" * 80)
    print("[4] FIELD-SPECIFIC CONTEXT BUILDING")
    print("=" * 80)
    
    fees_context = build_field_specific_context(pages_data, "tuition_fees", max_chars=10000)
    
    print(f"\n✓ Built tuition fees context: {len(fees_context)} chars")
    
    # Check if tuition page content is in the context
    if tuition_pages:
        tuition_url = tuition_pages[0]['url']
        if tuition_url in fees_context:
            print(f"✓ Tuition page IS included in context")
        else:
            print(f"✗ Tuition page NOT in context (may have been outscored)")
    
    # Show what's in the context
    print("\nContext preview (first 500 chars):")
    print("-" * 80)
    print(fees_context[:500])
    print("-" * 80)
    
    # Step 6: Run regex extraction on fees context
    print("\n" + "=" * 80)
    print("[5] REGEX PRE-EXTRACTION")
    print("=" * 80)
    
    from pipeline.regex_extractor import extract_regex_hints
    hints = extract_regex_hints(fees_context)
    
    print("\nRegex findings:")
    for key, value in hints.items():
        if value and 'fee' in key.lower():
            print(f"  {key}: {value}")
    
    # Step 7: Full extraction (DISABLED to save API quota - uncomment to test)
    print("\n" + "=" * 80)
    print("[6] LLM EXTRACTION (SKIPPED - uncomment to test)")
    print("=" * 80)
    print("\nTo test full LLM extraction, uncomment the code below in this script.")
    
    # UNCOMMENT TO TEST FULL EXTRACTION:
    # combined = "\n\n".join([f"=== {p['url']} ===\n{p['content']}" for p in pages_data])
    # result = await extract_fields(combined, url, "", pages_data, content_format="markdown")
    # print("\nExtraction result:")
    # print(f"  Tuition fees: {result.get('tuition_fees')}")
    # print(f"  Model used: {result.get('_model_used', 'unknown')}")

if __name__ == "__main__":
    asyncio.run(test_arkansas_state())
