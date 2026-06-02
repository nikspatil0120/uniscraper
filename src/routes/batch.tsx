import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { X } from "lucide-react";

import { TopBar } from "@/components/TopBar";
import { PrimaryButton } from "@/components/PrimaryButton";
import { api, type ScrapeRecord } from "@/lib/api";
import { StatusBadge, ResultsCard } from "@/components/ResultsCard";

export const Route = createFileRoute("/batch")({
  head: () => ({
    meta: [
      { title: "Batch Scrape — UniScraper" },
      { name: "description", content: "Run dozens of university scrapes in parallel." },
    ],
  }),
  component: BatchPage,
});

// ── Detail drawer ─────────────────────────────────────────────────────────────

function DetailDrawer({
  scrapeId,
  onClose,
}: {
  scrapeId: string;
  onClose: () => void;
}) {
  const detail = useQuery({
    queryKey: ["scrape", scrapeId],
    queryFn: () => api.getScrape(scrapeId),
  });

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className="fixed top-0 right-0 h-screen w-full max-w-[620px] z-50 overflow-y-auto slide-up"
        style={{ background: "var(--bg-base)", borderLeft: "1px solid var(--border)" }}
      >
        {/* Header */}
        <div
          className="sticky top-0 z-10 px-6 py-4 flex items-center justify-between"
          style={{ background: "var(--bg-base)", borderBottom: "1px solid var(--border)" }}
        >
          <div
            className="font-ui uppercase text-[10px] tracking-widest-2"
            style={{ color: "var(--text-muted)" }}
          >
            Scrape Detail
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: "var(--text-secondary)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {detail.isLoading && <div className="h-96 rounded shimmer" />}
          {detail.data && <ResultsCard data={detail.data} />}
        </div>
      </div>
    </>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function BatchPage() {
  const [urlText, setUrlText] = useState("");
  const [ids, setIds] = useState<string[]>([]);
  const [urls, setUrls] = useState<string[]>([]);
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [queuing, setQueuing] = useState(false);

  const start = useMutation({
    mutationFn: (urls: string[]) => api.startBatch(urls),
    onMutate: () => setQueuing(true),
    onSuccess: (data, vars) => {
      setIds(data.scrape_ids);
      setUrls(vars);
      setDrawerId(null);
      toast.success(`Batch started — ${data.total} URLs`);
    },
    onError: (e: Error) => toast.error(e.message),
    onSettled: () => setQueuing(false),
  });

  const queries = useQueries({
    queries: ids.map((id) => ({
      queryKey: ["scrape", id],
      queryFn: () => api.getScrape(id),
      refetchInterval: (q: { state: { data?: ScrapeRecord } }) => {
        const s = q.state.data?.status;
        const inProgress = !s || s === "processing" || s === "running";
        return inProgress ? 3000 : false;
      },
    })),
  });

  const completed = queries.filter((q) => {
    const s = q.data?.status;
    return s && s !== "processing" && s !== "running";
  }).length;
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
        d?.tuition_fees?.international ?? "",
        d?.english_requirements?.ielts ?? "",
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
        {/* URL input */}
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
            loading={queuing}
            loadingText="QUEUING..."
          >
            Run Batch
          </PrimaryButton>
          {queuing && (
            <button
              onClick={() => setQueuing(false)}
              className="font-ui uppercase text-[10px] tracking-widest-2 mt-2 block"
              style={{ color: "var(--text-muted)" }}
            >
              Cancel
            </button>
          )}
        </div>

        {/* Progress bar */}
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

        {/* Summary stats */}
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

        {/* Live results table */}
        {total > 0 && (
          <div
            className="mt-10 rounded-xl overflow-hidden"
            style={{ border: "1px solid var(--border)" }}
          >
            <table style={{ width: "100%", tableLayout: "fixed", borderCollapse: "collapse" }}>
              <colgroup>
                <col style={{ width: "38%" }} />
                <col style={{ width: "14%" }} />
                <col style={{ width: "36%" }} />
                <col style={{ width: "12%" }} />
              </colgroup>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["URL", "Status", "Result Preview", ""].map((h) => (
                    <th
                      key={h}
                      className="font-ui uppercase text-[10px] tracking-widest-2"
                      style={{
                        color: "var(--text-muted)",
                        padding: "12px 16px",
                        textAlign: "left",
                        fontWeight: 400,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ids.map((id, i) => {
                  const q = queries[i];
                  const d = q.data;
                  const status = d?.status ?? "processing";
                  const inProgress = status === "processing" || status === "running";
                  const isDone = !inProgress && !!d;

                  return (
                    <tr
                      key={id}
                      style={{ background: i % 2 === 0 ? "var(--bg-surface)" : "transparent" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.background =
                          i % 2 === 0 ? "var(--bg-surface)" : "transparent")
                      }
                    >
                      {/* URL */}
                      <td
                        className="font-mono text-[12px]"
                        style={{
                          color: "var(--text-secondary)",
                          padding: "14px 16px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {urls[i]}
                      </td>

                      {/* Status */}
                      <td style={{ padding: "14px 16px" }}>
                        <div className="flex items-center gap-2">
                          {inProgress && (
                            <span
                              className="pulse-dot inline-block w-1.5 h-1.5 rounded-full"
                              style={{ background: "var(--warning)" }}
                            />
                          )}
                          <StatusBadge status={status} />
                        </div>
                      </td>

                      {/* Preview */}
                      <td
                        className="font-mono text-[12px]"
                        style={{
                          color: "var(--text-primary)",
                          padding: "14px 16px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {d?.university_name
                          ? `${d.university_name} — ${d.program_name ?? "—"}`
                          : inProgress
                            ? "Working..."
                            : "—"}
                      </td>

                      {/* View button */}
                      <td style={{ padding: "14px 16px", textAlign: "right" }}>
                        {isDone && (
                          <button
                            onClick={() => setDrawerId(id)}
                            className="font-ui uppercase text-[10px] tracking-widest-2 hover:underline"
                            style={{ color: "var(--accent)" }}
                          >
                            View →
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {drawerId && (
        <DetailDrawer scrapeId={drawerId} onClose={() => setDrawerId(null)} />
      )}
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
