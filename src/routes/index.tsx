import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

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

function ScrapePage() {
  const [url, setUrl] = useState("");
  const [hint, setHint] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const resultsRef = useRef<HTMLDivElement>(null);

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

  const detail = useQuery({
    queryKey: ["scrape", activeId],
    queryFn: () => api.getScrape(activeId!),
    enabled: !!activeId,
    refetchInterval: (q) => {
      const s = (q.state.data as ScrapeRecord | undefined)?.status;
      const inProgress = !s || s === "processing" || s === "running";
      return inProgress ? 2000 : false;
    },
  });

  useEffect(() => {
    if (!detail.data) return;
    const s = detail.data.status;
    if (s === "processing" || s === "running") return;
    qc.invalidateQueries({ queryKey: ["scrapes"] });
    if (s === "success") toast.success("Scrape complete");
    else if (s === "partial") toast.message("Partial extraction — some fields missing");
    else toast.error("Scrape failed");
  }, [detail.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) {
      toast.error("Enter a URL first");
      return;
    }
    startScrape.mutate({ url: url.trim(), hint: hint.trim() || undefined });
  };

  const isProcessing = !!activeId && (
    !detail.data ||
    detail.data.status === "processing" ||
    detail.data.status === "running"
  );
  const isDone = !!detail.data &&
    detail.data.status !== "processing" &&
    detail.data.status !== "running";

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
                style={{
                  background: "var(--bg-raised)",
                  color: "var(--text-primary)",
                  border: "1px solid transparent",
                }}
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
        </section>

        {/* RIGHT — results */}
        <section
          ref={resultsRef}
          className="relative p-10 grid-pattern flex-1 min-w-0 overflow-y-auto"
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

          {isProcessing && startedAt && (
            <ScrapeTimeline 
              startedAt={startedAt} 
              currentStep={detail.data?.current_step}
            />
          )}

          {isDone && detail.data && <ResultsCard data={detail.data} />}
        </section>
      </div>
    </div>
  );
}
