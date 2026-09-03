"""Persistent, append-only, tamper-evident audit trail."""
from __future__ import annotations

import hashlib
import json
from models.money_state import AuditEntry
from services.database import AuditRow, SessionLocal
from services.clock import utc_now


class AuditLog:
    def record(self, money_id: str, actor: str, action: str, detail: dict | None = None) -> AuditEntry:
        detail = detail or {}
        now = utc_now()
        with SessionLocal() as db:
            previous = (
                db.query(AuditRow)
                .filter(AuditRow.money_id == money_id)
                .order_by(AuditRow.id.desc())
                .first()
            )
            previous_hash = previous.entry_hash if previous else "GENESIS"
            canonical = json.dumps(
                {
                    "money_id": money_id,
                    "actor": actor,
                    "action": action,
                    "detail": detail,
                    "timestamp": now.isoformat(),
                    "previous_hash": previous_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            entry_hash = hashlib.sha256(canonical.encode()).hexdigest()
            row = AuditRow(
                money_id=money_id,
                actor=actor,
                action=action,
                detail=detail,
                previous_hash=previous_hash,
                entry_hash=entry_hash,
                timestamp=now,
            )
            db.add(row)
            db.commit()
        return AuditEntry(
            money_id=money_id,
            actor=actor,
            action=action,
            detail=detail,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            timestamp=now,
        )

    def for_transaction(self, money_id: str) -> list[AuditEntry]:
        with SessionLocal() as db:
            rows = db.query(AuditRow).filter(AuditRow.money_id == money_id).order_by(AuditRow.id.asc()).all()
            return [self._to_model(r) for r in rows]

    def all(self, limit: int = 500) -> list[AuditEntry]:
        with SessionLocal() as db:
            rows = db.query(AuditRow).order_by(AuditRow.id.desc()).limit(limit).all()
            return [self._to_model(r) for r in reversed(rows)]

    def verify(self, money_id: str | None = None) -> dict:
        """Recompute every selected chain and report the first-class evidence."""
        with SessionLocal() as db:
            query = db.query(AuditRow)
            if money_id:
                query = query.filter(AuditRow.money_id == money_id)
            rows = query.order_by(AuditRow.money_id.asc(), AuditRow.id.asc()).all()

        previous_by_money: dict[str, str] = {}
        invalid: list[dict] = []
        for row in rows:
            expected_previous = previous_by_money.get(row.money_id, "GENESIS")
            canonical = json.dumps(
                {
                    "money_id": row.money_id,
                    "actor": row.actor,
                    "action": row.action,
                    "detail": row.detail or {},
                    "timestamp": row.timestamp.isoformat(),
                    "previous_hash": row.previous_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            expected_hash = hashlib.sha256(canonical.encode()).hexdigest()
            errors = []
            if row.previous_hash != expected_previous:
                errors.append("previous_hash_mismatch")
            if row.entry_hash != expected_hash:
                errors.append("entry_hash_mismatch")
            if errors:
                invalid.append({"id": row.id, "money_id": row.money_id, "errors": errors})
            previous_by_money[row.money_id] = row.entry_hash

        return {
            "valid": not invalid,
            "entries_checked": len(rows),
            "chains_checked": len(previous_by_money),
            "invalid_entries": invalid,
        }

    @staticmethod
    def _to_model(row: AuditRow) -> AuditEntry:
        return AuditEntry(
            money_id=row.money_id,
            actor=row.actor,
            action=row.action,
            detail=row.detail or {},
            previous_hash=row.previous_hash,
            entry_hash=row.entry_hash,
            timestamp=row.timestamp,
        )


audit_log = AuditLog()
