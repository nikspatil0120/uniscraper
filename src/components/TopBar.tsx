import { useEffect, useState } from "react";

export function TopBar({ title }: { title: string }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const stamp =
    now.toISOString().slice(0, 10) + " " + now.toISOString().slice(11, 19) + " UTC";
  return (
    <div
      className="flex items-center justify-between"
      style={{
        height: 56,
        padding: "0 40px",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <h1
        className="font-display italic leading-none"
        style={{ fontSize: 22, color: "#F2EFE9" }}
      >
        {title}
      </h1>
      <div
        className="font-mono"
        style={{ fontSize: 13, color: "#4A4958" }}
      >
        {stamp}
      </div>
    </div>
  );
}
