import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json

async def main():
    client = AsyncIOMotorClient("mongodb+srv://patilniks69_db_user:Ryussei0120@cluster0.0gpoypz.mongodb.net/")
    db = client["uniscraper"]
    collection = db["scrape_results"]
    
    result = await collection.find_one({"scrape_id": "7ebb7677-575d-42bc-abf4-d17cab89edb9"})
    
    if not result:
        print("Scrape not found")
        return
    
    print("="*80)
    print("DATABASE RECORD")
    print("="*80)
    print(f"Status: {result.get('status')}")
    print(f"Tier: {result.get('tier_used')}")
    
    # Check crawl4ai_result
    if 'crawl4ai_result' in result:
        crawl = result['crawl4ai_result']
        pages = crawl.get('pages', [])
        print(f"\nCrawl4AI pages: {len(pages)}")
        
        print("\n--- ALL PAGES ---")
        for i, page in enumerate(pages, 1):
            url = page.get('url', 'NO URL')
            wc = page.get('word_count', 0)
            depth = page.get('depth', 0)
            bucket = page.get('bucket', 'NONE')
            score = page.get('relevance_score', 0)
            print(f"{i:2d}. d={depth} w={wc:4d} b={bucket:20s} s={score:3d} | {url}")
        
        # Check english pages
        print("\n--- ENGLISH-RELATED PAGES ---")
        english_pages = [p for p in pages if 'english' in p.get('url', '').lower() 
                        or p.get('bucket') == 'english_requirements']
        if english_pages:
            for page in english_pages:
                print(f"\nURL: {page.get('url')}")
                print(f"Bucket: {page.get('bucket')}")
                print(f"Score: {page.get('relevance_score')}")
                print(f"Words: {page.get('word_count')}")
                md = page.get('markdown', '')
                if md and len(md) > 100:
                    print(f"Content preview: {md[:200]}...")
                else:
                    print(f"Content: {md}")
        else:
            print("No english-related pages found")
        
        # Check tuition pages
        print("\n--- TUITION-RELATED PAGES ---")
        tuition_pages = [p for p in pages if 'tuition' in p.get('url', '').lower() 
                        or 'fees' in p.get('url', '').lower()
                        or p.get('bucket') == 'tuition_fees']
        if tuition_pages:
            for page in tuition_pages:
                print(f"\nURL: {page.get('url')}")
                print(f"Bucket: {page.get('bucket')}")
                print(f"Score: {page.get('relevance_score')}")
                print(f"Words: {page.get('word_count')}")
        else:
            print("No tuition-related pages found")
    else:
        print("No crawl4ai_result in DB")
    
    client.close()

asyncio.run(main())
