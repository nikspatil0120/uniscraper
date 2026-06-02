# tests/test_fetcher.py
# Unit tests for pipeline/fetcher.py
# Test cases:
#   - fetch_page returns HTML for a static page (mock httpx response)
#   - fetch_page falls back to Playwright when httpx returns 403
#   - fetch_page handles connection errors gracefully
#   - method_used field is set correctly in both cases

# TODO: implement tests
