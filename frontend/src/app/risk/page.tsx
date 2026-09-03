"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, SectionLabel, Button, Divider } from "@/components/ui";
import { MoneyStateBadge } from "@/components/StatusPill";
import { PolicyDecisionCard, PolicyGateNote } from "@/components/PolicyDecisionCard";
import { DecisionOpsStrip } from "@/components/DecisionOpsStrip";
import { useStore } from "@/lib/store";
import { formatINR } from "@/lib/format";
import { ArrowRight, Gauge, CreditCard, ShieldAlert } from "lucide-react";

function RiskContent() {
  const params = useSearchParams();
  const router = useRouter();
  const moneyId = params.get("money_id");
  const { getTransaction, runRisk, pay, getPolicyDecisions, getAgentRuns, transactions, manualReviews } = useStore();
  const [working, setWorking] = useState(false);

  const tx = moneyId ? getTransaction(moneyId) : transactions.find((t) => t.state === "CHECKOUT_CREATED");
  useEffect(() => { if (!moneyId && tx) router.replace(`/risk?money_id=${tx.money_id}`); }, [moneyId, tx, router]);

  if (!tx) return <Empty />;
  const txId = tx.money_id;
  const decisions = getPolicyDecisions(tx.money_id);
  const latestDecision = decisions[decisions.length - 1];
  const runs = getAgentRuns(tx.money_id);
  const pendingReview = manualReviews.find((r) => r.money_id === tx.money_id);

  async function doRisk() {
    setWorking(true);
    try { await runRisk(txId); } catch (e) { alert(e instanceof Error ? e.message : "Risk analysis failed"); } finally { setWorking(false); }
  }

  async function doPay() {
    setWorking(true);
    try { await pay(txId); } catch (e) { alert(e instanceof Error ? e.message : "Payment flow failed"); } finally { setWorking(false); }
  }

  return (
    <div className="max-w-[1100px] mx-auto px-6 py-10">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <SectionLabel>Step 2 · Risk &amp; Payment</SectionLabel>
          <h1 className="text-2xl font-bold" style={{ color: "var(--rzp-navy)" }}>Risk Agent scores; policy controls payment</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--rzp-muted)" }}>A VERIFY decision now enters a real manual-review state. `/pay` refuses to create a Razorpay order until policy or a human has allowed it.</p>
        </div>
        <MoneyStateBadge state={tx.state} />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <SectionLabel>Transaction</SectionLabel>
          <div className="space-y-1.5 text-sm">
            <Row label="Customer" value={tx.customer_name} /><Row label="Product" value={tx.product_name ?? "—"} /><Row label="Amount" value={formatINR(tx.amount)} mono /><Row label="money_id" value={tx.money_id} mono />
          </div>
          <Divider />
          {tx.state === "CHECKOUT_CREATED" && <Button className="w-full mt-4" onClick={() => void doRisk()} disabled={working}><Gauge size={15} /> {working ? "Supervisor running…" : "Run Agentic Risk Flow"}</Button>}
          {tx.risk_score !== null && tx.risk_score !== undefined && (
            <div className="mt-4 rise-in space-y-3">
              <div className="flex justify-between text-sm"><span style={{ color: "var(--rzp-muted)" }}>Risk score</span><span className="font-bold mono">{tx.risk_score.toFixed(2)}</span></div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: "#eef1f5" }}><div className="h-full" style={{ width: `${tx.risk_score * 100}%`, background: tx.risk_score >= 0.5 ? "var(--rzp-danger)" : "var(--rzp-success)" }} /></div>
              <div className="text-sm"><span style={{ color: "var(--rzp-muted)" }}>Recommendation: </span><b>{tx.risk_decision}</b></div>
              <div className="space-y-1.5">{tx.risk_factors.map((f) => <div key={f.signal} className="text-xs rounded-[4px] px-2.5 py-2" style={{ background: "var(--rzp-canvas)", color: "var(--rzp-muted)" }}><b style={{ color: "var(--rzp-navy)" }}>{f.signal}</b> · {f.detail}</div>)}</div>
            </div>
          )}
        </Card>

        <Card>
          <SectionLabel>Policy Engine</SectionLabel>
          {latestDecision ? <PolicyDecisionCard decision={latestDecision} /> : <p className="text-sm" style={{ color: "var(--rzp-muted)" }}>Waiting for risk analysis…</p>}

          {tx.state === "RISK_ANALYZED" && <Button className="w-full mt-4" onClick={() => void doPay()} disabled={working}><CreditCard size={15} /> {working ? "Opening Razorpay…" : "Pay with Razorpay Test Mode"}</Button>}

          {tx.state === "MANUAL_REVIEW" && pendingReview && (
            <div className="mt-4 rounded-[4px] border p-3 text-sm" style={{ borderColor: "var(--rzp-warning)", background: "var(--rzp-warning-tint)" }}>
              <div className="flex gap-2 font-semibold"><ShieldAlert size={16} /> Human approval required</div>
              <p className="text-xs mt-1">{pendingReview.reason}</p>
              <Button variant="secondary" className="w-full mt-3" onClick={() => router.push("/command-center")}>Open approval inbox <ArrowRight size={15} /></Button>
            </div>
          )}

          {tx.state === "PAYMENT_FAILED" && <Button variant="danger" className="w-full mt-4" onClick={() => router.push(`/recovery?money_id=${tx.money_id}`)}>Send to Recovery Agent <ArrowRight size={15} /></Button>}
          {tx.state === "SETTLEMENT_PENDING" && <Button variant="secondary" className="w-full mt-4" onClick={() => router.push("/finance")}>Continue to Reconciliation <ArrowRight size={15} /></Button>}

          {tx.state === "PAYMENT_INITIATED" && <p className="mt-4 text-xs" style={{ color: "var(--rzp-muted)" }}>Order created. RupeeOS is waiting for verified checkout status/webhook; it will not invent the result.</p>}
          <Divider /><div className="mt-3"><PolicyGateNote /></div>
        </Card>
      </div>
      {runs.length > 0 && <div className="mt-6"><DecisionOpsStrip runs={runs} /></div>}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) { return <div className="flex justify-between gap-4"><span style={{ color: "var(--rzp-muted)" }}>{label}</span><span className={`text-right ${mono ? "mono text-xs" : "font-medium"}`} style={{ color: "var(--rzp-navy)" }}>{value}</span></div>; }
function Empty() { const router = useRouter(); return <div className="max-w-[600px] mx-auto px-6 py-24 text-center"><h2 className="font-bold">No checkout transaction</h2><Button className="mt-4" onClick={() => router.push("/commerce")}>Go to Commerce</Button></div>; }
export default function RiskPage() { return <Suspense fallback={null}><RiskContent /></Suspense>; }
