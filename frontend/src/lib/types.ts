export type MoneyState =
  | "DISCOVERED"
  | "CHECKOUT_CREATED"
  | "RISK_ANALYZED"
  | "MANUAL_REVIEW"
  | "PAYMENT_INITIATED"
  | "PAYMENT_SUCCESS"
  | "PAYMENT_FAILED"
  | "RECOVERY_ANALYZED"
  | "RECOVERY_EXECUTED"
  | "RECOVERED"
  | "LOST"
  | "SETTLEMENT_PENDING"
  | "RECONCILED"
  | "EXCEPTION";

export interface StateTransition {
  previous_state?: MoneyState | null;
  new_state: MoneyState;
  triggering_agent: string;
  reason: string;
  timestamp: string;
}

export interface Transaction {
  money_id: string;
  customer_id: string;
  customer_name: string;
  amount: number;
  currency: string;
  state: MoneyState;
  product_name?: string | null;
  addon_name?: string | null;
  razorpay_order_id?: string | null;
  razorpay_payment_id?: string | null;
  risk_score?: number | null;
  risk_decision?: "ALLOW" | "VERIFY" | "HOLD" | null;
  risk_factors: Array<{ signal: string; weight: number; detail: string }>;
  failure_reason?: string | null;
  recovery_probability?: number | null;
  recovery_explanation?: string | null;
  recovery_attempts: number;
  settlement_amount?: number | null;
  reconciliation_status?: "MATCHED" | "FEE_ADJUSTED_MATCH" | "EXCEPTION" | null;
  history: StateTransition[];
  created_at: string;
  updated_at: string;
}

export interface PolicyDecision {
  money_id: string;
  approved: boolean;
  reason: string;
  action: string;
  timestamp: string;
}

export interface AgentRunRecord {
  money_id: string;
  agent: string;
  engine: string;
  mode: string;
  latency_ms: number;
  confidence?: number | null;
  summary: string;
  timestamp: string;
}

export interface ManualReview {
  review_id: string;
  money_id: string;
  review_type: "RISK" | "RECOVERY" | string;
  proposed_action: string;
  reason: string;
  status: "PENDING" | "APPROVED" | "REJECTED" | string;
  created_at: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
}

export interface AuditEntry {
  money_id: string;
  actor: string;
  action: string;
  detail: Record<string, unknown>;
  previous_hash: string;
  entry_hash: string;
  timestamp: string;
}

export interface SystemStatus {
  circuit_breaker_tripped: boolean;
  failure_rate: number;
  reason?: string;
  razorpay_configured?: boolean;
  storage?: string;
  agentic_runtime?: string;
  ai?: {
    enabled: boolean;
    configured: boolean;
    active: boolean;
    provider: string;
    model: string;
    mode: string;
    authority: string;
  };
}

export interface AgentManifest {
  name: string;
  role: string;
  engine: string;
  mode: string;
  capabilities: string[];
  allowed_actions: string[];
  guardrails: string[];
}

export interface GrowthRecommendation {
  intent: string;
  recommended_products: Array<{ product_id: string; name: string; price: number }>;
  reasoning: string;
  upsell: Array<{ product_id: string; name: string; price: number }>;
  estimated_cart_value: number;
}

export interface WorkflowStep {
  sequence: number;
  agent: string;
  observation: string;
  reasoning: string;
  recommendation: string;
  action: string;
  outcome: string;
  status: "COMPLETED" | "PAUSED" | "FAILED";
  confidence?: number | null;
  evidence: Record<string, unknown>;
  policy_decision?: { approved: boolean; action: string; reason: string } | null;
  started_at: string;
  completed_at: string;
}

export interface WorkflowRun {
  run_id: string;
  money_id: string;
  goal: string;
  status: "RUNNING" | "PAUSED" | "COMPLETED" | "FAILED" | "BUDGET_EXHAUSTED";
  current_agent?: string | null;
  stop_reason?: string | null;
  max_steps: number;
  steps_used: number;
  execute_external_actions: boolean;
  steps: WorkflowStep[];
  pending_checkout?: CheckoutOrder | null;
  created_at: string;
  updated_at: string;
}

export interface CheckoutOrder {
  money_id: string;
  razorpay_order_id: string;
  amount: number;
  amount_subunits: number;
  currency: string;
  key: string;
  name: string;
  description: string;
}

export interface CommandMetrics {
  revenue_processed: number;
  revenue_recovered: number;
  amount_at_risk: number;
  reconciled: number;
  exceptions: number;
  policy_decisions: number;
  policy_rejections: number;
  agent_runs: number;
  pending_manual_reviews: number;
  circuit_breaker: { tripped: boolean; failure_rate: number; reason: string };
}

export interface RecoveryBatchEvaluation {
  records: number;
  failed_revenue: number;
  eligible_revenue: number;
  recovery_attempts: number;
  recovered_count: number;
  recovered_revenue: number;
  recovery_rate: number;
  policy_blocks: number;
  manual_escalations: number;
  seed: number;
  note: string;
}
