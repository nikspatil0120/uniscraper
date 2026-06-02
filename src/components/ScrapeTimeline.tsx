import { useEffect, useState } from "react";
import { Check } from "lucide-react";

const STEPS = [
  "Fetching page",
  "Detecting content type",
  "Following sub-pages",
  "Extracting PDFs",
  "Running AI extraction",
  "Saving results",
];

// Approximate progression: ~15s total scrape
const STEP_TIMINGS = [1.5, 3.5, 6, 8.5, 12.5, 15];

export function ScrapeTimeline({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 100);
    return () => clearInterval(t);
  }, [startedAt]);

  const activeIndex = Math.min(
    STEPS.length - 1,
    STEP_TIMINGS.findIndex((t) => elapsed < t) === -1
      ? STEPS.length - 1
      : STEP_TIMINGS.findIndex((t) => elapsed < t),
  );

  return (
    <div className="w-full max-w-md mx-auto py-12">
      <div className="relative flex flex-col gap-7">
        {STEPS.map((label, i) => {
          const done = i < activeIndex;
          const active = i === activeIndex;
          return (
            <div key={label} className="flex items-center gap-4 relative">
              <div
                className="relative w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                style={{
                  border: done
                    ? "1.5px solid var(--accent)"
                    : active
                      ? "1.5px solid var(--accent)"
                      : "1.5px solid var(--text-muted)",
                  background: done ? "var(--accent)" : "transparent",
                  boxShadow: active ? "0 0 12px var(--accent-glow)" : "none",
                }}
              >
                {done && <Check size={12} strokeWidth={3} color="#0A0A0F" />}
                {active && (
                  <span
                    className="absolute inset-0 rounded-full pulse-dot"
                    style={{
                      background: "var(--accent)",
                      opacity: 0.35,
                    }}
                  />
                )}
              </div>
              <div
                className="font-ui uppercase text-[11px] tracking-widest-2"
                style={{
                  color: done
                    ? "var(--text-primary)"
                    : active
                      ? "var(--accent)"
                      : "var(--text-muted)",
                }}
              >
                {label}
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className="absolute left-[9.5px] top-7 w-[1.5px] overflow-hidden"
                  style={{ height: "28px", background: "var(--border)" }}
                >
                  <div
                    style={{
                      height: done ? "100%" : active ? "50%" : "0%",
                      background: "var(--accent)",
                      transition: "height 600ms ease-out",
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div
        className="mt-10 font-mono text-center text-[22px]"
        style={{ color: "var(--accent)" }}
      >
        {elapsed.toFixed(1)}s
      </div>
    </div>
  );
}
