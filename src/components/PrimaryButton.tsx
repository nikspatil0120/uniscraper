import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  loadingText?: string;
  children: ReactNode;
}

export function PrimaryButton({
  loading,
  loadingText = "WORKING...",
  children,
  className = "",
  disabled,
  ...rest
}: Props) {
  return (
    <button
      {...rest}
      disabled={loading || disabled}
      className={
        "w-full h-[52px] rounded-lg font-ui uppercase text-[13px] tracking-widest-2 font-bold " +
        "transition-all flex items-center justify-center gap-2 " +
        "disabled:opacity-70 disabled:cursor-not-allowed " +
        className
      }
      style={{
        background: "var(--accent)",
        color: "#0A0A0F",
      }}
      onMouseEnter={(e) => {
        if (loading || disabled) return;
        e.currentTarget.style.filter = "brightness(1.1)";
        e.currentTarget.style.transform = "translateY(-1px)";
        e.currentTarget.style.boxShadow = "0 8px 30px var(--accent-glow)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.filter = "";
        e.currentTarget.style.transform = "";
        e.currentTarget.style.boxShadow = "";
      }}
    >
      {loading ? (
        <>
          <Loader2 size={16} className="animate-spin" /> {loadingText}
        </>
      ) : (
        children
      )}
    </button>
  );
}
