# models/batch_request.py
# Pydantic request body model for POST /scrapes/batch.
# urls is a list of HttpUrl, minimum 1, maximum 20.
# Validation enforces the list length constraints.

from pydantic import BaseModel, HttpUrl, field_validator
from typing import List


class BatchRequest(BaseModel):
    """Request body for initiating a batch scrape of multiple URLs."""
    urls: List[HttpUrl]

    @field_validator("urls")
    @classmethod
    def validate_urls_length(cls, v):
        if len(v) < 1:
            raise ValueError("At least one URL is required")
        if len(v) > 20:
            raise ValueError("Maximum 20 URLs per batch")
        return v
