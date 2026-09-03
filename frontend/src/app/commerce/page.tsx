"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, SectionLabel, Button, Divider } from "@/components/ui";
import { PRODUCTS, Product } from "@/lib/catalog";
import { useStore } from "@/lib/store";
import { GrowthRecommendation } from "@/lib/types";
import { formatINR } from "@/lib/format";
import { Sparkles, ShoppingCart, ArrowRight, Bot, Server } from "lucide-react";

export default function CommercePage() {
  const [selected, setSelected] = useState<Product>(PRODUCTS[0]);
  const [includeAddon, setIncludeAddon] = useState(true);
  const [customerName, setCustomerName] = useState("Aarav Shah");
  const [agentRun, setAgentRun] = useState(false);
  const [recommendation, setRecommendation] = useState<GrowthRecommendation | null>(null);
  const [recommending, setRecommending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();
  const { startCheckout, recommendGrowth, backendConnected, lastError } = useStore();

  const total = selected.price + (includeAddon && selected.addon && agentRun ? selected.addon.price : 0);

  async function proceedToCheckout() {
    setSubmitting(true);
    try {
      const id = await startCheckout(selected, includeAddon && agentRun, customerName);
      router.push(`/risk?money_id=${id}`);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Could not create checkout");
    } finally {
      setSubmitting(false);
    }
  }

  async function runGrowthAgent() {
    setRecommending(true);
    try {
      const result = await recommendGrowth(selected);
      setRecommendation(result);
      setAgentRun(true);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Growth recommendation failed");
    } finally {
      setRecommending(false);
    }
  }

  return (
    <div className="max-w-[1100px] mx-auto px-6 py-10">
      <div className="mb-8">
        <SectionLabel>Step 1 · Commerce</SectionLabel>
        <h1 className="text-2xl font-bold" style={{ color: "var(--rzp-navy)" }}>Growth Agent — discover &amp; recommend</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--rzp-muted)" }}>
          The demo catalog uses an honest deterministic bundle rule. Creating checkout writes a real transaction to the backend Money State Graph: <span className="mono font-medium">DISCOVERED → CHECKOUT_CREATED</span>.
        </p>
      </div>

      <div className="mb-5 rounded-[4px] border px-3 py-2 text-xs flex items-center gap-2" style={{ borderColor: backendConnected ? "var(--rzp-success)" : "var(--rzp-danger)", background: backendConnected ? "var(--rzp-success-tint)" : "var(--rzp-danger-tint)" }}>
        <Server size={14} />
        {backendConnected ? "FastAPI connected · SQLite Money State Graph active" : `Backend disconnected${lastError ? ` — ${lastError}` : ""}`}
      </div>

      <div className="grid md:grid-cols-[1.4fr_1fr] gap-6">
        <Card>
          <SectionLabel>Choose a product</SectionLabel>
          <div className="space-y-2">
            {PRODUCTS.map((p) => (
              <button key={p.id} onClick={() => { setSelected(p); setAgentRun(false); setRecommendation(null); }} className="w-full text-left flex items-center justify-between rounded-[4px] border p-3.5 transition-colors" style={{ borderColor: selected.id === p.id ? "var(--rzp-blue)" : "var(--rzp-border)", background: selected.id === p.id ? "var(--rzp-blue-tint)" : "white" }}>
                <div>
                  <div className="font-semibold text-sm" style={{ color: "var(--rzp-navy)" }}>{p.name}</div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--rzp-muted)" }}>{p.blurb}</div>
                </div>
                <div className="font-semibold text-sm mono">{formatINR(p.price)}</div>
              </button>
            ))}
          </div>

          <div className="mt-5">
            <label className="text-xs font-medium block mb-1" style={{ color: "var(--rzp-muted)" }}>Customer name</label>
            <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} className="w-full border rounded-[4px] px-3 py-2 text-sm outline-none" style={{ borderColor: "var(--rzp-border)" }} />
          </div>

          <Divider />
          <Button onClick={() => void runGrowthAgent()} variant="secondary" className="w-full mt-4" disabled={recommending || !backendConnected}><Sparkles size={15} /> {recommending ? "Growth Agent running…" : "Run Growth Agent"}</Button>

          {agentRun && selected.addon && (
            <div className="mt-4 rise-in rounded-[4px] p-3.5 border flex gap-3" style={{ borderColor: "var(--rzp-blue)", background: "var(--rzp-blue-tint)" }}>
              <Bot size={18} className="shrink-0 mt-0.5" style={{ color: "var(--rzp-blue-dark)" }} />
              <div>
                <div className="text-sm font-semibold" style={{ color: "var(--rzp-navy)" }}>catalog-rules-v1 recommends: {selected.addon.name}</div>
                <p className="text-xs mt-1" style={{ color: "var(--rzp-muted)" }}>{recommendation?.reasoning ?? "Compatible add-on selected from the merchant demo catalog."} No fabricated model call or conversion statistic is shown.</p>
                <label className="flex items-center gap-2 mt-2 text-xs font-medium" style={{ color: "var(--rzp-navy)" }}>
                  <input type="checkbox" checked={includeAddon} onChange={(e) => setIncludeAddon(e.target.checked)} /> Include {selected.addon.name} (+{formatINR(selected.addon.price)})
                </label>
              </div>
            </div>
          )}
        </Card>

        <Card>
          <SectionLabel>Cart</SectionLabel>
          <div className="flex items-center gap-2 text-sm font-semibold mb-3" style={{ color: "var(--rzp-navy)" }}><ShoppingCart size={16} /> Checkout summary</div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span style={{ color: "var(--rzp-muted)" }}>{selected.name}</span><span className="mono">{formatINR(selected.price)}</span></div>
            {includeAddon && selected.addon && agentRun && <div className="flex justify-between rise-in"><span style={{ color: "var(--rzp-muted)" }}>{selected.addon.name}</span><span className="mono">{formatINR(selected.addon.price)}</span></div>}
          </div>
          <Divider />
          <div className="flex justify-between font-bold text-base mt-3"><span style={{ color: "var(--rzp-navy)" }}>Total</span><span className="mono">{formatINR(total)}</span></div>
          <Button onClick={() => void proceedToCheckout()} className="w-full mt-5" disabled={submitting || !backendConnected}>{submitting ? "Creating backend transaction…" : "Create checkout"} <ArrowRight size={15} /></Button>
        </Card>
      </div>
    </div>
  );
}
