"""Deterministic settlement reconciliation agent (`rules-v1`)."""
from services.policy_engine import evaluate_reconciliation


def _guess_reason(difference: float) -> tuple[str, float]:
    if difference < 0:
        return "unexplained shortfall", 0.35
    return "unexplained surplus", 0.30


def reconcile_batch(batch_id: str, records: list[dict]) -> dict:
    matched = fee_adjusted = exceptions = 0
    output_records = []

    for r in records:
        result = evaluate_reconciliation(r["expected_amount"], r["received_amount"])
        status = result["status"]
        output = {**r, **result}
        if status == "MATCHED":
            matched += 1
        elif status == "FEE_ADJUSTED_MATCH":
            fee_adjusted += 1
        else:
            exceptions += 1
            reason, confidence = _guess_reason(result["difference"])
            output.update({"identified_reason": reason, "confidence": confidence, "requires_review": True})
        output_records.append(output)

    total = len(records)
    match_rate = round((matched + fee_adjusted) / total, 4) if total else 0.0
    return {
        "batch_id": batch_id,
        "total_records": total,
        "matched": matched,
        "fee_adjusted": fee_adjusted,
        "exceptions": exceptions,
        "match_rate": match_rate,
        "records": output_records,
        "exception_records": [r for r in output_records if r["status"] == "EXCEPTION"],
        "engine": "rules-v1",
        "mode": "deterministic",
    }
