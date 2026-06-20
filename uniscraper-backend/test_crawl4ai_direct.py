"""Test Crawl4AI directly to see if it works"""
import asyncio
import sys

async def test():
    print("Testing Crawl4AI import...")
    try:
        from crawl4ai import AsyncWebCrawler
        print("✅ Crawl4AI imported successfully")
    except Exception as e:
        print(f"❌ Crawl4AI import failed: {e}")
        return
    
    print("\nTesting tier1_crawl4ai module...")
    try:
        from pipeline.tier1_crawl4ai import fetch_single_page, deep_crawl_program_page
        print("✅ tier1_crawl4ai imported successfully")
    except Exception as e:
        print(f"❌ tier1_crawl4ai import failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\nTesting fetch_single_page...")
    try:
        url = "https://www.ed.ac.uk/studying/postgraduate/degrees/index.php?r=site/view&id=107"
        result = await fetch_single_page(url)
        print(f"✅ fetch_single_page succeeded")
        print(f"   Words: {result.get('word_count')}")
        print(f"   Has markdown: {bool(result.get('markdown'))}")
    except Exception as e:
        print(f"❌ fetch_single_page failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\nTesting deep_crawl_program_page (max 3 pages)...")
    try:
        pages = await deep_crawl_program_page(url, max_pages=3)
        print(f"✅ deep_crawl_program_page succeeded")
        print(f"   Pages returned: {len(pages)}")
        if pages:
            print(f"   First page words: {pages[0].get('word_count')}")
    except Exception as e:
        print(f"❌ deep_crawl_program_page failed: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
