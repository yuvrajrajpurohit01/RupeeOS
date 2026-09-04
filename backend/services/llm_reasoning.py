"""Bounded OpenAI reasoning for RupeeOS.

The model can select and recommend, but it cannot execute tools or mutate money
state. Every recommendation is constrained by the state graph and the existing
deterministic Policy Engine.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Literal

import requests
from pydantic import BaseModel, Field, ValidationError


AgentName = Literal["supervisor", "growth", "risk", "recovery", "finance"]
RecommendedAction = Literal[
    "CONTINUE",
    "ALLOW",
    "VERIFY",
    "HOLD",
    "RETRY_NOW",
    "RETRY_LATER",
    "ESCALATE",
    "STOP_RECOVERY",
    "MANUAL_REVIEW",
    "STOP",
    "RECONCILE",
    "RAISE_EXCEPTION",
    "WAIT",
]


class AIReasoningDecision(BaseModel):
    selected_agent: AgentName
    diagnosis: str = Field(min_length=1, max_length=1200)
    recommended_action: RecommendedAction
    explanation: str = Field(min_length=1, max_length=1600)
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(max_length=8)
    recovery_plan: list[str] = Field(max_length=6)
    requires_human_review: bool


@dataclass(frozen=True)
class AIReasoningEnvelope:
    used: bool
    model: str
    decision: AIReasoningDecision | None = None
    response_id: str | None = None
    latency_ms: int = 0
    fallback_reason: str | None = None

    def trace(self) -> dict[str, Any]:
        return {
            "used": self.used,
            "provider": "openai" if self.used else "deterministic_fallback",
            "model": self.model,
            "response_id": self.response_id,
            "latency_ms": self.latency_ms,
            "fallback_reason": self.fallback_reason,
            "decision": self.decision.model_dump() if self.decision else None,
        }


SYSTEM_PROMPT = """You are the bounded reasoning layer inside RupeeOS, a Razorpay
Test Mode payment-operations system. Analyze only the supplied transaction
evidence. Select the specialist that should handle the current state, diagnose
the situation, and recommend one allowed action. Never claim that a payment was
successful or recovered without verified provider evidence. Never request or
expose secrets. You have no tools and cannot execute payments. A deterministic
state graph and Policy Engine will validate or reject your recommendation. Be
concise, evidence-grounded, and explicitly request human review when uncertain
or when the evidence indicates a high-value or risky action."""


class LLMReasoningService:
    endpoint = "https://api.openai.com/v1/responses"

    @property
    def model(self) -> str:
        return os.getenv("RUPEEOS_LLM_MODEL", "gpt-5.6-terra").strip()

    def status(self) -> dict[str, Any]:
        enabled = os.getenv("RUPEEOS_LLM_ENABLED", "false").lower() == "true"
        configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
        return {
            "enabled": enabled,
            "configured": configured,
            "active": enabled and configured,
            "provider": "openai",
            "model": self.model,
            "mode": "hybrid" if enabled and configured else "deterministic_fallback",
            "authority": "recommendation_only",
        }

    def analyze(
        self,
        *,
        expected_agent: AgentName,
        allowed_actions: list[str],
        context: dict[str, Any],
    ) -> AIReasoningEnvelope:
        status = self.status()
        if not status["enabled"]:
            return AIReasoningEnvelope(False, self.model, fallback_reason="RUPEEOS_LLM_ENABLED is false")
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return AIReasoningEnvelope(False, self.model, fallback_reason="OPENAI_API_KEY is not configured")

        safe_context = self._sanitize(context)
        user_payload = {
            "expected_agent_from_state_graph": expected_agent,
            "allowed_recommendations": allowed_actions,
            "transaction_evidence": safe_context,
            "instruction": "Return a structured advisory decision. The expected agent and allowed recommendations are hard constraints.",
        }
        started = time.perf_counter()
        try:
            response = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "reasoning": {"effort": "low"},
                    "input": [
                        {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
                        {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user_payload, separators=(",", ":"))}]},
                    ],
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "rupeeos_agent_reasoning",
                            "strict": True,
                            "schema": self._schema(),
                        }
                    },
                    "max_output_tokens": 1200,
                    "store": False,
                },
                timeout=(5, 25),
            )
            response.raise_for_status()
            body = response.json()
            decision = AIReasoningDecision.model_validate_json(self._output_text(body))
            self._validate_authority(decision, expected_agent, allowed_actions)
            return AIReasoningEnvelope(
                True,
                self.model,
                decision=decision,
                response_id=body.get("id"),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except (requests.RequestException, ValueError, KeyError, TypeError, ValidationError) as exc:
            return AIReasoningEnvelope(
                False,
                self.model,
                latency_ms=int((time.perf_counter() - started) * 1000),
                fallback_reason=f"{type(exc).__name__}: {str(exc)[:240]}",
            )

    @staticmethod
    def _validate_authority(decision: AIReasoningDecision, expected_agent: AgentName, allowed_actions: list[str]) -> None:
        if decision.selected_agent != expected_agent:
            raise ValueError(f"Model selected {decision.selected_agent}; state graph requires {expected_agent}")
        if decision.recommended_action not in allowed_actions:
            raise ValueError(f"Model action {decision.recommended_action} is outside the allowed recommendation set")

    @staticmethod
    def _sanitize(value: Any) -> Any:
        """Allow only bounded JSON evidence and remove secret-looking fields."""
        secret_markers = ("secret", "password", "signature", "api_key", "token")
        if isinstance(value, dict):
            return {
                str(key)[:80]: LLMReasoningService._sanitize(item)
                for key, item in list(value.items())[:50]
                if not any(marker in str(key).lower() for marker in secret_markers)
            }
        if isinstance(value, list):
            return [LLMReasoningService._sanitize(item) for item in value[:30]]
        if isinstance(value, str):
            return value[:1200]
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return str(value)[:1200]

    @staticmethod
    def _output_text(body: dict[str, Any]) -> str:
        for item in body.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
                if content.get("type") == "refusal":
                    raise ValueError("Model refused the reasoning request")
        raise ValueError("Responses API returned no structured output text")

    @staticmethod
    def _schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "selected_agent": {"type": "string", "enum": ["supervisor", "growth", "risk", "recovery", "finance"]},
                "diagnosis": {"type": "string"},
                "recommended_action": {"type": "string", "enum": ["CONTINUE", "ALLOW", "VERIFY", "HOLD", "RETRY_NOW", "RETRY_LATER", "ESCALATE", "STOP_RECOVERY", "MANUAL_REVIEW", "STOP", "RECONCILE", "RAISE_EXCEPTION", "WAIT"]},
                "explanation": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "recovery_plan": {"type": "array", "items": {"type": "string"}},
                "requires_human_review": {"type": "boolean"},
            },
            "required": ["selected_agent", "diagnosis", "recommended_action", "explanation", "confidence", "evidence", "recovery_plan", "requires_human_review"],
        }


llm_reasoning = LLMReasoningService()
