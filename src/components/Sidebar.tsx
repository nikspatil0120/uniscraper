import { Link, useRouterState } from "@tanstack/react-router";
import { Globe, History, Layers } from "lucide-react";

const NAV = [
  { to: "/", label: "Compile", icon: Globe },
  { to: "/history", label: "Archive", icon: History },
  { to: "/batch", label: "Batch", icon: Layers },
] as const;

export function Sidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <aside
      className="flex flex-col h-screen sticky top-0 border-r"
      style={{
        width: 240,
        minWidth: 240,
        background: "#FFFCF9",
        backdropFilter: "blur(20px)",
        borderRight: "1px solid #EDE5DC",
      }}
    >
      {/* Glow effect in background of logo */}
      <div className="absolute top-0 left-0 w-full h-44 overflow-hidden pointer-events-none opacity-60">
        <div
          className="absolute -top-12 -left-12 w-40 h-40 rounded-full"
          style={{
            background: "radial-gradient(circle, #FDDCC8 0%, transparent 70%)",
            filter: "blur(20px)",
          }}
        />
      </div>

      {/* Header / Brand */}
      <div className="p-8 pb-10">
        <Link to="/" className="block group">
          <div className="flex items-baseline gap-1">
            <span
              className="font-display italic leading-none font-bold text-[38px] transition-all duration-300 group-hover:tracking-wide"
              style={{ color: "#2C1F17" }}
            >
              UNI
            </span>
          </div>
          <div
            className="font-ui uppercase text-[9px] tracking-[0.25em] mt-1.5 font-bold transition-all duration-300 group-hover:text-[#A0440F]"
            style={{ color: "#C25520" }}
          >
            Archivist
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1.5 flex-1 px-4">
        {NAV.map((item) => {
          const active =
            item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
          const Icon = item.icon;

          return (
            <Link
              key={item.to}
              to={item.to}
              className="relative font-ui uppercase flex items-center transition-all duration-300 rounded-lg group"
              style={{
                height: 46,
                padding: "0 16px",
                fontSize: "11px",
                fontWeight: 600,
                letterSpacing: "0.15em",
                color: active ? "#A0440F" : "#9E9189",
                background: active ? "#FEF3EC" : "transparent",
                border: active
                  ? "1px solid #F5C9A8"
                  : "1px solid transparent",
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.color = "#3D2F27";
                  e.currentTarget.style.background = "#F5F0EA";
                  e.currentTarget.style.borderColor = "#E8DDD4";
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.color = "#9E9189";
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.borderColor = "transparent";
                }
              }}
            >
              {/* Active indicator bar */}
              {active && (
                <div
                  className="absolute left-0 top-3.5 w-1 h-5 rounded-r"
                  style={{
                    background: "#C25520",
                    boxShadow: "0 0 8px #F5A97888",
                  }}
                />
              )}

              <Icon
                size={16}
                className="mr-3 transition-transform duration-300 group-hover:scale-110"
                style={{
                  color: active ? "#C25520" : "#C4B5AA",
                }}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer / Status */}
    </aside>
  );
}