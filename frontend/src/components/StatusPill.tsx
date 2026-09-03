import { MoneyState } from "@/lib/types";

type Tone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE_STYLES: Record<Tone, React.CSSProperties> = {
  success: { background: "var(--rzp-success-tint)", color: "var(--rzp-success)" },
  warning: { background: "var(--rzp-warning-tint)", color: "var(--rzp-warning)" },
  danger: { background: "var(--rzp-danger-tint)", color: "var(--rzp-danger)" },
  info: { background: "var(--rzp-blue-tint)", color: "var(--rzp-blue-dark)" },
  neutral: { background: "#eef1f5", color: "var(--rzp-muted)" },
};

const STATE_TONE: Record<MoneyState, Tone> = {
  DISCOVERED: "neutral",
  CHECKOUT_CREATED: "neutral",
  RISK_ANALYZED: "info",
  MANUAL_REVIEW: "warning",
  PAYMENT_INITIATED: "info",
  PAYMENT_SUCCESS: "success",
  PAYMENT_FAILED: "danger",
  RECOVERY_ANALYZED: "warning",
  RECOVERY_EXECUTED: "warning",
  RECOVERED: "success",
  LOST: "danger",
  SETTLEMENT_PENDING: "info",
  RECONCILED: "success",
  EXCEPTION: "danger",
};

export function StatusPill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-[4px] px-2 py-0.5 text-xs font-semibold"
      style={TONE_STYLES[tone]}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
      {label}
    </span>
  );
}

export function MoneyStateBadge({ state }: { state: MoneyState }) {
  return <StatusPill label={state.replaceAll("_", " ")} tone={STATE_TONE[state]} />;
}
