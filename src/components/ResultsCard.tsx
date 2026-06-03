import { useMemo, useState } from "react";
import { Download, FileJson, Link as LinkIcon, ChevronDown } from "lucide-react";
import { fmt, getEnglish, getFees, type ScrapeRecord } from "@/lib/api";

interface Field {
  label: string;
  value: unknown;
  warn?: boolean;
}

interface Section {
  title: string;
  fields: Field[];
}

function FieldBlock({ field }: { field: Field }) {
  const { text, missing } = fmt(field.value);
  const accent = !missing;
  return (
    <div
      className="px-4 py-3 transition-colors cursor-default"
      style={{
        borderLeft: `2px solid ${accent ? "var(--accent)" : "var(--border)"}`,
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <div
        className="font-ui uppercase text-[9px] tracking-widest-2 mb-1.5"
        style={{ color: "var(--text-muted)" }}
      >
        {field.label}
      </div>
      <div
        className={missing ? "italic text-[13px]" : "font-mono text-[13px]"}
        style={{
          color: missing
            ? "var(--text-muted)"
            : field.warn
              ? "var(--warning)"
              : "var(--text-primary)",
          wordBreak: "break-word",
        }}
      >
        {text}
      </div>
    </div>
  );
}

function Badge({
  children,
  tone = "accent",
}: {
  children: React.ReactNode;
  tone?: "accent" | "warn" | "error";
}) {
  const colors = {
    accent: { bg: "var(--accent-dim)", fg: "var(--accent)" },
    warn: { bg: "var(--warning-dim)", fg: "var(--warning)" },
    error: { bg: "var(--error-dim)", fg: "var(--error)" },
  }[tone];
  return (
    <span
      className="font-mono text-[10px] uppercase px-2.5 py-1 rounded-full inline-block"
      style={{ background: colors.bg, color: colors.fg, letterSpacing: "0.05em" }}
    >
      {children}
    </span>
  );
}

export function ResultsCard({ data }: { data: ScrapeRecord }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);

  // Flatten nested objects for display
  const eng = getEnglish(data);
  const fees = getFees(data);
  const sources = data.source_urls ?? [];

  const sections: Section[] = useMemo(
    () => [
      {
        title: "Intake & Deadlines",
        fields: [
          { label: "Intake months", value: data.intake_months },
          { label: "Application deadlines", value: data.application_deadlines },
        ],
      },
      {
        title: "Academic Requirements",
        fields: [
          { label: "Min. academic requirement", value: data.min_academic_requirement },
          { label: "Accepted qualifications", value: data.accepted_qualifications },
          { label: "Work experience", value: data.work_experience },
        ],
      },
      {
        title: "Language",
        fields: [
          { label: "IELTS", value: eng.ielts },
          { label: "TOEFL", value: eng.toefl },
          { label: "PTE", value: eng.pte },
          { label: "Duolingo", value: eng.duolingo },
          { label: "Notes", value: eng.notes },
        ],
      },
      {
        title: "Fees",
        fields: [
          { label: "International tuition", value: fees.international },
          { label: "Domestic tuition", value: fees.domestic },
          { label: "Currency", value: fees.currency },
          { label: "Fee notes", value: fees.notes },
          { label: "Other fees", value: data.other_fees },
        ],
      },
      {
        title: "Opportunities",
        fields: [
          { label: "Scholarships", value: data.scholarships },
        ],
      },
      {
        title: "Other",
        fields: [
          { label: "Other requirements", value: data.other_requirements },
          { label: "Confidence notes", value: data.confidence_notes, warn: true },
        ],
      },
    ],
    [data, eng, fees],
  );

  const extractedCount = sections
    .flatMap((s) => s.fields)
    .filter((f) => !fmt(f.value).missing).length;

  const getSanitizedFilename = (ext: string) => {
    const uni = data.university_name || "university";
    const prog = data.program_name || "program";
    const name = `${uni}_${prog}`
      .toLowerCase()
      .replace(/[^a-z0-9_]/g, "_")
      .replace(/__+/g, "_")
      .trim();
    return `${name || data.scrape_id}.${ext}`;
  };

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = getSanitizedFilename("json");
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadCsv = () => {
    const rows = sections
      .flatMap((s) => s.fields)
      .map((f) => [f.label, fmt(f.value).text].map((c) => `"${c.replace(/"/g, '""')}"`).join(","));
    const blob = new Blob(["\ufeff", ["field,value", ...rows].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = getSanitizedFilename("csv");
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className="slide-up rounded-xl flex flex-col"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      {/* Error Banner - if scrape failed */}
      {data.error && (
        <div
          className="px-6 py-4 flex items-start gap-3"
          style={{
            background: "var(--error-dim)",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <div
            className="font-ui uppercase text-[10px] tracking-widest-2 flex-1"
            style={{ color: "var(--error)", lineHeight: "1.6" }}
          >
            <div className="font-bold mb-1">SCRAPING FAILED</div>
            <div className="font-mono normal-case text-[11px]" style={{ color: "var(--text-primary)" }}>
              {data.error}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="p-6 flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="font-display text-[26px] leading-tight text-text-primary">
            {fmt(data.university_name).missing ? "Unknown University" : data.university_name}
          </div>
          <div
            className="font-ui uppercase text-[13px] tracking-widest-2 mt-2"
            style={{ color: "var(--text-secondary)" }}
          >
            {fmt(data.program_name).missing ? "— program not found" : data.program_name}
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            {!fmt(data.degree_level).missing && <Badge>{data.degree_level}</Badge>}
            {!fmt(data.program_duration).missing && <Badge>{data.program_duration}</Badge>}
          </div>
        </div>
        <div
          className="font-mono text-[10px] uppercase whitespace-nowrap"
          style={{ color: "var(--text-muted)" }}
        >
          Extracted {extractedCount} fields
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--border)" }} />

      {/* Sections */}
      <div className="flex-1">
        {sections.map((sec, i) => (
          <div key={sec.title}>
            {i > 0 && <div style={{ borderTop: "1px solid var(--border)" }} />}
            <div className="px-6 pt-5 pb-3">
              <div
                className="font-ui uppercase text-[10px] tracking-widest-2"
                style={{ color: "var(--text-muted)" }}
              >
                {sec.title}
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-2 gap-y-1 px-4 pb-4">
              {sec.fields.map((f) => (
                <FieldBlock key={f.label} field={f} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Sources (expandable) */}
      {sourcesOpen && sources.length > 0 && (
        <div
          className="px-6 py-4 max-h-44 overflow-y-auto"
          style={{ borderTop: "1px solid var(--border)", background: "var(--bg-base)" }}
        >
          <ul className="space-y-1.5">
            {sources.map((s) => (
              <li key={s} className="flex items-center gap-2">
                <LinkIcon size={11} style={{ color: "var(--text-muted)" }} />
                <a
                  href={s}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-[11px] truncate hover:underline"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {s}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Bottom bar */}
      <div
        className="flex items-center justify-between px-6 py-4"
        style={{
          background: "var(--bg-surface)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <button
          onClick={() => setSourcesOpen((v) => !v)}
          className="font-ui uppercase text-[10px] tracking-widest-2 flex items-center gap-1.5 transition-colors"
          style={{ color: "var(--text-secondary)" }}
        >
          <ChevronDown
            size={12}
            style={{
              transform: sourcesOpen ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 200ms",
            }}
          />
          Sources ({sources.length})
        </button>
        <div className="flex gap-2">
          <button
            onClick={downloadJson}
            className="font-ui uppercase text-[10px] tracking-widest-2 flex items-center gap-1.5 px-3 py-2 rounded-md transition-colors"
            style={{ color: "var(--text-secondary)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            <FileJson size={12} /> JSON
          </button>
          <button
            onClick={downloadCsv}
            className="font-ui uppercase text-[10px] tracking-widest-2 flex items-center gap-1.5 px-3 py-2 rounded-md transition-colors"
            style={{ color: "var(--text-secondary)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
          >
            <Download size={12} /> CSV
          </button>
        </div>
      </div>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tone = status === "success" ? "accent" : status === "failed" ? "error" : "warn";
  return <Badge tone={tone as "accent" | "warn" | "error"}>{status}</Badge>;
}

export { Badge };
