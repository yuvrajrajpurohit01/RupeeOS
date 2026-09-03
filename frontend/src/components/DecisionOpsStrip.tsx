"use client";

import { useState } from "react";
import { AgentRunRecord } from "@/lib/types";
import { ChevronDown, Cpu } from "lucide-react";
import { formatTime } from "@/lib/format";

export function DecisionOpsStrip({ runs }: { runs: AgentRunRecord[] }) {
  const [open, setOpen] = useState(false);
  if (runs.length === 0) return null;
  const avgLatency = Math.round(runs.reduce((s, r) => s + r.latency_ms, 0) / runs.length);

  return (
    <div className="rounded-[4px] border overflow-hidden" style={{ borderColor: "var(--rzp-border)" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 text-xs font-semibold"
        style={{ color: "var(--rzp-muted)", background: "var(--rzp-canvas)" }}
      >
        <span className="flex items-center gap-1.5">
          <Cpu size={13} /> Agent Ops · {runs.length} decision run{runs.length > 1 ? "s" : ""} · {avgLatency}ms avg · telemetry is real
        </span>
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="divide-y" style={{ borderColor: "var(--rzp-border)" }}>
          {runs.map((r, i) => (
            <div key={`${r.money_id}-${r.agent}-${i}`} className="px-3.5 py-2 text-xs flex items-center justify-between gap-4">
              <div>
                <span className="font-semibold" style={{ color: "var(--rzp-navy)" }}>{r.agent}</span>
                <span className="mono ml-2 px-1.5 py-0.5 rounded-[4px]" style={{ background: "var(--rzp-blue-tint)", color: "var(--rzp-blue-dark)" }}>
                  {r.engine} · {r.mode}
                </span>
                <div className="mt-1" style={{ color: "var(--rzp-muted)" }}>{r.summary}</div>
              </div>
              <div className="mono text-right shrink-0" style={{ color: "var(--rzp-muted)" }}>
                <div>{r.latency_ms}ms</div>
                <div>{formatTime(r.timestamp)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
