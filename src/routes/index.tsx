import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { BookOpen, HelpCircle, Link2 } from "lucide-react";

import { TopBar } from "@/components/TopBar";
import { PrimaryButton } from "@/components/PrimaryButton";
import { ScrapeTimeline } from "@/components/ScrapeTimeline";
import { ResultsCard } from "@/components/ResultsCard";
import { api, type ScrapeRecord } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Compile — UniScraper" },
      { name: "description", content: "Extract university admission criteria and organize program specifications." },
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
    onError: (e: Error) => toast.error(e.message || "Failed to start compilation"),
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
    if (s === "success") toast.success("Compilation complete");
    else if (s === "partial") toast.message("Partial compilation — some criteria could not be archived");
    else toast.error("Compilation failed");
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
    <div className="page-in h-screen overflow-hidden flex flex-col" style={{ background: "#FFFCF9" }}>
      <TopBar title="AI Scraper" />

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* LEFT — Input Form */}
        <section
          className="p-10 flex flex-col gap-8 overflow-y-auto"
          style={{
            width: "42%",
            minWidth: 380,
            borderRight: "1px solid #EDE5DC",
            background: "#FBF7F3",
          }}
        >
          <div className="flex flex-col gap-2">
            <h2
              className="font-display italic text-[22px] font-bold"
              style={{ color: "#2C1F17" }}
            >
              Compile Program Data
            </h2>
            <p
              className="font-ui text-[12px] leading-relaxed"
              style={{ color: "#9E9189" }}
            >
              Submit a university course catalog page or program description. The compiler will fetch page content, map local links, and structure the admission criteria into a clean archive.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            {/* Target URL field */}
            <div className="flex flex-col gap-2">
              <label
                className="font-ui uppercase text-[9px] font-bold tracking-widest-2 flex items-center gap-1.5"
                style={{ color: "#9E9189" }}
              >
                <Link2 size={11} style={{ color: "#C25520" }} /> Target URL
              </label>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://university.edu/programs/computer-science"
                className="w-full font-mono text-[13px] rounded-lg px-4 py-3.5 transition-all duration-300 focus:outline-none"
                style={{
                  background: "#FFFFFF",
                  color: "#2C1F17",
                  border: "1px solid #E8DDD4",
                  boxShadow: "inset 0 1px 3px rgba(0,0,0,0.04)",
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = "#C25520";
                  e.currentTarget.style.boxShadow = "0 0 0 3px rgba(194, 85, 32, 0.08), inset 0 1px 3px rgba(0,0,0,0.04)";
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = "#E8DDD4";
                  e.currentTarget.style.boxShadow = "inset 0 1px 3px rgba(0,0,0,0.04)";
                }}
              />
            </div>

            {/* Hint field */}
            <div className="flex flex-col gap-2">
              <label
                className="font-ui uppercase text-[9px] font-bold tracking-widest-2 flex items-center gap-1.5"
                style={{ color: "#9E9189" }}
              >
                <HelpCircle size={11} style={{ color: "#C25520" }} /> Context Hint (Optional)
              </label>
              <input
                value={hint}
                onChange={(e) => setHint(e.target.value)}
                placeholder="e.g., Extract international student fees specifically"
                className="w-full font-mono text-[12px] rounded-lg px-4 py-3.5 transition-all duration-300 focus:outline-none"
                style={{
                  background: "#FFFFFF",
                  color: "#2C1F17",
                  border: "1px solid #E8DDD4",
                  boxShadow: "inset 0 1px 3px rgba(0,0,0,0.04)",
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = "#C25520";
                  e.currentTarget.style.boxShadow = "0 0 0 3px rgba(194, 85, 32, 0.08), inset 0 1px 3px rgba(0,0,0,0.04)";
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = "#E8DDD4";
                  e.currentTarget.style.boxShadow = "inset 0 1px 3px rgba(0,0,0,0.04)";
                }}
              />
            </div>

            <PrimaryButton
              type="submit"
              loading={startScrape.isPending || isProcessing}
              loadingText="COMPILING PAGE..."
              className="mt-2"
            >
              Compile Program Details
            </PrimaryButton>
          </form>
        </section>

        {/* RIGHT — Results View */}
        <section
          ref={resultsRef}
          className="relative p-10 flex-1 min-w-0 overflow-y-auto"
          style={{
            background: "#FFFCF9",
          }}
        >
          {!activeId && !isProcessing && !isDone && (
            <div className="flex flex-col items-center justify-center h-full text-center max-w-lg mx-auto">
              {/* Abstract graphic */}
              <div className="relative mb-8 flex items-center justify-center">
                <div
                  className="absolute w-28 h-28 rounded-full opacity-30"
                  style={{
                    background: "radial-gradient(circle, #FDDCC8 0%, transparent 70%)",
                    filter: "blur(12px)",
                  }}
                />
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center relative"
                  style={{
                    background: "#FEF3EC",
                    border: "1px dashed #F5C9A8",
                  }}
                >
                  <BookOpen size={22} style={{ color: "#C25520" }} className="animate-pulse" />
                </div>
              </div>

              <h3
                className="font-display italic text-[24px] font-bold mb-3"
                style={{ color: "#2C1F17" }}
              >
                Awaiting Ingestion
              </h3>
              <p
                className="font-ui text-[12px] leading-relaxed mb-6"
                style={{ color: "#9E9189" }}
              >
                Please enter a valid university URL in the input field on the left. The compiler will ingest the page details, parse catalog sub-links, and record the criteria.
              </p>

              <div
                className="flex items-center gap-2 px-3 py-1.5 rounded-md"
                style={{
                  border: "1px solid #E8DDD4",
                  background: "#F5F0EA",
                }}
              >
                <span
                  className="font-mono text-[10px] tracking-wider uppercase"
                  style={{ color: "#C4B5AA" }}
                >
                  READY TO COMPILE
                </span>
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