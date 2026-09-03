"""SQLite persistence for RupeeOS.

The demo uses SQLite by default so the Money State Graph survives process restarts.
Set RUPEEOS_DATABASE_URL to a SQLAlchemy URL (for example PostgreSQL) to swap
storage without changing the service layer.
"""
from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from services.clock import utc_now

DATABASE_URL = os.getenv("RUPEEOS_DATABASE_URL", "sqlite:///./rupeeos.db")

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class TransactionRow(Base):
    __tablename__ = "transactions"

    money_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(128), index=True)
    customer_name: Mapped[str] = mapped_column(String(160), default="Customer")
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    state: Mapped[str] = mapped_column(String(40), index=True)
    product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    addon_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    risk_factors: Mapped[list] = mapped_column(JSON, default=list)
    failure_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    recovery_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    settlement_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    reconciliation_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class PaymentAttemptRow(Base):
    __tablename__ = "payment_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    money_id: Mapped[str] = mapped_column(String(64), index=True)
    razorpay_order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="PRIMARY")
    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PolicyDecisionRow(Base):
    __tablename__ = "policy_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    money_id: Mapped[str] = mapped_column(String(64), index=True)
    approved: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AuditRow(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    money_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    previous_hash: Mapped[str] = mapped_column(String(64), default="GENESIS")
    entry_hash: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class WebhookEventRow(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    money_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="RECEIVED")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ManualReviewRow(Base):
    __tablename__ = "manual_reviews"

    review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    money_id: Mapped[str] = mapped_column(String(64), index=True)
    review_type: Mapped[str] = mapped_column(String(32))
    proposed_action: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ReconciliationBatchRow(Base):
    __tablename__ = "reconciliation_batches"

    batch_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AgentRunRow(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    money_id: Mapped[str] = mapped_column(String(64), index=True)
    agent: Mapped[str] = mapped_column(String(40), index=True)
    engine: Mapped[str] = mapped_column(String(80), default="rules-v1")
    mode: Mapped[str] = mapped_column(String(32), default="deterministic")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class AgentWorkflowRow(Base):
    """Durable supervisor run with its complete, inspectable reasoning trace."""

    __tablename__ = "agent_workflows"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    money_id: Mapped[str] = mapped_column(String(64), index=True)
    goal: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), index=True)
    current_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    max_steps: Mapped[int] = mapped_column(Integer, default=8)
    steps_used: Mapped[int] = mapped_column(Integer, default=0)
    execute_external_actions: Mapped[bool] = mapped_column(Boolean, default=False)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    pending_checkout: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
