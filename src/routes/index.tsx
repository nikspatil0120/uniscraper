import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronDown } from "lucide-react";

import { TopBar } from "@/components/TopBar";
import { PrimaryButton } from "@/components/PrimaryButton";
import { ScrapeTimeline } from "@/components/ScrapeTimeline";
import { ResultsCard } from "@/components/ResultsCard";
import { api, type ScrapeRecord } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Scrape — UniScraper" },
      { name: "description", content: "Scrape a university program page and extract admission data with AI." },
    ],
  }),
  component: ScrapePage,
});

const RECENT_KEY = "uniscraper.recent";

interface RecentItem {
  id: string;
  name: string;
  ts: number;
}

function loadRecent(): RecentItem[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
  } catch {
    return [];
  }
}

function pushRecent(item: RecentItem) {
  const all = [item, ...loadRecent().filter((r) => r.id !== item.id)].slice(0, 3);
  localStorage.setItem(RECENT_KEY, JSON.stringify(all));
}

function formatRelativeTime(ts: number) {
  const diff = Math.max(0, Date.now() - ts);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function ScrapePage() {
  const [url, setUrl] = useState("");
  const [hint, setHint] = useState("");
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchUrls, setBatchUrls] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [recent, setRecent] = useState<RecentItem[]>([]);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setRecent(loadRecent());
  }, []);

  const startScrape = useMutation({
    mutationFn: (vars: { url: string; hint?: string }) =>
      api.startScrape(vars.url, vars.hint),
    onSuccess: (data) => {
      setActiveId(data.scrape_id);
      setStartedAt(Date.now());
      navigate({ to: "/", replace: true });
    },
    onError: (e: Error) => toast.error(e.message || "Failed to start scrape"),
  });

  const startBatch = useMutation({
    mutationFn: (urls: string[]) => api.startBatch(urls),
    onSuccess: (d) => toast.success(`Batch started — ${d.total} URLs queued`),
    onError: (e: Error) => toast.error(e.message),
  });

  const detail = useQuery({
    queryKey: ["scrape", activeId],
    queryFn: () => api.getScrape(activeId!),
    enabled: !!activeId,
    refetchInterval: (q) => {
      const s = (q.state.data as ScrapeRecord | undefined)?.status;
      return s && s !== "processing" ? false : 2000;
    },
  });

  useEffect(() => {
    if (detail.data && detail.data.status !== "processing") {
      const name = detail.data.university_name || detail.data.url || activeId || "Scrape";
      pushRecent({ id: detail.data.scrape_id, name, ts: Date.now() });
      setRecent(loadRecent());
      qc.invalidateQueries({ queryKey: ["scrapes"] });
      if (detail.data.status === "success") toast.success("Scrape complete");
      else if (detail.data.status === "partial") toast.message("Partial extraction");
      else toast.error("Scrape failed");
    }
  }, [detail.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) {
      toast.error("Enter a URL first");
      return;
    }
    startScrape.mutate({ url: url.trim(), hint: hint.trim() || undefined });
  };

  const handleBatch = () => {
    const urls = batchUrls
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length === 0) {
      toast.error("Add at least one URL");
      return;
    }
    startBatch.mutate(urls);
  };

  const isProcessing = !!activeId && detail.data?.status === "processing";
  const isDone = detail.data && detail.data.status !== "processing";

  return (
    <div className="page-in h-screen overflow-hidden flex flex-col">
      <TopBar title="Scrape" />

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* LEFT — input */}
        <section
          className="p-10 flex flex-col gap-6 overflow-y-auto"
          style={{
            width: "45%",
            minWidth: 360,
            borderRight: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div>
              <label
                className="font-ui uppercase text-[10px] tracking-widest-2 block mb-2"
                style={{ color: "var(--text-secondary)" }}
              >
                Target URL
              </label>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://university.edu/programs/..."
                className="w-full font-mono text-[14px] rounded-lg px-5 py-4 focus-glow transition-all"
                style={{
                  background: "var(--bg-raised)",
                  color: "var(--text-primary)",
                  border: "1px solid transparent",
                }}
              />
            </div>

            <div>
              <label
                className="font-ui uppercase text-[10px] tracking-widest-2 block mb-2"
                style={{ color: "var(--text-secondary)" }}
              >
                Context Hint (Optional)
              </label>
              <input
                value={hint}
                onChange={(e) => setHint(e.target.value)}
                placeholder="e.g. fees for international students"
                className="w-full font-mono text-[13px] rounded-lg px-4 py-3 focus-glow"
                style={{ background: "var(--bg-raised)", color: "var(--text-primary)", border: "1px solid transparent" }}
              />
            </div>

            <PrimaryButton
              type="submit"
              loading={startScrape.isPending || isProcessing}
              loadingText="SCRAPING..."
            >
              Scrape
            </PrimaryButton>
          </form>

          <div style={{ borderTop: "1px solid var(--border)" }} className="pt-5">
            <button
              type="button"
              onClick={() => setBatchOpen((v) => !v)}
              className="font-ui uppercase text-[10px] tracking-widest-2 flex items-center gap-2 mb-3"
              style={{ color: "var(--text-secondary)" }}
            >
              <ChevronDown
                size={12}
                style={{
                  transform: batchOpen ? "rotate(180deg)" : "rotate(0)",
                  transition: "transform 200ms",
                }}
              />
              Batch Mode
            </button>
            {batchOpen && (
              <div className="flex flex-col gap-3">
                <textarea
                  value={batchUrls}
                  onChange={(e) => setBatchUrls(e.target.value)}
                  rows={5}
                  placeholder={"https://uni-a.edu/program-1\nhttps://uni-b.edu/program-2"}
                  className="w-full font-mono text-[13px] rounded-lg px-4 py-3 focus-glow resize-y"
                  style={{
                    background: "var(--bg-raised)",
                    color: "var(--text-primary)",
                    border: "1px solid transparent",
                  }}
                />
                <PrimaryButton
                  type="button"
                  onClick={handleBatch}
                  loading={startBatch.isPending}
                  loadingText="QUEUING..."
                >
                  Scrape All
                </PrimaryButton>
              </div>
            )}
          </div>

          <div className="mt-auto pt-8" style={{ borderTop: "1px solid var(--border)" }}>
              <div
                className="font-ui uppercase text-[9px] tracking-widest-2 mb-3"
                style={{ color: "var(--text-muted)" }}
              >
                Recent
              </div>
              {recent.length > 0 ? (
                <ul className="flex flex-col gap-1">
                  {recent.slice(0, 3).map((r) => (
                    <li key={r.id}>
                      <button
                        onClick={() => {
                          setActiveId(r.id);
                          setStartedAt(Date.now() - 16000);
                        }}
                        className="w-full text-left font-ui text-[12px] py-1.5 flex justify-between items-center transition-colors"
                        style={{ color: "#8B8A97", cursor: "pointer" }}
                      >
                        <span className="truncate">{r.name}</span>
                        <span className="ml-3 shrink-0">{formatRelativeTime(r.ts)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="font-ui text-[12px]" style={{ color: "var(--text-muted)" }}>
                  No scrapes yet
                </div>
              )}
            </div>
        </section>

        {/* RIGHT — results */}
        <section
          ref={resultsRef}
          className="relative p-10 grid-pattern flex-1 min-w-0"
        >
          {!activeId && !isProcessing && !isDone && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div
                className="font-display italic leading-none"
                style={{ fontSize: 180, color: "rgba(242,239,233,0.04)" }}
              >
                0
              </div>
              <div
                className="mt-6 font-ui uppercase tracking-widest-2"
                style={{ fontSize: 13, color: "#4A4958" }}
              >
                Paste a URL and hit scrape
              </div>
            </div>
          )}

          {isProcessing && startedAt && <ScrapeTimeline startedAt={startedAt} />}

          {isDone && detail.data && <ResultsCard data={detail.data} />}
        </section>
      </div>
    </div>
  );
}
