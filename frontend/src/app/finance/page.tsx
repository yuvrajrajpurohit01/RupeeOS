"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, SectionLabel, Button } from "@/components/ui";
import { StatusPill, MoneyStateBadge } from "@/components/StatusPill";
import { useStore } from "@/lib/store";
import { formatINR, timeAgo } from "@/lib/format";
import { ArrowRight, PlayCircle, ScrollText } from "lucide-react";

export default function FinancePage() {
  const { transactions, reconcileAll } = useStore();
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const pending = transactions.filter((t) => t.state === "SETTLEMENT_PENDING");
  const done = transactions.filter((t) => t.state === "RECONCILED" || t.state === "EXCEPTION");
  const matched = done.filter((t) => t.reconciliation_status === "MATCHED").length;
  const feeAdjusted = done.filter((t) => t.reconciliation_status === "FEE_ADJUSTED_MATCH").length;
  const exceptions = done.filter((t) => t.reconciliation_status === "EXCEPTION").length;

  async function run() { setRunning(true); try { await reconcileAll(); } catch (e) { alert(e instanceof Error ? e.message : "Reconciliation failed"); } finally { setRunning(false); } }

  return (
    <div className="max-w-[1100px] mx-auto px-6 py-10">
      <div className="mb-8 flex items-start justify-between gap-4"><div><SectionLabel>Step 4 · Reconciliation</SectionLabel><h1 className="text-2xl font-bold" style={{ color: "var(--rzp-navy)" }}>Finance Agent closes the money loop</h1><p className="mt-1 text-sm" style={{ color: "var(--rzp-muted)" }}>Captured payments sit in <span className="mono">SETTLEMENT_PENDING</span> until a persisted reconciliation batch classifies each record.</p></div><Button onClick={() => void run()} disabled={running || pending.length === 0}><PlayCircle size={15} /> {running ? "Reconciling…" : "Run reconciliation batch"}</Button></div>
      <div className="grid grid-cols-3 gap-4 mb-6"><Stat label="Matched" value={matched} tone="success" /><Stat label="Fee-adjusted" value={feeAdjusted} tone="info" /><Stat label="Exceptions" value={exceptions} tone="danger" /></div>
      <Card padded={false}>
        <div className="px-5 py-3.5 flex items-center gap-2 border-b" style={{ borderColor: "var(--rzp-border)" }}><ScrollText size={15} /><span className="text-sm font-semibold">Settlement records</span></div>
        {[...pending, ...done].length === 0 ? <div className="px-5 py-10 text-center text-sm" style={{ color: "var(--rzp-muted)" }}>No captured payment awaiting reconciliation.</div> : [...pending, ...done].map((t) => <div key={t.money_id} className="px-5 py-3 flex items-center justify-between border-b text-sm" style={{ borderColor: "var(--rzp-border)" }}><div><div className="font-medium">{t.customer_name}</div><div className="text-xs mono" style={{ color: "var(--rzp-muted)" }}>{t.money_id}</div></div><div className="mono">{formatINR(t.amount)}</div><div className="flex items-center gap-2">{t.reconciliation_status ? <StatusPill label={t.reconciliation_status.replaceAll("_", " ")} tone={t.reconciliation_status === "EXCEPTION" ? "danger" : "success"} /> : <MoneyStateBadge state={t.state} />}<span className="text-xs" style={{ color: "var(--rzp-muted)" }}>{timeAgo(t.updated_at)}</span></div></div>)}
      </Card>
      {done.length > 0 && <div className="mt-6 flex justify-end"><Button variant="secondary" onClick={() => router.push("/command-center")}>Continue to Command Center <ArrowRight size={15} /></Button></div>}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: "success" | "info" | "danger" }) { const color = tone === "success" ? "var(--rzp-success)" : tone === "danger" ? "var(--rzp-danger)" : "var(--rzp-blue-dark)"; return <Card><div className="text-xs font-semibold uppercase" style={{ color: "var(--rzp-muted)" }}>{label}</div><div className="text-3xl font-bold mt-1 mono" style={{ color }}>{value}</div></Card>; }
