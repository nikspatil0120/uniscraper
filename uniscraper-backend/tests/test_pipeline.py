# tests/test_pipeline.py
# Integration test for the full pipeline.
# Runs run_scrape() against a real URL (or a local mock server).
# Asserts that the returned ScrapeResult has status != "failed"
# and that at least university_name or program_name is populated.
# Requires OPENROUTER_API_KEY and MONGODB_URI to be set.
# Mark with @pytest.mark.integration to allow skipping in CI.

# TODO: implement integration test
