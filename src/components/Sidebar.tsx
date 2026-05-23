import { Link, useRouterState } from "@tanstack/react-router";

const NAV = [
  { to: "/", label: "Scrape" },
  { to: "/history", label: "History" },
  { to: "/batch", label: "Batch" },
] as const;

export function Sidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <aside
      className="hidden md:flex md:flex-col fixed left-0 top-0 h-screen w-[220px] z-30"
      style={{ background: "var(--bg-base)", borderRight: "1px solid var(--border)" }}
    >
      <div className="px-6 pt-8 pb-10">
        <Link to="/" className="block">
          <div className="font-display italic text-[44px] leading-none text-text-primary">
            Uni
          </div>
          <div
            className="font-ui uppercase text-[10px] mt-1 tracking-widest-2"
            style={{ color: "var(--accent)" }}
          >
            S c r a p e r
          </div>
        </Link>
      </div>

      <nav className="flex flex-col gap-1 px-3 flex-1">
        {NAV.map((item) => {
          const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className="relative font-ui uppercase text-[11px] tracking-widest-2 px-4 py-3 rounded-md transition-colors"
              style={{
                color: active ? "var(--accent)" : "var(--text-secondary)",
                background: active ? "var(--accent-dim)" : "transparent",
                borderLeft: `2px solid ${active ? "var(--accent)" : "transparent"}`,
              }}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-6 pb-6 flex items-center gap-2">
        <span
          className="pulse-dot inline-block w-1.5 h-1.5 rounded-full"
          style={{ background: "var(--accent)", boxShadow: "0 0 8px var(--accent-glow)" }}
        />
        <span
          className="font-ui text-[10px] uppercase tracking-widest-2"
          style={{ color: "var(--text-muted)" }}
        >
          Powered by AI
        </span>
      </div>
    </aside>
  );
}
