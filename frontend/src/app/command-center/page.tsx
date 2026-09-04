"use client";

import { useMemo, useState } from "react";
import { AlertOctagon, Bot, Check, FlaskConical, RotateCcw, ShieldCheck, TrendingUp, UserCheck, Workflow, X, Zap } from "lucide-react";
import { Card, SectionLabel, Button } from "@/components/ui";
import { StatusPill } from "@/components/StatusPill";
import { TransactionJourney } from "@/components/TransactionJourney";
import { DecisionOpsStrip } from "@/components/DecisionOpsStrip";
import { useStore } from "@/lib/store";
import { formatINR } from "@/lib/format";

export default function CommandCenterPage() {
  const {
    transactions,
    policyDecisions,
    agentRuns,
    agentManifests,
    workflowRuns,
    manualReviews,
    audit,
    systemStatus,
    metrics,
    evaluation,
    approveReview,
    rejectReview,
    simulateFailureSpike,
    resetCircuitBreaker,
    runEvaluation,
  } = useStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [workingReview, setWorkingReview] = useState<string | null>(null);
  const selected = useMemo(() => transactions.find((t) => t.money_id === selectedId) ?? transactions.find((t) => !t.customer_id.startsWith("demo_spike_")) ?? null, [transactions, selectedId]);

  async function approve(id: string) {
    setWorkingReview(id);
    try { await approveReview(id); } catch (e) { alert(e instanceof Error ? e.message : "Approval failed"); } finally { setWorkingReview(null); }
  }
  async function reject(id: string) {
    setWorkingReview(id);
    try { await rejectReview(id); } catch (e) { alert(e instanceof Error ? e.message : "Rejection failed"); } finally { setWorkingReview(null); }
  }

  const approved = policyDecisions.filter((p) => p.approved).length;
  const rejected = policyDecisions.length - approved;

  return (
    <div className="max-w-[1200px] mx-auto px-6 py-10">
      <div className="mb-8"><SectionLabel>Step 5 · Command Center</SectionLabel><h1 className="text-2xl font-bold" style={{ color: "var(--rzp-navy)" }}>One operating view for every rupee</h1><p className="mt-1 text-sm" style={{ color: "var(--rzp-muted)" }}>Persistent state, human approvals, policy decisions, decision telemetry, batch evidence, and a tamper-evident audit chain now come from the backend.</p></div>

      <Card className="mb-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-[4px] flex items-center justify-center" style={{ background: systemStatus.circuit_breaker_tripped ? "var(--rzp-danger-tint)" : "var(--rzp-success-tint)", color: systemStatus.circuit_breaker_tripped ? "var(--rzp-danger)" : "var(--rzp-success)" }}>{systemStatus.circuit_breaker_tripped ? <AlertOctagon size={20} /> : <ShieldCheck size={20} />}</div>
            <div><div className="font-bold text-sm">{systemStatus.circuit_breaker_tripped ? "Circuit Breaker Tripped" : "System Normal"}</div><div className="text-xs" style={{ color: "var(--rzp-muted)" }}>EXCEPTION/LOST rate: <span className="mono font-semibold">{(systemStatus.failure_rate * 100).toFixed(0)}%</span> · {systemStatus.reason}</div></div>
          </div>
          <div className="flex gap-2"><Button variant="secondary" size="sm" onClick={() => void resetCircuitBreaker()}><RotateCcw size={13} /> Reset demo spike</Button><Button variant="danger" size="sm" onClick={() => void simulateFailureSpike()}><Zap size={13} /> Simulate failure spike</Button></div>
        </div>
        {systemStatus.circuit_breaker_tripped && <div className="mt-3 text-xs rounded-[4px] p-2.5" style={{ background: "var(--rzp-danger-tint)", color: "var(--rzp-danger)" }}>The backend now blocks new autonomous money actions and routes them to human review.</div>}
      </Card>

      <Card className="mb-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-[4px] flex items-center justify-center" style={{ background: systemStatus.ai?.active ? "var(--rzp-blue-tint)" : "var(--rzp-canvas)", color: "var(--rzp-blue-dark)" }}><Bot size={20} /></div>
            <div>
              <div className="font-bold text-sm">Hybrid AI reasoning</div>
              <div className="text-xs" style={{ color: "var(--rzp-muted)" }}>{systemStatus.ai?.model ?? "gpt-5.6-terra"} · {systemStatus.ai?.active ? "live structured reasoning" : "safe deterministic fallback"}</div>
            </div>
          </div>
          <StatusPill label={systemStatus.ai?.active ? "AI ACTIVE" : "AI FALLBACK"} tone={systemStatus.ai?.active ? "success" : "warning"} />
        </div>
        <p className="text-xs mt-3" style={{ color: "var(--rzp-muted)" }}>The model selects and explains recommendations using structured output. The Money State Graph validates routing, and only the deterministic Policy Engine can authorize an external action.</p>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Metric label="Revenue processed" value={formatINR(metrics?.revenue_processed ?? 0)} />
        <Metric label="Revenue recovered" value={formatINR(metrics?.revenue_recovered ?? 0)} />
        <Metric label="Amount at risk" value={formatINR(metrics?.amount_at_risk ?? 0)} />
        <Metric label="Audit entries" value={String(audit.length)} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <Card>
          <div className="flex items-center justify-between gap-3"><SectionLabel>Human approval inbox</SectionLabel><StatusPill label={`${manualReviews.length} pending`} tone={manualReviews.length ? "warning" : "success"} /></div>
          {manualReviews.length === 0 ? <p className="text-sm" style={{ color: "var(--rzp-muted)" }}>No money action currently needs a human.</p> : <div className="space-y-3">{manualReviews.map((r) => {
            const tx = transactions.find((t) => t.money_id === r.money_id);
            return <div key={r.review_id} className="rounded-[4px] border p-3" style={{ borderColor: "var(--rzp-border)" }}><div className="flex items-start justify-between gap-3"><div><div className="text-sm font-semibold">{r.review_type} · {r.proposed_action.replaceAll("_", " ")}</div><div className="text-xs mono mt-0.5" style={{ color: "var(--rzp-muted)" }}>{r.money_id}{tx ? ` · ${formatINR(tx.amount)}` : ""}</div></div><UserCheck size={17} style={{ color: "var(--rzp-warning)" }} /></div><p className="text-xs mt-2" style={{ color: "var(--rzp-muted)" }}>{r.reason}</p><div className="flex gap-2 mt-3"><Button size="sm" onClick={() => void approve(r.review_id)} disabled={workingReview === r.review_id}><Check size={13} /> Approve</Button><Button variant="danger" size="sm" onClick={() => void reject(r.review_id)} disabled={workingReview === r.review_id}><X size={13} /> Reject</Button></div></div>;
          })}</div>}
        </Card>

        <Card>
          <SectionLabel>Policy &amp; safety</SectionLabel>
          <div className="flex gap-2 mb-4"><StatusPill label={`${approved} approved`} tone="success" /><StatusPill label={`${rejected} rejected / gated`} tone="danger" /></div>
          <div className="grid grid-cols-2 gap-3 text-sm"><Mini label="Policy decisions" value={String(metrics?.policy_decisions ?? policyDecisions.length)} /><Mini label="Pending reviews" value={String(metrics?.pending_manual_reviews ?? manualReviews.length)} /><Mini label="Reconciled" value={String(metrics?.reconciled ?? 0)} /><Mini label="Exceptions" value={String(metrics?.exceptions ?? 0)} /></div>
          <p className="text-xs mt-4" style={{ color: "var(--rzp-muted)" }}>High-value VERIFY, circuit-breaker gates, retry limits, recovery probability, and autonomous amount limits are enforced server-side.</p>
        </Card>
      </div>

      <div className="grid lg:grid-cols-[0.9fr_1.1fr] gap-6 mb-6">
        <Card>
          <div className="flex items-center justify-between"><SectionLabel>Money State Graph</SectionLabel>{selected && <span className="text-[11px] mono" style={{ color: "var(--rzp-muted)" }}>{selected.money_id}</span>}</div>
          {transactions.length > 1 && <select className="w-full border rounded-[4px] px-2 py-2 text-xs mb-4" style={{ borderColor: "var(--rzp-border)" }} value={selected?.money_id ?? ""} onChange={(e) => setSelectedId(e.target.value)}>{transactions.filter((t) => !t.customer_id.startsWith("demo_spike_")).slice(0, 20).map((t) => <option value={t.money_id} key={t.money_id}>{t.customer_name} · {formatINR(t.amount)} · {t.state}</option>)}</select>}
          {selected ? <TransactionJourney transaction={selected} /> : <p className="text-sm" style={{ color: "var(--rzp-muted)" }}>Create a transaction to see its state journey.</p>}
        </Card>

        <Card>
          <div className="flex items-center justify-between gap-4"><div><SectionLabel>Recovery batch evidence</SectionLabel><p className="text-xs" style={{ color: "var(--rzp-muted)" }}>Seeded synthetic benchmark for repeatable Buildathon evidence; clearly separated from live merchant metrics.</p></div><Button variant="secondary" size="sm" onClick={() => void runEvaluation()}><FlaskConical size={13} /> Run 250 records</Button></div>
          {evaluation ? <div className="grid grid-cols-2 gap-3 mt-4"><Mini label="Failed revenue" value={formatINR(evaluation.failed_revenue)} /><Mini label="Recovered revenue" value={formatINR(evaluation.recovered_revenue)} /><Mini label="Recovery rate" value={`${(evaluation.recovery_rate * 100).toFixed(1)}%`} /><Mini label="Policy blocks" value={String(evaluation.policy_blocks)} /><Mini label="Manual escalations" value={String(evaluation.manual_escalations)} /><Mini label="Attempts" value={String(evaluation.recovery_attempts)} /><p className="col-span-2 text-[11px]" style={{ color: "var(--rzp-muted)" }}>{evaluation.note}</p></div> : <div className="mt-4 text-sm" style={{ color: "var(--rzp-muted)" }}>Run the benchmark to produce measured, repeatable synthetic results.</div>}
        </Card>
      </div>

      <div className="grid lg:grid-cols-[0.8fr_1.2fr] gap-6 mb-6">
        <Card>
          <div className="flex items-center justify-between gap-3">
            <SectionLabel>Live agent registry</SectionLabel>
            <StatusPill label={`${agentManifests.length} bounded agents`} tone="info" />
          </div>
          <div className="space-y-2">
            {agentManifests.map((agent) => (
              <div key={agent.name} className="rounded-[4px] border p-3" style={{ borderColor: "var(--rzp-border)" }}>
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 text-sm font-semibold capitalize"><Bot size={14} /> {agent.name}</span>
                  <span className="mono text-[10px]" style={{ color: "var(--rzp-muted)" }}>{agent.engine}</span>
                </div>
                <p className="text-xs mt-1" style={{ color: "var(--rzp-muted)" }}>{agent.role}</p>
                <div className="mt-2 text-[10px]" style={{ color: "var(--rzp-blue-dark)" }}>{agent.capabilities.join(" · ")}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between gap-3">
            <SectionLabel>Durable supervisor traces</SectionLabel>
            <StatusPill label={`${workflowRuns.length} runs`} tone={workflowRuns.length ? "info" : "neutral"} />
          </div>
          {workflowRuns.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--rzp-muted)" }}>Run Risk or Recovery to create an inspectable plan and execution trace.</p>
          ) : (
            <div className="space-y-3">
              {workflowRuns.slice(0, 8).map((run) => (
                <div key={run.run_id} className="rounded-[4px] border p-3" style={{ borderColor: "var(--rzp-border)" }}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold"><Workflow size={14} /> {run.goal.replaceAll("_", " ").toLowerCase()}</div>
                      <div className="mono text-[10px] mt-1" style={{ color: "var(--rzp-muted)" }}>{run.run_id} · {run.money_id}</div>
                    </div>
                    <StatusPill label={run.status} tone={run.status === "COMPLETED" ? "success" : run.status === "FAILED" ? "danger" : "warning"} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs" style={{ color: "var(--rzp-muted)" }}>
                    <span>steps <b className="mono">{run.steps_used}/{run.max_steps}</b></span>
                    <span>current <b>{run.current_agent ?? "—"}</b></span>
                    <span>stop <b>{run.stop_reason?.replaceAll("_", " ").toLowerCase() ?? "—"}</b></span>
                  </div>
                  {run.steps.length > 0 && <p className="mt-2 text-xs" style={{ color: "var(--rzp-navy)" }}><b>{run.steps.at(-1)?.agent}:</b> {run.steps.at(-1)?.outcome}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card>
        <SectionLabel>Agent decision telemetry</SectionLabel>
        <p className="text-xs mb-3" style={{ color: "var(--rzp-muted)" }}>This surface reports the engine actually used for each decision: {systemStatus.ai?.active ? "OpenAI structured reasoning with deterministic policy enforcement" : "deterministic fallback because AI is disabled or unconfigured"}.</p>
        <DecisionOpsStrip runs={agentRuns.slice(-30)} />
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) { return <Card><div className="text-xs font-semibold uppercase" style={{ color: "var(--rzp-muted)" }}><TrendingUp size={13} className="inline mr-1" />{label}</div><div className="text-2xl font-bold mt-1.5 mono" style={{ color: "var(--rzp-navy)" }}>{value}</div></Card>; }
function Mini({ label, value }: { label: string; value: string }) { return <div className="rounded-[4px] p-3" style={{ background: "var(--rzp-canvas)" }}><div className="text-[11px] uppercase font-semibold" style={{ color: "var(--rzp-muted)" }}>{label}</div><div className="text-lg font-bold mono mt-1">{value}</div></div>; }
