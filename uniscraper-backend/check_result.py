import httpx
import json

resp = httpx.get('http://localhost:8000/api/v1/scrape/7ebb7677-575d-42bc-abf4-d17cab89edb9')
data = resp.json()

print("="*80)
print("SCRAPE RESULT ANALYSIS")
print("="*80)
print(f"Status: {data.get('status')}")
print(f"Tier: {data.get('tier_used')}")
print(f"Pages fetched: {data.get('pages_fetched')}")
print(f"Time: {data.get('execution_time_seconds')}s")

print("\n--- ENGLISH REQUIREMENTS ---")
english = data.get('english_requirements') or {}
for k, v in english.items():
    print(f"{k}: {v}")

print("\n--- TUITION FEES ---")
tuition = data.get('tuition_fees') or {}
for k, v in tuition.items():
    print(f"{k}: {v}")

# Check if there's page URLs
if 'pages_fetched_list' in data:
    print(f"\n--- PAGES ({len(data['pages_fetched_list'])}) ---")
    for i, page in enumerate(data['pages_fetched_list'][:5], 1):
        print(f"{i}. {page}")

# Check crawl4ai data
if 'metadata' in data:
    meta = data['metadata']
    print("\n--- METADATA ---")
    print(f"Crawl4AI pages: {meta.get('crawl4ai_pages_fetched')}")
    print(f"Relevant buckets: {meta.get('relevant_buckets')}")
    
print("\n--- ALL FIELDS ---")
fields = ['university_name', 'program_name', 'degree_level', 'program_duration',
          'intake_months', 'application_deadlines', 'min_academic_requirement',
          'accepted_qualifications', 'work_experience', 'other_requirements',
          'other_fees', 'scholarships']
for f in fields:
    val = data.get(f)
    if val:
        print(f"{f}: {str(val)[:100]}")
