"""
Audit Log Router — /api/v1/audit
"""
import csv
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.database import get_db
from app.models import AuditLog, User
from app.services import audit_service

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Log"])

_AUDIT_READ = ("internal_auditor", "admin", "super_admin")


@router.get("/logs")
def get_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    module: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_AUDIT_READ)),
):
    return audit_service.get_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        module=module,
        action=action,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get("/logs/export.csv")
def export_audit_logs_csv(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    module: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_AUDIT_READ)),
):
    payload = audit_service.get_logs(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        module=module,
        action=action,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=1,
        page_size=2000,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "created_at",
        "actor_username",
        "module",
        "action",
        "entity_type",
        "entity_id",
        "ip_address",
        "old_values",
        "new_values",
    ])
    for row in payload["items"]:
        writer.writerow([
            row.get("id"),
            row.get("created_at"),
            row.get("actor_username"),
            row.get("module"),
            row.get("action"),
            row.get("entity_type"),
            row.get("entity_id"),
            row.get("ip_address"),
            row.get("old_values"),
            row.get("new_values"),
        ])
    audit_service.log(
        db,
        user_id=current_user.id,
        action="audit_logs_export",
        module="audit",
        entity_type="audit_log",
        entity_id=None,
        new_values={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "module": module,
            "action": action,
            "user_id": user_id,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "count": len(payload["items"]),
        },
        ip_address=request.client.host if request and request.client else None,
    )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit_logs.csv"'},
    )


@router.get("/entity/{entity_type}/{entity_id}")
def get_entity_history(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_AUDIT_READ)),
):
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "history": audit_service.get_entity_history(db, entity_type=entity_type, entity_id=entity_id),
    }


@router.get("/modules")
def get_modules(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_AUDIT_READ)),
):
    rows = db.query(AuditLog.module).distinct().filter(AuditLog.module.isnot(None)).all()
    return sorted({r[0] for r in rows})


@router.get("/actions")
def get_actions(
    module: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_AUDIT_READ)),
):
    q = db.query(AuditLog.action).distinct().filter(AuditLog.action.isnot(None))
    if module:
        q = q.filter(AuditLog.module == module)
    rows = q.all()
    return sorted({r[0] for r in rows})
