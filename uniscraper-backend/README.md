# UniScraper Backend

AI-powered university admission data extraction API. Scrapes program pages, extracts structured admission data using a hybrid LLM pipeline, and serves results via a REST API.

---

## Prerequisites

- Python 3.11+
- MongoDB (local or Atlas)
- Gemini API key ([get one free](https://aistudio.google.com/))
- Ollama (optional, for local LLM fallback) — [install](https://ollama.com/)

---

## Installation

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and fill in environment variables
cp .env.example .env
```

### Optional: local LLM fallback

```bash
ollama pull qwen2.5:1.5b
```

When Gemini hits rate limits, the system automatically falls back to this local model.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `MONGODB_URI` | ✅ | MongoDB connection string (Atlas or local) |
| `DB_NAME` | | Database name (default: `autonova_scraper`) |
| `LLM_MODEL` | | Primary model (default: `gemini-2.5-flash`) |
| `LLM_MAX_TOKENS` | | Max output tokens (default: `4000`) |
| `LLM_CONTEXT_LIMIT` | | Max chars sent to LLM (default: `16000`) |
| `MAX_SUBPAGES` | | Sub-pages fetched per scrape (default: `4`) |
| `MAX_PDFS` | | PDFs extracted per page (default: `2`) |
| `CORS_ORIGINS` | | Comma-separated allowed origins |
| `SCRAPE_DELAY_SECONDS` | | Delay between batch test scrapes (default: `7`) |

---

## Running

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`

---

## API Reference

### `POST /api/v1/scrape`
Start a scrape. Returns immediately — poll for result.

```json
// Request
{ "url": "https://university.edu/programs/cs", "context_hint": "optional hint" }

// Response (202)
{ "scrape_id": "abc123", "status": "processing" }

// If same URL was scraped within 24h:
{ "scrape_id": "abc123", "status": "cached", "cached_from": "abc123" }
```

---

### `GET /api/v1/scrape/{scrape_id}`
Poll for result. `status` will be `processing` → `success` / `partial` / `failed`.

---

### `DELETE /api/v1/scrape/{scrape_id}`
Delete a scrape result.

---

### `GET /api/v1/scrapes`
List past scrapes (paginated).

```
?page=1&limit=20
```

---

### `POST /api/v1/scrapes/batch`
Queue multiple URLs. Each is staggered **25 seconds apart** to stay under Gemini's rate limit.

```json
// Request
{ "urls": ["https://uni-a.edu/prog-1", "https://uni-b.edu/prog-2"] }

// Response (202)
{
  "batch_id": "batch_xyz",
  "scrape_ids": ["id1", "id2"],
  "total": 2,
  "status": "processing",
  "estimated_seconds": 50
}
```

---

### `GET /api/v1/batch/{batch_id}`
Batch progress with per-URL status breakdown.

---

### `GET /api/v1/export/csv`
Download all results as CSV.

---

### `GET /health`
`{"status": "ok", "version": "1.0.0"}`

---

## Extracted Schema

Every scrape returns these fields (null where not found):

```
university_name, program_name, degree_level, program_duration,
intake_months, application_deadlines, min_academic_requirement,
accepted_qualifications, work_experience, other_requirements,
english_requirements { ielts, toefl, pte, duolingo, notes },
tuition_fees { domestic, international, currency, notes },
other_fees, scholarships, confidence_notes,
field_sources { field_name → source_url, ... }
```

`field_sources` uses dot-notation for nested fields:
```json
{
  "english_requirements.ielts": "https://uni.edu/language-requirements",
  "tuition_fees.international": "https://uni.edu/fees"
}
```

---

## Pipeline Architecture

```
fetch_page(url)
    │  httpx (fast) → Playwright fallback (JS-rendered pages)
    │
extract_relevant_links(html)
    │  scores all <a href> by keyword relevance, returns top 4
    │
fetch sub-pages concurrently (max 3 at a time)
    │  each classified: admissions / english_requirements / tuition /
    │                   scholarships / programme_overview / curriculum
    │
extract_fields(combined_text, pages_data)
    │
    ├── Field-specific context routing
    │     IELTS/TOEFL  → english_requirements page
    │     Fees         → tuition page + main page
    │     Deadlines    → admissions page
    │     Duration     → programme_overview page
    │
    ├── Regex pre-extraction (IELTS, TOEFL, fees, deadlines, GPA)
    │     → injected as anchor hints into the LLM prompt
    │
    ├── Gemini 2.5 Flash call
    │     Rate limiting: semaphore + 20s gap + 3 RPM tracker
    │     On 429 → Ollama/qwen2.5:1.5b (local, ~15s)
    │     On 429 again → Gemini 2.5 Flash-Lite
    │     Retry delays: 30s → 60s → 120s → 180s → 240s
    │
    ├── Semantic validation
    │     PhD duration < 2 years → nulled
    │     IELTS outside 4.0–9.0 → flagged
    │     GPA in curriculum context → flagged
    │
    └── Regex fallbacks
          fills any null fields the LLM missed
```

---

## Project Structure

```
uniscraper-backend/
├── main.py                  FastAPI app, CORS, router registration
├── config.py                Typed settings from .env (pydantic-settings)
├── database.py              Motor MongoDB client singleton
├── models/                  Pydantic request/response schemas
├── routers/
│   ├── scrape.py            POST/GET /scrape — single URL with 24h cache
│   ├── batch.py             POST /scrapes/batch — staggered queue
│   ├── history.py           GET /scrapes — paginated history
│   └── export.py            GET /export/csv
├── pipeline/
│   ├── orchestrator.py      Main coordinator — runs the full pipeline
│   ├── fetcher.py           httpx + Playwright fallback
│   ├── link_extractor.py    Scores and selects relevant sub-pages
│   ├── ai_extractor.py      LLM call with routing, fallbacks, rate limiting
│   ├── regex_extractor.py   Pre/post-LLM regex extraction layer
│   ├── pdf_extractor.py     PDF text extraction from linked PDFs
│   └── merger.py            Merges multi-source results with field_sources
├── prompts/
│   └── extraction_prompt.py System + user prompt templates
├── utils/
│   ├── text_cleaner.py      HTML → clean text, reveals hidden accordions
│   ├── page_classifier.py   Classifies pages by type + FIELD_TO_PAGE_TYPES
│   ├── section_classifier.py Admission-focused section extraction
│   ├── field_validators.py  Semantic validation rules
│   ├── url_utils.py         URL normalisation, domain matching, scoring
│   └── csv_builder.py       Flat CSV export from nested schema
├── scripts/
│   ├── test_single_url.py   Run pipeline on one URL, print results
│   └── validate_universities.py  Batch validation runner
└── tests/
    ├── test_*.py            Unit tests
    └── validation/
        ├── test_universities.py  10-university validation suite
        └── results/         JSON output from validation runs
```

---

## Testing

```bash
# Run a single URL through the full pipeline
venv\Scripts\python scripts/test_single_url.py "https://gsas.harvard.edu/program/applied-physics"

# Unit tests
pytest tests/ -v

# Validation suite
pytest tests/validation/ -v
```

---

## Rate Limiting

Gemini free tier: 10 RPM. The system self-throttles to stay under 3 RPM:

- **Global semaphore** — only one Gemini call at a time across all concurrent requests
- **20s minimum gap** between calls
- **Rolling 60s window** — tracks actual request timestamps, sleeps if approaching limit
- **10s post-success cooldown** — smooths traffic after each successful call
- **Batch stagger** — 25s between each URL in a batch job

On consecutive 429s: automatic fallback to `qwen2.5:1.5b` (local) → `gemini-2.5-flash-lite`.
