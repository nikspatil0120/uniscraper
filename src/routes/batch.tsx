import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { X, FileSpreadsheet, ListPlus, PlayCircle, BarChart3 } from "lucide-react";

import { TopBar } from "@/components/TopBar";
import { PrimaryButton } from "@/components/PrimaryButton";
import { api, type ScrapeRecord } from "@/lib/api";
import { StatusBadge, ResultsCard } from "@/components/ResultsCard";

export const Route = createFileRoute("/batch")({
  head: () => ({
    meta: [
      { title: "Batch Compiler — UniScraper" },
      { name: "description", content: "Run multiple university program compilations in parallel." },
    ],
  }),
  component: BatchPage,
});

function DetailDrawer({ scrapeId, onClose }: { scrapeId: string; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ["scrape", scrapeId],
    queryFn: () => api.getScrape(scrapeId),
  });

  return (
    <>
      <div
        className="fixed inset-0 z-40 transition-opacity duration-300"
        style={{ background: "rgba(44, 31, 23, 0.35)", backdropFilter: "blur(6px)" }}
        onClick={onClose}
      />
      <div
        className="fixed top-0 right-0 h-screen w-full max-w-[620px] z-50 overflow-y-auto slide-up"
        style={{
          background: "#FFFCF9",
          borderLeft: "1px solid #EDE5DC",
          boxShadow: "-10px 0 40px rgba(44, 31, 23, 0.1)",
        }}
      >
        <div
          className="sticky top-0 z-10 px-8 py-5 flex items-center justify-between"
          style={{ background: "#FFFCF9", borderBottom: "1px solid #EDE5DC" }}
        >
          <div
            className="font-ui uppercase text-[10px] font-bold tracking-widest-2"
            style={{ color: "#C4B5AA" }}
          >
            Compilation Sheet
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors border border-transparent"
            style={{ color: "#9E9189", background: "#F5F0EA" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#C25520";
              e.currentTarget.style.borderColor = "#F5C9A8";
              e.currentTarget.style.background = "#FEF3EC";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "#9E9189";
              e.currentTarget.style.borderColor = "transparent";
              e.currentTarget.style.background = "#F5F0EA";
            }}
          >
            <X size={15} />
          </button>
        </div>
        <div className="p-8">
          {detail.isLoading && <div className="h-96 rounded shimmer" />}
          {detail.data && <ResultsCard data={detail.data} />}
        </div>
      </div>
    </>
  );
}

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
    const list = urlText.split("\n").map((u) => u.trim()).filter(Boolean);
    if (list.length === 0) { toast.error("Add at least one URL"); return; }
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
      ].map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",");
    });
    const blob = new Blob([[headers.join(","), ...rows].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `batch-archive-${Date.now()}.csv`;
    a.click();
    toast.success("CSV Export downloaded");
  };

  return (
    <div className="page-in min-h-screen flex flex-col" style={{ background: "#FFFCF9" }}>
      <TopBar title="Batch Compiler" />

      <div className="px-10 py-8 flex-1 flex flex-col gap-6 max-w-[1100px] w-full mx-auto">

        {/* Intro */}
        <div className="flex flex-col gap-1.5 mb-2">
          <h2 className="font-display italic text-[22px] font-bold" style={{ color: "#2C1F17" }}>
            Run Batch Compilation
          </h2>
          <p className="font-ui text-[12px] leading-relaxed" style={{ color: "#9E9189" }}>
            Queue multiple university course URLs. The system will stagger compiling page contents in parallel to construct structured Admission criteria sheets.
          </p>
        </div>

        {/* URL inputs */}
        <div className="flex flex-col gap-2">
          <label
            className="font-ui uppercase text-[9px] font-bold tracking-widest-2 flex items-center gap-1.5"
            style={{ color: "#9E9189" }}
          >
            <ListPlus size={12} style={{ color: "#C25520" }} /> Target URLs — One per line
          </label>
          <textarea
            value={urlText}
            onChange={(e) => setUrlText(e.target.value)}
            placeholder={"https://university-a.edu/programs/cs-msc\nhttps://university-b.edu/programs/data-science"}
            className="w-full font-mono text-[12.5px] rounded-lg px-4 py-3.5 transition-all duration-300 focus:outline-none resize-y"
            style={{
              minHeight: 180,
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

        {/* Trigger Button */}
        <div className="flex items-center gap-4 max-w-[280px]">
          <PrimaryButton type="button" onClick={handleRun} loading={queuing} loadingText="QUEUING COMPILATION...">
            <div className="flex items-center gap-2">
              <PlayCircle size={15} /> Run Batch Compiler
            </div>
          </PrimaryButton>
          {queuing && (
            <button
              onClick={() => setQueuing(false)}
              className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2 cursor-pointer transition-colors"
              style={{ color: "#C4B5AA" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#2C1F17")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#C4B5AA")}
            >
              Cancel
            </button>
          )}
        </div>

        {/* Progress bar */}
        {total > 0 && !allDone && (
          <div
            className="mt-6 rounded-lg p-5"
            style={{ border: "1px solid #EDE5DC", background: "#FBF7F3" }}
          >
            <div style={{ width: "100%", height: 6, borderRadius: 999, background: "#EDE5DC", overflow: "hidden" }}>
              <div
                className="batch-progress-fill transition-all duration-500"
                style={{ height: 6, borderRadius: 999, width: `${(completed / total) * 100}%`, background: "#C25520" }}
              />
            </div>
            <div className="flex justify-between items-center mt-3">
              <div className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2" style={{ color: "#9E9189" }}>
                Compiling Batch
              </div>
              <div className="font-mono text-[12px] font-bold" style={{ color: "#C25520" }}>
                {completed} / {total} COMPLETE ({((completed / total) * 100).toFixed(0)}%)
              </div>
            </div>
          </div>
        )}

        {/* Summary stats */}
        {allDone && (
          <div className="mt-4 flex flex-col gap-6 slide-up">
            <div className="flex items-center gap-2 pb-2 border-b" style={{ borderColor: "#EDE5DC" }}>
              <BarChart3 size={14} style={{ color: "#C25520" }} />
              <span className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2" style={{ color: "#9E9189" }}>
                Batch Summary Metrics
              </span>
            </div>
            <div className="flex flex-col sm:flex-row gap-4">
              <StatCard label="Compiled" value={stats.success} tone="#C25520" borderCol="#F5C9A8" bg="#FEF3EC" />
              <StatCard label="Partial" value={stats.partial} tone="#B07D2E" borderCol="#F0D4A0" bg="#FDF6E8" />
              <StatCard label="Failed" value={stats.failed} tone="var(--error)" borderCol="#F5C0C0" bg="#FEF0F0" />
            </div>
            <div className="max-w-[280px]">
              <PrimaryButton type="button" onClick={downloadAllCsv}>
                <div className="flex items-center gap-2">
                  <FileSpreadsheet size={15} /> Download All CSV
                </div>
              </PrimaryButton>
            </div>
          </div>
        )}

        {/* Live results table */}
        {total > 0 && (
          <div
            className="mt-6 rounded-xl overflow-hidden"
            style={{
              border: "1px solid #E8DDD4",
              background: "#FFFFFF",
              boxShadow: "0 4px 16px rgba(44, 31, 23, 0.06)",
            }}
          >
            <table style={{ width: "100%", tableLayout: "fixed", borderCollapse: "collapse" }}>
              <colgroup>
                <col style={{ width: "40%" }} />
                <col style={{ width: "14%" }} />
                <col style={{ width: "34%" }} />
                <col style={{ width: "12%" }} />
              </colgroup>
              <thead>
                <tr style={{ borderBottom: "1px solid #EDE5DC", background: "#FBF7F3" }}>
                  {["Target URL", "Status", "University / Program", ""].map((h) => (
                    <th
                      key={h}
                      className="font-ui uppercase text-[9px] font-bold tracking-widest-2"
                      style={{ color: "#C4B5AA", padding: "14px 18px", textAlign: "left", fontWeight: 700 }}
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
                      className="transition-colors duration-200"
                      style={{
                        background: i % 2 === 0 ? "#FDFAF7" : "#FFFFFF",
                        borderBottom: "1px solid #EDE5DC",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "#FEF3EC")}
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.background = i % 2 === 0 ? "#FDFAF7" : "#FFFFFF")
                      }
                    >
                      <td
                        className="font-mono text-[11.5px]"
                        style={{ color: "#78716C", padding: "14px 18px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                      >
                        {urls[i]}
                      </td>
                      <td style={{ padding: "14px 18px" }}>
                        <div className="flex items-center gap-2">
                          {inProgress && (
                            <span
                              className="pulse-dot inline-block w-1.5 h-1.5 rounded-full"
                              style={{ background: "#B07D2E" }}
                            />
                          )}
                          <StatusBadge status={status} />
                        </div>
                      </td>
                      <td
                        className="font-ui text-[12px] font-medium"
                        style={{ color: "#2C1F17", padding: "14px 18px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                      >
                        {d?.university_name
                          ? `${d.university_name} — ${d.program_name ?? "—"}`
                          : inProgress ? "Compiling..." : "—"}
                      </td>
                      <td style={{ padding: "14px 18px", textAlign: "right" }}>
                        {isDone && (
                          <button
                            onClick={() => setDrawerId(id)}
                            className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2 transition-colors cursor-pointer"
                            style={{ color: "#C25520" }}
                            onMouseEnter={(e) => (e.currentTarget.style.color = "#A0440F")}
                            onMouseLeave={(e) => (e.currentTarget.style.color = "#C25520")}
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

      {drawerId && <DetailDrawer scrapeId={drawerId} onClose={() => setDrawerId(null)} />}
    </div>
  );
}

function StatCard({
  label, value, tone, borderCol, bg,
}: {
  label: string; value: number; tone: string; borderCol: string; bg: string;
}) {
  return (
    <div
      style={{
        flex: 1,
        padding: "24px 20px",
        borderRadius: 10,
        borderLeft: `3px solid ${tone}`,
        border: `1px solid ${borderCol}`,
        background: bg,
        boxShadow: "0 2px 8px rgba(44, 31, 23, 0.06)",
      }}
    >
      <div className="font-display leading-none font-bold" style={{ fontSize: 48, color: tone }}>
        {value}
      </div>
      <div
        className="font-ui uppercase font-bold text-[9px] tracking-widest-2"
        style={{ marginTop: 10, color: "#C4B5AA" }}
      >
        {label}
      </div>
    </div>
  );
}