"""Persistent Money State Graph orchestrator."""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Optional

from models.money_state import AgentRunRecord, ManualReview, MoneyState, PolicyDecisionRecord, StateTransition, Transaction
from services import policy_engine
from services.audit_service import audit_log
from services.clock import utc_now
from services.database import (
    AgentRunRow,
    ManualReviewRow,
    PaymentAttemptRow,
    PolicyDecisionRow,
    SessionLocal,
    TransactionRow,
)

VALID_TRANSITIONS: dict[MoneyState, set[MoneyState]] = {
    MoneyState.DISCOVERED: {MoneyState.CHECKOUT_CREATED},
    MoneyState.CHECKOUT_CREATED: {MoneyState.RISK_ANALYZED, MoneyState.MANUAL_REVIEW, MoneyState.EXCEPTION},
    MoneyState.MANUAL_REVIEW: {MoneyState.RISK_ANALYZED, MoneyState.RECOVERY_EXECUTED, MoneyState.EXCEPTION, MoneyState.LOST},
    MoneyState.RISK_ANALYZED: {MoneyState.PAYMENT_INITIATED, MoneyState.MANUAL_REVIEW, MoneyState.EXCEPTION},
    MoneyState.PAYMENT_INITIATED: {MoneyState.PAYMENT_SUCCESS, MoneyState.PAYMENT_FAILED},
    MoneyState.PAYMENT_FAILED: {MoneyState.RECOVERY_ANALYZED},
    MoneyState.RECOVERY_ANALYZED: {MoneyState.RECOVERY_EXECUTED, MoneyState.MANUAL_REVIEW, MoneyState.LOST},
    MoneyState.RECOVERY_EXECUTED: {MoneyState.RECOVERED, MoneyState.RECOVERY_ANALYZED},
    MoneyState.PAYMENT_SUCCESS: {MoneyState.SETTLEMENT_PENDING},
    MoneyState.RECOVERED: {MoneyState.SETTLEMENT_PENDING},
    MoneyState.SETTLEMENT_PENDING: {MoneyState.RECONCILED, MoneyState.EXCEPTION},
}


class InvalidTransitionError(Exception):
    pass


class Orchestrator:
    def create_transaction(
        self,
        customer_id: str,
        amount: float,
        currency: str = "INR",
        customer_name: str = "Customer",
        product_name: str | None = None,
        addon_name: str | None = None,
    ) -> Transaction:
        txn = Transaction(
            customer_id=customer_id,
            customer_name=customer_name,
            amount=amount,
            currency=currency,
            product_name=product_name,
            addon_name=addon_name,
        )
        with SessionLocal() as db:
            db.add(
                TransactionRow(
                    money_id=txn.money_id,
                    customer_id=txn.customer_id,
                    customer_name=txn.customer_name,
                    amount=txn.amount,
                    currency=txn.currency,
                    state=txn.state.value,
                    product_name=txn.product_name,
                    addon_name=txn.addon_name,
                    history=[],
                    risk_factors=[],
                    created_at=txn.created_at,
                    updated_at=txn.updated_at,
                )
            )
            db.commit()
        audit_log.record(txn.money_id, "orchestrator", "TRANSACTION_CREATED", {"amount": amount, "currency": currency})
        return txn

    def get_transaction(self, money_id: str) -> Optional[Transaction]:
        with SessionLocal() as db:
            row = db.get(TransactionRow, money_id)
            return self._row_to_txn(row) if row else None

    def list_transactions(self, state: Optional[MoneyState] = None) -> list[Transaction]:
        with SessionLocal() as db:
            q = db.query(TransactionRow)
            if state:
                q = q.filter(TransactionRow.state == state.value)
            rows = q.order_by(TransactionRow.updated_at.desc()).all()
            return [self._row_to_txn(r) for r in rows]

    def recent_transactions(self, n: int = 20) -> list[Transaction]:
        return self.list_transactions()[:n]

    def update_fields(self, money_id: str, **fields) -> Transaction:
        with SessionLocal() as db:
            row = db.get(TransactionRow, money_id)
            if not row:
                raise KeyError(f"No transaction with money_id={money_id}")
            for key, value in fields.items():
                if hasattr(row, key):
                    setattr(row, key, value.value if isinstance(value, MoneyState) else value)
            row.updated_at = utc_now()
            db.commit()
            db.refresh(row)
            return self._row_to_txn(row)

    def apply_transition(self, money_id: str, new_state: MoneyState, agent: str, reason: str) -> Transaction:
        with SessionLocal() as db:
            row = db.get(TransactionRow, money_id)
            if not row:
                raise KeyError(f"No transaction with money_id={money_id}")
            current = MoneyState(row.state)
            allowed = VALID_TRANSITIONS.get(current, set())
            if new_state not in allowed:
                raise InvalidTransitionError(f"{current.value} -> {new_state.value} is not valid; allowed={sorted(s.value for s in allowed)}")
            now = utc_now()
            history = list(row.history or [])
            transition = {
                "previous_state": current.value,
                "new_state": new_state.value,
                "triggering_agent": agent,
                "reason": reason,
                "timestamp": now.isoformat(),
            }
            history.append(transition)
            row.history = history
            row.state = new_state.value
            row.updated_at = now
            db.commit()
        audit_log.record(money_id, agent, "STATE_TRANSITION", {"from": current.value, "to": new_state.value, "reason": reason})
        return self.get_transaction(money_id)

    def record_policy_decision(self, money_id: str, decision: policy_engine.PolicyDecision) -> PolicyDecisionRecord:
        now = utc_now()
        with SessionLocal() as db:
            db.add(
                PolicyDecisionRow(
                    money_id=money_id,
                    approved=decision.approved,
                    reason=decision.reason,
                    action=decision.action,
                    timestamp=now,
                )
            )
            db.commit()
        audit_log.record(
            money_id,
            "policy_engine",
            "POLICY_DECISION",
            {"approved": decision.approved, "reason": decision.reason, "action": decision.action},
        )
        return PolicyDecisionRecord(money_id=money_id, approved=decision.approved, reason=decision.reason, action=decision.action, timestamp=now)

    def get_policy_decisions(self, money_id: str | None = None) -> list[PolicyDecisionRecord]:
        with SessionLocal() as db:
            q = db.query(PolicyDecisionRow)
            if money_id:
                q = q.filter(PolicyDecisionRow.money_id == money_id)
            rows = q.order_by(PolicyDecisionRow.timestamp.asc()).all()
            return [
                PolicyDecisionRecord(
                    money_id=r.money_id,
                    approved=r.approved,
                    reason=r.reason,
                    action=r.action,
                    timestamp=r.timestamp,
                )
                for r in rows
            ]

    def record_agent_run(
        self,
        money_id: str,
        agent: str,
        started_at: float,
        summary: str,
        confidence: float | None = None,
        engine: str = "rules-v1",
        mode: str = "deterministic",
    ) -> AgentRunRecord:
        latency_ms = max(1, int((time.perf_counter() - started_at) * 1000))
        now = utc_now()
        with SessionLocal() as db:
            db.add(
                AgentRunRow(
                    money_id=money_id,
                    agent=agent,
                    engine=engine,
                    mode=mode,
                    latency_ms=latency_ms,
                    confidence=confidence,
                    summary=summary,
                    timestamp=now,
                )
            )
            db.commit()
        return AgentRunRecord(
            money_id=money_id,
            agent=agent,
            engine=engine,
            mode=mode,
            latency_ms=latency_ms,
            confidence=confidence,
            summary=summary,
            timestamp=now,
        )

    def get_agent_runs(self, money_id: str | None = None) -> list[AgentRunRecord]:
        with SessionLocal() as db:
            q = db.query(AgentRunRow)
            if money_id:
                q = q.filter(AgentRunRow.money_id == money_id)
            rows = q.order_by(AgentRunRow.timestamp.asc()).all()
            return [
                AgentRunRecord(
                    money_id=r.money_id,
                    agent=r.agent,
                    engine=r.engine,
                    mode=r.mode,
                    latency_ms=r.latency_ms,
                    confidence=r.confidence,
                    summary=r.summary,
                    timestamp=r.timestamp,
                )
                for r in rows
            ]

    def create_payment_attempt(self, money_id: str, order_id: str, kind: str) -> None:
        with SessionLocal() as db:
            db.add(PaymentAttemptRow(money_id=money_id, razorpay_order_id=order_id, kind=kind, status="CREATED"))
            row = db.get(TransactionRow, money_id)
            if row:
                row.razorpay_order_id = order_id
                row.updated_at = utc_now()
            db.commit()

    def find_by_order_id(self, order_id: str | None) -> Optional[Transaction]:
        if not order_id:
            return None
        with SessionLocal() as db:
            attempt = db.query(PaymentAttemptRow).filter(PaymentAttemptRow.razorpay_order_id == order_id).first()
            if not attempt:
                return None
            row = db.get(TransactionRow, attempt.money_id)
            return self._row_to_txn(row) if row else None

    def mark_attempt(self, order_id: str, status: str, payment_id: str | None = None) -> None:
        with SessionLocal() as db:
            attempt = db.query(PaymentAttemptRow).filter(PaymentAttemptRow.razorpay_order_id == order_id).first()
            if attempt:
                attempt.status = status
                attempt.updated_at = utc_now()
                if payment_id:
                    attempt.razorpay_payment_id = payment_id
                db.commit()

    def mark_payment_captured(self, money_id: str, payment_id: str | None, order_id: str | None, source: str) -> Transaction:
        txn = self.get_transaction(money_id)
        if not txn:
            raise KeyError(money_id)
        if payment_id:
            self.update_fields(money_id, razorpay_payment_id=payment_id)
        if order_id:
            self.mark_attempt(order_id, "CAPTURED", payment_id)

        current = self.get_transaction(money_id).state
        if current == MoneyState.PAYMENT_INITIATED:
            self.apply_transition(money_id, MoneyState.PAYMENT_SUCCESS, source, "Razorpay payment captured")
            self.apply_transition(money_id, MoneyState.SETTLEMENT_PENDING, "orchestrator", "Captured payment awaiting settlement reconciliation")
        elif current == MoneyState.RECOVERY_EXECUTED:
            self.apply_transition(money_id, MoneyState.RECOVERED, source, "Recovery payment captured")
            self.apply_transition(money_id, MoneyState.SETTLEMENT_PENDING, "orchestrator", "Recovered payment awaiting settlement reconciliation")
        # Duplicate / out-of-order capture after the terminal success path is a no-op.
        return self.get_transaction(money_id)

    def mark_payment_failed(self, money_id: str, failure_reason: str, description: str, order_id: str | None, source: str) -> Transaction:
        txn = self.get_transaction(money_id)
        if not txn:
            raise KeyError(money_id)
        if order_id:
            self.mark_attempt(order_id, "FAILED")
        self.update_fields(money_id, failure_reason=failure_reason)
        current = self.get_transaction(money_id).state
        if current == MoneyState.PAYMENT_INITIATED:
            self.apply_transition(money_id, MoneyState.PAYMENT_FAILED, source, description or failure_reason)
        elif current == MoneyState.RECOVERY_EXECUTED:
            self.apply_transition(money_id, MoneyState.RECOVERY_ANALYZED, source, "Recovery retry failed; eligible for another bounded analysis")
        return self.get_transaction(money_id)

    def create_manual_review(self, money_id: str, review_type: str, proposed_action: str, reason: str) -> ManualReview:
        review_id = f"review_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        with SessionLocal() as db:
            row = ManualReviewRow(
                review_id=review_id,
                money_id=money_id,
                review_type=review_type,
                proposed_action=proposed_action,
                reason=reason,
                status="PENDING",
                created_at=now,
            )
            db.add(row)
            db.commit()
        audit_log.record(money_id, "policy_engine", "MANUAL_REVIEW_CREATED", {"review_id": review_id, "type": review_type, "reason": reason})
        return ManualReview(
            review_id=review_id,
            money_id=money_id,
            review_type=review_type,
            proposed_action=proposed_action,
            reason=reason,
            status="PENDING",
            created_at=now,
        )

    def list_manual_reviews(self, status: str | None = "PENDING") -> list[ManualReview]:
        with SessionLocal() as db:
            q = db.query(ManualReviewRow)
            if status:
                q = q.filter(ManualReviewRow.status == status)
            rows = q.order_by(ManualReviewRow.created_at.desc()).all()
            return [self._review_to_model(r) for r in rows]

    def get_manual_review(self, review_id: str) -> Optional[ManualReview]:
        with SessionLocal() as db:
            row = db.get(ManualReviewRow, review_id)
            return self._review_to_model(row) if row else None

    def resolve_manual_review(self, review_id: str, approved: bool, resolved_by: str = "demo_operator") -> ManualReview:
        with SessionLocal() as db:
            row = db.get(ManualReviewRow, review_id)
            if not row:
                raise KeyError(review_id)
            if row.status != "PENDING":
                return self._review_to_model(row)
            row.status = "APPROVED" if approved else "REJECTED"
            row.resolved_at = utc_now()
            row.resolved_by = resolved_by
            db.commit()
            model = self._review_to_model(row)
        audit_log.record(model.money_id, resolved_by, f"MANUAL_REVIEW_{model.status}", {"review_id": review_id, "type": model.review_type})
        return model

    def circuit_breaker_status(self) -> dict:
        return policy_engine.check_circuit_breaker(self.recent_transactions(20))

    @staticmethod
    def _row_to_txn(row: TransactionRow) -> Transaction:
        history = []
        for h in row.history or []:
            history.append(
                StateTransition(
                    previous_state=MoneyState(h["previous_state"]) if h.get("previous_state") else None,
                    new_state=MoneyState(h["new_state"]),
                    triggering_agent=h["triggering_agent"],
                    reason=h["reason"],
                    timestamp=datetime.fromisoformat(h["timestamp"]) if isinstance(h.get("timestamp"), str) else h.get("timestamp"),
                )
            )
        return Transaction(
            money_id=row.money_id,
            customer_id=row.customer_id,
            customer_name=row.customer_name,
            amount=row.amount,
            currency=row.currency,
            state=MoneyState(row.state),
            product_name=row.product_name,
            addon_name=row.addon_name,
            razorpay_order_id=row.razorpay_order_id,
            razorpay_payment_id=row.razorpay_payment_id,
            risk_score=row.risk_score,
            risk_decision=row.risk_decision,
            risk_factors=row.risk_factors or [],
            failure_reason=row.failure_reason,
            recovery_probability=row.recovery_probability,
            recovery_explanation=row.recovery_explanation,
            recovery_attempts=row.recovery_attempts,
            settlement_amount=row.settlement_amount,
            reconciliation_status=row.reconciliation_status,
            history=history,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _review_to_model(row: ManualReviewRow) -> ManualReview:
        return ManualReview(
            review_id=row.review_id,
            money_id=row.money_id,
            review_type=row.review_type,
            proposed_action=row.proposed_action,
            reason=row.reason,
            status=row.status,
            created_at=row.created_at,
            resolved_at=row.resolved_at,
            resolved_by=row.resolved_by,
        )


orchestrator = Orchestrator()
