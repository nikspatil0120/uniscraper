"""
Check what's in the McGill admissions page
"""
import httpx
import re

url = "https://www.mcgill.ca/desautels/programs/mba/admissions"

resp = httpx.get(url, timeout=10.0, follow_redirects=True)

print("="*80)
print(f"MCGILL ADMISSIONS PAGE: {url}")
print("="*80)
print(f"Status: {resp.status_code}")
print(f"Length: {len(resp.text)} chars\n")

# Extract IELTS scores
ielts_pattern = r'ielts[:\s]+(\d+\.?\d*)'
ielts_matches = re.findall(ielts_pattern, resp.text.lower())
if ielts_matches:
    print(f"IELTS scores found: {ielts_matches}")
else:
    print("No IELTS scores found in text")

# Extract TOEFL scores  
toefl_pattern = r'toefl[:\s]+(\d+)'
toefl_matches = re.findall(toefl_pattern, resp.text.lower())
if toefl_matches:
    print(f"TOEFL scores found: {toefl_matches}")
else:
    print("No TOEFL scores found in text")

# Check if there's a 404 message despite 200 status
if "404" in resp.text or "not found" in resp.text.lower() or "does not exist" in resp.text.lower():
    print("\n⚠️  WARNING: Page contains '404' or 'not found' text (soft 404)")
    
    # Find the 404 message
    for line in resp.text.split('\n'):
        if '404' in line or 'not found' in line.lower() or 'does not exist' in line.lower():
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            if clean_line and len(clean_line) < 200:
                print(f"  Message: {clean_line}")

print("\n" + "="*80)
print("SNIPPET (first 1000 chars):")
print("="*80)
# Strip HTML tags for readability
text = re.sub(r'<[^>]+>', '', resp.text)
text = re.sub(r'\s+', ' ', text)
print(text[:1000])
