"""Money State Graph — API-facing models for RupeeOS."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid

from pydantic import BaseModel, Field
from services.clock import utc_now


class MoneyState(str, Enum):
    DISCOVERED = "DISCOVERED"
    CHECKOUT_CREATED = "CHECKOUT_CREATED"
    RISK_ANALYZED = "RISK_ANALYZED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    RECOVERY_ANALYZED = "RECOVERY_ANALYZED"
    RECOVERY_EXECUTED = "RECOVERY_EXECUTED"
    RECOVERED = "RECOVERED"
    LOST = "LOST"
    SETTLEMENT_PENDING = "SETTLEMENT_PENDING"
    RECONCILED = "RECONCILED"
    EXCEPTION = "EXCEPTION"


class StateTransition(BaseModel):
    previous_state: Optional[MoneyState]
    new_state: MoneyState
    triggering_agent: str
    reason: str
    timestamp: datetime = Field(default_factory=utc_now)


class Transaction(BaseModel):
    money_id: str = Field(default_factory=lambda: f"txn_{uuid.uuid4().hex[:12]}")
    customer_id: str
    customer_name: str = "Customer"
    amount: float
    currency: str = "INR"
    state: MoneyState = MoneyState.DISCOVERED
    product_name: Optional[str] = None
    addon_name: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    risk_score: Optional[float] = None
    risk_decision: Optional[str] = None
    risk_factors: list[dict[str, Any]] = Field(default_factory=list)
    failure_reason: Optional[str] = None
    recovery_probability: Optional[float] = None
    recovery_explanation: Optional[str] = None
    recovery_attempts: int = 0
    settlement_amount: Optional[float] = None
    reconciliation_status: Optional[str] = None
    history: list[StateTransition] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PolicyDecisionRecord(BaseModel):
    money_id: str
    approved: bool
    reason: str
    action: str
    timestamp: datetime = Field(default_factory=utc_now)


class AuditEntry(BaseModel):
    money_id: str
    actor: str
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str
    entry_hash: str
    timestamp: datetime


class ManualReview(BaseModel):
    review_id: str
    money_id: str
    review_type: str
    proposed_action: str
    reason: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None


class AgentRunRecord(BaseModel):
    money_id: str
    agent: str
    engine: str
    mode: str
    latency_ms: int
    confidence: Optional[float] = None
    summary: str
    timestamp: datetime
