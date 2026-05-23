import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { TopBar } from "@/components/TopBar";
import { api, type ScrapeRecord } from "@/lib/api";
import { Badge, ResultsCard, StatusBadge } from "@/components/ResultsCard";

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

  const items = list.data?.items ?? [];
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) =>
        (i.university_name ?? "").toLowerCase().includes(q) ||
        (i.program_name ?? "").toLowerCase().includes(q),
    );
  }, [items, query]);

  const totalPages = Math.max(1, Math.ceil((list.data?.total ?? 0) / 20));

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
          <a
            href={api.exportCsvUrl()}
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
        </div>

        {/* Table */}
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: "1px solid var(--border)" }}
        >
          <div
            className="grid grid-cols-[2fr_2fr_0.8fr_0.8fr_1fr_0.6fr] gap-4 px-6 py-3"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            {["University", "Program", "Level", "Status", "Date", ""].map((h) => (
              <div
                key={h}
                className="font-ui uppercase text-[10px] tracking-widest-2"
                style={{ color: "var(--text-muted)" }}
              >
                {h}
              </div>
            ))}
          </div>

          {list.isLoading && (
            <div className="px-6 py-6">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="grid grid-cols-[2fr_2fr_0.8fr_0.8fr_1fr_0.6fr] gap-4 items-center"
                  style={{ marginBottom: 16 }}
                >
                  <div className="shimmer" style={{ width: 180, height: 16, borderRadius: 4 }} />
                  <div className="shimmer" style={{ width: 140, height: 14, borderRadius: 4 }} />
                  <div className="shimmer" style={{ width: 60, height: 22, borderRadius: 999 }} />
                  <div className="shimmer" style={{ width: 70, height: 22, borderRadius: 999 }} />
                  <div className="shimmer" style={{ width: 90, height: 14, borderRadius: 4 }} />
                  <div />
                </div>
              ))}
            </div>
          )}

          {!list.isLoading && filtered.length === 0 && (
            <div className="py-20 text-center">
              <div
                className="font-display italic"
                style={{ fontSize: 24, color: "#4A4958" }}
              >
                No scrapes yet
              </div>
              <div
                className="font-ui mt-2"
                style={{ fontSize: 12, color: "#4A4958" }}
              >
                Run your first scrape to see history here
              </div>
            </div>
          )}

          {filtered.map((row: ScrapeRecord, i) => (
            <div
              key={row.scrape_id}
              className="grid grid-cols-[2fr_2fr_0.8fr_0.8fr_1fr_0.6fr] gap-4 px-6 py-4 items-center transition-colors"
              style={{ background: i % 2 === 0 ? "var(--bg-surface)" : "transparent" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = i % 2 === 0 ? "var(--bg-surface)" : "transparent")
              }
            >
              <div className="font-display text-[15px]" style={{ color: "var(--text-primary)" }}>
                {row.university_name ? row.university_name : <NotFound />}
              </div>
              <div className="font-ui text-[12px]" style={{ color: "var(--text-secondary)" }}>
                {row.program_name ? row.program_name : <NotFound />}
              </div>
              <div>{row.degree_level ? <Badge>{row.degree_level}</Badge> : <NotFound />}</div>
              <div>
                <StatusBadge status={row.status} />
              </div>
              <div className="font-mono text-[12px]" style={{ color: "var(--text-muted)" }}>
                {row.created_at ? new Date(row.created_at).toLocaleString() : <NotFound />}
              </div>
              <div className="flex items-center gap-4 justify-end">
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
            </div>
          ))}
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
