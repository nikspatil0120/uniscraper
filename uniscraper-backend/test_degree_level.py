"""
Unit tests for _fallback_degree_level edge case fixes.
Run: .\venv\Scripts\python test_degree_level.py
"""
from pipeline.program_discovery import _fallback_degree_level

cases = [
    # (title, url, expected_level)
    ("MS Engineering Management",           "https://astate.edu/programs/ms-in-engineering-management.html",   "Master's"),
    ("MSE in Chemistry",                    "https://astate.edu/programs/mse-in-chemistry.html",               "Master's"),
    ("MSA in Agriculture",                  "https://astate.edu/programs/msa-in-agriculture.html",             "Master's"),
    ("MSW in Social Work",                  "https://astate.edu/programs/msw-in-social-work.html",             "Master's"),
    ("MSN in Nursing",                      "https://astate.edu/programs/msn-in-nursing.html",                 "Master's"),
    ("Ed.S. in Clinical Mental Health",     "https://astate.edu/programs/eds-in-psychology.html",              "Doctoral"),
    ("Doctor of Physical Therapy",          "https://astate.edu/programs/dpt-in-physical-therapy.html",        "Doctoral"),
    ("Doctor of Nursing Practice (DNP)",    "https://astate.edu/programs/dnp-in-nurse-anesthesia.html",        "Doctoral"),
    ("Doctor of Occupational Therapy",      "https://astate.edu/programs/otd-in-occupational-therapy.html",    "Doctoral"),
    ("MBA in Marketing",                    "https://astate.edu/programs/mba-in-marketing.html",               "MBA"),
    ("MA in Sociology",                     "https://astate.edu/programs/ma-in-sociology.html",                "Master's"),
    ("MSc Business Psychology",             "https://manchester.ac.uk/study/masters/courses/list/09994/msc-business-psychology/", "Master's"),
    ("PhD Cell Biology",                    "https://manchester.ac.uk/study/postgraduate-research/phd-cell-biology/",            "PhD"),
    ("Graduate Certificate in Statistics",  "https://astate.edu/programs/graduate-certificate-in-statistics.html",               "Certificate"),
    # MBA should NOT be caught by bare "ba" substring
    ("MBA in Business Administration",      "https://astate.edu/programs/mba-in-business-administration.html", "MBA"),
]

all_pass = True
for title, url, expected in cases:
    got = _fallback_degree_level(url, title)
    ok = got == expected
    if not ok:
        all_pass = False
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] got={got:12s} want={expected:12s} | {title}")

print()
print("ALL PASS" if all_pass else "SOME TESTS FAILED")
