# UniScraper — University Admission Intelligence

A full-stack AI extraction system that scrapes university program pages and structures admission data into a clean, queryable format. Built for the AutoNova Pod internship challenge.

---

## What it does

Paste a university program URL → get back structured admission data in ~15 seconds:

- IELTS / TOEFL / PTE / Duolingo requirements
- Tuition fees (domestic + international, with currency)
- Application deadlines
- Academic entry requirements
- Program duration, intake months, degree level
- Scholarships and other requirements

Every field includes a `field_sources` attribution showing which URL the data came from.

---

## Architecture

```
Frontend (React + TanStack)
    │
    └── FastAPI Backend (Python)
            │
            ├── Fetcher          httpx → Playwright fallback
            ├── Link Extractor   scores sub-pages by relevance
            ├── Page Classifier  admissions / english / tuition / etc.
            ├── AI Extractor     field-specific context routing
            │       ├── PRIMARY   Gemini 2.5 Flash
            │       ├── FALLBACK  Qwen2.5:1.5b via Ollama (local)
            │       └── FALLBACK  Gemini 2.5 Flash-Lite
            ├── Regex Extractor  pre-extracts scores/fees as anchors
            ├── Field Validator  semantic sanity checks
            └── MongoDB          stores all results
```

### Key design decisions

**Field-specific page routing** — instead of dumping all page text into one prompt, each field group (english requirements, fees, deadlines) gets routed to the most relevant sub-page. IELTS comes from the language requirements page, fees from the fee page, etc.

**Hybrid LLM routing** — Gemini Flash is primary. On rate limits (429), the system automatically falls back to a local Qwen2.5:1.5b model via Ollama, then to Gemini Flash-Lite. No scrape ever fails due to quota.

**Accordion/hidden content** — university sites often hide IELTS tables inside collapsed accordions. The HTML cleaner explicitly reveals `hidden` and `aria-hidden` elements before parsing.

**24h URL cache** — submitting the same URL twice within 24 hours returns the cached result instantly.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, TanStack Router/Query, Tailwind CSS v4 |
| Backend | FastAPI, Python 3.12, asyncio |
| Database | MongoDB Atlas |
| Primary LLM | Gemini 2.5 Flash |
| Local LLM | Qwen2.5:1.5b via Ollama |
| HTTP | httpx (async) |
| HTML parsing | BeautifulSoup + lxml |

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

Pre-validated against real university pages. Results stored in `uniscraper-backend/tests/validation/results/`.

Run a validation:
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
