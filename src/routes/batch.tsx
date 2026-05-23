import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useMutation, useQueries } from "@tanstack/react-query";
import { toast } from "sonner";

import { TopBar } from "@/components/TopBar";
import { PrimaryButton } from "@/components/PrimaryButton";
import { api, type ScrapeRecord } from "@/lib/api";
import { StatusBadge } from "@/components/ResultsCard";

export const Route = createFileRoute("/batch")({
  head: () => ({
    meta: [
      { title: "Batch Scrape — UniScraper" },
      { name: "description", content: "Run dozens of university scrapes in parallel." },
    ],
  }),
  component: BatchPage,
});

function BatchPage() {
  const [urlText, setUrlText] = useState("");
  const [ids, setIds] = useState<string[]>([]);
  const [urls, setUrls] = useState<string[]>([]);

  const start = useMutation({
    mutationFn: (urls: string[]) => api.startBatch(urls),
    onSuccess: (data, vars) => {
      setIds(data.scrape_ids);
      setUrls(vars);
      toast.success(`Batch started — ${data.total} URLs`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const queries = useQueries({
    queries: ids.map((id) => ({
      queryKey: ["scrape", id],
      queryFn: () => api.getScrape(id),
      refetchInterval: (q: { state: { data?: ScrapeRecord } }) =>
        q.state.data && q.state.data.status !== "processing" ? false : 3000,
    })),
  });

  const completed = queries.filter((q) => q.data && q.data.status !== "processing").length;
  const total = ids.length;
  const allDone = total > 0 && completed === total;

  const stats = useMemo(() => {
    const success = queries.filter((q) => q.data?.status === "success").length;
    const partial = queries.filter((q) => q.data?.status === "partial").length;
    const failed = queries.filter((q) => q.data?.status === "failed").length;
    return { success, partial, failed };
  }, [queries]);

  const handleRun = () => {
    const list = urlText
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (list.length === 0) {
      toast.error("Add at least one URL");
      return;
    }
    start.mutate(list);
  };

  const downloadAllCsv = () => {
    const headers = ["url", "university", "program", "status", "international_tuition", "ielts"];
    const rows = queries.map((q, i) => {
      const d = q.data;
      return [
        urls[i],
        d?.university_name ?? "",
        d?.program_name ?? "",
        d?.status ?? "pending",
        d?.international_tuition ?? "",
        d?.ielts ?? "",
      ]
        .map((c) => `"${String(c).replace(/"/g, '""')}"`)
        .join(",");
    });
    const blob = new Blob([[headers.join(","), ...rows].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `batch-${Date.now()}.csv`;
    a.click();
  };

  return (
    <div className="page-in">
      <TopBar title="Batch Scrape" />

      <div className="px-10 py-8 max-w-[1100px]">
        <div className="mb-3">
          <label
            className="font-ui uppercase text-[10px] tracking-widest-2 block mb-2"
            style={{ color: "var(--text-secondary)" }}
          >
            Enter URLs — One Per Line
          </label>
          <textarea
            value={urlText}
            onChange={(e) => setUrlText(e.target.value)}
            placeholder={
              "https://university-a.edu/programs/cs-msc\nhttps://university-b.edu/programs/data-science"
            }
            className="w-full font-mono text-[13px] rounded-lg px-5 py-4 focus-glow resize-y"
            style={{
              minHeight: 200,
              background: "var(--bg-raised)",
              color: "var(--text-primary)",
              border: "1px solid transparent",
            }}
          />
        </div>

        <div className="max-w-[300px]">
          <PrimaryButton
            type="button"
            onClick={handleRun}
            loading={start.isPending}
            loadingText="QUEUING..."
          >
            Run Batch
          </PrimaryButton>
        </div>

        {/* Progress */}
        {total > 0 && !allDone && (
          <div className="mt-10">
            <div
              className="overflow-hidden"
              style={{ width: "100%", height: 4, background: "#1A1A24", borderRadius: 2 }}
            >
              <div
                className="transition-all duration-500"
                style={{
                  height: 4,
                  borderRadius: 2,
                  background: "linear-gradient(90deg, #4FFFB0, #7AFFCC)",
                  width: `${(completed / total) * 100}%`,
                }}
              />
            </div>
            <div
              className="font-mono"
              style={{ marginTop: 10, fontSize: 13, color: "#4FFFB0" }}
            >
              {completed} / {total} COMPLETE
            </div>
          </div>
        )}

        {/* Summary */}
        {allDone && (
          <div className="mt-10">
            <div
              className="flex flex-col sm:flex-row slide-up"
              style={{ gap: 16, marginBottom: 32 }}
            >
              <StatCard label="Successful" value={stats.success} tone="#4FFFB0" />
              <StatCard label="Partial" value={stats.partial} tone="#FFB84F" />
              <StatCard label="Failed" value={stats.failed} tone="#FF5C5C" />
            </div>
            <div className="max-w-[320px]">
              <PrimaryButton type="button" onClick={downloadAllCsv}>
                Download All as CSV
              </PrimaryButton>
            </div>
          </div>
        )}

        {/* Live table */}
        {total > 0 && (
          <div
            className="mt-10 rounded-xl overflow-hidden"
            style={{ border: "1px solid var(--border)" }}
          >
            <div
              className="grid grid-cols-[3fr_1fr_3fr] gap-4 px-6 py-3"
              style={{ borderBottom: "1px solid var(--border)" }}
            >
              {["URL", "Status", "Result Preview"].map((h) => (
                <div
                  key={h}
                  className="font-ui uppercase text-[10px] tracking-widest-2"
                  style={{ color: "var(--text-muted)" }}
                >
                  {h}
                </div>
              ))}
            </div>

            {ids.map((id, i) => {
              const q = queries[i];
              const d = q.data;
              const status = d?.status ?? "processing";
              const isProc = status === "processing";
              return (
                <div
                  key={id}
                  className="grid grid-cols-[3fr_1fr_3fr] gap-4 px-6 py-4 items-center"
                  style={{ background: i % 2 === 0 ? "var(--bg-surface)" : "transparent" }}
                >
                  <div
                    className="font-mono text-[12px] truncate"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {urls[i]}
                  </div>
                  <div className="flex items-center gap-2">
                    {isProc && (
                      <span
                        className="pulse-dot inline-block w-1.5 h-1.5 rounded-full"
                        style={{ background: "var(--warning)" }}
                      />
                    )}
                    <StatusBadge status={status} />
                  </div>
                  <div
                    className="font-mono text-[12px] truncate"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {d?.university_name
                      ? `${d.university_name} — ${d.program_name ?? "—"}`
                      : isProc
                        ? "Working..."
                        : "—"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div
      style={{
        flex: 1,
        padding: "28px 24px",
        background: "#111118",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: 12,
      }}
    >
      <div className="font-display italic leading-none" style={{ fontSize: 56, color: tone }}>
        {value}
      </div>
      <div
        className="font-ui uppercase"
        style={{ marginTop: 12, fontSize: 10, letterSpacing: "0.15em", color: "#4A4958" }}
      >
        {label}
      </div>
    </div>
  );
}
