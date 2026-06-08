import { useMemo, useState } from "react";
import { Download, FileJson, Link as LinkIcon, ChevronDown, CheckCircle2 } from "lucide-react";
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
      className="px-4 py-3.5 transition-all duration-200 cursor-default rounded-lg border border-transparent"
      style={{
        borderLeft: `2.5px solid ${accent ? "var(--accent)" : "rgba(255, 255, 255, 0.03)"}`,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "rgba(255, 255, 255, 0.015)";
        e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.02)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.borderColor = "transparent";
      }}
    >
      <div
        className="font-ui uppercase text-[8.5px] font-bold tracking-widest-2 mb-1.5"
        style={{ color: "var(--text-muted)" }}
      >
        {field.label}
      </div>
      <div
        className={missing ? "italic text-[12.5px]" : "font-mono text-[12.5px]"}
        style={{
          color: missing
            ? "var(--text-muted)"
            : field.warn
              ? "var(--warning)"
              : "var(--text-primary)",
          wordBreak: "break-word",
          lineHeight: 1.5,
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
    accent: { bg: "rgba(229, 143, 101, 0.06)", fg: "var(--accent)", border: "rgba(229, 143, 101, 0.15)" },
    warn: { bg: "rgba(226, 175, 112, 0.06)", fg: "var(--warning)", border: "rgba(226, 175, 112, 0.15)" },
    error: { bg: "rgba(208, 112, 112, 0.06)", fg: "var(--error)", border: "rgba(208, 112, 112, 0.15)" },
  }[tone];

  return (
    <span
      className="font-ui text-[10px] uppercase font-bold px-3 py-1 rounded-md inline-block border"
      style={{ 
        background: colors.bg, 
        color: colors.fg, 
        borderColor: colors.border,
        letterSpacing: "0.08em" 
      }}
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
        title: "Language Requirements",
        fields: [
          { label: "IELTS", value: eng.ielts },
          { label: "TOEFL", value: eng.toefl },
          { label: "PTE", value: eng.pte },
          { label: "Duolingo", value: eng.duolingo },
          { label: "Notes", value: eng.notes },
        ],
      },
      {
        title: "Tuition & Fees",
        fields: [
          { label: "International tuition", value: fees.international },
          { label: "Domestic tuition", value: fees.domestic },
          { label: "Currency", value: fees.currency },
          { label: "Fee notes", value: fees.notes },
          { label: "Other fees", value: data.other_fees },
        ],
      },
      {
        title: "Scholarships & Opportunities",
        fields: [
          { label: "Scholarships", value: data.scholarships },
        ],
      },
      {
        title: "Additional Criteria",
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
      className="slide-up rounded-xl flex flex-col glass-panel-raised"
      style={{ 
        boxShadow: "0 10px 40px rgba(0,0,0,0.3)",
        border: "1px solid rgba(255, 255, 255, 0.04)"
      }}
    >
      {/* Error Banner - if compile failed */}
      {data.error && (
        <div
          className="px-6 py-4 flex items-start gap-3 rounded-t-xl"
          style={{
            background: "rgba(208, 112, 112, 0.08)",
            borderBottom: "1px solid rgba(208, 112, 112, 0.15)",
          }}
        >
          <div
            className="font-ui uppercase text-[10px] tracking-widest-2 flex-1"
            style={{ color: "var(--error)", lineHeight: "1.6" }}
          >
            <div className="font-bold mb-1">COMPILATION FAILED</div>
            <div className="font-mono normal-case text-[11px]" style={{ color: "var(--text-primary)" }}>
              {data.error}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-[28px] font-bold leading-tight" style={{ color: "var(--text-primary)" }}>
            {fmt(data.university_name).missing ? "Unknown University" : data.university_name}
          </h2>
          <div
            className="font-ui uppercase text-[12px] font-semibold tracking-widest-2 mt-2"
            style={{ color: "var(--text-secondary)" }}
          >
            {fmt(data.program_name).missing ? "— Program Details Unavailable" : data.program_name}
          </div>
          <div className="flex flex-wrap gap-2 mt-4">
            {!fmt(data.degree_level).missing && <Badge>{data.degree_level}</Badge>}
            {!fmt(data.program_duration).missing && <Badge>{data.program_duration}</Badge>}
          </div>
        </div>
        
        {/* Metric Pill */}
        <div
          className="flex items-center gap-2 self-start md:self-center px-4 py-2 rounded-lg"
          style={{
            background: "rgba(255, 255, 255, 0.01)",
            border: "1px solid rgba(255, 255, 255, 0.03)",
          }}
        >
          <CheckCircle2 size={13} style={{ color: "var(--accent)" }} />
          <span className="font-ui uppercase text-[10px] font-bold tracking-widest text-text-secondary">
            Compiled <span className="font-mono text-accent text-[11px]">{extractedCount}</span> fields
          </span>
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--border)" }} />

      {/* Sections */}
      <div className="flex-1 p-4 flex flex-col gap-6">
        {sections.map((sec) => (
          <div 
            key={sec.title}
            className="rounded-lg p-4"
            style={{
              background: "rgba(255, 255, 255, 0.005)",
              border: "1px solid rgba(255, 255, 255, 0.01)"
            }}
          >
            <div className="px-2 pb-3 mb-2 flex items-center gap-2 border-b border-white/[0.01]">
              <span className="w-1.5 h-1.5 rounded-full bg-accent" />
              <div
                className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2"
                style={{ color: "var(--text-muted)" }}
              >
                {sec.title}
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2">
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
          className="px-8 py-5 max-h-44 overflow-y-auto"
          style={{ borderTop: "1px solid var(--border)", background: "rgba(20, 18, 17, 0.3)" }}
        >
          <ul className="space-y-2">
            {sources.map((s) => (
              <li key={s} className="flex items-center gap-2.5">
                <LinkIcon size={10} style={{ color: "var(--text-muted)" }} />
                <a
                  href={s}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-[11px] truncate text-text-secondary hover:text-accent hover:underline transition-colors"
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
        className="flex items-center justify-between px-8 py-4 rounded-b-xl"
        style={{
          background: "rgba(28, 25, 23, 0.4)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <button
          onClick={() => setSourcesOpen((v) => !v)}
          className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2 flex items-center gap-2 transition-all duration-200 text-text-secondary hover:text-text-primary"
        >
          <ChevronDown
            size={12}
            style={{
              transform: sourcesOpen ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 200ms",
              color: "var(--accent)"
            }}
          />
          Sources ({sources.length})
        </button>
        
        <div className="flex gap-2">
          <button
            onClick={downloadJson}
            className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2 flex items-center gap-2 px-3.5 py-2 rounded-lg transition-all duration-300 border border-transparent"
            style={{ 
              color: "var(--text-secondary)",
              background: "rgba(255, 255, 255, 0.01)"
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--accent)";
              e.currentTarget.style.background = "rgba(229, 143, 101, 0.05)";
              e.currentTarget.style.borderColor = "rgba(229, 143, 101, 0.15)";
              e.currentTarget.style.transform = "translateY(-1px)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--text-secondary)";
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.01)";
              e.currentTarget.style.borderColor = "transparent";
              e.currentTarget.style.transform = "";
            }}
          >
            <FileJson size={12} /> JSON
          </button>
          
          <button
            onClick={downloadCsv}
            className="font-ui uppercase text-[9.5px] font-bold tracking-widest-2 flex items-center gap-2 px-3.5 py-2 rounded-lg transition-all duration-300 border border-transparent"
            style={{ 
              color: "var(--text-secondary)",
              background: "rgba(255, 255, 255, 0.01)"
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--accent)";
              e.currentTarget.style.background = "rgba(229, 143, 101, 0.05)";
              e.currentTarget.style.borderColor = "rgba(229, 143, 101, 0.15)";
              e.currentTarget.style.transform = "translateY(-1px)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--text-secondary)";
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.01)";
              e.currentTarget.style.borderColor = "transparent";
              e.currentTarget.style.transform = "";
            }}
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
  return <Badge tone={tone as "accent" | "warn" | "error"}>{status === "success" ? "compiled" : status === "failed" ? "failed" : "partial"}</Badge>;
}

export { Badge };
