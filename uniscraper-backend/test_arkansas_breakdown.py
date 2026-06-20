#!/usr/bin/env python3
"""
Test Arkansas State scrape to validate breakdown field extraction
"""
import requests
import time
import json

API_BASE = "http://localhost:8000/api/v1"
# Using the "estimate-your-costs" page directly since it has the breakdown table
ARKANSAS_URL = "https://www.astate.edu/admissions-and-aid/tuition-and-fees/estimate-your-costs.html"

def test_arkansas_breakdown():
    """Test that Arkansas State breakdown field is extracted properly"""
    print("=" * 80)
    print("TESTING ARKANSAS STATE - COST BREAKDOWN FIELD")
    print("=" * 80)
    
    # Start scrape
    print(f"\n1. Starting scrape: {ARKANSAS_URL}")
    resp = requests.post(f"{API_BASE}/scrape", json={
        "url": ARKANSAS_URL,
        "context_hint": "Arkansas State University Graduate Programs"
    })
    data = resp.json()
    scrape_id = data["scrape_id"]
    print(f"   Scrape ID: {scrape_id}")
    
    # Poll for completion
    print("\n2. Polling for completion...")
    max_wait = 300  # 5 minutes
    start = time.time()
    
    while time.time() - start < max_wait:
        resp = requests.get(f"{API_BASE}/scrape/{scrape_id}")
        result = resp.json()
        status = result["status"]
        
        elapsed = time.time() - start
        print(f"   [{elapsed:.1f}s] Status: {status}", end="")
        
        if status in ["success", "partial", "failed"]:
            print(" ✓")
            break
        
        print(" ⏳")
        time.sleep(5)
    
    # Check results
    print("\n3. Checking results...")
    print(f"   Status: {result['status']}")
    print(f"   University: {result.get('university_name', 'N/A')}")
    print(f"   Tier used: {result.get('tier_used', 'N/A')}")
    print(f"   Pages fetched: {result.get('pages_fetched', 'N/A')}")
    print(f"   Elapsed: {result.get('elapsed_seconds', 'N/A')}s")
    
    # Check tuition fees
    print("\n4. Tuition Fees:")
    fees = result.get("tuition_fees")
    if fees:
        print(f"   Domestic: {fees.get('domestic', 'N/A')}")
        print(f"   International: {fees.get('international', 'N/A')}")
        print(f"   Currency: {fees.get('currency', 'N/A')}")
        print(f"   Breakdown: {fees.get('breakdown', 'N/A')}")
        print(f"   Notes: {fees.get('notes', 'N/A')}")
    else:
        print("   ❌ No tuition fees extracted")
    
    # Detailed breakdown check
    print("\n5. Breakdown Field Analysis:")
    breakdown = fees.get('breakdown') if fees else None
    if breakdown and breakdown != "N/A":
        print(f"   ✅ BREAKDOWN EXTRACTED: {breakdown}")
    else:
        print("   ❌ NO BREAKDOWN EXTRACTED")
        print("\n   This means either:")
        print("   - The LLM didn't extract it (prompt issue)")
        print("   - The page structure changed")
        print("   - The tier didn't fetch the right page")
    
    # Save full result to file
    print("\n6. Saving full result to arkansas_breakdown_result.json")
    with open("arkansas_breakdown_result.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print("\n" + "=" * 80)
    return result

if __name__ == "__main__":
    result = test_arkansas_breakdown()
