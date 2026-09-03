"""Typed contracts for the durable RupeeOS agentic runtime."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


WorkflowStatus = Literal["RUNNING", "PAUSED", "COMPLETED", "FAILED", "BUDGET_EXHAUSTED"]
StepStatus = Literal["COMPLETED", "PAUSED", "FAILED"]


class AgentManifest(BaseModel):
    name: str
    role: str
    engine: str
    mode: str
    capabilities: list[str]
    allowed_actions: list[str]
    guardrails: list[str]


class WorkflowStep(BaseModel):
    sequence: int
    agent: str
    observation: str
    reasoning: str
    recommendation: str
    action: str
    outcome: str
    status: StepStatus
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    policy_decision: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime


class WorkflowRun(BaseModel):
    run_id: str
    money_id: str
    goal: str
    status: WorkflowStatus
    current_agent: str | None = None
    stop_reason: str | None = None
    max_steps: int = Field(ge=1, le=20)
    steps_used: int = Field(ge=0)
    execute_external_actions: bool = False
    steps: list[WorkflowStep] = Field(default_factory=list)
    pending_checkout: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
