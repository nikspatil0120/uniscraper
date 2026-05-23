export const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000";

export type ScrapeStatus = "processing" | "success" | "partial" | "failed";

export interface ScrapeRecord {
  scrape_id: string;
  status: ScrapeStatus;
  university_name?: string | null;
  program_name?: string | null;
  degree_level?: string | null;
  duration?: string | null;
  intake_months?: string | null;
  application_deadlines?: string | null;
  min_academic_requirement?: string | null;
  accepted_qualifications?: string | null;
  work_experience?: string | null;
  ielts?: string | null;
  toefl?: string | null;
  pte?: string | null;
  duolingo?: string | null;
  language_notes?: string | null;
  international_tuition?: string | null;
  domestic_tuition?: string | null;
  currency?: string | null;
  other_fees?: string | null;
  scholarships?: string | null;
  financial_aid?: string | null;
  other_requirements?: string | null;
  confidence_notes?: string | null;
  sources?: string[] | null;
  url?: string;
  created_at?: string;
  extracted_fields?: number;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
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
  startScrape: (url: string, context_hint?: string) =>
    http<{ scrape_id: string; status: ScrapeStatus }>("/scrape", {
      method: "POST",
      body: JSON.stringify({ url, context_hint }),
    }),
  getScrape: (id: string) => http<ScrapeRecord>(`/scrape/${id}`),
  listScrapes: (page = 1, limit = 20) =>
    http<{ items: ScrapeRecord[]; total: number; page: number; limit: number }>(
      `/scrapes?page=${page}&limit=${limit}`,
    ),
  startBatch: (urls: string[]) =>
    http<{ batch_id: string; scrape_ids: string[]; total: number }>("/scrapes/batch", {
      method: "POST",
      body: JSON.stringify({ urls }),
    }),
  exportCsvUrl: () => `${API_URL}/scrapes/export/csv`,
  deleteScrape: (id: string) =>
    fetch(`${API_URL}/scrape/${id}`, { method: "DELETE" }).then((r) => {
      if (!r.ok) throw new Error("delete failed");
    }),
};

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
