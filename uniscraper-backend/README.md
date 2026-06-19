# UniScraper Backend

AI-powered university admission data extraction API with university program discovery.  
Scrapes program pages, extracts structured admission data using a hybrid LLM pipeline, and serves results via a REST API.

---

## Prerequisites

- Python 3.11+
- MongoDB (local or Atlas)
- Gemini API key — [get one free](https://aistudio.google.com/)
- SerpAPI key — [free tier at serpapi.com](https://serpapi.com/users/sign_up) (Phase 2 discovery, no card required)
- Ollama (optional, for local LLM fallback) — [install](https://ollama.com/)

---

## Installation

```bash
# Install dependencies (no venv required)
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env

# Run
python main.py
# or: uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Optional: local LLM fallback

```bash
ollama pull qwen2.5:1.5b
```

Automatically used when Gemini hits rate limits.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `MONGODB_URI` | ✅ | MongoDB connection string |
| `SERPAPI_KEY` | ✅ (Phase 2) | SerpAPI key for program discovery fallback |
| `DB_NAME` | | Database name (default: `autonova_scraper`) |
| `LLM_MODEL` | | Primary model (default: `gemini-2.5-flash`) |
| `LLM_MAX_TOKENS` | | Max output tokens (default: `4000`) |
| `LLM_CONTEXT_LIMIT` | | Max chars sent to LLM (default: `50000`) |
| `MAX_SUBPAGES` | | Sub-pages fetched per scrape (default: `20`) |
| `MAX_CONCURRENT_FETCHES` | | Concurrent page fetches (default: `8`) |
| `MAX_PDFS` | | PDFs extracted per page (default: `2`) |
| `CORS_ORIGINS` | | Comma-separated allowed origins |
| `FIRECRAWL_API_KEY` | | Firecrawl key for Tier 2 fetching |
| `CRAWL4AI_ENABLED` | | Enable Crawl4AI Tier 3 (default: `true`) |
| `SERPAPI_ENABLED` | | Enable SerpAPI fallback (default: `true`) |
| `LOG_LEVEL` | | Logging level (default: `INFO`) |

---

## API Reference

### Phase 2 — University Program Discovery

#### `POST /api/v1/discover`
Start a program discovery job for a university. Returns immediately (202).

```json
// Request
{ "university_name": "Arkansas State University" }

// Response — new job
{ "discovery_id": "abc123", "status": "processing" }

// Response — cached (same university searched within 24h)
{ "discovery_id": "abc123", "status": "cached", "cached_from": "prev_id" }
```

#### `GET /api/v1/discover/{discovery_id}`
Poll for discovery result. Status transitions: `processing` → `running` → `success` / `no_programs_found` / `failed`.

```json
{
  "discovery_id": "abc123",
  "university_name": "Arkansas State University",
  "status": "success",
  "domain": "astate.edu",
  "domain_method": "heuristic",
  "domain_confidence": "high",
  "programs": [
    {
      "program_name": "Master of Athletic Training",
      "degree_level": "Master's",
      "url": "https://astate.edu/programs/mathtr-in-athletic-training.html"
    },
    {
      "program_name": "MBA in Marketing",
      "degree_level": "MBA",
      "url": "https://astate.edu/programs/mba-in-marketing.html"
    }
  ],
  "programs_count": 16,
  "elapsed_seconds": 55.9
}
```

**Status meanings:**

| Status | Meaning |
|---|---|
| `processing` / `running` | Still working — keep polling |
| `success` | Programs found, `programs` array populated |
| `no_programs_found` | Domain resolved but no program pages located |
| `failed` | Could not resolve university domain |
| `cached` | Returned existing result from last 24h |

---

### Phase 1 — Scraping

#### `POST /api/v1/scrape`
Start a scrape. Returns immediately — poll for result.

```json
// Request
{ "url": "https://university.edu/programs/mba", "context_hint": "optional hint" }

// Response (202)
{ "scrape_id": "abc123", "status": "processing" }

// If same URL scraped within 24h:
{ "scrape_id": "abc123", "status": "cached", "cached_from": "abc123" }
```

#### `GET /api/v1/scrape/{scrape_id}`
Poll for result. Status: `processing` → `running` → `success` / `partial` / `failed`.

#### `DELETE /api/v1/scrape/{scrape_id}`
Delete a scrape result (204).

#### `POST /api/v1/scrapes/batch`
Queue multiple URLs. Each staggered **25 seconds apart** to respect rate limits.

```json
// Request (1–20 URLs)
{ "urls": ["https://uni-a.edu/prog-1", "https://uni-b.edu/prog-2"] }

// Response (202)
{
  "batch_id": "batch_xyz",
  "scrape_ids": ["id1", "id2"],
  "total": 2,
  "estimated_seconds": 50
}
```

#### `GET /api/v1/batch/{batch_id}`
Batch progress with per-URL status breakdown.

#### `GET /api/v1/scrapes`
Paginated history. Query params: `?page=1&limit=20&search=&status=`.

#### `GET /api/v1/export/csv`
Download results as CSV. Query params: `?all=true` or `?scrape_ids=id1,id2`.

#### `GET /health`
`{"status": "ok", "version": "1.0.0"}`

---

## Extracted Scrape Schema

```
university_name, program_name, degree_level, program_duration,
intake_months[], application_deadlines, min_academic_requirement,
accepted_qualifications, work_experience, other_requirements,
english_requirements {
    ielts, toefl, pte, duolingo, notes
},
tuition_fees {
    domestic, international, currency, breakdown, notes
},
other_fees, scholarships, confidence_notes,
field_sources { "field.subfield" → "source_url", ... }
```

`field_sources` uses dot-notation:
```json
{
  "english_requirements.ielts": "https://uni.edu/language-requirements",
  "tuition_fees.international": "https://uni.edu/fees"
}
```

---

## Project Structure

```
uniscraper-backend/
├── main.py                      FastAPI app, CORS, router registration
├── config.py                    Typed settings from .env (pydantic-settings)
├── database.py                  Motor MongoDB client singleton
│
├── models/
│   ├── scrape_request.py        ScrapeRequest pydantic model
│   ├── batch_request.py         BatchRequest pydantic model
│   ├── scrape_result.py         ScrapeResult response schema
│   └── discover_request.py      DiscoverRequest pydantic model  ← NEW
│
├── routers/
│   ├── scrape.py                POST/GET/DELETE /scrape — 24h cache
│   ├── batch.py                 POST /scrapes/batch — staggered queue
│   ├── history.py               GET /scrapes — paginated history
│   ├── export.py                GET /export/csv and /export/json
│   └── discover.py              POST/GET /discover — Phase 2  ← NEW
│
├── pipeline/
│   ├── orchestrator.py          Phase 1 coordinator
│   ├── intelligent_fetcher.py   Three-tier fetch strategy selector
│   ├── tier1_custom.py          httpx + Playwright BFS (Tier 1)
│   ├── tier2_firecrawl.py       Firecrawl API (Tier 2)
│   ├── tier3_crawl4ai.py        Crawl4AI deep BFS (Tier 3)
│   ├── fetcher.py               Raw httpx + Playwright fetcher
│   ├── ai_extractor.py          Gemini → Groq → Ollama with rate limiting
│   ├── gap_analyzer.py          Detects missing critical fields
│   ├── targeted_recrawl.py      Fetches pages to fill detected gaps
│   ├── regex_extractor.py       Pre/post-LLM regex fallback layer
│   ├── pdf_extractor.py         PDF text extraction
│   ├── merger.py                Multi-source result merging
│   ├── domain_resolver.py       University name → domain  ← NEW
│   ├── program_discovery.py     BFS program page crawler  ← NEW
│   ├── serpapi_client.py        SerpAPI fallback client  ← NEW
│   └── discovery_orchestrator.py Phase 2 async pipeline  ← NEW
│
├── prompts/
│   └── extraction_prompt.py     Gemini system + user prompt templates
│
└── utils/
    ├── text_cleaner.py          HTML → clean text, SVG/noise stripping
    ├── page_classifier.py       Page type classification
    ├── section_classifier.py    Admission-focused section extraction
    ├── field_validators.py      Semantic validation rules
    ├── url_utils.py             URL normalisation, domain matching
    └── csv_builder.py           Flat CSV export from nested schema
```

---

## Discovery Pipeline Architecture

```
POST /api/v1/discover {"university_name": "Arkansas State University"}
    │
    ├── Check 24h MongoDB cache → return if hit
    │
    ├── domain_resolver.py
    │     1. Slug heuristic: "Arkansas State" → "astate"
    │        Try: astate.edu, astate.ac.uk, astate.edu.au, astate.ca
    │        HEAD verify each — first 200 with matching title wins
    │     2. Known overrides: McGill → mcgill.ca, etc.
    │     3. SerpAPI fallback: search "{name} official website"
    │
    ├── program_discovery.py
    │     1. Probe ~35 common paths (/programs, /study, /colleges...)
    │        on both bare domain and www. prefix
    │        Concurrency: 3 at a time (avoid 429s)
    │     2. SerpAPI fallback if 0 index pages found
    │        Two queries: graduate programs + general programs
    │        Sibling search for known path patterns
    │     3. BFS from index pages (depth ≤ 3, max 80 pages)
    │        Prioritise /programs/* URLs
    │        Skip: news/events/staff/login/campus/class-profile/etc.
    │     4. is_program_page() filter:
    │        ✅ Has degree keyword in URL or title
    │        ✅ Not a listing/index page
    │        ✅ Not an admin/nav page
    │        ✅ Title not generic (error 404, search, class profile...)
    │        ✅ Not too many sibling-dir degree links (would be a listing)
    │     5. SerpAPI post-BFS fallback (if BFS finds 0 programs)
    │     6. Deduplicate by normalised program name, cap at 200
    │
    └── Save to MongoDB (status=success), 24h TTL
```

---

## Scrape Pipeline Architecture

```
POST /api/v1/scrape {"url": "..."}
    │
    ├── Check 24h cache (status=success/partial)
    │
    ├── intelligent_fetcher.py
    │     Tier 1 (Custom): httpx BFS + Playwright fallback
    │       Scores links by admission/fees/english keywords
    │       Early exit when all critical page types found
    │     Tier 2 (Firecrawl): if Tier 1 gets Cloudflare 403s
    │     Tier 3 (Crawl4AI): if Tier 2 still fails
    │
    ├── ai_extractor.py — Pass 1
    │     Field-specific context routing per field type
    │     Regex pre-extraction as anchor hints
    │     Gemini 2.5 Flash → Groq fallback → Ollama fallback
    │     Rate limit: semaphore + 20s gap + 3 RPM rolling window
    │
    ├── gap_analyzer.py
    │     Check CRITICAL_FIELDS: tuition, english, deadlines, academic
    │     Suggest page types to fetch if any are null
    │
    ├── targeted_recrawl.py (if gaps found)
    │     httpx HEAD + fetch for candidate URLs
    │     Max 5 new pages
    │
    ├── ai_extractor.py — Pass 2 (if new pages found)
    │
    ├── field_validators.py
    │     PhD duration < 2y → null
    │     IELTS outside 4.0–9.0 → flagged
    │
    └── Save to MongoDB
          status=success: has uni+prog+8 non-null fields
          status=partial: fewer fields
          status=failed: nothing extracted
```

---

## Rate Limiting

| Service | Limit | Handling |
|---|---|---|
| Gemini | 10 RPM free | Semaphore + 20s gap + rolling 60s window |
| Gemini 429s | — | Auto-fallback: Groq → Ollama → Flash-Lite |
| Batch scrapes | — | 25s stagger between URLs |
| Discovery BFS | — | 3-concurrent index probes, 5-concurrent BFS fetches |
| SerpAPI | ~100/month free | Monthly counter in MongoDB, warn at 80 |
