import httpx
import json
import asyncio

async def check_mcgill():
    """Check McGill MBA extraction results"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get('http://localhost:8000/api/v1/scrape/071fec5f-257b-414c-a38b-f26a1fbdf9c9')
        data = resp.json()
        
        print("="*80)
        print("McGILL MBA EXTRACTION RESULTS")
        print("="*80)
        
        print(f"\nStatus: {data.get('status')}")
        print(f"Pages: {data.get('pages_fetched')}")
        print(f"Time: {data.get('elapsed_seconds')}s")
        
        print("\n--- TUITION FEES ---")
        tuition = data.get('tuition_fees', {})
        print(json.dumps(tuition, indent=2))
        
        print("\n--- ENGLISH REQUIREMENTS ---")
        english = data.get('english_requirements', {})
        print(json.dumps(english, indent=2))
        
        print("\n--- BASIC FIELDS ---")
        print(f"University: {data.get('university_name')}")
        print(f"Program: {data.get('program_name')}")
        print(f"Duration: {data.get('program_duration')}")
        print(f"Intake: {data.get('intake_months')}")
        print(f"Deadlines: {data.get('application_deadlines')}")
        
        print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(check_mcgill())
