import React from "react";

export function Card({
  children,
  className = "",
  padded = true,
}: {
  children: React.ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <div
      className={`bg-white border rounded-[4px] ${padded ? "p-5" : ""} ${className}`}
      style={{ borderColor: "var(--rzp-border)", boxShadow: "var(--shadow-low)" }}
    >
      {children}
    </div>
  );
}

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="text-xs font-semibold uppercase tracking-wide mb-2"
      style={{ color: "var(--rzp-muted)", letterSpacing: "0.06em" }}
    >
      {children}
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  size = "md",
  type = "button",
  className = "",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  disabled?: boolean;
  size?: "sm" | "md";
  type?: "button" | "submit";
  className?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-[4px] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  const sizes = size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2.5 text-sm";
  const variants: Record<string, string> = {
    primary: "text-white",
    secondary: "border",
    ghost: "",
    danger: "text-white",
  };
  const style: React.CSSProperties =
    variant === "primary"
      ? { background: "var(--rzp-blue)" }
      : variant === "danger"
      ? { background: "var(--rzp-danger)" }
      : variant === "secondary"
      ? { borderColor: "var(--rzp-border)", color: "var(--rzp-navy)", background: "white" }
      : { color: "var(--rzp-blue-dark)" };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${sizes} ${variants[variant]} ${className}`}
      style={style}
      onMouseEnter={(e) => {
        if (variant === "primary") (e.currentTarget as HTMLButtonElement).style.background = "var(--rzp-blue-dark)";
      }}
      onMouseLeave={(e) => {
        if (variant === "primary") (e.currentTarget as HTMLButtonElement).style.background = "var(--rzp-blue)";
      }}
    >
      {children}
    </button>
  );
}

export function Divider() {
  return <div className="h-px w-full" style={{ background: "var(--rzp-border)" }} />;
}
