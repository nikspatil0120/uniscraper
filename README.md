# UniScraper — University Admission Intelligence

A full-stack AI extraction system that scrapes university program pages and structures admission data into a clean, queryable format. Built for the AutoNova Pod internship challenge.

**Latest:** Bucket-based relevance architecture achieving **50% speed improvement** and **accurate tuition extraction**. See [IMPLEMENTATION_COMPLETE.md](./IMPLEMENTATION_COMPLETE.md) for details.

---

## What it does

Paste a university program URL → get back structured admission data in **~90-140 seconds**:

- IELTS / TOEFL / PTE / Duolingo requirements
- Tuition fees (domestic + international, with currency)
- Application deadlines
- Academic entry requirements
- Program duration, intake months, degree level
- Scholarships and other requirements

Every field includes a `field_sources` attribution showing which URL the data came from.

### Performance Highlights

- **Speed:** 74-142s average (50% improvement over previous implementation)
- **Accuracy:** Arkansas State MBA: $5,029 domestic / $8,977 international tuition extracted ✅
- **Efficiency:** 70% page reduction (15-20 pages vs 50 previously)
- **Smart Crawling:** BFS exhaustive crawling with early exit when critical pages found

---

## Architecture

```
Frontend (React + TanStack)
    │
    └── FastAPI Backend (Python)
            │
            ├── Tier 1: Crawl4AI (Playwright-based)
            │     └── BFS exhaustive crawling (depth=4, max=20 pages)
            │
            ├── Tier 2: Firecrawl (fallback)
            │     └── BFS crawling with full content extraction
            │
            ├── Page Classifier       admissions / english / tuition / etc.
            │
            ├── AI Extractor          ⭐ Bucket-based relevance architecture
            │     ├── Relevance scoring (+200 boost for real tuition pages)
            │     ├── Threshold filtering (score >= 80)
            │     ├── Multiple sources → LLM synthesis
            │     ├── PRIMARY:   Gemini 2.5 Flash
            │     ├── FALLBACK:  Qwen2.5:1.5b via Ollama (local)
            │     └── FALLBACK:  Gemini 2.5 Flash-Lite
            │
            ├── Regex Extractor       pre-extracts scores/fees as anchors
            ├── Field Validator       semantic sanity checks
            └── MongoDB               stores all results (24h cache)
```

### Key design decisions

**Bucket-based relevance architecture** ⭐ — Instead of picking the "top 3" pages, the system uses **threshold-based buckets** (score >= 80) to include ALL relevant pages for each field. This ensures information completeness and robustness to minor scoring variations. Principle: **"Scoring determines ordering, not exclusion"**.

**Enhanced relevance scoring** — Real tuition pages (e.g., `/admissions-and-aid/tuition-and-fees`) receive +200 boost, while fake constructed URLs (`.html/fees`) get -100 penalty. Result: Real pages consistently score 410-510.

**BFS exhaustive crawling** — Wave-based breadth-first search discovers pages 2-3 levels deep (e.g., university-wide tuition pages). Early exit logic stops at 15-20 pages when all critical pages (fees, english, entry) are found.

**Field-specific page routing** — Each field group (english requirements, fees, deadlines) gets routed to its most relevant pages. Multiple sources are sent to LLM for synthesis, not just a single page.

**Hybrid LLM routing** — Gemini Flash is primary. On rate limits (429), the system automatically falls back to a local Qwen2.5:1.5b model via Ollama, then to Gemini Flash-Lite. No scrape ever fails due to quota.

**Content deduplication** — MD5 hashing prevents duplicate pages with identical content from being processed.

**24h URL cache** — Submitting the same URL twice within 24 hours returns the cached result instantly.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, TanStack Router/Query, Tailwind CSS v4 |
| Backend | FastAPI, Python 3.12, asyncio |
| Crawling | Tier 1: Crawl4AI (Playwright), Tier 2: Firecrawl |
| Database | MongoDB Atlas |
| Primary LLM | Gemini 2.5 Flash |
| Local LLM | Qwen2.5:1.5b via Ollama |
| HTTP | httpx (async) |
| HTML parsing | BeautifulSoup + lxml |

---

## Performance Benchmarks

| University | Time | Pages | Fields | Tuition Extraction |
|------------|------|-------|--------|-------------------|
| Arkansas State MBA | 141.6s | 15 | 12/15 (80%) | ✅ $5,029/$8,977 |
| McGill MBA | 74s | 20 | 8/15 (53%) | ⚠️ Notes only |
| Edinburgh MSc | 119s | 13 | 7/15 (47%) | ⚠️ Notes only |
| Monash MBA | 109s | 20 | 3/15 (20%) | ❌ Needs investigation |

**Average:** 111.5s, 17 pages, 7.5/15 fields (50%)

### Improvements Over Previous Implementation

- **Speed:** 50% faster (141.6s vs 281.5s on Arkansas State)
- **Pages:** 70% reduction (15 vs 50 pages)
- **Tuition:** Working extraction (was null/null, now $5,029/$8,977)
- **Score accuracy:** Real pages score 410-510 (vs noise <80)

See [BUCKET_ARCHITECTURE_SUCCESS.md](./BUCKET_ARCHITECTURE_SUCCESS.md) for detailed validation.

---

## Documentation

- **[IMPLEMENTATION_COMPLETE.md](./IMPLEMENTATION_COMPLETE.md)** - Complete implementation summary
- **[BUCKET_ARCHITECTURE_SUCCESS.md](./BUCKET_ARCHITECTURE_SUCCESS.md)** - Architecture validation
- **[THRESHOLD_VALIDATION_REPORT.md](./THRESHOLD_VALIDATION_REPORT.md)** - Empirical threshold validation
- **[FINAL_ARCHITECTURE_SUMMARY.md](./FINAL_ARCHITECTURE_SUMMARY.md)** - Architecture details
- **[ARCHITECTURE_BUCKET_APPROACH.md](./ARCHITECTURE_BUCKET_APPROACH.md)** - Bucket approach explanation

---

## Running locally

### Backend

```bash
cd uniscraper-backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Copy and fill in your keys
cp .env.example .env

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Required `.env` values:

```
GEMINI_API_KEY=your_key_here
MONGODB_URI=your_mongodb_atlas_uri
```

Optional (for local LLM fallback):
```bash
ollama pull qwen2.5:1.5b
```

### Frontend

```bash
npm install
npx vite dev
```

Open [http://localhost:5173](http://localhost:5173)

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/scrape` | Start a scrape, returns `scrape_id` |
| `GET` | `/api/v1/scrape/{id}` | Poll for result |
| `POST` | `/api/v1/scrapes/batch` | Queue multiple URLs (25s stagger) |
| `GET` | `/api/v1/batch/{id}` | Batch progress |
| `GET` | `/api/v1/scrapes` | History (paginated) |
| `GET` | `/api/v1/export/csv` | Export results as CSV |
| `GET` | `/health` | `{"status": "ok"}` |

### Example

```bash
curl -X POST http://localhost:8000/api/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.manchester.ac.uk/study/masters/courses/list/21573/msc-advanced-computer-science/"}'
```

Response:
```json
{
  "scrape_id": "abc123...",
  "status": "processing"
}
```

Poll until `status` is `"success"` or `"partial"`.

---

## Extracted schema

```json
{
  "university_name": "The University of Manchester",
  "program_name": "MSc Advanced Computer Science",
  "degree_level": "Master of Science",
  "program_duration": "12 months full-time",
  "intake_months": ["September"],
  "application_deadlines": "Staged admissions process with multiple selection deadlines",
  "min_academic_requirement": "First-class honours degree (70% average)...",
  "accepted_qualifications": "BSc Eng, BEng or BTech degree",
  "english_requirements": {
    "ielts": "7.0 overall with no sub-test below 6.5",
    "toefl": "100 iBT overall with no sub-test less than 22",
    "pte": null,
    "duolingo": null,
    "notes": "..."
  },
  "tuition_fees": {
    "domestic": "£15,300 per annum",
    "international": null,
    "currency": "GBP",
    "notes": "..."
  },
  "other_fees": null,
  "scholarships": "...",
  "work_experience": null,
  "other_requirements": "...",
  "confidence_notes": "...",
  "field_sources": {
    "university_name": "https://www.manchester.ac.uk/...",
    "english_requirements.ielts": "https://www.manchester.ac.uk/study/international/admissions/language-requirements",
    "tuition_fees.domestic": "https://www.manchester.ac.uk/study/masters/fees-and-funding/..."
  }
}
```

---

## Validation results

Validated against real university pages with bucket-based architecture. 

**Test Results:**
- Arkansas State MBA: 12/15 fields (80%), tuition ✅ working
- McGill MBA: 8/15 fields (53%)
- Edinburgh MSc: 7/15 fields (47%)
- Monash MBA: 3/15 fields (20%) - under investigation

Full validation reports in `uniscraper-backend/tests/validation/results/` and documentation files above.

Run a fresh validation:
```bash
cd uniscraper-backend
venv\Scripts\python scripts/test_single_url.py "https://gsas.harvard.edu/program/applied-physics"
```

---

## Rate limiting

Gemini free tier: 10 RPM. The system self-throttles to 3 RPM using:
- Global asyncio semaphore (one call at a time)
- 20s minimum gap between calls
- Rolling 60s window tracker
- Automatic fallback to local Qwen2.5:1.5b on consecutive 429s

Batch scrapes are staggered 25 seconds apart automatically.
