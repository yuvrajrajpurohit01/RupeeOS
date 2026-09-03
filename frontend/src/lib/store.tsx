"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, post } from "./api";
import { Product } from "./catalog";
import { openRazorpayCheckout } from "./razorpayCheckout";
import {
  AgentRunRecord,
  AgentManifest,
  AuditEntry,
  CheckoutOrder,
  CommandMetrics,
  GrowthRecommendation,
  ManualReview,
  PolicyDecision,
  RecoveryBatchEvaluation,
  SystemStatus,
  Transaction,
  WorkflowRun,
} from "./types";

interface StoreState {
  transactions: Transaction[];
  policyDecisions: PolicyDecision[];
  agentRuns: AgentRunRecord[];
  agentManifests: AgentManifest[];
  workflowRuns: WorkflowRun[];
  manualReviews: ManualReview[];
  audit: AuditEntry[];
  systemStatus: SystemStatus;
  metrics: CommandMetrics | null;
  evaluation: RecoveryBatchEvaluation | null;
  activeMoneyId: string | null;
  loading: boolean;
  backendConnected: boolean;
  lastError: string | null;
}

interface StoreApi extends StoreState {
  activeTransaction: Transaction | null;
  getTransaction: (id: string) => Transaction | undefined;
  getPolicyDecisions: (id: string) => PolicyDecision[];
  getAgentRuns: (id: string) => AgentRunRecord[];
  refreshAll: () => Promise<void>;
  startCheckout: (product: Product, includeAddon: boolean, customerName: string) => Promise<string>;
  recommendGrowth: (product: Product) => Promise<GrowthRecommendation>;
  runRisk: (moneyId: string) => Promise<void>;
  pay: (moneyId: string) => Promise<void>;
  runRecovery: (moneyId: string) => Promise<void>;
  reconcileAll: () => Promise<void>;
  approveReview: (reviewId: string) => Promise<void>;
  rejectReview: (reviewId: string) => Promise<void>;
  simulateFailureSpike: () => Promise<void>;
  resetCircuitBreaker: () => Promise<void>;
  runEvaluation: () => Promise<void>;
}

const StoreContext = createContext<StoreApi | null>(null);

const EMPTY_STATUS: SystemStatus = {
  circuit_breaker_tripped: false,
  failure_rate: 0,
  reason: "Connecting to backend…",
};

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<StoreState>({
    transactions: [],
    policyDecisions: [],
    agentRuns: [],
    agentManifests: [],
    workflowRuns: [],
    manualReviews: [],
    audit: [],
    systemStatus: EMPTY_STATUS,
    metrics: null,
    evaluation: null,
    activeMoneyId: null,
    loading: true,
    backendConnected: false,
    lastError: null,
  });

  const refreshAll = useCallback(async () => {
    try {
      const [tx, policy, runs, reviews, auditLog, status, metrics, manifests, workflows] = await Promise.all([
        api<{ transactions: Transaction[] }>("/transactions?limit=200"),
        api<{ decisions: PolicyDecision[] }>("/policy-decisions"),
        api<{ runs: AgentRunRecord[] }>("/agent-runs"),
        api<{ reviews: ManualReview[] }>("/manual-reviews?status=PENDING"),
        api<{ entries: AuditEntry[] }>("/audit?limit=500"),
        api<SystemStatus>("/system/status"),
        api<CommandMetrics>("/command-center/metrics"),
        api<{ agents: AgentManifest[] }>("/agentic/agents"),
        api<{ runs: WorkflowRun[] }>("/agentic/runs?limit=100"),
      ]);
      setState((prev) => ({
        ...prev,
        transactions: tx.transactions,
        policyDecisions: policy.decisions,
        agentRuns: runs.runs,
        agentManifests: manifests.agents,
        workflowRuns: workflows.runs,
        manualReviews: reviews.reviews,
        audit: auditLog.entries,
        systemStatus: status,
        metrics,
        loading: false,
        backendConnected: true,
        lastError: null,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Backend request failed";
      setState((prev) => ({ ...prev, loading: false, backendConnected: false, lastError: message }));
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refreshAll(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshAll]);

  const pollTransaction = useCallback(async (moneyId: string, tries = 6) => {
    for (let i = 0; i < tries; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 800));
      try {
        const txn = await api<Transaction>(`/transactions/${moneyId}`);
        setState((prev) => ({
          ...prev,
          transactions: prev.transactions.some((t) => t.money_id === moneyId)
            ? prev.transactions.map((t) => (t.money_id === moneyId ? txn : t))
            : [txn, ...prev.transactions],
        }));
        if (!["PAYMENT_INITIATED", "RECOVERY_EXECUTED"].includes(txn.state)) break;
      } catch {
        break;
      }
    }
    await refreshAll();
  }, [refreshAll]);

  const verifyCheckout = useCallback(async (moneyId: string, response: { razorpay_payment_id: string; razorpay_signature: string }) => {
    await post(`/transactions/${moneyId}/payment/verify`, response);
  }, []);

  const openCheckout = useCallback(async (order: CheckoutOrder, customerName: string) => {
    const outcome = await openRazorpayCheckout(order, customerName, async (response) => {
      await verifyCheckout(order.money_id, response);
    });
    await pollTransaction(order.money_id, outcome === "success" ? 4 : 7);
  }, [pollTransaction, verifyCheckout]);

  const startCheckout = useCallback(async (product: Product, includeAddon: boolean, customerName: string) => {
    const addon = includeAddon ? product.addon : undefined;
    const amount = product.price + (addon?.price ?? 0);
    const customerId = `cust_${customerName.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "demo"}_${Date.now().toString().slice(-6)}`;
    const txn = await post<Transaction>("/transactions", {
      customer_id: customerId,
      customer_name: customerName || "Demo customer",
      amount,
      currency: "INR",
      product_name: product.name,
      addon_name: addon?.name,
    });
    const checkedOut = await post<Transaction>(`/transactions/${txn.money_id}/checkout`, {
      cart: { product_name: product.name, addon_name: addon?.name, amount },
    });
    setState((prev) => ({ ...prev, activeMoneyId: checkedOut.money_id }));
    await refreshAll();
    return checkedOut.money_id;
  }, [refreshAll]);

  const recommendGrowth = useCallback(async (product: Product) => {
    const result = await post<GrowthRecommendation>("/growth/recommend", {
      query: product.name,
      budget: product.price + (product.addon?.price ?? 0),
    });
    await refreshAll();
    return result;
  }, [refreshAll]);

  const runRisk = useCallback(async (moneyId: string) => {
    await post("/agentic/runs", {
      money_id: moneyId,
      goal: "ASSESS_AND_ROUTE_PAYMENT",
      max_steps: 4,
      execute_external_actions: false,
    });
    await refreshAll();
  }, [refreshAll]);

  const pay = useCallback(async (moneyId: string) => {
    try {
      const txn = await api<Transaction>(`/transactions/${moneyId}`);
      const order = await post<CheckoutOrder>(`/transactions/${moneyId}/pay`);
      await openCheckout(order, txn.customer_name);
    } finally {
      await refreshAll();
    }
  }, [openCheckout, refreshAll]);

  const runRecovery = useCallback(async (moneyId: string) => {
    try {
      const response = await post<{
        run: WorkflowRun;
        pending_checkout?: CheckoutOrder | null;
      }>("/agentic/runs", {
        money_id: moneyId,
        goal: "RECOVER_FAILED_PAYMENT",
        max_steps: 4,
        execute_external_actions: true,
      });
      if (response.pending_checkout) {
        const transaction = await api<Transaction>(`/transactions/${moneyId}`);
        await openCheckout(response.pending_checkout, transaction.customer_name);
      }
    } finally {
      await refreshAll();
    }
  }, [openCheckout, refreshAll]);

  const reconcileAll = useCallback(async () => {
    const fresh = await api<{ transactions: Transaction[] }>("/transactions?state=SETTLEMENT_PENDING&limit=200");
    if (fresh.transactions.length === 0) return;
    await post("/reconciliation/run", {
      batch_id: `settlement_${Date.now()}`,
      settlement_records: fresh.transactions.map((t) => ({
        money_id: t.money_id,
        expected_amount: t.amount,
        received_amount: t.amount,
      })),
    });
    await refreshAll();
  }, [refreshAll]);

  const approveReview = useCallback(async (reviewId: string) => {
    try {
      const response = await post<{ transaction: Transaction; checkout?: CheckoutOrder | null }>(`/manual-reviews/${reviewId}/approve`, {
        resolved_by: "buildathon_operator",
      });
      if (response.checkout) await openCheckout(response.checkout, response.transaction.customer_name);
    } finally {
      await refreshAll();
    }
  }, [openCheckout, refreshAll]);

  const rejectReview = useCallback(async (reviewId: string) => {
    await post(`/manual-reviews/${reviewId}/reject`, { resolved_by: "buildathon_operator" });
    await refreshAll();
  }, [refreshAll]);

  const simulateFailureSpike = useCallback(async () => {
    await post("/system/demo/failure-spike");
    await refreshAll();
  }, [refreshAll]);

  const resetCircuitBreaker = useCallback(async () => {
    await post("/system/demo/reset-spike");
    await refreshAll();
  }, [refreshAll]);

  const runEvaluation = useCallback(async () => {
    const evaluation = await post<RecoveryBatchEvaluation>("/evaluation/recovery-batch", { size: 250, seed: 42 });
    setState((prev) => ({ ...prev, evaluation }));
  }, []);

  const activeTransaction = useMemo(
    () => state.transactions.find((t) => t.money_id === state.activeMoneyId) ?? state.transactions[0] ?? null,
    [state.transactions, state.activeMoneyId]
  );

  const value: StoreApi = {
    ...state,
    activeTransaction,
    getTransaction: (id) => state.transactions.find((t) => t.money_id === id),
    getPolicyDecisions: (id) => state.policyDecisions.filter((p) => p.money_id === id),
    getAgentRuns: (id) => state.agentRuns.filter((r) => r.money_id === id),
    refreshAll,
    startCheckout,
    recommendGrowth,
    runRisk,
    pay,
    runRecovery,
    reconcileAll,
    approveReview,
    rejectReview,
    simulateFailureSpike,
    resetCircuitBreaker,
    runEvaluation,
  };

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): StoreApi {
  const value = useContext(StoreContext);
  if (!value) throw new Error("useStore must be used inside StoreProvider");
  return value;
}
