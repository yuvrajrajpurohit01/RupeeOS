"""Validated HTTP request bodies for the RupeeOS API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class GrowthRecommendRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    budget: float | None = Field(default=None, gt=0, le=10_000_000)
    money_id: str | None = Field(default=None, max_length=64)


class CreateTransactionRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:@-]+$")
    customer_name: str = Field(default="Customer", min_length=1, max_length=160)
    amount: float = Field(gt=0, le=10_000_000)
    currency: Literal["INR"] = "INR"
    product_name: str | None = Field(default=None, max_length=200)
    addon_name: str | None = Field(default=None, max_length=200)

    @field_validator("amount")
    @classmethod
    def amount_has_at_most_two_decimals(cls, value: float) -> float:
        if round(value, 2) != value:
            raise ValueError("amount can have at most two decimal places")
        return value


class CheckoutRequest(BaseModel):
    cart: dict[str, Any] = Field(default_factory=dict)


class CustomerHistory(BaseModel):
    is_new_customer: bool = True
    failed_attempts_last_hour: int = Field(default=0, ge=0, le=100)
    billing_shipping_mismatch: bool = False
    transactions_last_hour: int = Field(default=1, ge=0, le=1000)


class RiskAnalyzeRequest(BaseModel):
    customer_history: CustomerHistory = Field(default_factory=CustomerHistory)


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str = Field(min_length=1, max_length=100)
    razorpay_signature: str = Field(min_length=32, max_length=256)


class ResolveReviewRequest(BaseModel):
    resolved_by: str = Field(default="demo_operator", min_length=1, max_length=100)


class SettlementRecord(BaseModel):
    money_id: str = Field(min_length=1, max_length=64)
    expected_amount: float = Field(ge=0, le=10_000_000)
    received_amount: float = Field(ge=0, le=10_000_000)


class ReconciliationRequest(BaseModel):
    batch_id: str | None = Field(default=None, min_length=1, max_length=100)
    settlement_records: list[SettlementRecord] = Field(min_length=1, max_length=5000)


class EvaluationRequest(BaseModel):
    size: int = Field(default=250, ge=50, le=2000)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)


class AgenticRunRequest(BaseModel):
    money_id: str = Field(min_length=1, max_length=64)
    goal: str = Field(default="HANDLE_TRANSACTION", min_length=1, max_length=160)
    max_steps: int = Field(default=8, ge=1, le=20)
    execute_external_actions: bool = False


class AgenticResumeRequest(BaseModel):
    max_steps: int | None = Field(default=None, ge=1, le=20)
    execute_external_actions: bool | None = None
