"""
Quick API test to trigger Arkansas State MBA scrape and monitor results
"""
import requests
import time
import json

# Trigger scrape
url = "http://localhost:8000/scrape"
payload = {
    "url": "https://www.astate.edu/programs/mba-in-business-administration.html",
    "context_hint": "MBA program"
}

print("=" * 80)
print("ARKANSAS STATE MBA SCRAPE TEST")
print("=" * 80)
print(f"\n[1] Triggering scrape: {payload['url']}")

response = requests.post(url, json=payload)
data = response.json()

scrape_id = data.get("scrape_id")
print(f"✓ Scrape started: {scrape_id}")

# Poll for results
print(f"\n[2] Monitoring progress...")
start_time = time.time()
last_status = None

while True:
    try:
        result_response = requests.get(f"http://localhost:8000/result/{scrape_id}")
        result = result_response.json()
        
        status = result.get("status")
        
        if status != last_status:
            elapsed = time.time() - start_time
            print(f"  [{elapsed:.0f}s] Status: {status}")
            last_status = status
        
        if status in ["success", "failed", "partial"]:
            elapsed = time.time() - start_time
            print(f"\n[3] COMPLETE in {elapsed:.1f}s")
            print("=" * 80)
            
            # Display key results
            print("\nRESULTS:")
            print(f"  Status: {status}")
            print(f"  University: {result.get('university_name')}")
            print(f"  Program: {result.get('program_name')}")
            print(f"  Pages fetched: {result.get('pages_fetched')}")
            print(f"  Tier used: {result.get('tier_used')}")
            print(f"  Method: {result.get('method_used')}")
            
            # CRITICAL: Tuition fees
            tuition = result.get('tuition_fees', {})
            print(f"\n  TUITION FEES:")
            print(f"    Domestic: {tuition.get('domestic')}")
            print(f"    International: {tuition.get('international')}")
            print(f"    Currency: {tuition.get('currency')}")
            print(f"    Notes: {tuition.get('notes')}")
            
            # Other key fields
            english = result.get('english_requirements', {})
            print(f"\n  ENGLISH REQUIREMENTS:")
            print(f"    IELTS: {english.get('ielts')}")
            print(f"    TOEFL: {english.get('toefl')}")
            
            print(f"\n  Duration: {result.get('program_duration')}")
            print(f"  Intake: {result.get('intake_months')}")
            print(f"  Deadlines: {result.get('application_deadlines')}")
            
            # Source URLs
            source_urls = result.get('source_urls', [])
            print(f"\n  SOURCE URLS ({len(source_urls)}):")
            for i, src_url in enumerate(source_urls[:5], 1):
                url_short = src_url[-60:] if len(src_url) > 60 else src_url
                print(f"    {i}. {url_short}")
            if len(source_urls) > 5:
                print(f"    ... and {len(source_urls) - 5} more")
            
            # Check for tuition page
            tuition_urls = [u for u in source_urls if 'tuition' in u.lower() or 'fees' in u.lower()]
            if tuition_urls:
                print(f"\n  ✓ TUITION PAGES DISCOVERED:")
                for tu in tuition_urls:
                    print(f"    - {tu}")
            else:
                print(f"\n  ✗ NO tuition-specific pages in source URLs")
            
            print("\n" + "=" * 80)
            break
            
        time.sleep(2)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        break
    except Exception as e:
        print(f"\n  Error polling: {e}")
        time.sleep(2)
