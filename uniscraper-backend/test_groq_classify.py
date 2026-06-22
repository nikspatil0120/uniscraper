import asyncio, sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from pipeline.program_discovery import _call_groq_classify, gemini_classify_candidates

async def test():
    print("=== Testing Groq direct classification ===")
    batch = [
        {"index": 0, "url": "https://astate.edu/programs/ms-in-computer-science.html",
         "title": "MS in Computer Science | Arkansas State",
         "snippet": "Graduate program preparing students for careers in software engineering and research."},
        {"index": 1, "url": "https://astate.edu/programs/mba-in-marketing.html",
         "title": "MBA in Marketing | Arkansas State",
         "snippet": "Professional MBA program with a marketing concentration."},
        {"index": 2, "url": "https://astate.edu/about/campus.html",
         "title": "Campus Life | Arkansas State",
         "snippet": "Student life resources, housing, and campus activities."},
        {"index": 3, "url": "https://astate.edu/programs/ma-in-sociology.html",
         "title": "MA in Sociology | Arkansas State",
         "snippet": "Master of Arts in Sociology with thesis and non-thesis options."},
    ]
    results = await _call_groq_classify(batch)
    print(f"Got {len(results)} results:")
    for r in results:
        prog = r.get("is_program")
        name = r.get("program_name")
        level = r.get("degree_level")
        conf = r.get("confidence")
        print(f"  is_program={prog} level={level} conf={conf} name={name}")

    print()
    print("=== Testing via gemini_classify_candidates with Groq fallback ===")
    # Use 3 real URLs — Gemini is quota-exhausted so should fall through to Groq
    candidates = [
        "https://astate.edu/programs/ms-in-computer-science.html",
        "https://astate.edu/programs/mba-in-marketing.html",
        "https://astate.edu/programs/ma-in-sociology.html",
    ]
    programs, status = await gemini_classify_candidates(candidates, "Arkansas State University", batch_size=3)
    print(f"Status: {status}, programs: {len(programs)}")
    for p in programs:
        print(f"  [{p['degree_level']:12s}] {p['program_name']}")

asyncio.run(test())
