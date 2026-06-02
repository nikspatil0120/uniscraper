import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.fetcher import fetch_page

async def main():
    url = "https://programsandcourses.anu.edu.au/program/MCOMP"
    print(f"Testing: {url}")
    result = await fetch_page(url)
    print(f"Method:  {result['method_used']}")
    print(f"Words:   {result['word_count']}")
    print(f"Error:   {result['error']}")
    if result['word_count'] > 200:
        print("SUCCESS — Playwright is working!")
    else:
        print("FAIL — still getting thin content")

asyncio.run(main())
