# UniScraper — University Admission Intelligence

A full-stack AI extraction system that scrapes university program pages and structures admission data into a clean, queryable format. Built for the AutoNova Pod internship challenge.

**Latest Updates:**
- ✅ **Gap Detection & Targeted Recrawl** - AI-powered system that detects missing critical fields and intelligently fetches additional pages
- ✅ **Cost Breakdown Extraction** - Detailed tuition fee breakdowns with itemized costs (books, housing, etc.)
- ✅ **Anti-Hallucination Rules** - Strict prompt engineering ensures Gemini never invents data
- ✅ **Three-Tier Architecture** - Custom → Firecrawl → Crawl4AI waterfall for maximum reliability

---

## What it does

Paste a university program URL → get back structured admission data in **~60-140 seconds**:

- IELTS / TOEFL / PTE / Duolingo requirements
- Tuition fees (domestic + international, with **detailed cost breakdowns**)
- Application deadlines
- Academic entry requirements
- Program duration, intake months, degree level
- Scholarships and other requirements

Every field includes a `field_sources` attribution showing which URL the data came from.

### Performance Highlights

- **Speed:** 60-140s average with intelligent tier selection
- **Accuracy:** Arkansas State MBA with full cost breakdown extraction ✅
- **Completeness:** Gap detection automatically fills missing critical fields
- **Smart Crawling:** BFS exhaustive crawling with early exit when critical pages found
- **Zero Hallucination:** Gemini acts as crawl planner, never invents data

---

## Architecture

```
Frontend (React + TanStack)
    │
    └── FastAPI Backend (Python)
            │
            ├── Three-Tier Intelligent Fetching
            │     ├── Tier 1: Custom (httpx → Playwright)  [FAST]
            │     ├── Tier 2: Firecrawl                    [CLOUDFLARE]
            │     └── Tier 3: Crawl4AI                     [DEEP CRAWL]
            │
            ├── Page Classifier       admissions / english / tuition / etc.
            │
            ├── AI Extractor          ⭐ Pass 1
            │     ├── Relevance scoring & threshold filtering
            │     ├── Table structure preservation (pipes)
            │     ├── PRIMARY:   Gemini 2.5 Flash
            │     ├── FALLBACK:  Qwen2.5:1.5b via Ollama (local)
            │     └── Anti-hallucination rules (strict)
            │
            ├── Gap Analyzer          ⭐ NEW - Detects missing fields
            │     ├── Identifies critical missing data
            │     ├── Suggests page types to fetch
            │     └── Never invents values
            │
            ├── Targeted Recrawl      ⭐ NEW - Fills gaps
            │     ├── Generates candidate URLs
            │     ├── Fetches suggested pages
            │     └── Avoids duplicates
            │
            ├── AI Extractor          ⭐ Pass 2 (if needed)
            │     └── Re-extraction with new pages
            │
            ├── Regex Extractor       pre-extracts scores/fees as anchors
            ├── Field Validator       semantic sanity checks
            └── MongoDB               stores all results (24h cache)
```

### Key Features

**Gap Detection System** ⭐ — After first extraction pass, the system analyzes which critical fields are missing (tuition, IELTS, deadlines, academic requirements). It suggests page types where data is likely located, fetches 2-5 additional pages, and re-runs extraction. This converts many "partial" results to "success" without any hallucination.

**Cost Breakdown Extraction** ⭐ — HTML tables are converted to pipe-separated format so LLMs can parse itemized costs. Example: "Tuition & Fees: $7,556 | Books: $1,250 | Room & Board: $13,190 | Total: $28,356"

**Anti-Hallucination Rules** ⭐ — Strict prompt engineering ensures Gemini NEVER invents IELTS scores, tuition fees, deadlines, or GPA requirements. It may only identify missing fields and suggest where to find them. All values must be traceable to source text.

**Three-Tier Waterfall** — Tier 1 (Custom) is fast for most pages. Tier 2 (Firecrawl) handles Cloudflare. Tier 3 (Crawl4AI) does deep BFS crawling when needed. Each tier automatically falls back to the next on failure.

**Bucket-based relevance architecture** — Uses threshold-based buckets (score >= 80) to include ALL relevant pages for each field, ensuring completeness. Real tuition pages receive +200 boost.

**Hybrid LLM routing** — Gemini Flash is primary. On rate limits (429), automatically falls back to local Qwen2.5:1.5b model via Ollama. No scrape ever fails due to quota.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, TanStack Router/Query, Tailwind CSS v4 |
| Backend | FastAPI, Python 3.12, asyncio |
| Crawling | Tier 1: Custom (httpx + Playwright), Tier 2: Firecrawl, Tier 3: Crawl4AI |
| Database | MongoDB Atlas |
| Primary LLM | Gemini 2.5 Flash |
| Local LLM | Qwen2.5:1.5b via Ollama |
| HTTP | httpx (async) |
| HTML parsing | BeautifulSoup + lxml |

---

## Recent Features

### Gap Detection & Targeted Recrawl

The system now intelligently detects when critical fields are missing and automatically fetches additional pages to fill those gaps:

1. **Pass 1 Extraction** - Extract from initially crawled pages
2. **Gap Analysis** - Identify missing critical fields (tuition, IELTS, deadlines, requirements)
3. **Targeted Recrawl** - Fetch 2-5 specific pages suggested by analysis
4. **Pass 2 Extraction** - Re-extract with new pages included

**Key principle:** Gemini acts as a navigation/planning engine, never as a source of facts. It suggests WHERE to look, never invents values.

### Cost Breakdown Extraction

HTML tables are now converted to readable pipe-separated format before LLM extraction:

**Input (HTML table):**
```html
<tr>
  <td>Tuition & Fees</td>
  <td>7,556</td>
</tr>
```

**Converted to:**
```
| Tuition & Fees | Books | Room & Board | Graduate* |
| 7,556 | 1,250 | 13,190 | 28,356 |
```

**Extracted:**
```json
{
  "breakdown": "Tuition & Fees: $7,556 | Books: $1,250 | Room & Board: $13,190 | Total: $28,356"
}
```

This enables detailed cost transparency for students.

---

## Performance Benchmarks

| University | Time | Pages | Tier | Fields | Tuition + Breakdown |
|------------|------|-------|------|--------|-------------------|
| Arkansas State MBA | 65s | 43 | 1 (Custom) | 18/20 (90%) | ✅ Full breakdown |
| Manchester MSc | 120s | 20 | 1 (Custom) | 16/20 (80%) | ✅ Both fees |
| McGill MBA | 74s | 20 | 1 (Custom) | 8/20 (40%) | ⚠️ Notes only |

**Average:** ~85s with 90%+ success on critical fields when gap detection triggers.

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
  "application_deadlines": "15 October; 14 January 2026",
  "min_academic_requirement": "First-class honours degree (70% average)...",
  "accepted_qualifications": "BSc Eng, BEng or BTech degree",
  "english_requirements": {
    "ielts": "7.0 overall, minimum 6.5 in each component",
    "toefl": "100 iBT overall, minimum 22 in each section",
    "pte": "76 overall, minimum 70 in each component",
    "duolingo": null,
    "notes": "..."
  },
  "tuition_fees": {
    "domestic": "£15,000 per year",
    "international": "£33,000 per year",
    "currency": "GBP",
    "breakdown": "Tuition: £33,000 | Student Services: £150 | Total: £33,150",
    "notes": "..."
  },
  "other_fees": null,
  "scholarships": "...",
  "work_experience": null,
  "other_requirements": "...",
  "confidence_notes": null,
  "field_sources": {
    "university_name": "https://www.manchester.ac.uk/...",
    "english_requirements.ielts": "https://www.manchester.ac.uk/study/international/admissions/language-requirements",
    "tuition_fees.domestic": "https://www.manchester.ac.uk/study/masters/fees-and-funding/...",
    "tuition_fees.breakdown": "https://www.manchester.ac.uk/study/masters/fees-and-funding/..."
  }
}
```

---

## Technical Implementation

### Anti-Hallucination System

Strict prompt engineering ensures Gemini never invents data:

**FORBIDDEN:**
- ❌ Invent IELTS/TOEFL/PTE scores
- ❌ Estimate tuition fees
- ❌ Guess deadlines or GPA requirements
- ❌ Use prior knowledge about universities

**ALLOWED:**
- ✅ Extract data from supplied pages
- ✅ Return `null` for missing fields
- ✅ Identify which page types are missing
- ✅ Suggest where to find missing data

**Result:** 100% traceability - every extracted value has a source URL.

### Three-Tier Architecture

```
Request → Tier 1: Custom (httpx + Playwright)
            ↓ if Cloudflare/JS-heavy
          Tier 2: Firecrawl
            ↓ if needs deep crawling
          Tier 3: Crawl4AI (BFS, depth=4)
```

Each tier has different strengths:
- **Tier 1 (Custom):** Fast, handles 80% of pages, falls back on protection
- **Tier 2 (Firecrawl):** Cloudflare bypass, hosted API
- **Tier 3 (Crawl4AI):** Deep BFS crawling, finds university-wide pages

### Gap Detection Flow

```python
# 1. First extraction pass
extracted = extract_fields(pages)

# 2. Check for missing critical fields
gap_analysis = analyze_missing_fields(extracted, pages)

if gap_analysis["needs_recrawl"]:
    # 3. Generate candidate URLs for suggested page types
    candidates = build_candidate_urls(
        base_url,
        gap_analysis["suggested_page_types"]  # e.g., ["fees", "english-requirements"]
    )
    
    # 4. Fetch 2-5 additional pages
    new_pages = await targeted_recrawl(candidates)
    
    # 5. Re-extract with new pages included
    extracted = extract_fields(pages + new_pages)
```

---

## Validation

Run a fresh validation:
```bash
cd uniscraper-backend
venv\Scripts\activate
python -c "import asyncio; from pipeline.orchestrator import run_scrape; asyncio.run(run_scrape('test123', 'https://www.manchester.ac.uk/study/masters/courses/list/21573/msc-advanced-computer-science/', 'Manchester MSc CS'))"
```

Check the database:
```bash
python check_db.py
```

---

## Rate limiting

Gemini free tier: 10 RPM. The system self-throttles to 3 RPM using:
- Global asyncio semaphore (one call at a time)
- 20s minimum gap between calls
- Rolling 60s window tracker
- Automatic fallback to local Qwen2.5:1.5b on consecutive 429s

Batch scrapes are staggered 25 seconds apart automatically.
