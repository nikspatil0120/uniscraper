import httpx
import json

resp = httpx.get('http://localhost:8000/api/v1/scrape/e6992fc9-e2c6-4ae6-b27c-05a80858b270')
data = resp.json()

print("="*80)
print("ARKANSAS STATE SCRAPE RESULT")
print("="*80)
print(f"Status: {data.get('status')}")
print(f"Message: {data.get('message')}")
print(f"Tier: {data.get('tier_used')}")
print(f"Pages: {data.get('pages_fetched')}")
print(f"Time: {data.get('execution_time_seconds')}s")

if 'error' in data:
    print(f"\n❌ ERROR: {data['error']}")

if 'error_message' in data:
    print(f"\n❌ ERROR MESSAGE: {data['error_message']}")

# Check what fields were extracted
fields_extracted = []
for key in ['university_name', 'program_name', 'degree_level', 'program_duration',
            'intake_months', 'application_deadlines']:
    if data.get(key):
        fields_extracted.append(key)

print(f"\nFields extracted: {len(fields_extracted)}")
for f in fields_extracted:
    print(f"  ✓ {f}: {str(data[f])[:80]}")

# Check English and Tuition
print("\nEnglish requirements:")
english = data.get('english_requirements') or {}
for k, v in english.items():
    print(f"  {k}: {v}")

print("\nTuition fees:")
tuition = data.get('tuition_fees') or {}
for k, v in tuition.items():
    print(f"  {k}: {v}")
