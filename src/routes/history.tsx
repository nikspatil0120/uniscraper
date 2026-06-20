import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Trash2, X, AlertCircle, FileSpreadsheet, FileCode } from "lucide-react";
import { toast } from "sonner";

import { TopBar } from "@/components/TopBar";
import { api, type ScrapeRecord } from "@/lib/api";
import { Badge, ResultsCard, StatusBadge } from "@/components/ResultsCard";
import { NotFound } from "@/components/NotFound";
import { formatToIST } from "@/lib/utils";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "Archive — UniScraper" },
      { name: "description", content: "Browse, search, and export compiled university programs." },
    ],
  }),
  component: HistoryPage,
});

function HistoryPage() {
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const qc = useQueryClient();

  const handleExportAllCsv = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    try {
      const res = await fetch(api.exportCsvUrl());
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const today = new Date().toISOString().split("T")[0];
      a.download = `uniscraper_archive_${today}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("CSV Export downloaded");
    } catch (err) {
      toast.error("CSV Export failed");
    }
  };

  const handleExportAllJson = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    try {
      const res = await fetch(api.exportJsonUrl());
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const today = new Date().toISOString().split("T")[0];
      a.download = `uniscraper_archive_${today}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("JSON Export downloaded");
    } catch (err) {
      toast.error("JSON Export failed");
    }
  };

  const list = useQuery({
    queryKey: ["scrapes", page],
    queryFn: () => api.listScrapes(page, 20),
  });

  const detail = useQuery({
    queryKey: ["scrape", drawerId],
    queryFn: () => api.getScrape(drawerId!),
    enabled: !!drawerId,
  });

  const del = useMutation({
    mutationFn: api.deleteScrape,
    onSuccess: () => {
      toast.success("Archive deleted");
      qc.invalidateQueries({ queryKey: ["scrapes"] });
    },
    onError: () => toast.error("Delete failed"),
  });

  const items = list.data?.data ?? [];
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) =>
        (i.university_name ?? "").toLowerCase().includes(q) ||
        (i.program_name ?? "").toLowerCase().includes(q),
    );
  }, [items, query]);

  const totalPages = Math.max(1, list.data?.pages ?? 1);

  return (
    <div className="page-in min-h-screen flex flex-col" style={{ background: "#FFFCF9" }}>
      <TopBar title="Program Archive" />

      <div className="px-10 py-8 flex-1 flex flex-col gap-6 max-w-[1300px] w-full mx-auto">

        {/* Controls Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-2">

          {/* Search bar */}
          <div className="relative flex-1 min-w-[280px] max-w-md">
            <Search
              size={13}
              className="absolute left-4 top-1/2 -translate-y-1/2"
              style={{ color: "#C4B5AA" }}
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search archive by university or course..."
              className="w-full font-ui text-[12.5px] rounded-lg pl-10 pr-4 py-3 transition-all duration-300 focus:outline-none"
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

          {/* Export Actions */}
          <div className="flex gap-2">
            <a
              href={api.exportCsvUrl()}
              onClick={handleExportAllCsv}
              className="font-ui uppercase text-[10px] font-bold tracking-widest-2 px-4 py-3 rounded-lg transition-all duration-300 flex items-center gap-2 border"
              style={{
                borderColor: "#F5C9A8",
                color: "#C25520",
                background: "#FEF3EC",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#FDE8D4";
                e.currentTarget.style.borderColor = "#EFA882";
                e.currentTarget.style.transform = "translateY(-1px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#FEF3EC";
                e.currentTarget.style.borderColor = "#F5C9A8";
                e.currentTarget.style.transform = "";
              }}
            >
              <FileSpreadsheet size={13} /> Export All CSV
            </a>

            <a
              href={api.exportJsonUrl()}
              onClick={handleExportAllJson}
              className="font-ui uppercase text-[10px] font-bold tracking-widest-2 px-4 py-3 rounded-lg transition-all duration-300 flex items-center gap-2 border"
              style={{
                borderColor: "#E8DDD4",
                color: "#9E9189",
                background: "#F5F0EA",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#EDE5DC";
                e.currentTarget.style.borderColor = "#D4C9BD";
                e.currentTarget.style.transform = "translateY(-1px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#F5F0EA";
                e.currentTarget.style.borderColor = "#E8DDD4";
                e.currentTarget.style.transform = "";
              }}
            >
              <FileCode size={13} /> Export All JSON
            </a>
          </div>
        </div>

        {/* Table Container */}
        <div
          className="rounded-xl overflow-hidden"
          style={{
            border: "1px solid #E8DDD4",
            background: "#FFFFFF",
            boxShadow: "0 4px 16px rgba(44, 31, 23, 0.06)",
          }}
        >
          <table style={{ width: "100%", tableLayout: "fixed", borderCollapse: "collapse" }}>
            <colgroup>
              <col style={{ width: "30%" }} />
              <col style={{ width: "30%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "13%" }} />
              <col style={{ width: "15%" }} />
            </colgroup>
            <thead>
              <tr style={{ borderBottom: "1px solid #EDE5DC", background: "#FBF7F3" }}>
                {["University", "Program", "Degree", "Status", "Date Processed"].map((h) => (
                  <th
                    key={h}
                    className="font-ui uppercase text-[9px] font-bold tracking-widest-2"
                    style={{
                      color: "#C4B5AA",
                      padding: "16px 20px",
                      textAlign: "left",
                      fontWeight: 700,
                    }}
                  >
                    {h}
                  </th>
                ))}
                <th style={{ width: 90, padding: "16px 20px" }} />
              </tr>
            </thead>
            <tbody>
              {list.isLoading &&
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #EDE5DC" }}>
                    <td style={{ padding: "18px 20px" }}>
                      <div className="shimmer" style={{ width: "80%", height: 14, borderRadius: 4 }} />
                    </td>
                    <td style={{ padding: "18px 20px" }}>
                      <div className="shimmer" style={{ width: "70%", height: 12, borderRadius: 4 }} />
                    </td>
                    <td style={{ padding: "18px 20px" }}>
                      <div className="shimmer" style={{ width: 50, height: 20, borderRadius: 6 }} />
                    </td>
                    <td style={{ padding: "18px 20px" }}>
                      <div className="shimmer" style={{ width: 60, height: 20, borderRadius: 6 }} />
                    </td>
                    <td style={{ padding: "18px 20px" }}>
                      <div className="shimmer" style={{ width: "85%", height: 12, borderRadius: 4 }} />
                    </td>
                    <td />
                  </tr>
                ))}

              {!list.isLoading && filtered.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ padding: "100px 24px", textAlign: "center" }}>
                    <div
                      className="font-display italic text-[24px]"
                      style={{ color: "#C4B5AA" }}
                    >
                      Archive Empty
                    </div>
                    <div
                      className="font-ui uppercase text-[10px] tracking-widest-2 mt-3"
                      style={{ color: "#D4C9BD" }}
                    >
                      Process a program page on the dashboard to generate records
                    </div>
                  </td>
                </tr>
              )}

              {filtered.map((row: ScrapeRecord, i) => (
                <tr
                  key={row.scrape_id}
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
                    className="font-display font-semibold text-[14px]"
                    style={{ color: "#2C1F17", padding: "16px 20px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  >
                    {row.university_name ? row.university_name : <NotFound />}
                  </td>
                  <td
                    className="font-ui text-[12px] font-medium"
                    style={{ color: "#78716C", padding: "16px 20px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  >
                    {row.program_name ? row.program_name : <NotFound />}
                  </td>
                  <td style={{ padding: "16px 20px" }}>
                    {row.degree_level ? <Badge>{row.degree_level}</Badge> : <NotFound />}
                  </td>
                  <td style={{ padding: "16px 20px" }}>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={row.status} />
                      {row.error && (
                        <div
                          className="group relative"
                          style={{ display: "inline-flex", alignItems: "center" }}
                        >
                          <AlertCircle
                            size={13}
                            style={{ color: "var(--error)", cursor: "help" }}
                          />
                          <div
                            className="absolute left-0 top-full mt-2 hidden group-hover:block z-10 w-64 p-3 rounded-lg"
                            style={{
                              background: "#FFFFFF",
                              border: "1px solid #E8DDD4",
                              boxShadow: "0 8px 24px rgba(44, 31, 23, 0.12)",
                            }}
                          >
                            <div
                              className="font-ui uppercase text-[8.5px] font-bold tracking-widest-2 mb-1"
                              style={{ color: "var(--error)" }}
                            >
                              ERROR DETAILS
                            </div>
                            <div
                              className="font-mono text-[11px]"
                              style={{ color: "#2C1F17", lineHeight: "1.5" }}
                            >
                              {row.error}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </td>
                  <td
                    className="font-mono text-[11.5px]"
                    style={{ color: "#C4B5AA", padding: "16px 20px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  >
                    {row.created_at ? formatToIST(row.created_at) : <NotFound />}
                  </td>
                  <td style={{ padding: "16px 20px" }}>
                    <div className="flex items-center gap-3.5 justify-end">
                      <button
                        onClick={() => setDrawerId(row.scrape_id)}
                        className="font-ui uppercase text-[10px] font-bold tracking-widest-2 transition-colors duration-200"
                        style={{ color: "#C25520" }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = "#A0440F")}
                        onMouseLeave={(e) => (e.currentTarget.style.color = "#C25520")}
                      >
                        View
                      </button>
                      <button
                        onClick={() => del.mutate(row.scrape_id)}
                        className="transition-colors duration-200"
                        style={{ color: "#C4B5AA", cursor: "pointer" }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--error)")}
                        onMouseLeave={(e) => (e.currentTarget.style.color = "#C4B5AA")}
                        aria-label="Delete record"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-center gap-6 mt-4">
          <button
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2 disabled:opacity-20 cursor-pointer disabled:cursor-not-allowed"
            style={{ color: "#78716C" }}
          >
            ← Prev
          </button>
          <div className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2" style={{ color: "#C4B5AA" }}>
            Page <span style={{ color: "#C25520" }}>{page}</span> of {totalPages}
          </div>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2 disabled:opacity-20 cursor-pointer disabled:cursor-not-allowed"
            style={{ color: "#78716C" }}
          >
            Next →
          </button>
        </div>
      </div>

      {/* Drawer */}
      {drawerId && (
        <>
          {/* Blur overlay */}
          <div
            className="fixed inset-0 z-40 transition-opacity duration-300"
            style={{
              background: "rgba(44, 31, 23, 0.35)",
              backdropFilter: "blur(6px)",
            }}
            onClick={() => setDrawerId(null)}
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
              style={{
                background: "#FFFCF9",
                borderBottom: "1px solid #EDE5DC",
              }}
            >
              <div
                className="font-ui uppercase text-[10px] font-bold tracking-widest-2"
                style={{ color: "#C4B5AA" }}
              >
                Results Sheet
              </div>
              <button
                onClick={() => setDrawerId(null)}
                className="p1.5 rounded-lg transition-colors border border-transparent"
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
      )}
    </div>
  );
}