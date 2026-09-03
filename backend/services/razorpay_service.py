"""Razorpay Test Mode integration helpers."""
from __future__ import annotations

import hashlib
import hmac
import os

try:
    import razorpay
except ImportError:  # lets non-payment tests run before optional dependency installation
    razorpay = None
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if razorpay and RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET else None


def is_configured() -> bool:
    return _client is not None


def create_order(amount_inr: float, receipt: str, notes: dict | None = None) -> dict:
    if not _client:
        raise RuntimeError("Razorpay is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")
    order = _client.order.create(
        {
            "amount": int(round(amount_inr * 100)),
            "currency": "INR",
            "receipt": receipt[:40],
            "notes": notes or {},
        }
    )
    return {
        "razorpay_order_id": order["id"],
        "amount": amount_inr,
        "amount_subunits": order["amount"],
        "currency": order["currency"],
        "key": RAZORPAY_KEY_ID,
    }


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    if not RAZORPAY_KEY_SECRET:
        raise RuntimeError("RAZORPAY_KEY_SECRET not configured")
    generated = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(generated, signature)


def fetch_payment(payment_id: str) -> dict:
    if not _client:
        raise RuntimeError("Razorpay is not configured")
    return _client.payment.fetch(payment_id)


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    if not RAZORPAY_WEBHOOK_SECRET:
        raise RuntimeError("RAZORPAY_WEBHOOK_SECRET not configured")
    expected = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_webhook_event(payload: dict) -> dict:
    event = payload.get("event", "")
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    return {
        "event": event,
        "razorpay_order_id": entity.get("order_id"),
        "razorpay_payment_id": entity.get("id"),
        "amount": (entity.get("amount") or 0) / 100,
        "status": entity.get("status"),
        "error_reason": entity.get("error_reason"),
        "error_description": entity.get("error_description"),
    }
