"""Core safety regression tests for the Buildathon demo."""
import hashlib
import sys
from pathlib import Path
import hmac
import json
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["RUPEEOS_DATABASE_URL"] = "sqlite:///./test_rupeeos.db"
os.environ["RAZORPAY_KEY_ID"] = ""
os.environ["RAZORPAY_KEY_SECRET"] = ""
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["RUPEEOS_LLM_ENABLED"] = "false"

from fastapi.testclient import TestClient

import main
from main import app
from services.database import Base, engine
from services.llm_reasoning import AIReasoningDecision, AIReasoningEnvelope, LLMReasoningService


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _fake_order(amount_inr: float, receipt: str, notes=None):
    suffix = hashlib.sha1(receipt.encode()).hexdigest()[:8]
    return {
        "razorpay_order_id": f"order_test_{suffix}",
        "amount": amount_inr,
        "amount_subunits": int(amount_inr * 100),
        "currency": "INR",
        "key": "rzp_test_fake",
    }


def test_high_value_requires_human_approval(monkeypatch):
    monkeypatch.setattr(main.razorpay_service, "create_order", _fake_order)
    with TestClient(app) as client:
        tx = client.post("/transactions", json={"customer_id": "c1", "customer_name": "High Value", "amount": 12999}).json()
        money_id = tx["money_id"]
        client.post(f"/transactions/{money_id}/checkout", json={})
        result = client.post(
            f"/transactions/{money_id}/risk-analyze",
            json={"customer_history": {"is_new_customer": True, "transactions_last_hour": 1}},
        ).json()
        assert result["transaction"]["state"] == "MANUAL_REVIEW"
        assert client.post(f"/transactions/{money_id}/pay", json={}).status_code == 409

        review = next(r for r in client.get("/manual-reviews?status=PENDING").json()["reviews"] if r["money_id"] == money_id)
        approved = client.post(f"/manual-reviews/{review['review_id']}/approve", json={}).json()
        assert approved["transaction"]["state"] == "RISK_ANALYZED"
        assert client.post(f"/transactions/{money_id}/pay", json={}).status_code == 200


def test_webhook_is_idempotent_and_reconciliation_closes_loop(monkeypatch):
    monkeypatch.setattr(main.razorpay_service, "create_order", _fake_order)
    with TestClient(app) as client:
        tx = client.post("/transactions", json={"customer_id": "c2", "customer_name": "Normal", "amount": 4999}).json()
        money_id = tx["money_id"]
        client.post(f"/transactions/{money_id}/checkout", json={})
        client.post(
            f"/transactions/{money_id}/risk-analyze",
            json={"customer_history": {"is_new_customer": True, "transactions_last_hour": 1}},
        )
        order = client.post(f"/transactions/{money_id}/pay", json={}).json()

        payload = {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"order_id": order["razorpay_order_id"], "id": "pay_test_1", "amount": 499900, "status": "captured"}}},
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"test-webhook-secret", raw, hashlib.sha256).hexdigest()
        headers = {"X-Razorpay-Signature": signature, "x-razorpay-event-id": "evt_test_1", "Content-Type": "application/json"}

        assert client.post("/webhooks/razorpay", content=raw, headers=headers).json()["status"] == "processed"
        assert client.post("/webhooks/razorpay", content=raw, headers=headers).json()["status"] == "duplicate_ignored"
        assert client.get(f"/transactions/{money_id}").json()["state"] == "SETTLEMENT_PENDING"

        client.post(
            "/reconciliation/run",
            json={"batch_id": "batch_test", "settlement_records": [{"money_id": money_id, "expected_amount": 4999, "received_amount": 4999}]},
        )
        assert client.get(f"/transactions/{money_id}").json()["state"] == "RECONCILED"


def test_agentic_supervisor_routes_risk_and_pauses_before_external_action():
    with TestClient(app) as client:
        tx = client.post(
            "/transactions",
            json={"customer_id": "agentic_customer", "customer_name": "Agentic Demo", "amount": 999},
        ).json()
        money_id = tx["money_id"]
        client.post(f"/transactions/{money_id}/checkout", json={})

        response = client.post(
            "/agentic/runs",
            json={
                "money_id": money_id,
                "goal": "ASSESS_AND_ROUTE_PAYMENT",
                "max_steps": 4,
                "execute_external_actions": False,
            },
        )
        assert response.status_code == 201
        run = response.json()["run"]
        assert run["status"] == "PAUSED"
        assert run["stop_reason"] == "EXTERNAL_ACTIONS_DISABLED"
        assert [step["agent"] for step in run["steps"]] == ["risk", "supervisor"]
        assert run["steps"][0]["policy_decision"]["approved"] is True
        assert client.get(f"/transactions/{money_id}").json()["state"] == "RISK_ANALYZED"

        stored = client.get(f"/agentic/runs/{run['run_id']}").json()
        assert stored["steps_used"] == 2


def test_agentic_supervisor_enforces_step_budget():
    with TestClient(app) as client:
        tx = client.post(
            "/transactions",
            json={"customer_id": "budget_customer", "customer_name": "Budget Demo", "amount": 499},
        ).json()
        response = client.post(
            "/agentic/runs",
            json={"money_id": tx["money_id"], "max_steps": 1},
        )
        run = response.json()["run"]
        assert run["status"] == "BUDGET_EXHAUSTED"
        assert run["stop_reason"] == "MAX_STEPS_REACHED"
        assert run["steps_used"] == 1


def test_ai_reasoning_is_structured_and_cannot_select_wrong_agent(monkeypatch):
    service = LLMReasoningService()
    monkeypatch.setenv("RUPEEOS_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("RUPEEOS_LLM_MODEL", "gpt-5.6-terra")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            decision = {
                "selected_agent": "recovery",
                "diagnosis": "Network interruption is recoverable.",
                "recommended_action": "RETRY_NOW",
                "explanation": "Verified failure evidence supports one bounded retry.",
                "confidence": 0.86,
                "evidence": ["failure_reason=network_error", "attempts=0"],
                "recovery_plan": ["Create a fresh order", "Wait for verified payment evidence"],
                "requires_human_review": False,
            }
            return {"id": "resp_test", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(decision)}]}]}

    monkeypatch.setattr("services.llm_reasoning.requests.post", lambda *args, **kwargs: FakeResponse())
    result = service.analyze(
        expected_agent="recovery",
        allowed_actions=["RETRY_NOW", "RETRY_LATER", "ESCALATE", "STOP_RECOVERY"],
        context={"failure_reason": "network_error", "attempts": 0, "api_key": "must-not-leak"},
    )
    assert result.used is True
    assert result.decision.selected_agent == "recovery"
    assert result.decision.recommended_action == "RETRY_NOW"

    wrong = result.decision.model_copy(update={"selected_agent": "risk"})
    try:
        service._validate_authority(wrong, "recovery", ["RETRY_NOW"])
        assert False, "wrong specialist must be rejected"
    except ValueError:
        pass


def test_ai_can_only_make_risk_recommendation_more_conservative():
    from services.agent_supervisor import agent_supervisor

    decision = AIReasoningDecision(
        selected_agent="risk",
        diagnosis="Evidence is uncertain.",
        recommended_action="VERIFY",
        explanation="Request human verification.",
        confidence=0.72,
        evidence=["new customer"],
        recovery_plan=[],
        requires_human_review=True,
    )
    ai = AIReasoningEnvelope(used=True, model="gpt-5.6-terra", decision=decision)
    assert agent_supervisor._conservative_risk_recommendation("ALLOW", ai) == "VERIFY"
    permissive_ai = AIReasoningEnvelope(used=True, model="gpt-5.6-terra", decision=decision.model_copy(update={"recommended_action": "ALLOW"}))
    assert agent_supervisor._conservative_risk_recommendation("HOLD", permissive_ai) == "HOLD"


def test_agentic_recovery_creates_fresh_policy_approved_order(monkeypatch):
    monkeypatch.setattr(main.razorpay_service, "create_order", _fake_order)
    with TestClient(app) as client:
        tx = client.post(
            "/transactions",
            json={"customer_id": "recovery_customer", "customer_name": "Recovery Demo", "amount": 999},
        ).json()
        money_id = tx["money_id"]
        client.post(f"/transactions/{money_id}/checkout", json={})
        client.post(f"/transactions/{money_id}/risk-analyze", json={})
        primary_order = client.post(f"/transactions/{money_id}/pay", json={}).json()

        payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "order_id": primary_order["razorpay_order_id"],
                        "id": "pay_failed_1",
                        "amount": 99900,
                        "status": "failed",
                        "error_reason": "network_error",
                        "error_description": "Network interrupted",
                    }
                }
            },
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"test-webhook-secret", raw, hashlib.sha256).hexdigest()
        client.post(
            "/webhooks/razorpay",
            content=raw,
            headers={
                "X-Razorpay-Signature": signature,
                "x-razorpay-event-id": "evt_recovery_failure",
                "Content-Type": "application/json",
            },
        )

        response = client.post(
            "/agentic/runs",
            json={
                "money_id": money_id,
                "goal": "RECOVER_FAILED_PAYMENT",
                "max_steps": 4,
                "execute_external_actions": True,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["run"]["stop_reason"] == "PAYMENT_CHECKOUT_REQUIRED"
        assert body["run"]["steps"][0]["agent"] == "recovery"
        assert body["run"]["steps"][0]["policy_decision"]["approved"] is True
        assert body["pending_checkout"]["razorpay_order_id"] != primary_order["razorpay_order_id"]
        assert client.get(f"/transactions/{money_id}").json()["state"] == "RECOVERY_EXECUTED"


def test_audit_chain_can_be_verified():
    with TestClient(app) as client:
        tx = client.post(
            "/transactions",
            json={"customer_id": "audit_customer", "customer_name": "Audit Demo", "amount": 1499},
        ).json()
        verification = client.get(f"/audit/verify?money_id={tx['money_id']}").json()
        assert verification["valid"] is True
        assert verification["entries_checked"] >= 1
        assert verification["chains_checked"] == 1


def test_validation_and_readiness_endpoints():
    with TestClient(app) as client:
        invalid = client.post(
            "/transactions",
            json={"customer_id": "bad id with spaces", "customer_name": "Bad", "amount": -1},
        )
        assert invalid.status_code == 422
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        ai = client.get("/ai/status").json()
        assert ai["active"] is False
        assert ai["authority"] == "recommendation_only"
        agents = client.get("/agentic/agents").json()["agents"]
        assert {agent["name"] for agent in agents} == {"supervisor", "growth", "risk", "recovery", "finance"}


def test_growth_agent_uses_backend_catalog_and_records_real_run():
    with TestClient(app) as client:
        result = client.post(
            "/growth/recommend",
            json={"query": "RupeePods Pro", "budget": 5498, "money_id": "growth_test"},
        )
        assert result.status_code == 200
        body = result.json()
        assert body["recommended_products"][0]["product_id"] == "pro-headphones"
        assert body["upsell"][0]["product_id"] == "protection"
        runs = client.get("/agent-runs?money_id=growth_test").json()["runs"]
        assert runs[-1]["agent"] == "growth"
        assert runs[-1]["engine"] == "catalog-rules-v1"
