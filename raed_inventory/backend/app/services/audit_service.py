"""
Audit Log Service
─────────────────
Records who did what to which entity and when.

Usage (in any service or router):
    from app.services import audit_service
    audit_service.log(
        db,
        user_id=current_user.id,
        action="approve",
        module="inventory",
        entity_type="daily_inventory",
        entity_id=inventory.id,
        new_values={"status": "approved"},
        ip_address=request.client.host,
    )

Set AUDIT_LOG_ENABLED=false in .env to silently skip all writes (e.g. in tests).
"""
import json
import os
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import AuditLog, User


# Respect AUDIT_LOG_ENABLED env var — allows tests/scripts to skip writes.
# Evaluated per call so tests can toggle via os.environ without stale module state.
def _audit_writes_enabled() -> bool:
    return os.getenv("AUDIT_LOG_ENABLED", "true").lower() not in ("false", "0", "no")


# ──────────────────────────────────────────────────────────────────────────────
# WRITE
# ──────────────────────────────────────────────────────────────────────────────

def log(
    db: Session,
    *,
    user_id: Optional[int],
    action: str,
    module: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> Optional[AuditLog]:
    """
    Write one audit entry. Returns None if audit logging is disabled.
    Never raises — a failed audit write must never crash the main operation.
    """
    if not _audit_writes_enabled():
        return None

    def _serialise(v: Any) -> Optional[str]:
        if v is None:
            return None
        try:
            return json.dumps(v, default=_json_default, ensure_ascii=False)
        except Exception:
            return str(v)

    try:
        # Use a savepoint so a failed audit write never rolls back the caller's transaction.
        # begin_nested() creates a SAVEPOINT in PostgreSQL / a nested transaction in SQLite.
        with db.begin_nested():
            entry = AuditLog(
                user_id=user_id,
                action=action,
                module=module,
                entity_type=entity_type,
                entity_id=entity_id,
                old_values=_serialise(old_values),
                new_values=_serialise(new_values),
                ip_address=ip_address,
            )
            db.add(entry)
        return entry
    except Exception:
        # Savepoint was already rolled back; caller's transaction is intact.
        return None


def _json_default(obj: Any) -> Any:
    """JSON serialiser for types not handled by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "value"):          # Enum
        return obj.value
    return str(obj)


# ──────────────────────────────────────────────────────────────────────────────
# READ
# ──────────────────────────────────────────────────────────────────────────────

def get_logs(
    db: Session,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    module: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    q = db.query(AuditLog)

    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if module:
        q = q.filter(AuditLog.module == module)
    if action:
        q = q.filter(AuditLog.action == action)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if date_from:
        q = q.filter(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.filter(AuditLog.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = q.count()
    entries = (
        q.order_by(desc(AuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_entry_to_dict(e, db) for e in entries],
    }


def get_entity_history(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
) -> list[dict]:
    """Return full chronological history of a single entity."""
    entries = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        )
        .order_by(AuditLog.created_at)
        .all()
    )
    return [_entry_to_dict(e, db) for e in entries]


# ──────────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────────

def _entry_to_dict(entry: AuditLog, db: Session) -> dict:
    actor = db.query(User).filter(User.id == entry.user_id).first() if entry.user_id else None
    return {
        "id": entry.id,
        "action": entry.action,
        "module": entry.module,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "actor_id": entry.user_id,
        "actor_username": actor.username if actor else None,
        "old_values": _try_parse(entry.old_values),
        "new_values": _try_parse(entry.new_values),
        "ip_address": entry.ip_address,
        "created_at": entry.created_at,
    }


def _try_parse(text: Optional[str]) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return text
