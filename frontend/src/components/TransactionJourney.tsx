import { Transaction } from "@/lib/types";
import { MoneyStateBadge } from "./StatusPill";
import { formatTime } from "@/lib/format";

export function TransactionJourney({ transaction }: { transaction: Transaction }) {
  const steps = [
    { state: "DISCOVERED" as const, timestamp: transaction.created_at, actor: "orchestrator", reason: "Money object created" },
    ...transaction.history.map((h) => ({ state: h.new_state, timestamp: h.timestamp, actor: h.triggering_agent, reason: h.reason })),
  ];
  return (
    <div className="space-y-3">
      {steps.map((step, index) => (
        <div key={`${step.state}-${index}`} className="grid grid-cols-[18px_1fr] gap-3">
          <div className="relative flex justify-center">
            <span className="mt-1 h-2.5 w-2.5 rounded-full" style={{ background: "var(--rzp-blue)" }} />
            {index < steps.length - 1 && <span className="absolute top-4 bottom-[-14px] w-px" style={{ background: "var(--rzp-border)" }} />}
          </div>
          <div className="pb-1">
            <div className="flex items-center justify-between gap-2">
              <MoneyStateBadge state={step.state} />
              <span className="text-[11px] mono" style={{ color: "var(--rzp-muted)" }}>{formatTime(step.timestamp)}</span>
            </div>
            <div className="mt-1 text-xs" style={{ color: "var(--rzp-muted)" }}>
              <span className="font-semibold" style={{ color: "var(--rzp-navy)" }}>{step.actor}</span> — {step.reason}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
