import { useEffect, useState } from "react";

export function TopBar({ title }: { title: string }) {
  const [stamp, setStamp] = useState("");
  useEffect(() => {
    const update = () =>
      setStamp(new Date().toISOString().replace("T", " ").substring(0, 19) + " UTC");
    update();
    const t = setInterval(update, 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div
      className="flex items-center justify-between"
      style={{
        height: 56,
        padding: "0 40px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        background: "#0A0A0F",
        flexShrink: 0,
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
