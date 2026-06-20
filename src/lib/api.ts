export const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined) || "";

// All backend routes live under /api/v1
// In dev: proxied by vite to http://localhost:8000/api/v1
// In prod: set VITE_API_URL=https://your-backend.com
const V1 = `${API_BASE}/api/v1`;

export type ScrapeStatus = "processing" | "running" | "success" | "partial" | "failed";

// Matches the backend ScrapeResult Pydantic model exactly
export interface EnglishRequirements {
  ielts?: string | null;
  toefl?: string | null;
  pte?: string | null;
  duolingo?: string | null;
  notes?: string | null;
}

export interface TuitionFees {
  domestic?: string | null;
  international?: string | null;
  currency?: string | null;
  breakdown?: string | null;
  notes?: string | null;
}

export interface ScrapeRecord {
  scrape_id: string;
  status: ScrapeStatus;
  created_at?: string;
  url_requested?: string;
  source_urls?: string[];
  source_count?: number;

  // Program identity
  university_name?: string | null;
  program_name?: string | null;
  degree_level?: string | null;
  program_duration?: string | null;

  // Intake & deadlines
  intake_months?: string[] | null;
  application_deadlines?: string | null;

  // Academic requirements
  min_academic_requirement?: string | null;
  accepted_qualifications?: string | null;

  // Language requirements
  english_requirements?: EnglishRequirements | null;

  // Fees
  tuition_fees?: TuitionFees | null;
  other_fees?: string | null;

  // Extras
  scholarships?: string | null;
  work_experience?: string | null;
  other_requirements?: string | null;

  // Metadata
  confidence_notes?: string | null;
  field_sources?: Record<string, string> | null;
  elapsed_seconds?: number | null;
  method_used?: string | null;
  tier_used?: number | null;          // 1 (Crawl4AI), 2 (Firecrawl), or 3 (httpx)
  pages_fetched?: number | null;      // Number of pages scraped
  llm_model?: string | null;          // LLM model used for extraction
  error?: string | null;
}

// Paginated list response from GET /api/v1/scrapes
export interface ScrapeListResponse {
  data: ScrapeRecord[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  // POST /api/v1/scrape — start a scrape, returns immediately
  startScrape: (url: string, context_hint?: string) =>
    http<{ scrape_id: string; status: ScrapeStatus }>(`${V1}/scrape`, {
      method: "POST",
      body: JSON.stringify({ url, context_hint }),
    }),

  // GET /api/v1/scrape/:id — poll for result
  getScrape: (id: string) => http<ScrapeRecord>(`${V1}/scrape/${id}`),

  // GET /api/v1/scrapes — paginated history list
  listScrapes: (page = 1, limit = 20) =>
    http<ScrapeListResponse>(`${V1}/scrapes?page=${page}&limit=${limit}`),

  // POST /api/v1/scrapes/batch — queue multiple URLs
  startBatch: (urls: string[]) =>
    http<{ batch_id: string; scrape_ids: string[]; total: number }>(`${V1}/scrapes/batch`, {
      method: "POST",
      body: JSON.stringify({ urls }),
    }),

  // GET /api/v1/batch/:id — batch job status
  getBatch: (batchId: string) => http<Record<string, unknown>>(`${V1}/batch/${batchId}`),

  // GET /api/v1/scrapes/export/csv — download all as CSV
  exportCsvUrl: () => `${V1}/scrapes/export/csv?all=true`,

  // GET /api/v1/scrapes/export/json — download all as JSON
  exportJsonUrl: () => `${V1}/scrapes/export/json?all=true`,

  // DELETE /api/v1/scrape/:id
  deleteScrape: (id: string): Promise<void> =>
    fetch(`${V1}/scrape/${id}`, { method: "DELETE" }).then((r) => {
      if (!r.ok && r.status !== 404) throw new Error("delete failed");
    }),
};

// ── Display helpers ───────────────────────────────────────────────────────────

export function fmt(v: unknown): { text: string; missing: boolean } {
  if (v === null || v === undefined || v === "" || v === "null") {
    return { text: "— not found", missing: true };
  }
  if (Array.isArray(v)) {
    if (v.length === 0) return { text: "— not found", missing: true };
    return { text: v.join(", "), missing: false };
  }
  return { text: String(v), missing: false };
}

// Convenience: flatten english_requirements for display
export function getEnglish(record: ScrapeRecord) {
  const e = record.english_requirements;
  return {
    ielts: e?.ielts ?? null,
    toefl: e?.toefl ?? null,
    pte: e?.pte ?? null,
    duolingo: e?.duolingo ?? null,
    notes: e?.notes ?? null,
  };
}

// Convenience: flatten tuition_fees for display
export function getFees(record: ScrapeRecord) {
  const f = record.tuition_fees;
  return {
    domestic: f?.domestic ?? null,
    international: f?.international ?? null,
    currency: f?.currency ?? null,
    breakdown: f?.breakdown ?? null,
    notes: f?.notes ?? null,
  };
}
