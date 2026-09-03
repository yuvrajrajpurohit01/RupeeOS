"""Deterministic Policy Engine.

Agents may recommend. Only this layer authorizes money-moving actions.
"""
from dataclasses import dataclass
from typing import Literal

MAX_RETRIES = 3
MIN_RECOVERY_PROBABILITY = 0.40
HIGH_VALUE_THRESHOLD = 10000
MAX_AUTONOMOUS_RECOVERY_AMOUNT = 10000
CIRCUIT_BREAKER_FAILURE_RATE = 0.25


@dataclass
class PolicyDecision:
    approved: bool
    reason: str
    action: str


def approve_risk_action(risk_decision: str, circuit_breaker_tripped: bool) -> PolicyDecision:
    if circuit_breaker_tripped:
        return PolicyDecision(False, "Circuit breaker is tripped; human approval required", "MANUAL_REVIEW")
    if risk_decision == "ALLOW":
        return PolicyDecision(True, "Risk is within autonomous payment bounds", "INITIATE_PAYMENT")
    if risk_decision == "VERIFY":
        return PolicyDecision(False, "Transaction requires explicit human verification", "MANUAL_REVIEW")
    return PolicyDecision(False, "Risk policy placed the transaction on hold", "BLOCK")


def approve_recovery(
    action: Literal["RETRY_NOW", "RETRY_LATER", "STOP_RECOVERY", "ESCALATE"],
    attempts: int,
    recovery_probability: float,
    amount: float,
    circuit_breaker_tripped: bool,
    max_attempts: int = MAX_RETRIES,
) -> PolicyDecision:
    if circuit_breaker_tripped:
        return PolicyDecision(False, "Circuit breaker is tripped; recovery needs human approval", "MANUAL_REVIEW")
    if attempts >= max_attempts:
        return PolicyDecision(False, "Maximum retry limit reached", "STOP_RECOVERY")
    if recovery_probability < MIN_RECOVERY_PROBABILITY:
        return PolicyDecision(False, "Recovery probability is below the autonomous threshold", "STOP_RECOVERY")
    if amount > MAX_AUTONOMOUS_RECOVERY_AMOUNT:
        return PolicyDecision(False, "Recovery amount exceeds autonomous limit", "MANUAL_REVIEW")
    if action == "RETRY_NOW":
        return PolicyDecision(True, "Fresh Razorpay retry is permitted within policy bounds", "RETRY_NOW")
    if action in ("RETRY_LATER", "ESCALATE"):
        return PolicyDecision(False, "Recommended action requires a human decision", "MANUAL_REVIEW")
    return PolicyDecision(False, "Recovery should stop", "STOP_RECOVERY")


def evaluate_risk_decision(risk_score: float, amount: float) -> str:
    if risk_score >= 0.8:
        return "HOLD"
    if risk_score >= 0.5 or amount >= HIGH_VALUE_THRESHOLD:
        return "VERIFY"
    return "ALLOW"


def evaluate_reconciliation(expected_amount: float, received_amount: float) -> dict:
    difference = round(received_amount - expected_amount, 2)
    if difference == 0:
        return {"status": "MATCHED", "requires_review": False}
    if abs(difference) <= expected_amount * 0.02:
        return {"status": "FEE_ADJUSTED_MATCH", "difference": difference, "requires_review": False}
    return {"status": "EXCEPTION", "difference": difference, "requires_review": True}


def check_circuit_breaker(recent_transactions: list, threshold: float = CIRCUIT_BREAKER_FAILURE_RATE) -> dict:
    if not recent_transactions:
        return {"tripped": False, "failure_rate": 0.0, "reason": "No recent transactions to evaluate"}

    failed_states = {"EXCEPTION", "LOST"}

    def _state_value(t):
        s = getattr(t, "state", t)
        return getattr(s, "value", s)

    failures = sum(1 for t in recent_transactions if _state_value(t) in failed_states)
    rate = failures / len(recent_transactions)
    tripped = rate > threshold
    reason = (
        f"Failure rate {rate:.1%} exceeds {threshold:.0%} threshold — automated money actions require human review"
        if tripped
        else "Within normal operating range"
    )
    return {"tripped": tripped, "failure_rate": round(rate, 4), "reason": reason}
