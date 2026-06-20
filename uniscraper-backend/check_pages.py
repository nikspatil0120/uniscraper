import httpx
import json

resp = httpx.get('http://localhost:8000/api/v1/scrape/7ebb7677-575d-42bc-abf4-d17cab89edb9')
data = resp.json()

# Check the raw crawl4ai result
if 'crawl4ai_result' in data:
    print("="*80)
    print("CRAWL4AI PAGES DISCOVERED")
    print("="*80)
    
    pages = data['crawl4ai_result'].get('pages', [])
    print(f"Total pages: {len(pages)}\n")
    
    for i, page in enumerate(pages, 1):
        url = page.get('url', 'NO URL')
        wc = page.get('word_count', 0)
        depth = page.get('depth', 0)
        print(f"{i:2d}. depth={depth} words={wc:4d} | {url}")
    
    # Now check bucket classifications
    print("\n" + "="*80)
    print("BUCKET CLASSIFICATIONS")
    print("="*80)
    
    for i, page in enumerate(pages, 1):
        url = page.get('url', '')
        bucket = page.get('bucket', 'NONE')
        score = page.get('relevance_score', 0)
        if bucket != 'irrelevant':
            print(f"{i:2d}. score={score:3d} bucket={bucket:20s} | {url}")
    
    # Check if any english-requirements pages
    print("\n" + "="*80)
    print("ENGLISH REQUIREMENTS PAGES")
    print("="*80)
    
    english_pages = [p for p in pages if 'english' in p.get('url', '').lower()]
    if english_pages:
        for page in english_pages:
            print(f"URL: {page.get('url')}")
            print(f"Bucket: {page.get('bucket')}")
            print(f"Score: {page.get('relevance_score')}")
            print(f"Words: {page.get('word_count')}")
            print(f"Preview: {page.get('markdown', '')[:200]}")
            print()
    else:
        print("No pages with 'english' in URL found")
        
        # Check by bucket instead
        bucket_pages = [p for p in pages if p.get('bucket') == 'english_requirements']
        if bucket_pages:
            print(f"\nFound {len(bucket_pages)} in english_requirements bucket:")
            for page in bucket_pages:
                print(f"  {page.get('url')} (score={page.get('relevance_score')})")
        else:
            print("No pages in english_requirements bucket")
else:
    print("No crawl4ai_result in response")
