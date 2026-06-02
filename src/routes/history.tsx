import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { TopBar } from "@/components/TopBar";
import { api, type ScrapeRecord } from "@/lib/api";
import { Badge, ResultsCard, StatusBadge } from "@/components/ResultsCard";
import { NotFound } from "@/components/NotFound";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "History — UniScraper" },
      { name: "description", content: "Browse, search, and export past university scrapes." },
    ],
  }),
  component: HistoryPage,
});

function HistoryPage() {
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const qc = useQueryClient();

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
      toast.success("Deleted");
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
    <div className="page-in">
      <TopBar title="History" />

      <div className="px-10 py-8">
        <div className="flex flex-wrap items-center gap-3 mb-8">
          <div className="relative flex-1 min-w-[240px]">
            <Search
              size={14}
              className="absolute left-4 top-1/2 -translate-y-1/2"
              style={{ color: "var(--text-muted)" }}
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search university or program..."
              className="w-full font-mono text-[13px] rounded-lg pl-10 pr-4 py-3 focus-glow"
              style={{
                background: "var(--bg-raised)",
                color: "var(--text-primary)",
                border: "1px solid transparent",
              }}
            />
          </div>
          <div className="flex gap-2">
            <a
              href={api.exportCsvUrl()}
              download="uniscraper_export.csv"
              className="font-ui uppercase text-[11px] tracking-widest-2 px-4 py-3 rounded-lg transition-all"
              style={{
                border: "1px solid var(--accent)",
                color: "var(--accent)",
                background: "transparent",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-dim)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              Export All CSV
            </a>
            <a
              href={api.exportJsonUrl()}
              download="uniscraper_export.json"
              className="font-ui uppercase text-[11px] tracking-widest-2 px-4 py-3 rounded-lg transition-all"
              style={{
                border: "1px solid var(--accent)",
                color: "var(--accent)",
                background: "transparent",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-dim)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              Export All JSON
            </a>
          </div>
        </div>

        {/* Table */}
        <div
          className="rounded-xl"
          style={{ border: "1px solid var(--border)", overflow: "hidden" }}
        >
          <table style={{ width: "100%", tableLayout: "fixed", borderCollapse: "collapse" }}>
            <colgroup>
              <col style={{ width: "28%" }} />
              <col style={{ width: "32%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "14%" }} />
            </colgroup>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["University", "Program", "Level", "Status", "Date"].map((h) => (
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
                <th style={{ width: 80, padding: "12px 16px" }} />
              </tr>
            </thead>
            <tbody>
              {list.isLoading &&
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    <td style={{ padding: "14px 16px" }}>
                      <div className="shimmer" style={{ width: "80%", height: 16, borderRadius: 4 }} />
                    </td>
                    <td style={{ padding: "14px 16px" }}>
                      <div className="shimmer" style={{ width: "75%", height: 14, borderRadius: 4 }} />
                    </td>
                    <td style={{ padding: "14px 16px" }}>
                      <div className="shimmer" style={{ width: 52, height: 22, borderRadius: 999 }} />
                    </td>
                    <td style={{ padding: "14px 16px" }}>
                      <div className="shimmer" style={{ width: 60, height: 22, borderRadius: 999 }} />
                    </td>
                    <td style={{ padding: "14px 16px" }}>
                      <div className="shimmer" style={{ width: "80%", height: 14, borderRadius: 4 }} />
                    </td>
                    <td />
                  </tr>
                ))}

              {!list.isLoading && filtered.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ padding: "80px 24px", textAlign: "center" }}>
                    <div
                      className="font-display italic"
                      style={{ fontSize: 22, color: "#4A4958" }}
                    >
                      No scrapes yet
                    </div>
                    <div
                      className="font-ui uppercase"
                      style={{
                        fontSize: 11,
                        letterSpacing: "0.12em",
                        color: "#4A4958",
                        marginTop: 8,
                      }}
                    >
                      Run your first scrape to see results here
                    </div>
                  </td>
                </tr>
              )}

              {filtered.map((row: ScrapeRecord, i) => (
                <tr
                  key={row.scrape_id}
                  style={{ background: i % 2 === 0 ? "var(--bg-surface)" : "transparent", cursor: "default" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = i % 2 === 0 ? "var(--bg-surface)" : "transparent")
                  }
                >
                  <td
                    className="font-display text-[15px]"
                    style={{ color: "var(--text-primary)", padding: "14px 16px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  >
                    {row.university_name ? row.university_name : <NotFound />}
                  </td>
                  <td
                    className="font-ui text-[12px]"
                    style={{ color: "var(--text-secondary)", padding: "14px 16px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  >
                    {row.program_name ? row.program_name : <NotFound />}
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    {row.degree_level ? <Badge>{row.degree_level}</Badge> : <NotFound />}
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <StatusBadge status={row.status} />
                  </td>
                  <td
                    className="font-mono text-[12px]"
                    style={{ color: "var(--text-muted)", padding: "14px 16px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  >
                    {row.created_at ? new Date(row.created_at).toLocaleString() : <NotFound />}
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <div className="flex items-center gap-3 justify-end">
                      <button
                        onClick={() => setDrawerId(row.scrape_id)}
                        className="font-ui uppercase text-[10px] tracking-widest-2 hover:underline"
                        style={{ color: "var(--accent)" }}
                      >
                        View →
                      </button>
                      <button
                        onClick={() => del.mutate(row.scrape_id)}
                        className="transition-colors"
                        style={{ color: "var(--text-muted)" }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--error)")}
                        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                        aria-label="Delete"
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
        <div className="flex items-center justify-center gap-6 mt-8">
          <button
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="font-ui uppercase text-[10px] tracking-widest-2 disabled:opacity-30"
            style={{ color: "var(--text-secondary)" }}
          >
            ← Prev
          </button>
          <div className="font-ui uppercase text-[10px] tracking-widest-2" style={{ color: "var(--text-muted)" }}>
            Page <span style={{ color: "var(--accent)" }}>{page}</span> of {totalPages}
          </div>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="font-ui uppercase text-[10px] tracking-widest-2 disabled:opacity-30"
            style={{ color: "var(--text-secondary)" }}
          >
            Next →
          </button>
        </div>
      </div>

      {/* Drawer */}
      {drawerId && (
        <>
          <div
            className="fixed inset-0 z-40"
            style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
            onClick={() => setDrawerId(null)}
          />
          <div
            className="fixed top-0 right-0 h-screen w-full max-w-[600px] z-50 overflow-y-auto slide-up"
            style={{ background: "var(--bg-base)", borderLeft: "1px solid var(--border)" }}
          >
            <div
              className="sticky top-0 z-10 px-6 py-4 flex items-center justify-between"
              style={{
                background: "var(--bg-base)",
                borderBottom: "1px solid var(--border)",
              }}
            >
              <div
                className="font-ui uppercase text-[10px] tracking-widest-2"
                style={{ color: "var(--text-muted)" }}
              >
                Scrape Detail
              </div>
              <button
                onClick={() => setDrawerId(null)}
                className="p-1.5 rounded-md transition-colors"
                style={{ color: "var(--text-secondary)" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
              >
                <X size={16} />
              </button>
            </div>
            <div className="p-6">
              {detail.isLoading && <div className="h-96 rounded shimmer" />}
              {detail.data && <ResultsCard data={detail.data} />}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
