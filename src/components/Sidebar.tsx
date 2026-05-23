import { Link, useRouterState } from "@tanstack/react-router";

const NAV = [
  { to: "/", label: "Scrape", icon: "◈" },
  { to: "/history", label: "History", icon: "≡" },
  { to: "/batch", label: "Batch", icon: "⊞" },
] as const;

export function Sidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <aside
      className="flex flex-col"
      style={{
        width: 220,
        minWidth: 220,
        height: "100vh",
        position: "sticky",
        top: 0,
        background: "#111118",
        borderRight: "1px solid rgba(255,255,255,0.06)",
        padding: 0,
      }}
    >
      <div style={{ padding: "32px 24px 40px 24px" }}>
        <Link to="/" className="block">
          <div
            className="font-display italic leading-none"
            style={{ fontSize: 32, color: "#F2EFE9" }}
          >
            UNI
          </div>
          <div
            className="font-ui uppercase mt-1"
            style={{ fontSize: 10, letterSpacing: "0.2em", color: "#4FFFB0" }}
          >
            Scraper
          </div>
        </Link>
      </div>

      <nav className="flex flex-col gap-1 flex-1" style={{ padding: "0 12px" }}>
        {NAV.map((item) => {
          const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className="relative font-ui uppercase flex items-center transition-colors"
              style={{
                height: 44,
                padding: "0 12px",
                borderRadius: 6,
                fontSize: 11,
                letterSpacing: "0.15em",
                color: active ? "#4FFFB0" : "#4A4958",
                background: active ? "rgba(79,255,176,0.08)" : "transparent",
                borderLeft: `2px solid ${active ? "#4FFFB0" : "transparent"}`,
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.color = "#8B8A97";
                  e.currentTarget.style.background = "#1A1A24";
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.color = "#4A4958";
                  e.currentTarget.style.background = "transparent";
                }
              }}
            >
              <span style={{ fontSize: 14, marginRight: 10, lineHeight: 1 }}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex items-center" style={{ padding: 24, gap: 8 }}>
        <span
          className="pulse-dot inline-block rounded-full"
          style={{ width: 6, height: 6, background: "#4FFFB0" }}
        />
        <span
          className="font-ui uppercase"
          style={{ fontSize: 10, letterSpacing: "0.15em", color: "#4A4958" }}
        >
          API ONLINE
        </span>
      </div>
    </aside>
  );
}
