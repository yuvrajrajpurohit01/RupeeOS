"""RupeeOS FastAPI backend.

Run from backend/: uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
import os
import random
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from agents import finance_agent, growth_agent, recovery_agent, risk_agent
from models.api import (
    AgenticResumeRequest,
    AgenticRunRequest,
    CheckoutRequest,
    CreateTransactionRequest,
    EvaluationRequest,
    GrowthRecommendRequest,
    ReconciliationRequest,
    ResolveReviewRequest,
    RiskAnalyzeRequest,
    VerifyPaymentRequest,
)
from models.money_state import MoneyState
from services import policy_engine, razorpay_service
from services.agent_supervisor import agent_supervisor
from services.audit_service import audit_log
from services.clock import utc_now
from services.llm_reasoning import llm_reasoning
from services.database import (
    ReconciliationBatchRow,
    SessionLocal,
    TransactionRow,
    WebhookEventRow,
    init_db,
)
from services.orchestrator import InvalidTransitionError, orchestrator

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RupeeOS API",
    version="4.1.0",
    description="Policy-constrained multi-agent money lifecycle orchestration for Razorpay Test Mode.",
    lifespan=lifespan,
)

allowed_origins = [x.strip() for x in os.getenv("RUPEEOS_CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-RupeeOS-Request-ID", "X-Razorpay-Signature", "x-razorpay-event-id"],
)


@app.exception_handler(InvalidTransitionError)
async def invalid_transition_handler(_request: Request, exc: InvalidTransitionError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=409, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Growth / catalog recommendation
# ---------------------------------------------------------------------------

@app.post("/growth/recommend")
def growth_recommend(body: GrowthRecommendRequest):
    started = time.perf_counter()
    result = growth_agent.recommend(body.query, body.budget)
    money_id = body.money_id or "growth_preview"
    orchestrator.record_agent_run(
        money_id,
        "growth",
        started,
        result.get("reasoning", "Catalog recommendation completed"),
        engine="catalog-rules-v1",
        mode="deterministic",
    )
    return result


# ---------------------------------------------------------------------------
# Transactions / Money State Graph
# ---------------------------------------------------------------------------

@app.post("/transactions", status_code=201)
def create_transaction(body: CreateTransactionRequest):
    return orchestrator.create_transaction(
        customer_id=body.customer_id,
        customer_name=body.customer_name,
        amount=body.amount,
        currency=body.currency,
        product_name=body.product_name,
        addon_name=body.addon_name,
    )


@app.get("/transactions")
def list_transactions(
    state: Optional[MoneyState] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    txns = orchestrator.list_transactions(state)
    return {"transactions": txns[offset : offset + limit], "total": len(txns)}


@app.get("/transactions/{money_id}")
def get_transaction(money_id: str):
    txn = orchestrator.get_transaction(money_id)
    if not txn:
        raise HTTPException(404, f"No transaction {money_id}")
    return txn


@app.post("/transactions/{money_id}/checkout")
def checkout(money_id: str, body: CheckoutRequest | None = None):
    txn = orchestrator.get_transaction(money_id)
    if not txn:
        raise HTTPException(404, f"No transaction {money_id}")
    txn = orchestrator.apply_transition(money_id, MoneyState.CHECKOUT_CREATED, "growth_agent", "Cart finalized by customer")
    audit_log.record(money_id, "growth_agent", "CART_CREATED", {"cart": body.cart if body else {}})
    return txn


@app.post("/transactions/{money_id}/risk-analyze")
def risk_analyze(money_id: str, body: RiskAnalyzeRequest | None = None):
    txn = orchestrator.get_transaction(money_id)
    if not txn:
        raise HTTPException(404, f"No transaction {money_id}")
    if txn.state != MoneyState.CHECKOUT_CREATED:
        raise HTTPException(409, f"Risk analysis requires CHECKOUT_CREATED; current state is {txn.state.value}")

    started = time.perf_counter()
    customer_history = body.customer_history.model_dump() if body else {}
    result = risk_agent.analyze(txn.amount, customer_history)
    orchestrator.update_fields(
        money_id,
        risk_score=result["risk_score"],
        risk_decision=result["risk_decision"],
        risk_factors=result["factors"],
    )
    orchestrator.record_agent_run(
        money_id,
        "risk",
        started,
        f"Risk {result['risk_score']:.2f} -> {result['risk_decision']}",
        confidence=result["confidence"],
    )

    cb = orchestrator.circuit_breaker_status()
    decision = policy_engine.approve_risk_action(result["risk_decision"], cb["tripped"])
    record = orchestrator.record_policy_decision(money_id, decision)

    if decision.action == "INITIATE_PAYMENT" and decision.approved:
        orchestrator.apply_transition(money_id, MoneyState.RISK_ANALYZED, "policy_engine", decision.reason)
    elif decision.action == "MANUAL_REVIEW":
        orchestrator.apply_transition(money_id, MoneyState.MANUAL_REVIEW, "policy_engine", decision.reason)
        orchestrator.create_manual_review(money_id, "RISK", "INITIATE_PAYMENT", decision.reason)
    else:
        orchestrator.apply_transition(money_id, MoneyState.EXCEPTION, "policy_engine", decision.reason)

    audit_log.record(money_id, "risk_agent", "RISK_ANALYZED", result)
    return {"transaction": orchestrator.get_transaction(money_id), "risk_analysis": result, "policy_decision": record}


@app.post("/transactions/{money_id}/pay")
def initiate_payment(money_id: str):
    txn = orchestrator.get_transaction(money_id)
    if not txn:
        raise HTTPException(404, f"No transaction {money_id}")
    if txn.state != MoneyState.RISK_ANALYZED:
        raise HTTPException(409, f"Payment is policy-gated; current state is {txn.state.value}")

    cb = orchestrator.circuit_breaker_status()
    if cb["tripped"]:
        decision = policy_engine.PolicyDecision(False, cb["reason"], "MANUAL_REVIEW")
        orchestrator.record_policy_decision(money_id, decision)
        orchestrator.apply_transition(money_id, MoneyState.MANUAL_REVIEW, "policy_engine", decision.reason)
        review = orchestrator.create_manual_review(money_id, "RISK", "INITIATE_PAYMENT", decision.reason)
        raise HTTPException(409, f"Circuit breaker requires manual review {review.review_id}")

    try:
        order = razorpay_service.create_order(txn.amount, receipt=money_id, notes={"money_id": money_id, "kind": "PRIMARY"})
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc

    orchestrator.create_payment_attempt(money_id, order["razorpay_order_id"], "PRIMARY")
    orchestrator.apply_transition(money_id, MoneyState.PAYMENT_INITIATED, "orchestrator", "Razorpay Test Mode order created")
    audit_log.record(money_id, "razorpay_service", "ORDER_CREATED", {"razorpay_order_id": order["razorpay_order_id"], "kind": "PRIMARY"})
    return {**order, "money_id": money_id, "name": "RupeeOS Demo", "description": txn.product_name or "RupeeOS transaction"}


@app.post("/transactions/{money_id}/payment/verify")
def verify_checkout_payment(money_id: str, body: VerifyPaymentRequest):
    txn = orchestrator.get_transaction(money_id)
    if not txn:
        raise HTTPException(404, f"No transaction {money_id}")

    payment_id = body.razorpay_payment_id
    signature = body.razorpay_signature
    if not payment_id or not signature or not txn.razorpay_order_id:
        raise HTTPException(422, "razorpay_payment_id and razorpay_signature are required")

    if not razorpay_service.verify_payment_signature(txn.razorpay_order_id, payment_id, signature):
        audit_log.record(money_id, "razorpay_service", "PAYMENT_SIGNATURE_REJECTED", {"payment_id": payment_id})
        raise HTTPException(400, "Invalid Razorpay payment signature")

    orchestrator.mark_attempt(txn.razorpay_order_id, "SIGNATURE_VERIFIED", payment_id)
    orchestrator.update_fields(money_id, razorpay_payment_id=payment_id)
    audit_log.record(money_id, "razorpay_service", "PAYMENT_SIGNATURE_VERIFIED", {"payment_id": payment_id})

    status = "signature_verified"
    try:
        payment = razorpay_service.fetch_payment(payment_id)
        status = payment.get("status", status)
        if status == "captured":
            orchestrator.mark_payment_captured(money_id, payment_id, txn.razorpay_order_id, "checkout_verifier")
    except Exception as exc:  # webhook remains authoritative if status fetch is temporarily unavailable
        audit_log.record(money_id, "razorpay_service", "PAYMENT_STATUS_FETCH_DEFERRED", {"error": type(exc).__name__})

    return {"verified": True, "payment_status": status, "transaction": orchestrator.get_transaction(money_id)}


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------

@app.post("/transactions/{money_id}/recover")
def recover(money_id: str):
    txn = orchestrator.get_transaction(money_id)
    if not txn:
        raise HTTPException(404, f"No transaction {money_id}")
    if txn.state not in (MoneyState.PAYMENT_FAILED, MoneyState.RECOVERY_ANALYZED):
        raise HTTPException(409, f"Recovery requires PAYMENT_FAILED/RECOVERY_ANALYZED; current state is {txn.state.value}")

    started = time.perf_counter()
    analysis = recovery_agent.analyze(txn.failure_reason or "unknown", txn.amount, txn.recovery_attempts)
    orchestrator.update_fields(
        money_id,
        recovery_probability=analysis["recovery_probability"],
        recovery_explanation=analysis["explanation"],
    )
    if txn.state == MoneyState.PAYMENT_FAILED:
        orchestrator.apply_transition(money_id, MoneyState.RECOVERY_ANALYZED, "recovery_agent", analysis["explanation"])
    orchestrator.record_agent_run(
        money_id,
        "recovery",
        started,
        f"{analysis['recommended_action']} at P={analysis['recovery_probability']:.2f}",
        confidence=analysis["confidence"],
    )

    cb = orchestrator.circuit_breaker_status()
    decision = policy_engine.approve_recovery(
        action=analysis["recommended_action"],
        attempts=txn.recovery_attempts,
        recovery_probability=analysis["recovery_probability"],
        amount=txn.amount,
        circuit_breaker_tripped=cb["tripped"],
    )
    record = orchestrator.record_policy_decision(money_id, decision)
    checkout = None

    if decision.approved and decision.action == "RETRY_NOW":
        try:
            order = razorpay_service.create_order(
                txn.amount,
                receipt=f"{money_id}-r{txn.recovery_attempts + 1}",
                notes={"money_id": money_id, "kind": "RECOVERY"},
            )
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        orchestrator.update_fields(money_id, recovery_attempts=txn.recovery_attempts + 1)
        orchestrator.create_payment_attempt(money_id, order["razorpay_order_id"], "RECOVERY")
        orchestrator.apply_transition(money_id, MoneyState.RECOVERY_EXECUTED, "orchestrator", decision.reason)
        checkout = {**order, "money_id": money_id, "name": "RupeeOS Recovery", "description": "Recovery payment attempt"}
    elif decision.action == "MANUAL_REVIEW":
        orchestrator.apply_transition(money_id, MoneyState.MANUAL_REVIEW, "policy_engine", decision.reason)
        review = orchestrator.create_manual_review(money_id, "RECOVERY", analysis["recommended_action"], decision.reason)
        return {
            "transaction": orchestrator.get_transaction(money_id),
            "recovery_analysis": analysis,
            "policy_decision": record,
            "manual_review": review,
            "checkout": None,
        }
    else:
        orchestrator.apply_transition(money_id, MoneyState.LOST, "policy_engine", decision.reason)

    return {
        "transaction": orchestrator.get_transaction(money_id),
        "recovery_analysis": analysis,
        "policy_decision": record,
        "checkout": checkout,
    }


# ---------------------------------------------------------------------------
# Human approval inbox
# ---------------------------------------------------------------------------

@app.get("/manual-reviews")
def manual_reviews(status: Optional[str] = "PENDING"):
    return {"reviews": orchestrator.list_manual_reviews(status)}


@app.post("/manual-reviews/{review_id}/approve")
def approve_manual_review(review_id: str, body: ResolveReviewRequest | None = None):
    review = orchestrator.get_manual_review(review_id)
    if not review:
        raise HTTPException(404, "Manual review not found")
    if review.status != "PENDING":
        return {"review": review, "transaction": orchestrator.get_transaction(review.money_id)}

    txn = orchestrator.get_transaction(review.money_id)
    if not txn:
        raise HTTPException(404, "Transaction not found")

    checkout = None
    resolved_by = body.resolved_by if body else "demo_operator"

    if review.review_type == "RISK":
        if txn.state != MoneyState.MANUAL_REVIEW:
            raise HTTPException(409, f"Transaction is in {txn.state.value}")
        orchestrator.record_policy_decision(review.money_id, policy_engine.PolicyDecision(True, "Human reviewer approved payment initiation", "INITIATE_PAYMENT"))
        orchestrator.apply_transition(review.money_id, MoneyState.RISK_ANALYZED, "human_reviewer", "Manual risk review approved")
    elif review.review_type == "RECOVERY":
        if txn.state != MoneyState.MANUAL_REVIEW:
            raise HTTPException(409, f"Transaction is in {txn.state.value}")
        try:
            order = razorpay_service.create_order(
                txn.amount,
                receipt=f"{txn.money_id}-hr{txn.recovery_attempts + 1}",
                notes={"money_id": txn.money_id, "kind": "RECOVERY_MANUAL"},
            )
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        orchestrator.record_policy_decision(review.money_id, policy_engine.PolicyDecision(True, "Human reviewer approved recovery retry", "RETRY_NOW"))
        orchestrator.update_fields(txn.money_id, recovery_attempts=txn.recovery_attempts + 1)
        orchestrator.create_payment_attempt(txn.money_id, order["razorpay_order_id"], "RECOVERY_MANUAL")
        orchestrator.apply_transition(txn.money_id, MoneyState.RECOVERY_EXECUTED, "human_reviewer", "Manual recovery retry approved")
        checkout = {**order, "money_id": txn.money_id, "name": "RupeeOS Recovery", "description": "Human-approved recovery attempt"}

    resolved = orchestrator.resolve_manual_review(review_id, True, resolved_by)
    return {"review": resolved, "transaction": orchestrator.get_transaction(review.money_id), "checkout": checkout}


@app.post("/manual-reviews/{review_id}/reject")
def reject_manual_review(review_id: str, body: ResolveReviewRequest | None = None):
    review = orchestrator.get_manual_review(review_id)
    if not review:
        raise HTTPException(404, "Manual review not found")
    if review.status != "PENDING":
        return {"review": review, "transaction": orchestrator.get_transaction(review.money_id)}
    txn = orchestrator.get_transaction(review.money_id)
    resolved = orchestrator.resolve_manual_review(review_id, False, body.resolved_by if body else "demo_operator")
    target = MoneyState.LOST if review.review_type == "RECOVERY" else MoneyState.EXCEPTION
    if txn and txn.state == MoneyState.MANUAL_REVIEW:
        orchestrator.apply_transition(review.money_id, target, "human_reviewer", "Manual review rejected")
    return {"review": resolved, "transaction": orchestrator.get_transaction(review.money_id)}


# ---------------------------------------------------------------------------
# Audit / policy / decision telemetry
# ---------------------------------------------------------------------------

@app.get("/transactions/{money_id}/policy-decisions")
def transaction_policy_decisions(money_id: str):
    return orchestrator.get_policy_decisions(money_id)


@app.get("/policy-decisions")
def all_policy_decisions():
    return {"decisions": orchestrator.get_policy_decisions()}


@app.get("/transactions/{money_id}/audit")
def transaction_audit(money_id: str):
    return audit_log.for_transaction(money_id)


@app.get("/audit")
def all_audit(limit: int = Query(default=500, ge=1, le=2000)):
    return {"entries": audit_log.all(limit)}


@app.get("/audit/verify")
def verify_audit(money_id: Optional[str] = None):
    return audit_log.verify(money_id)


@app.get("/agent-runs")
def agent_runs(money_id: Optional[str] = None):
    return {"runs": orchestrator.get_agent_runs(money_id)}


# ---------------------------------------------------------------------------
# Durable agentic supervisor
# ---------------------------------------------------------------------------

@app.get("/agentic/agents")
def agent_manifests():
    return {"agents": agent_supervisor.manifests()}


@app.post("/agentic/runs", status_code=201)
def start_agentic_run(body: AgenticRunRequest):
    try:
        run = agent_supervisor.start(
            money_id=body.money_id,
            goal=body.goal,
            max_steps=body.max_steps,
            execute_external_actions=body.execute_external_actions,
        )
    except KeyError as exc:
        raise HTTPException(404, f"No transaction {body.money_id}") from exc
    return {"run": run, "pending_checkout": run.pending_checkout}


@app.get("/agentic/runs")
def list_agentic_runs(
    money_id: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    return {"runs": agent_supervisor.list(money_id, limit)}


@app.get("/agentic/runs/{run_id}")
def get_agentic_run(run_id: str):
    run = agent_supervisor.get(run_id)
    if not run:
        raise HTTPException(404, f"No agentic run {run_id}")
    return run


@app.post("/agentic/runs/{run_id}/resume")
def resume_agentic_run(run_id: str, body: AgenticResumeRequest | None = None):
    try:
        run = agent_supervisor.resume(
            run_id,
            max_steps=body.max_steps if body else None,
            execute_external_actions=body.execute_external_actions if body else None,
        )
    except KeyError as exc:
        raise HTTPException(404, f"No agentic run {run_id}") from exc
    return {"run": run, "pending_checkout": run.pending_checkout}


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

@app.post("/reconciliation/run")
def run_reconciliation(body: ReconciliationRequest):
    batch_id = body.batch_id or f"batch_{utc_now().strftime('%Y%m%d%H%M%S')}"
    records = [record.model_dump() for record in body.settlement_records]

    started = time.perf_counter()
    result = finance_agent.reconcile_batch(batch_id, records)
    with SessionLocal() as db:
        existing = db.get(ReconciliationBatchRow, batch_id)
        if existing:
            existing.result = result
        else:
            db.add(ReconciliationBatchRow(batch_id=batch_id, result=result))
        db.commit()

    for row in result["records"]:
        txn = orchestrator.get_transaction(row["money_id"])
        if not txn or txn.state != MoneyState.SETTLEMENT_PENDING:
            continue
        orchestrator.update_fields(
            txn.money_id,
            settlement_amount=row["received_amount"],
            reconciliation_status=row["status"],
        )
        if row["status"] == "EXCEPTION":
            orchestrator.apply_transition(txn.money_id, MoneyState.EXCEPTION, "finance_agent", "Settlement mismatch requires review")
        else:
            orchestrator.apply_transition(txn.money_id, MoneyState.RECONCILED, "finance_agent", f"Settlement {row['status'].lower()}")

    orchestrator.record_agent_run(
        batch_id,
        "finance",
        started,
        f"Reconciled {result['total_records']} records at {result['match_rate']:.1%} match rate",
        confidence=result["match_rate"],
    )
    audit_log.record(batch_id, "finance_agent", "RECONCILIATION_RUN", {"match_rate": result["match_rate"], "total_records": result["total_records"]})
    return result


@app.get("/reconciliation/batch")
def get_reconciliation(batch_id: str):
    with SessionLocal() as db:
        row = db.get(ReconciliationBatchRow, batch_id)
        if not row:
            raise HTTPException(404, f"No reconciliation batch {batch_id}")
        return row.result


# ---------------------------------------------------------------------------
# Evaluation and system controls
# ---------------------------------------------------------------------------

@app.post("/evaluation/recovery-batch")
def evaluate_recovery_batch(body: EvaluationRequest | None = None):
    """Deterministic synthetic benchmark; no money is moved and no DB state is mutated."""
    size = body.size if body else 250
    seed = body.seed if body else 42
    rng = random.Random(seed)
    failure_mix = [
        ("bank_timeout", 0.22),
        ("network_error", 0.18),
        ("otp_expired", 0.17),
        ("issuer_unavailable", 0.15),
        ("insufficient_funds", 0.13),
        ("card_declined", 0.10),
        ("unknown", 0.05),
    ]
    labels = [x[0] for x in failure_mix]
    weights = [x[1] for x in failure_mix]

    failed_revenue = eligible_revenue = recovered_revenue = 0.0
    attempted = blocked = manual = recovered_count = 0
    for _ in range(size):
        reason = rng.choices(labels, weights=weights, k=1)[0]
        amount = float(rng.choice([499, 999, 1499, 2499, 4999, 7999, 12999]))
        failed_revenue += amount
        analysis = recovery_agent.analyze(reason, amount, 0)
        decision = policy_engine.approve_recovery(
            analysis["recommended_action"], 0, analysis["recovery_probability"], amount, False
        )
        if analysis["recovery_probability"] >= policy_engine.MIN_RECOVERY_PROBABILITY:
            eligible_revenue += amount
        if decision.approved and decision.action == "RETRY_NOW":
            attempted += 1
            # Seeded outcome simulation for evaluation only, driven by the bounded probability.
            if rng.random() < analysis["recovery_probability"]:
                recovered_count += 1
                recovered_revenue += amount
        elif decision.action == "MANUAL_REVIEW":
            manual += 1
        else:
            blocked += 1

    return {
        "records": size,
        "failed_revenue": round(failed_revenue, 2),
        "eligible_revenue": round(eligible_revenue, 2),
        "recovery_attempts": attempted,
        "recovered_count": recovered_count,
        "recovered_revenue": round(recovered_revenue, 2),
        "recovery_rate": round(recovered_count / attempted, 4) if attempted else 0.0,
        "policy_blocks": blocked,
        "manual_escalations": manual,
        "seed": seed,
        "note": "Synthetic seeded evaluation only; it does not represent live merchant recovery performance.",
    }


@app.get("/system/status")
def system_status():
    cb = orchestrator.circuit_breaker_status()
    return {
        "circuit_breaker_tripped": cb["tripped"],
        "failure_rate": cb["failure_rate"],
        "reason": cb["reason"],
        "razorpay_configured": razorpay_service.is_configured(),
        "storage": "sqlite",
        "agentic_runtime": "durable-supervisor-v2-hybrid-ai",
        "ai": llm_reasoning.status(),
    }


@app.get("/ai/status")
def ai_status():
    """Expose configuration state without revealing the API key."""
    return llm_reasoning.status()


@app.get("/health/live")
def health_live():
    return {"status": "alive", "service": "rupeeos-api", "version": app.version}


@app.get("/health/ready")
def health_ready():
    from sqlalchemy import text

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, f"Database is not ready: {type(exc).__name__}") from exc
    return {"status": "ready", "database": "connected", "razorpay_configured": razorpay_service.is_configured(), "ai": llm_reasoning.status()}


@app.post("/system/demo/failure-spike")
def simulate_failure_spike():
    if os.getenv("RUPEEOS_DEMO_MODE", "true").lower() != "true":
        raise HTTPException(403, "Demo controls disabled")
    now = utc_now()
    with SessionLocal() as db:
        for i in range(6):
            money_id = f"demo_spike_{now.strftime('%H%M%S')}_{i}"
            db.add(
                TransactionRow(
                    money_id=money_id,
                    customer_id=f"demo_spike_{i}",
                    customer_name="Circuit breaker demo",
                    amount=5000 + i * 1000,
                    currency="INR",
                    state="EXCEPTION" if i < 5 else "LOST",
                    product_name="Synthetic failure spike",
                    history=[],
                    risk_factors=[],
                    created_at=now,
                    updated_at=now,
                )
            )
        db.commit()
    return system_status()


@app.post("/system/demo/reset-spike")
def reset_failure_spike():
    if os.getenv("RUPEEOS_DEMO_MODE", "true").lower() != "true":
        raise HTTPException(403, "Demo controls disabled")
    with SessionLocal() as db:
        db.query(TransactionRow).filter(TransactionRow.customer_id.like("demo_spike_%")).delete(synchronize_session=False)
        db.commit()
    return system_status()


@app.get("/command-center/metrics")
def command_center_metrics():
    txns = orchestrator.list_transactions()

    def visited(txn, state: MoneyState) -> bool:
        return txn.state == state or any(h.new_state == state for h in txn.history)

    captured = [t for t in txns if visited(t, MoneyState.PAYMENT_SUCCESS) or visited(t, MoneyState.RECOVERED)]
    recovered = [t for t in txns if visited(t, MoneyState.RECOVERED)]
    at_risk = [t for t in txns if t.state in (MoneyState.PAYMENT_FAILED, MoneyState.RECOVERY_ANALYZED, MoneyState.RECOVERY_EXECUTED, MoneyState.MANUAL_REVIEW)]
    decisions = orchestrator.get_policy_decisions()
    runs = orchestrator.get_agent_runs()
    cb = orchestrator.circuit_breaker_status()
    return {
        "revenue_processed": round(sum(t.amount for t in captured), 2),
        "revenue_recovered": round(sum(t.amount for t in recovered), 2),
        "amount_at_risk": round(sum(t.amount for t in at_risk), 2),
        "reconciled": sum(1 for t in txns if t.state == MoneyState.RECONCILED),
        "exceptions": sum(1 for t in txns if t.state == MoneyState.EXCEPTION),
        "policy_decisions": len(decisions),
        "policy_rejections": sum(1 for d in decisions if not d.approved),
        "agent_runs": len(runs),
        "pending_manual_reviews": len(orchestrator.list_manual_reviews("PENDING")),
        "circuit_breaker": cb,
    }


# ---------------------------------------------------------------------------
# Razorpay webhooks: raw-body verification + x-razorpay-event-id idempotency
# ---------------------------------------------------------------------------

@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        valid = razorpay_service.verify_webhook_signature(raw_body, signature)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not valid:
        raise HTTPException(400, "Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Webhook body is not valid JSON") from exc
    event = razorpay_service.parse_webhook_event(payload)
    event_id = request.headers.get("x-razorpay-event-id") or f"payload_{hashlib.sha256(raw_body).hexdigest()}"
    payload_hash = hashlib.sha256(raw_body).hexdigest()

    with SessionLocal() as db:
        existing = db.get(WebhookEventRow, event_id)
        if existing:
            return {"status": "duplicate_ignored", "event_id": event_id}
        db.add(
            WebhookEventRow(
                event_id=event_id,
                event_type=event["event"],
                payload_hash=payload_hash,
                status="RECEIVED",
            )
        )
        db.commit()

    txn = orchestrator.find_by_order_id(event.get("razorpay_order_id"))
    if not txn:
        with SessionLocal() as db:
            row = db.get(WebhookEventRow, event_id)
            row.status = "UNMATCHED"
            row.processed_at = utc_now()
            db.commit()
        # Return 2xx so a permanently unknown demo event is not retried forever.
        return {"status": "unmatched_ignored", "event_id": event_id}

    try:
        if event["event"] == "payment.captured":
            orchestrator.mark_payment_captured(
                txn.money_id,
                event.get("razorpay_payment_id"),
                event.get("razorpay_order_id"),
                "razorpay_webhook",
            )
        elif event["event"] == "payment.failed":
            orchestrator.mark_payment_failed(
                txn.money_id,
                event.get("error_reason") or "unknown",
                event.get("error_description") or "Razorpay payment failed",
                event.get("razorpay_order_id"),
                "razorpay_webhook",
            )
        else:
            audit_log.record(txn.money_id, "razorpay_webhook", "WEBHOOK_OBSERVED", event)

        audit_log.record(txn.money_id, "razorpay_webhook", event["event"] or "unknown", {**event, "event_id": event_id})
        with SessionLocal() as db:
            row = db.get(WebhookEventRow, event_id)
            row.money_id = txn.money_id
            row.status = "PROCESSED"
            row.processed_at = utc_now()
            db.commit()
        return {"status": "processed", "event_id": event_id}
    except InvalidTransitionError:
        # Webhook ordering is not guaranteed. A late event must not corrupt a newer money state.
        audit_log.record(txn.money_id, "razorpay_webhook", "OUT_OF_ORDER_EVENT_IGNORED", {**event, "event_id": event_id})
        with SessionLocal() as db:
            row = db.get(WebhookEventRow, event_id)
            row.money_id = txn.money_id
            row.status = "OUT_OF_ORDER_IGNORED"
            row.processed_at = utc_now()
            db.commit()
        return {"status": "out_of_order_ignored", "event_id": event_id}


@app.get("/")
def root():
    return {
        "service": "RupeeOS API",
        "status": "running",
        "version": app.version,
        "docs": "/docs",
        "health": "/health/ready",
        "agentic_runtime": "/agentic/agents",
    }
