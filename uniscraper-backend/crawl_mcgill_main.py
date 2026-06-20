"""
Crawl McGill MBA main page to see what links are actually available
"""
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
import asyncio

async def main():
    url = "https://www.mcgill.ca/desautels/programs/mba/mba-program"
    
    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    
    print("="*80)
    print(f"CRAWLING: {url}")
    print("="*80)
    
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        
        if not result.success:
            print(f"❌ Crawl failed: {result.error_message}")
            return
        
        print(f"✅ Success: {len(result.markdown)} chars\n")
        
        # Extract all links
        links = result.links.get("internal", [])
        
        print(f"Found {len(links)} internal links\n")
        
        # Filter for admission/english/requirements links
        relevant = []
        for link in links:
            href = link.get("href", "")
            text = link.get("text", "").lower()
            
            if any(kw in href.lower() for kw in ["admission", "english", "requirement", "ielts", "toefl", "language"]):
                relevant.append((href, text))
        
        if relevant:
            print(f"RELEVANT LINKS ({len(relevant)}):")
            print("="*80)
            for href, text in relevant[:20]:
                print(f"  Text: {text[:50]:50s} | {href}")
        else:
            print("No relevant links found")
        
        # Check if content mentions IELTS/TOEFL
        content_lower = result.markdown.lower()
        has_ielts = "ielts" in content_lower
        has_toefl = "toefl" in content_lower
        
        print("\n" + "="*80)
        print("MAIN PAGE CONTENT CHECK:")
        print("="*80)
        print(f"Has IELTS: {has_ielts}")
        print(f"Has TOEFL: {has_toefl}")
        
        if has_ielts or has_toefl:
            print("\n📄 Main page contains English requirements!")
            # Find the relevant section
            lines = result.markdown.split('\n')
            for i, line in enumerate(lines):
                if 'ielts' in line.lower() or 'toefl' in line.lower():
                    # Print context (5 lines before and after)
                    start = max(0, i-3)
                    end = min(len(lines), i+4)
                    print("\n".join(lines[start:end]))
                    print("---")

asyncio.run(main())
