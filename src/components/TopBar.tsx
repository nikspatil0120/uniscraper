import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { getCurrentIST } from "@/lib/utils";

export function TopBar({ title }: { title: string }) {
  const [stamp, setStamp] = useState("");

  useEffect(() => {
    const update = () => setStamp(getCurrentIST());
    update();
    const t = setInterval(update, 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div
      className="flex items-center justify-between w-full"
      style={{
        height: 64,
        padding: "0 40px",
        background: "rgba(20, 18, 17, 0.7)",
        backdropFilter: "blur(16px)",
        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
        flexShrink: 0,
        zIndex: 30,
      }}
    >
      <h1
        className="font-display leading-none font-bold"
        style={{ fontSize: 20, color: "var(--text-primary)" }}
      >
        {title}
      </h1>

      {/* Timestamp Pill */}
      <div
        className="flex items-center gap-2 px-3 py-1.5 rounded-full"
        style={{
          background: "rgba(255, 255, 255, 0.02)",
          border: "1px solid rgba(255, 255, 255, 0.04)",
        }}
      >
        <Clock size={12} style={{ color: "var(--text-secondary)" }} />
        <span
          className="font-mono"
          style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.05em" }}
        >
          {stamp}
        </span>
      </div>
    </div>
  );
}
