"""Recovery decision agent.

Current implementation is explicitly deterministic (`rules-v1`). It produces a
bounded recommendation and explanation; execution always belongs to the Policy
Engine + orchestrator. No LLM/model usage is claimed unless a real provider is
added later.
"""
_BASE_PROBABILITY = {
    "bank_timeout": 0.70,
    "insufficient_funds": 0.35,
    "card_declined": 0.30,
    "network_error": 0.80,
    "otp_expired": 0.60,
    "issuer_unavailable": 0.55,
    "unknown": 0.40,
}

_RECOMMENDED_ACTION_BY_REASON = {
    "bank_timeout": "RETRY_NOW",
    "network_error": "RETRY_NOW",
    "otp_expired": "RETRY_NOW",
    "issuer_unavailable": "RETRY_LATER",
    "insufficient_funds": "RETRY_LATER",
    "card_declined": "ESCALATE",
    "unknown": "ESCALATE",
}


def analyze(failure_reason: str, amount: float, attempts: int) -> dict:
    failure_reason = failure_reason or "unknown"
    base = _BASE_PROBABILITY.get(failure_reason, _BASE_PROBABILITY["unknown"])
    probability = max(0.0, round(base - (0.15 * attempts), 2))
    recommended_action = _RECOMMENDED_ACTION_BY_REASON.get(failure_reason, "ESCALATE")
    if probability < 0.40:
        recommended_action = "STOP_RECOVERY"

    explanation = (
        f"rules-v1 maps '{failure_reason}' to a {int(base * 100)}% early-recovery prior; "
        f"after {attempts} prior attempt(s), the bounded score is {int(probability * 100)}%."
    )
    return {
        "failure_class": failure_reason,
        "confidence": 0.78,
        "recovery_probability": probability,
        "recommended_action": recommended_action,
        "explanation": explanation,
        "engine": "rules-v1",
        "mode": "deterministic",
        "amount": amount,
    }
