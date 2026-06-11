# config.py
# Loads environment variables from .env using pydantic-settings.
# Exports a singleton `settings` object used throughout the app.
# All configuration values are typed and validated on startup.

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    mongodb_uri: str = "mongodb://localhost:27017"
    db_name: str = "autonova_scraper"
    max_subpages: int = 50  # increased for exhaustive crawling
    max_depth: int = 4      # crawl up to 4 levels deep
    max_concurrent_fetches: int = 12  # parallel fetch limit — increased for speed
    min_page_words: int = 30  # minimum words to keep a page
    max_pdfs: int = 2
    llm_model: str = "gemini-2.5-flash-lite"
    llm_max_tokens: int = 4000
    llm_context_limit: int = 50000  # increased to 50k chars (well within 1M token limit)
    scrape_delay_seconds: int = 7   # delay between scrapes when testing multiple URLs
    # Raw comma-separated string from .env — use cors_origins_list property in app code
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    # ── Three-tier fetching pipeline ──────────────────────────────────────────
    firecrawl_api_key: str = ""
    crawl4ai_enabled: bool = True
    firecrawl_enabled: bool = True

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse the comma-separated CORS_ORIGINS string into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
