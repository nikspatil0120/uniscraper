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
        "w-full h-[52px] rounded-lg font-ui uppercase text-[12px] tracking-widest-2 font-bold " +
        "transition-all duration-300 ease-out flex items-center justify-center gap-2 " +
        "disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:box-shadow-none " +
        className
      }
      style={{
        background: "linear-gradient(135deg, #E58F65 0%, #D4B895 100%)",
        color: "#141211",
        border: "none",
        cursor: "pointer",
        position: "relative",
        overflow: "hidden",
      }}
      onMouseEnter={(e) => {
        if (loading || disabled) return;
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 8px 30px rgba(229, 143, 101, 0.4)";
        e.currentTarget.style.filter = "brightness(1.05)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "";
        e.currentTarget.style.boxShadow = "";
        e.currentTarget.style.filter = "";
      }}
    >
      {/* Light shimmer hover overlay effect */}
      <span 
        className="absolute inset-0 w-full h-full opacity-0 hover:opacity-10 transition-opacity duration-300 pointer-events-none"
        style={{
          background: "linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0) 100%)"
        }}
      />
      {loading ? (
        <>
          <Loader2 size={15} className="animate-spin" /> {loadingText}
        </>
      ) : (
        children
      )}
    </button>
  );
}
