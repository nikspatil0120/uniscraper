import { useEffect, useState } from "react";

export function TopBar({ title }: { title: string }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const stamp =
    now.toISOString().slice(0, 10) + "  " + now.toTimeString().slice(0, 8) + " UTC";
  return (
    <div
      className="flex items-end justify-between px-10 pt-10 pb-6"
      style={{ borderBottom: "1px solid var(--border)" }}
    >
      <h1 className="font-display italic text-[40px] leading-none text-text-primary">
        {title}
      </h1>
      <div
        className="font-mono text-[11px] uppercase"
        style={{ color: "var(--text-muted)" }}
      >
        {stamp}
      </div>
    </div>
  );
}
