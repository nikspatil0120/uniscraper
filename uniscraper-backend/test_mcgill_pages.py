"""
Test if McGill's english-requirements page is actually accessible
"""
import httpx

BASE_URL = "https://www.mcgill.ca/desautels/programs/mba"

# Possible english requirement page URLs
test_urls = [
    f"{BASE_URL}/english-requirements",
    f"{BASE_URL}/english-language-requirements",
    f"{BASE_URL}/admission-requirements",
    f"{BASE_URL}/admissions",
    "https://www.mcgill.ca/desautels/programs/mba/admission-requirements",
    "https://www.mcgill.ca/desautels/programs/mba/admissions",
    "https://www.mcgill.ca/desautels/programs/mba-program/admission-requirements",
    "https://www.mcgill.ca/english-language",
    "https://www.mcgill.ca/gradapplicants/apply/prepare/english",
]

print("="*80)
print("TESTING MCGILL ENGLISH REQUIREMENTS PAGES")
print("="*80)

for url in test_urls:
    try:
        resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        status = resp.status_code
        length = len(resp.text)
        
        # Check if it's a real page or 404
        if status == 200:
            has_ielts = "ielts" in resp.text.lower()
            has_toefl = "toefl" in resp.text.lower()
            has_404 = "404" in resp.text.lower() or "not found" in resp.text.lower()
            
            indicator = "✅" if (has_ielts or has_toefl) and not has_404 else "⚠️"
            detail = []
            if has_ielts: detail.append("IELTS")
            if has_toefl: detail.append("TOEFL")
            if has_404: detail.append("404-PAGE")
            
            print(f"{indicator} {status} {length:6d} chars {', '.join(detail):20s} | {url}")
        else:
            print(f"❌ {status} {'':6s}       {'':20s} | {url}")
    except Exception as e:
        print(f"❌ ERROR {'':6s}      {str(e)[:20]:20s} | {url}")

print("="*80)
