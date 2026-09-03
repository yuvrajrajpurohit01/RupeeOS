import { PolicyDecision } from "@/lib/types";
import { CheckCircle2, XCircle, ShieldCheck } from "lucide-react";
import { formatTime } from "@/lib/format";

export function PolicyDecisionCard({ decision }: { decision: PolicyDecision }) {
  const approved = decision.approved;
  return (
    <div
      className="rounded-[4px] border p-3.5 rise-in"
      style={{
        borderColor: approved ? "var(--rzp-success)" : "var(--rzp-danger)",
        background: approved ? "var(--rzp-success-tint)" : "var(--rzp-danger-tint)",
      }}
    >
      <div className="flex items-start gap-2.5">
        {approved ? (
          <CheckCircle2 size={18} className="shrink-0 mt-0.5" style={{ color: "var(--rzp-success)" }} />
        ) : (
          <XCircle size={18} className="shrink-0 mt-0.5" style={{ color: "var(--rzp-danger)" }} />
        )}
        <div className="flex-1">
          <div className="flex items-center justify-between gap-2">
            <span
              className="text-xs font-bold uppercase tracking-wide"
              style={{ color: approved ? "var(--rzp-success)" : "var(--rzp-danger)" }}
            >
              Policy Engine {approved ? "approved" : "rejected"} — {decision.action.replaceAll("_", " ").toLowerCase()}
            </span>
            <span className="text-[11px] mono" style={{ color: "var(--rzp-muted)" }}>
              {formatTime(decision.timestamp)}
            </span>
          </div>
          <p className="text-sm mt-1" style={{ color: "var(--rzp-navy)" }}>
            {decision.reason}
          </p>
        </div>
      </div>
    </div>
  );
}

export function PolicyGateNote() {
  return (
    <div className="flex items-center gap-2 text-[11px]" style={{ color: "var(--rzp-muted)" }}>
      <ShieldCheck size={13} />
      Agents recommend. Deterministic policy approves. Actions are logged.
    </div>
  );
}
