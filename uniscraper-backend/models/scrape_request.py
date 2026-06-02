# models/scrape_request.py
# Pydantic request body model for POST /scrape.
# Validates that url is a proper HTTP/HTTPS URL.
# context_hint is optional free-text to guide the LLM extraction.

from pydantic import BaseModel, HttpUrl
from typing import Optional


class ScrapeRequest(BaseModel):
    """Request body for initiating a single URL scrape."""
    url: HttpUrl
    context_hint: Optional[str] = None
