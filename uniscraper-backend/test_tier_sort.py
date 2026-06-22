"""
Test the post-classification tier sort logic.
Run: .\venv\Scripts\python test_tier_sort.py
"""

# Simulate what comes out of Gemini (mixed order — certs confirmed before masters)
simulated_confirmed = [
    {"program_name": "Certificate in eSports", "degree_level": "Certificate", "url": "https://astate.edu/programs/certificate-in-esports.html"},
    {"program_name": "Certificate in Fitness Administration", "degree_level": "Certificate", "url": "https://astate.edu/programs/certificate-in-fitness-administration.html"},
    {"program_name": "MS in Computer Science", "degree_level": "Master's", "url": "https://astate.edu/programs/ms-in-computer-science.html"},
    {"program_name": "Certificate in Business Fundamentals", "degree_level": "Certificate", "url": "https://astate.edu/programs/certificate-in-business-fundamentals.html"},
    {"program_name": "PhD in Environmental Sciences", "degree_level": "PhD", "url": "https://astate.edu/programs/phd-in-environmental-sciences.html"},
    {"program_name": "MBA in Marketing", "degree_level": "MBA", "url": "https://astate.edu/programs/mba-in-marketing.html"},
    {"program_name": "Doctor of Occupational Therapy", "degree_level": "Doctoral", "url": "https://astate.edu/programs/otd-in-occupational-therapy.html"},
    {"program_name": "Certificate in Data Analytics", "degree_level": "Certificate", "url": "https://astate.edu/programs/certificate-in-data-analytics.html"},
    {"program_name": "MA in Sociology", "degree_level": "Master's", "url": "https://astate.edu/programs/ma-in-sociology.html"},
    {"program_name": "MS in Electrical Engineering", "degree_level": "Master's", "url": "https://astate.edu/programs/ms-in-electrical-engineering.html"},
]

_DEGREE_PRIORITY = {
    "PhD":         0,
    "Doctoral":    0,
    "MBA":         1,
    "Master's":    1,
    "Certificate": 2,
    "Diploma":     2,
    "Unspecified": 2,
    "Associate's": 3,
    "Bachelor's":  3,
}

# Apply tier sort
sorted_confirmed = sorted(simulated_confirmed, key=lambda p: _DEGREE_PRIORITY.get(p.get("degree_level", "Unspecified"), 2))

print("=== After tier sort (with cap=6 to show certificates pushed to end) ===")
for i, p in enumerate(sorted_confirmed, 1):
    tier = _DEGREE_PRIORITY.get(p["degree_level"], 2)
    marker = "<-- would be CUT" if i > 6 else ""
    print(f"  {i:2d}. [tier={tier} {p['degree_level']:12s}] {p['program_name']} {marker}")

print()
print("=== Top 6 (simulating cap=6) ===")
for p in sorted_confirmed[:6]:
    print(f"  [{p['degree_level']:12s}] {p['program_name']}")

# Verify: all PhDs and Master's come before any Certificate
tiers = [_DEGREE_PRIORITY[p["degree_level"]] for p in sorted_confirmed]
is_sorted = all(tiers[i] <= tiers[i+1] for i in range(len(tiers)-1))
print()
print("Tier order correct:", is_sorted)
assert is_sorted, "SORT FAILED"
print("PASS")
