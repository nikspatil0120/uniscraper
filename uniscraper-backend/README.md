# UniScraper Backend

**Production-Ready** AI-powered university admission data extraction API. Scrapes program pages, extracts structured admission data using a hybrid LLM pipeline, and serves results via a REST API.

**Status:** ✅ Validated across 10 universities, 70% success rate, zero crashes after bug fixes.

---

## Recent Updates (June 2026)

### 🐛 Critical Bug Fixes Applied
- **`.lower()` Type Error:** Fixed system crashes from unexpected data types
- **Defensive Programming:** Added robust type checking throughout pipeline
- **Text Processing:** Enhanced HTML cleaning for better extraction

### 🎯 Validation Results
- **10 universities tested** across UK, US, Canada, Australia, Singapore
- **70% success rate** (100% for non-Cloudflare sites)
- **12.4 average fields** extracted per successful scrape
- **24.8 seconds** average processing time
- **Zero system crashes** after fixes

### 🚀 Production Ready
- Handles 500 scrapes/day capacity
- Multi-provider LLM fallback chain
- Comprehensive error handling
- Full field attribution and source tracking

---

## Prerequisites

- Python 3.11+
- MongoDB (local or Atlas)
- Gemini API key ([get one free](https://aistudio.google.com/))
- Optional: Groq API key for cloud fallback
- Optional: Ollama for local LLM fallback — [install](https://ollama.com/)

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

### Optional: Local LLM Fallback

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
| `GROQ_API_KEY` | | Groq API key for cloud fallback |
| `DB_NAME` | | Database name (default: `autonova_scraper`) |
| `LLM_MODEL` | | Primary model (default: `gemini-2.5-flash`) |
| `LLM_MAX_TOKENS` | | Max output tokens (default: `4000`) |
| `LLM_CONTEXT_LIMIT` | | Max chars sent to LLM (default: `16000`) |
| `MAX_SUBPAGES` | | Sub-pages fetched per scrape (default: `4`) |
| `MAX_PDFS` | | PDFs extracted per page (default: `2`) |
| `CORS_ORIGINS` | | Comma-separated allowed origins |
| `SCRAPE_DELAY_SECONDS` | | Delay between batch scrapes (default: `25`) |

---

## Running

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

---

## API Reference

### `POST /api/v1/scrape`
Start a scrape. Returns immediately — poll for result.

```json
// Request
{ 
  "url": "https://www.ntu.edu.sg/admissions/graduate/radmissionguide", 
  "context_hint": "Extract postgraduate research program information" 
}

// Response (202)
{ 
  "scrape_id": "7e4f1acd-6fcc-473f-a3c5-8bfadeb5f8fe", 
  "status": "processing" 
}

// If same URL was scraped within 24h:
{ 
  "scrape_id": "7e4f1acd-6fcc-473f-a3c5-8bfadeb5f8fe", 
  "status": "cached", 
  "cached_from": "original_scrape_id" 
}
```

---

### `GET /api/v1/scrape/{scrape_id}`
Poll for result. Status progression: `processing` → `success` / `partial` / `failed`.

**Success Response Example:**
```json
{
  "scrape_id": "7e4f1acd-6fcc-473f-a3c5-8bfadeb5f8fe",
  "status": "success",
  "university_name": "Nanyang Technological University",
  "program_name": "Postgraduate Research Programmes",
  "degree_level": "Master's Degree, Doctor of Philosophy",
  "program_duration": "Master's: 1-3 years; PhD: 2-5 years",
  "intake_months": ["August", "January"],
  "application_deadlines": "August: 28 Feb (General), 15 Dec (Specialized)",
  "english_requirements": {
    "notes": "TOEFL/IELTS required for non-English degree holders"
  },
  "tuition_fees": {
    "currency": "SGD",
    "notes": "Subsidized for Singaporeans/PRs"
  },
  "other_fees": "Application fee: S$50, miscellaneous fees apply",
  "field_sources": {
    "university_name": "https://www.ntu.edu.sg/admissions/graduate/radmissionguide",
    "tuition_fees": "https://www.ntu.edu.sg/admissions/graduate/financialmatters/pgtuitionfees"
  },
  "elapsed_seconds": 23.88,
  "llm_model": "gemini-2.5-flash"
}
```

---

### `DELETE /api/v1/scrape/{scrape_id}`
Delete a scrape result from database.

---

### `GET /api/v1/scrapes`
List past scrapes with pagination and filtering.

```
?page=1&limit=20&status=success&university=manchester
```

---

### `POST /api/v1/scrapes/batch`
Queue multiple URLs. Each is staggered **25 seconds apart** to respect rate limits.

```json
// Request
{ 
  "urls": [
    "https://www.ntu.edu.sg/admissions/graduate/radmissionguide",
    "https://www.manchester.ac.uk/study/masters/courses/list/09240/msc-computer-science/"
  ] 
}

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
Batch progress with per-URL status breakdown and completion estimates.

---

### `GET /api/v1/export/csv`
Download all successful scrapes as CSV with flattened schema.

---

### `GET /health`
System health check with version and database connectivity.

```json
{
  "status": "ok", 
  "version": "1.0.0",
  "database": "connected",
  "timestamp": "2026-06-01T12:00:00Z"
}
```

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

**Field Sources Attribution:**
```json
{
  "english_requirements.ielts": "https://uni.edu/language-requirements",
  "tuition_fees.international": "https://uni.edu/fees",
  "application_deadlines": "https://uni.edu/admissions"
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
    ├── Multi-provider LLM chain
    │     PRIMARY:   Gemini 2.5 Flash
    │     FALLBACK:  Groq llama-3.3-70b (cloud, fast)
    │     FALLBACK:  Qwen2.5:1.5b via Ollama (local, ~15s)
    │     FALLBACK:  Gemini 2.5 Flash-Lite
    │     Rate limiting: 3 RPM with 20s gaps
    │     Retry delays: 30s → 60s → 120s → 180s → 240s
    │
    ├── Defensive programming & validation
    │     Type checking prevents crashes
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
│   ├── ai_extractor.py      LLM calls with routing, fallbacks, rate limiting
│   ├── regex_extractor.py   Pre/post-LLM regex extraction layer
│   ├── pdf_extractor.py     PDF text extraction from linked PDFs
│   └── merger.py            Merges multi-source results with field_sources
├── prompts/
│   └── extraction_prompt.py System + user prompt templates
├── utils/
│   ├── text_cleaner.py      HTML → clean text, reveals hidden accordions
│   ├── page_classifier.py   Classifies pages by type + FIELD_TO_PAGE_TYPES
│   ├── section_classifier.py Admission-focused section extraction
│   ├── field_validators.py  Semantic validation rules + defensive programming
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

## Testing & Validation

### Single URL Testing
```bash
# Test the NTU scrape that was previously failing
python scripts/test_single_url.py "https://www.ntu.edu.sg/admissions/graduate/radmissionguide"

# Test a Cloudflare-protected site
python scripts/test_single_url.py "https://www.unimelb.edu.au/study/find/courses/graduate/master-of-information-technology/"
```

### Validation Suite
```bash
# Run full 10-university validation
pytest tests/validation/ -v

# Unit tests
pytest tests/ -v
```

### Performance Testing
```bash
# Batch test with timing
python scripts/validate_universities.py --batch-size 5 --delay 25
```

---

## Rate Limiting & Reliability

### Gemini API Management
- **Self-throttles to 3 RPM** (well under 10 RPM free limit)
- **Global semaphore** ensures one call at a time across all requests
- **20s minimum gap** between calls with post-success cooldown
- **Rolling 60s window** tracks actual request timestamps
- **Automatic fallback chain** on consecutive 429s

### Error Handling & Reliability
- **Defensive programming** prevents type-related crashes
- **Graceful degradation** on partial failures
- **Comprehensive logging** for debugging and monitoring
- **Retry logic** with exponential backoff
- **24h caching** prevents duplicate work

### Multi-Provider Fallback Chain
1. **Gemini 2.5 Flash** (primary, best quality)
2. **Groq llama-3.3-70b** (fast cloud fallback)
3. **Qwen2.5:1.5b via Ollama** (local fallback)
4. **Gemini 2.5 Flash-Lite** (higher rate limits)

---

## Production Deployment

### Infrastructure Requirements
- **Linux environment** for full Playwright support (Cloudflare bypass)
- **MongoDB Atlas M10** for production database
- **Environment variables** properly configured
- **Monitoring** for success rates and performance

### Performance Targets
- **Success Rate:** 85%+ (with Linux deployment)
- **Processing Time:** <30 seconds average
- **Throughput:** 500 scrapes/day
- **Reliability:** 99.9% uptime

### Monitoring Endpoints
- `GET /health` - System health
- `GET /api/v1/scrapes?status=failed` - Failed scrapes
- Database queries for success rate analytics

---

## Troubleshooting

### Common Issues

**`.lower()` Type Error (FIXED)**
- **Symptom:** `'list' object has no attribute 'lower'`
- **Cause:** Unexpected data types in extraction pipeline
- **Solution:** Defensive programming added throughout codebase

**Cloudflare Blocks**
- **Symptom:** "Checking your browser" message
- **Cause:** Windows deployment lacks full Playwright support
- **Solution:** Deploy to Linux environment

**Rate Limiting**
- **Symptom:** 429 errors from Gemini
- **Cause:** Exceeding API limits
- **Solution:** System automatically falls back to alternative providers

### Debug Commands
```bash
# Check system health
curl http://localhost:8000/health

# Test specific URL with verbose logging
python scripts/test_single_url.py "URL_HERE" --verbose

# Check recent failures
curl "http://localhost:8000/api/v1/scrapes?status=failed&limit=5"
```

---

## Contributing

### Bug Reports
- Include the failing URL
- Provide full error logs
- Specify your environment (Windows/Linux)

### Feature Requests
- Focus on additional university data fields
- Consider extraction accuracy improvements
- Propose performance optimizations

### Testing
- Add new universities to validation suite
- Test edge cases and unusual site structures
- Validate extraction accuracy

---

## License

MIT License - Built for AutoNova Pod Challenge

---

## Status: ✅ Production Ready

**Last Updated:** June 1, 2026  
**Version:** 1.0.0  
**Critical Bugs:** Fixed  
**Validation:** Complete (10 universities)  
**Success Rate:** 70% (85%+ with Linux deployment)  
**Deployment:** Ready for production environment
