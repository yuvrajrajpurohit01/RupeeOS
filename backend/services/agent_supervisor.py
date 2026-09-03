"""Durable, policy-constrained multi-agent supervisor for RupeeOS.

The supervisor observes the Money State Graph, selects the next specialist,
records a structured trace, and stops at explicit human/external boundaries.
Specialists can recommend actions; the deterministic policy engine remains the
only authority for money-related execution.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from agents import recovery_agent, risk_agent
from models.agentic import AgentManifest, WorkflowRun, WorkflowStep
from models.money_state import MoneyState
from services import policy_engine, razorpay_service
from services.audit_service import audit_log
from services.clock import utc_now
from services.database import AgentWorkflowRow, SessionLocal
from services.orchestrator import orchestrator


AGENT_MANIFESTS = [
    AgentManifest(
        name="supervisor",
        role="Observe money state, select specialists, enforce budgets, and pause at safety boundaries.",
        engine="state-graph-v2",
        mode="deterministic",
        capabilities=["state routing", "durable plans", "pause/resume", "trace aggregation"],
        allowed_actions=["SELECT_AGENT", "PAUSE_WORKFLOW", "RESUME_WORKFLOW", "COMPLETE_WORKFLOW"],
        guardrails=["maximum 20 steps", "no direct charge capability", "every step persisted"],
    ),
    AgentManifest(
        name="growth",
        role="Recommend catalog products and compatible add-ons.",
        engine="catalog-rules-v1",
        mode="deterministic",
        capabilities=["intent matching", "budget filtering", "bundle recommendation"],
        allowed_actions=["RECOMMEND_PRODUCT", "RECOMMEND_ADDON"],
        guardrails=["read-only catalog access", "no order creation", "no payment action"],
    ),
    AgentManifest(
        name="risk",
        role="Assess transaction risk with inspectable signals and recommend ALLOW, VERIFY, or HOLD.",
        engine="rules-v1",
        mode="deterministic",
        capabilities=["risk scoring", "factor attribution", "cost-aware recommendation"],
        allowed_actions=["RECOMMEND_ALLOW", "RECOMMEND_VERIFY", "RECOMMEND_HOLD"],
        guardrails=["cannot create an order", "policy engine authorizes next action", "high-value human gate"],
    ),
    AgentManifest(
        name="recovery",
        role="Diagnose payment failures and recommend bounded recovery actions.",
        engine="rules-v1",
        mode="deterministic",
        capabilities=["failure classification", "recovery scoring", "retry recommendation"],
        allowed_actions=["RECOMMEND_RETRY", "RECOMMEND_ESCALATION", "RECOMMEND_STOP"],
        guardrails=["retry budget enforced", "amount ceiling enforced", "cannot bypass policy"],
    ),
    AgentManifest(
        name="finance",
        role="Reconcile captured payments against settlement evidence.",
        engine="rules-v1",
        mode="deterministic",
        capabilities=["settlement matching", "fee tolerance", "exception classification"],
        allowed_actions=["MARK_MATCH", "MARK_FEE_ADJUSTED", "RAISE_EXCEPTION"],
        guardrails=["requires settlement records", "mismatches remain reviewable", "no payout capability"],
    ),
]


class AgentSupervisor:
    def manifests(self) -> list[AgentManifest]:
        return AGENT_MANIFESTS

    def start(
        self,
        money_id: str,
        goal: str = "HANDLE_TRANSACTION",
        max_steps: int = 8,
        execute_external_actions: bool = False,
    ) -> WorkflowRun:
        if not orchestrator.get_transaction(money_id):
            raise KeyError(money_id)
        now = utc_now()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        with SessionLocal() as db:
            db.add(
                AgentWorkflowRow(
                    run_id=run_id,
                    money_id=money_id,
                    goal=goal,
                    status="RUNNING",
                    current_agent="supervisor",
                    max_steps=max_steps,
                    steps_used=0,
                    execute_external_actions=execute_external_actions,
                    steps=[],
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()
        audit_log.record(
            money_id,
            "supervisor",
            "AGENTIC_RUN_STARTED",
            {"run_id": run_id, "goal": goal, "max_steps": max_steps, "execute_external_actions": execute_external_actions},
        )
        return self._drive(run_id)

    def resume(
        self,
        run_id: str,
        max_steps: int | None = None,
        execute_external_actions: bool | None = None,
    ) -> WorkflowRun:
        run = self.get(run_id)
        if not run:
            raise KeyError(run_id)
        if run.status == "COMPLETED":
            return run
        with SessionLocal() as db:
            row = db.get(AgentWorkflowRow, run_id)
            row.status = "RUNNING"
            row.stop_reason = None
            row.current_agent = "supervisor"
            if max_steps is not None:
                row.max_steps = max_steps
            if execute_external_actions is not None:
                row.execute_external_actions = execute_external_actions
            row.updated_at = utc_now()
            db.commit()
        audit_log.record(run.money_id, "supervisor", "AGENTIC_RUN_RESUMED", {"run_id": run_id})
        return self._drive(run_id)

    def get(self, run_id: str) -> WorkflowRun | None:
        with SessionLocal() as db:
            row = db.get(AgentWorkflowRow, run_id)
            return self._to_model(row) if row else None

    def list(self, money_id: str | None = None, limit: int = 100) -> list[WorkflowRun]:
        with SessionLocal() as db:
            query = db.query(AgentWorkflowRow)
            if money_id:
                query = query.filter(AgentWorkflowRow.money_id == money_id)
            rows = query.order_by(AgentWorkflowRow.updated_at.desc()).limit(limit).all()
            return [self._to_model(row) for row in rows]

    def _drive(self, run_id: str) -> WorkflowRun:
        while True:
            run = self.get(run_id)
            if not run:
                raise KeyError(run_id)
            if run.steps_used >= run.max_steps:
                return self._finish(run_id, "BUDGET_EXHAUSTED", "MAX_STEPS_REACHED", "supervisor")

            txn = orchestrator.get_transaction(run.money_id)
            if not txn:
                return self._finish(run_id, "FAILED", "TRANSACTION_NOT_FOUND", "supervisor")

            state = txn.state
            if state in {MoneyState.RECONCILED, MoneyState.LOST, MoneyState.EXCEPTION}:
                return self._finish(run_id, "COMPLETED", f"TERMINAL_STATE:{state.value}", "supervisor")
            if state == MoneyState.DISCOVERED:
                self._checkout_step(run, txn)
                continue
            if state == MoneyState.CHECKOUT_CREATED:
                result = self._risk_step(run, txn)
                if result:
                    return result
                continue
            if state == MoneyState.RISK_ANALYZED:
                return self._payment_boundary_step(run, txn)
            if state == MoneyState.MANUAL_REVIEW:
                return self._boundary_step(run, txn, "HUMAN_APPROVAL_REQUIRED", "A pending policy decision requires a human reviewer.")
            if state in {MoneyState.PAYMENT_INITIATED, MoneyState.RECOVERY_EXECUTED}:
                return self._boundary_step(run, txn, "PAYMENT_EVENT_REQUIRED", "Waiting for verified Razorpay checkout status or webhook evidence.")
            if state in {MoneyState.PAYMENT_FAILED, MoneyState.RECOVERY_ANALYZED}:
                return self._recovery_step(run, txn)
            if state in {MoneyState.PAYMENT_SUCCESS, MoneyState.RECOVERED, MoneyState.SETTLEMENT_PENDING}:
                return self._boundary_step(run, txn, "SETTLEMENT_INPUT_REQUIRED", "Finance Agent needs an external settlement record before reconciliation.")
            return self._finish(run_id, "FAILED", f"UNHANDLED_STATE:{state.value}", "supervisor")

    def _checkout_step(self, run: WorkflowRun, txn) -> None:
        started = utc_now()
        orchestrator.apply_transition(
            txn.money_id,
            MoneyState.CHECKOUT_CREATED,
            "supervisor",
            "Supervisor accepted the transaction goal and prepared it for specialist risk analysis",
        )
        self._append_step(
            run.run_id,
            WorkflowStep(
                sequence=run.steps_used + 1,
                agent="supervisor",
                observation="Transaction is DISCOVERED and has not entered the checkout workflow.",
                reasoning="Risk analysis requires a finalized checkout state.",
                recommendation="Advance to CHECKOUT_CREATED and delegate to Risk Agent.",
                action="PREPARE_CHECKOUT",
                outcome="Money State Graph advanced to CHECKOUT_CREATED.",
                status="COMPLETED",
                confidence=1.0,
                evidence={"previous_state": "DISCOVERED", "new_state": "CHECKOUT_CREATED"},
                started_at=started,
                completed_at=utc_now(),
            ),
        )

    def _risk_step(self, run: WorkflowRun, txn) -> WorkflowRun | None:
        started_dt = utc_now()
        started_perf = time.perf_counter()
        analysis = risk_agent.analyze(txn.amount, {"is_new_customer": True, "transactions_last_hour": 1})
        orchestrator.update_fields(
            txn.money_id,
            risk_score=analysis["risk_score"],
            risk_decision=analysis["risk_decision"],
            risk_factors=analysis["factors"],
        )
        orchestrator.record_agent_run(
            txn.money_id,
            "risk",
            started_perf,
            f"Risk {analysis['risk_score']:.2f} -> {analysis['risk_decision']}",
            confidence=analysis["confidence"],
            engine=analysis["engine"],
            mode=analysis["mode"],
        )
        breaker = orchestrator.circuit_breaker_status()
        decision = policy_engine.approve_risk_action(analysis["risk_decision"], breaker["tripped"])
        orchestrator.record_policy_decision(txn.money_id, decision)

        if decision.approved and decision.action == "INITIATE_PAYMENT":
            orchestrator.apply_transition(txn.money_id, MoneyState.RISK_ANALYZED, "policy_engine", decision.reason)
            outcome = "Risk recommendation approved; transaction is ready for payment order creation."
            step_status = "COMPLETED"
            stop_reason = None
        elif decision.action == "MANUAL_REVIEW":
            orchestrator.apply_transition(txn.money_id, MoneyState.MANUAL_REVIEW, "policy_engine", decision.reason)
            orchestrator.create_manual_review(txn.money_id, "RISK", "INITIATE_PAYMENT", decision.reason)
            outcome = "Transaction routed to the human approval inbox."
            step_status = "PAUSED"
            stop_reason = "HUMAN_APPROVAL_REQUIRED"
        else:
            orchestrator.apply_transition(txn.money_id, MoneyState.EXCEPTION, "policy_engine", decision.reason)
            outcome = "Transaction blocked by policy and moved to EXCEPTION."
            step_status = "COMPLETED"
            stop_reason = None

        self._append_step(
            run.run_id,
            WorkflowStep(
                sequence=run.steps_used + 1,
                agent="risk",
                observation=f"Checkout amount is INR {txn.amount:.2f}; {len(analysis['factors'])} risk signals were evaluated.",
                reasoning=f"rules-v1 produced score {analysis['risk_score']:.2f} and recommendation {analysis['risk_decision']}.",
                recommendation=analysis["risk_decision"],
                action=decision.action,
                outcome=outcome,
                status=step_status,
                confidence=analysis["confidence"],
                evidence={"risk_score": analysis["risk_score"], "factors": analysis["factors"], "circuit_breaker": breaker},
                policy_decision={"approved": decision.approved, "action": decision.action, "reason": decision.reason},
                started_at=started_dt,
                completed_at=utc_now(),
            ),
        )
        if stop_reason:
            return self._finish(run.run_id, "PAUSED", stop_reason, "risk")
        return None

    def _payment_boundary_step(self, run: WorkflowRun, txn) -> WorkflowRun:
        started = utc_now()
        if not run.execute_external_actions:
            self._append_step(
                run.run_id,
                WorkflowStep(
                    sequence=run.steps_used + 1,
                    agent="supervisor",
                    observation="Policy approved payment initiation, but external actions are disabled for this run.",
                    reasoning="Creating a Razorpay order crosses the configured external-action boundary.",
                    recommendation="Resume with execute_external_actions=true or use the explicit /pay endpoint.",
                    action="PAUSE_FOR_EXTERNAL_ACTION",
                    outcome="No Razorpay order was created.",
                    status="PAUSED",
                    confidence=1.0,
                    evidence={"state": txn.state.value, "execute_external_actions": False},
                    started_at=started,
                    completed_at=utc_now(),
                ),
            )
            return self._finish(run.run_id, "PAUSED", "EXTERNAL_ACTIONS_DISABLED", "supervisor")

        breaker = orchestrator.circuit_breaker_status()
        if breaker["tripped"]:
            decision = policy_engine.PolicyDecision(False, breaker["reason"], "MANUAL_REVIEW")
            orchestrator.record_policy_decision(txn.money_id, decision)
            orchestrator.apply_transition(txn.money_id, MoneyState.MANUAL_REVIEW, "policy_engine", decision.reason)
            orchestrator.create_manual_review(txn.money_id, "RISK", "INITIATE_PAYMENT", decision.reason)
            outcome = "Circuit breaker routed order creation to human review."
            checkout = None
            status = "PAUSED"
            reason = "HUMAN_APPROVAL_REQUIRED"
        else:
            try:
                checkout = razorpay_service.create_order(
                    txn.amount,
                    receipt=txn.money_id,
                    notes={"money_id": txn.money_id, "kind": "PRIMARY", "agentic_run_id": run.run_id},
                )
                orchestrator.create_payment_attempt(txn.money_id, checkout["razorpay_order_id"], "PRIMARY")
                orchestrator.apply_transition(txn.money_id, MoneyState.PAYMENT_INITIATED, "supervisor", "Policy-approved Razorpay order created")
                checkout = {**checkout, "money_id": txn.money_id, "name": "RupeeOS", "description": txn.product_name or "RupeeOS transaction"}
                outcome = "Razorpay order created; customer checkout is required."
                status = "COMPLETED"
                reason = "PAYMENT_CHECKOUT_REQUIRED"
                self._set_pending_checkout(run.run_id, checkout)
            except RuntimeError as exc:
                checkout = None
                outcome = str(exc)
                status = "PAUSED"
                reason = "PAYMENT_PROVIDER_CONFIGURATION_REQUIRED"

        self._append_step(
            run.run_id,
            WorkflowStep(
                sequence=run.steps_used + 1,
                agent="supervisor",
                observation="Transaction is policy-approved and ready for payment order creation.",
                reasoning="The supervisor may prepare checkout only when external actions are explicitly enabled.",
                recommendation="Create a Razorpay order and wait for customer/payment evidence." if not breaker["tripped"] else "Escalate to a human reviewer.",
                action="CREATE_RAZORPAY_ORDER" if checkout else "PAUSE_PAYMENT",
                outcome=outcome,
                status=status,
                confidence=1.0,
                evidence={"circuit_breaker": breaker, "order_created": checkout is not None},
                started_at=started,
                completed_at=utc_now(),
            ),
        )
        return self._finish(run.run_id, "PAUSED", reason, "supervisor")

    def _recovery_step(self, run: WorkflowRun, txn) -> WorkflowRun:
        started_dt = utc_now()
        started_perf = time.perf_counter()
        analysis = recovery_agent.analyze(txn.failure_reason or "unknown", txn.amount, txn.recovery_attempts)
        orchestrator.update_fields(
            txn.money_id,
            recovery_probability=analysis["recovery_probability"],
            recovery_explanation=analysis["explanation"],
        )
        if txn.state == MoneyState.PAYMENT_FAILED:
            orchestrator.apply_transition(txn.money_id, MoneyState.RECOVERY_ANALYZED, "recovery_agent", analysis["explanation"])
        orchestrator.record_agent_run(
            txn.money_id,
            "recovery",
            started_perf,
            f"{analysis['recommended_action']} at P={analysis['recovery_probability']:.2f}",
            confidence=analysis["confidence"],
            engine=analysis["engine"],
            mode=analysis["mode"],
        )
        breaker = orchestrator.circuit_breaker_status()
        decision = policy_engine.approve_recovery(
            analysis["recommended_action"],
            txn.recovery_attempts,
            analysis["recovery_probability"],
            txn.amount,
            breaker["tripped"],
        )
        orchestrator.record_policy_decision(txn.money_id, decision)
        checkout = None

        if decision.approved and decision.action == "RETRY_NOW" and not run.execute_external_actions:
            outcome = "Recovery retry is policy-approved but external actions are disabled."
            stop_reason = "EXTERNAL_ACTIONS_DISABLED"
            step_status = "PAUSED"
        elif decision.approved and decision.action == "RETRY_NOW":
            try:
                checkout = razorpay_service.create_order(
                    txn.amount,
                    receipt=f"{txn.money_id}-r{txn.recovery_attempts + 1}",
                    notes={"money_id": txn.money_id, "kind": "RECOVERY", "agentic_run_id": run.run_id},
                )
                orchestrator.update_fields(txn.money_id, recovery_attempts=txn.recovery_attempts + 1)
                orchestrator.create_payment_attempt(txn.money_id, checkout["razorpay_order_id"], "RECOVERY")
                orchestrator.apply_transition(txn.money_id, MoneyState.RECOVERY_EXECUTED, "supervisor", decision.reason)
                checkout = {**checkout, "money_id": txn.money_id, "name": "RupeeOS Recovery", "description": "Policy-approved recovery attempt"}
                self._set_pending_checkout(run.run_id, checkout)
                outcome = "Fresh Razorpay recovery order created; customer checkout is required."
                stop_reason = "PAYMENT_CHECKOUT_REQUIRED"
                step_status = "COMPLETED"
            except RuntimeError as exc:
                outcome = str(exc)
                stop_reason = "PAYMENT_PROVIDER_CONFIGURATION_REQUIRED"
                step_status = "PAUSED"
        elif decision.action == "MANUAL_REVIEW":
            orchestrator.apply_transition(txn.money_id, MoneyState.MANUAL_REVIEW, "policy_engine", decision.reason)
            orchestrator.create_manual_review(txn.money_id, "RECOVERY", analysis["recommended_action"], decision.reason)
            outcome = "Recovery action routed to the human approval inbox."
            stop_reason = "HUMAN_APPROVAL_REQUIRED"
            step_status = "PAUSED"
        else:
            orchestrator.apply_transition(txn.money_id, MoneyState.LOST, "policy_engine", decision.reason)
            outcome = "Bounded recovery stopped; transaction moved to LOST."
            stop_reason = "TERMINAL_STATE:LOST"
            step_status = "COMPLETED"

        self._append_step(
            run.run_id,
            WorkflowStep(
                sequence=run.steps_used + 1,
                agent="recovery",
                observation=f"Payment failed with '{txn.failure_reason or 'unknown'}' after {txn.recovery_attempts} recovery attempt(s).",
                reasoning=analysis["explanation"],
                recommendation=analysis["recommended_action"],
                action=decision.action,
                outcome=outcome,
                status=step_status,
                confidence=analysis["confidence"],
                evidence={"recovery_probability": analysis["recovery_probability"], "circuit_breaker": breaker, "order_created": checkout is not None},
                policy_decision={"approved": decision.approved, "action": decision.action, "reason": decision.reason},
                started_at=started_dt,
                completed_at=utc_now(),
            ),
        )
        final_status = "COMPLETED" if stop_reason.startswith("TERMINAL_STATE") else "PAUSED"
        return self._finish(run.run_id, final_status, stop_reason, "recovery")

    def _boundary_step(self, run: WorkflowRun, txn, reason: str, explanation: str) -> WorkflowRun:
        started = utc_now()
        self._append_step(
            run.run_id,
            WorkflowStep(
                sequence=run.steps_used + 1,
                agent="supervisor",
                observation=f"Money State Graph is {txn.state.value}.",
                reasoning=explanation,
                recommendation="Pause safely until the required evidence or approval is available.",
                action="PAUSE_WORKFLOW",
                outcome=explanation,
                status="PAUSED",
                confidence=1.0,
                evidence={"state": txn.state.value},
                started_at=started,
                completed_at=utc_now(),
            ),
        )
        return self._finish(run.run_id, "PAUSED", reason, "supervisor")

    def _append_step(self, run_id: str, step: WorkflowStep) -> None:
        with SessionLocal() as db:
            row = db.get(AgentWorkflowRow, run_id)
            steps = list(row.steps or [])
            steps.append(step.model_dump(mode="json"))
            row.steps = steps
            row.steps_used = len(steps)
            row.current_agent = step.agent
            row.updated_at = utc_now()
            db.commit()
        audit_log.record(
            self.get(run_id).money_id,
            step.agent,
            "AGENTIC_STEP_COMPLETED",
            {"run_id": run_id, "sequence": step.sequence, "action": step.action, "status": step.status, "outcome": step.outcome},
        )

    def _set_pending_checkout(self, run_id: str, checkout: dict[str, Any]) -> None:
        with SessionLocal() as db:
            row = db.get(AgentWorkflowRow, run_id)
            row.pending_checkout = checkout
            row.updated_at = utc_now()
            db.commit()

    def _finish(self, run_id: str, status: str, reason: str, current_agent: str) -> WorkflowRun:
        with SessionLocal() as db:
            row = db.get(AgentWorkflowRow, run_id)
            row.status = status
            row.stop_reason = reason
            row.current_agent = current_agent
            row.updated_at = utc_now()
            money_id = row.money_id
            db.commit()
        audit_log.record(money_id, "supervisor", f"AGENTIC_RUN_{status}", {"run_id": run_id, "stop_reason": reason})
        return self.get(run_id)

    @staticmethod
    def _to_model(row: AgentWorkflowRow) -> WorkflowRun:
        return WorkflowRun(
            run_id=row.run_id,
            money_id=row.money_id,
            goal=row.goal,
            status=row.status,
            current_agent=row.current_agent,
            stop_reason=row.stop_reason,
            max_steps=row.max_steps,
            steps_used=row.steps_used,
            execute_external_actions=row.execute_external_actions,
            steps=[WorkflowStep.model_validate(step) for step in (row.steps or [])],
            pending_checkout=row.pending_checkout,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


agent_supervisor = AgentSupervisor()
