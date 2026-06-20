"""
Test script to reproduce the Playwright error on Windows
"""
import asyncio
from playwright.async_api import async_playwright

async def test_playwright():
    print("Starting Playwright test...")
    print(f"Python version: 3.12.10")
    print(f"Playwright version: 1.60.0")
    print(f"Windows: 11 Pro Build 26200")
    print()
    
    try:
        async with async_playwright() as p:
            print("✓ Playwright context created")
            
            print("Launching Chromium browser...")
            browser = await p.chromium.launch(headless=True)
            print("✓ Browser launched successfully!")
            
            page = await browser.new_page()
            print("✓ New page created")
            
            print("Navigating to test URL...")
            await page.goto("https://example.com")
            print(f"✓ Page loaded: {await page.title()}")
            
            await browser.close()
            print("✓ Browser closed successfully")
            print("\n🎉 All Playwright operations completed successfully!")
            
    except NotImplementedError as e:
        print(f"\n❌ NotImplementedError: {e}")
        print("\nThis error occurs because:")
        print("- Windows asyncio.create_subprocess_exec() is not implemented")
        print("- in ProactorEventLoop (default on Windows)")
        print("\nFull traceback:")
        import traceback
        traceback.print_exc()
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_playwright())
