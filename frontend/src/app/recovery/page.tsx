"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowLeft, ArrowRight, HeartPulse, ShieldAlert } from "lucide-react";
import { Card, SectionLabel, Button, Divider } from "@/components/ui";
import { MoneyStateBadge } from "@/components/StatusPill";
import { PolicyDecisionCard, PolicyGateNote } from "@/components/PolicyDecisionCard";
import { DecisionOpsStrip } from "@/components/DecisionOpsStrip";
import { useStore } from "@/lib/store";
import { formatINR } from "@/lib/format";

function RecoveryContent() {
  const params = useSearchParams();
  const router = useRouter();
  const moneyId = params.get("money_id");
  const { getTransaction, transactions, runRecovery, getPolicyDecisions, getAgentRuns, manualReviews } = useStore();
  const [running, setRunning] = useState(false);
  const tx = moneyId ? getTransaction(moneyId) : transactions.find((t) => t.state === "PAYMENT_FAILED");
  useEffect(() => { if (!moneyId && tx) router.replace(`/recovery?money_id=${tx.money_id}`); }, [moneyId, tx, router]);

  if (!tx) return <div className="max-w-[600px] mx-auto px-6 py-24 text-center"><h2 className="font-bold">No failed payment awaiting recovery</h2><Button className="mt-4" onClick={() => router.push("/commerce")}>Start a transaction</Button></div>;
  const txId = tx.money_id;

  const decisions = getPolicyDecisions(tx.money_id);
  const latest = decisions[decisions.length - 1];
  const runs = getAgentRuns(tx.money_id).filter((r) => r.agent === "recovery");
  const review = manualReviews.find((r) => r.money_id === tx.money_id && r.review_type === "RECOVERY");
  const terminal = ["SETTLEMENT_PENDING", "RECONCILED", "LOST", "EXCEPTION"].includes(tx.state);

  async function run() {
    setRunning(true);
    try { await runRecovery(txId); } catch (e) { alert(e instanceof Error ? e.message : "Recovery failed"); } finally { setRunning(false); }
  }

  return (
    <div className="max-w-[1100px] mx-auto px-6 py-10">
      <div className="mb-8 flex justify-between gap-4"><div><SectionLabel>Step 3 · Recovery</SectionLabel><h1 className="text-2xl font-bold" style={{ color: "var(--rzp-navy)" }}>Recovery Agent diagnoses; policy executes bounded action</h1><p className="mt-1 text-sm" style={{ color: "var(--rzp-muted)" }}>For retryable failures, an approved recovery creates a fresh Razorpay order and opens a new real checkout attempt.</p></div><MoneyStateBadge state={tx.state} /></div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <SectionLabel>Failed transaction</SectionLabel>
          <div className="space-y-1.5 text-sm"><Row label="Customer" value={tx.customer_name} /><Row label="Amount" value={formatINR(tx.amount)} /><Row label="Failure reason" value={tx.failure_reason ?? "—"} /><Row label="Recovery attempts" value={String(tx.recovery_attempts)} /></div>
          <div className="mt-3 rounded-[4px] border p-3 flex gap-2 text-sm" style={{ borderColor: "var(--rzp-danger)", background: "var(--rzp-danger-tint)" }}><AlertTriangle size={15} /><span>Payment failed — {tx.failure_reason ?? "awaiting reason"}</span></div>
          {tx.recovery_explanation && <div className="mt-3 text-xs rounded-[4px] p-3" style={{ background: "var(--rzp-canvas)", color: "var(--rzp-muted)" }}><b style={{ color: "var(--rzp-navy)" }}>Why this decision:</b> {tx.recovery_explanation}</div>}
          <Divider />
          {["PAYMENT_FAILED", "RECOVERY_ANALYZED"].includes(tx.state) && <Button className="w-full mt-4" onClick={() => void run()} disabled={running}><HeartPulse size={15} /> {running ? "Supervisor running…" : "Run Agentic Recovery Flow"}</Button>}
        </Card>

        <Card>
          <SectionLabel>Policy decision</SectionLabel>
          {tx.recovery_probability !== null && tx.recovery_probability !== undefined && <div className="mb-3 flex justify-between text-sm"><span style={{ color: "var(--rzp-muted)" }}>Recovery probability</span><b className="mono">{tx.recovery_probability.toFixed(2)}</b></div>}
          {latest ? <PolicyDecisionCard decision={latest} /> : <p className="text-sm" style={{ color: "var(--rzp-muted)" }}>Waiting for Recovery Agent…</p>}
          {tx.state === "MANUAL_REVIEW" && review && <div className="mt-4 rounded-[4px] border p-3 text-sm" style={{ borderColor: "var(--rzp-warning)", background: "var(--rzp-warning-tint)" }}><div className="flex gap-2 font-semibold"><ShieldAlert size={16} /> Recovery needs human approval</div><p className="text-xs mt-1">{review.reason}</p><Button variant="secondary" className="w-full mt-3" onClick={() => router.push("/command-center")}>Open approval inbox <ArrowRight size={15} /></Button></div>}
          {tx.state === "RECOVERY_EXECUTED" && <p className="mt-4 text-xs" style={{ color: "var(--rzp-muted)" }}>Recovery order is active. State changes only after verified Razorpay payment status/webhook.</p>}
          {terminal && <div className="mt-4 space-y-2"><Button variant="secondary" className="w-full" onClick={() => router.push("/finance")}>Continue to Reconciliation <ArrowRight size={15} /></Button><Button variant="ghost" className="w-full" onClick={() => router.push("/commerce")}><ArrowLeft size={14} /> Start another transaction</Button></div>}
          <Divider /><div className="mt-3"><PolicyGateNote /></div>
        </Card>
      </div>
      {runs.length > 0 && <div className="mt-6"><DecisionOpsStrip runs={runs} /></div>}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) { return <div className="flex justify-between gap-4"><span style={{ color: "var(--rzp-muted)" }}>{label}</span><span className="font-medium text-right" style={{ color: "var(--rzp-navy)" }}>{value}</span></div>; }
export default function RecoveryPage() { return <Suspense fallback={null}><RecoveryContent /></Suspense>; }
