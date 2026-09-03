"""Explainable deterministic risk-scoring agent (`rules-v1`)."""
from services.policy_engine import HIGH_VALUE_THRESHOLD, evaluate_risk_decision


def analyze(amount: float, customer_history: dict) -> dict:
    factors = []
    score = 0.1

    if customer_history.get("is_new_customer"):
        score += 0.25
        factors.append({"signal": "new_customer", "weight": 0.25, "detail": "First transaction from this customer_id"})
    else:
        score -= 0.1
        factors.append({"signal": "returning_customer", "weight": -0.1, "detail": "Returning-customer signal lowers risk"})

    if amount >= HIGH_VALUE_THRESHOLD:
        score += 0.2
        factors.append({"signal": "high_value", "weight": 0.2, "detail": f"Amount ₹{amount:,.0f} exceeds ₹{HIGH_VALUE_THRESHOLD:,.0f} verification threshold"})

    failed_attempts = customer_history.get("failed_attempts_last_hour", 0)
    if failed_attempts > 0:
        weight = min(0.15 * failed_attempts, 0.4)
        score += weight
        factors.append({"signal": "recent_failed_attempts", "weight": weight, "detail": f"{failed_attempts} recent failed attempt(s)"})

    if customer_history.get("billing_shipping_mismatch"):
        score += 0.2
        factors.append({"signal": "address_mismatch", "weight": 0.2, "detail": "Billing and shipping addresses differ"})

    velocity = customer_history.get("transactions_last_hour", 1)
    if velocity <= 1:
        score -= 0.05
        factors.append({"signal": "velocity_normal", "weight": -0.05, "detail": "Normal transaction velocity"})
    elif velocity >= 4:
        score += 0.2
        factors.append({"signal": "high_velocity", "weight": 0.2, "detail": f"{velocity} transactions in the last hour"})

    score = max(0.0, min(1.0, round(score, 2)))
    decision = evaluate_risk_decision(score, amount)
    return {
        "risk_score": score,
        "risk_decision": decision,
        "confidence": round(0.90 if score < 0.4 or score >= 0.9 else 0.80, 2),
        "factors": factors,
        "false_positive_cost_estimate": amount if decision in ("VERIFY", "HOLD") else 0.0,
        "engine": "rules-v1",
        "mode": "deterministic",
    }
