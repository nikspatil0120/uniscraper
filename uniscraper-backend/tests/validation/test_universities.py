# tests/validation/test_universities.py
# The 10-university validation test suite.
# Runs the full pipeline against 10 known university program URLs.
# For each URL, asserts minimum field coverage thresholds:
#   - university_name, program_name, degree_level must be populated
#   - At least one of: tuition_fees, english_requirements must be populated
# Saves full JSON results to tests/validation/results/{timestamp}.json
# Run with: pytest tests/validation/ -v

# TODO: add 10 university URLs and implement validation assertions
