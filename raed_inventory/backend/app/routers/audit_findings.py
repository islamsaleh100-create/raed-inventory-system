import csv
import io
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit_permissions import can_acknowledge_audit_finding, can_create_audit_finding
from app.core.auth import get_user_roles, require_roles
from app.database import get_db
from app.models import (
    AuditFinding,
    BranchRequest,
    BranchRequestStatus,
    DeliveryOrder,
    DeliveryOrderStatus,
    Item,
    ProductionOrder,
    ProductionOrderStatus,
    User,
    WarehouseLine,
    WarehouseLineStatus,
)
from app.schemas import AuditFindingAcknowledge, AuditFindingCreate, AuditFindingUpdate
from app.services import audit_service


router = APIRouter(prefix="/api/v1/audit/findings", tags=["Audit Findings"])

_READ_ROLES = ("internal_auditor", "admin", "super_admin", "operations_manager", "area_manager")


def _finding_to_dict(db: Session, row: AuditFinding) -> dict:
    created_by_name = db.query(User.full_name).filter(User.id == row.created_by).scalar()
    acknowledged_by_name = None
    if row.acknowledged_by:
        acknowledged_by_name = db.query(User.full_name).filter(User.id == row.acknowledged_by).scalar()
    return {
        "id": row.id,
        "finding_no": row.finding_no,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "severity": row.severity,
        "title": row.title,
        "description": row.description,
        "created_by": row.created_by,
        "created_by_name": created_by_name,
        "created_at": row.created_at,
        "acknowledged_by": row.acknowledged_by,
        "acknowledged_by_name": acknowledged_by_name,
        "acknowledged_at": row.acknowledged_at,
        "response_text": row.response_text,
        "status": row.status,
    }


def _next_finding_no(db: Session) -> str:
    last_id = db.query(func.max(AuditFinding.id)).scalar() or 0
    return f"AF-{last_id + 1:06d}"


def _audit_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _base_query(db: Session):
    return db.query(AuditFinding)


@router.get("")
def list_findings(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
    created_by: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_READ_ROLES)),
):
    q = _base_query(db)
    if severity:
        q = q.filter(AuditFinding.severity == severity)
    if status:
        q = q.filter(AuditFinding.status == status)
    if entity_type:
        q = q.filter(AuditFinding.entity_type == entity_type)
    if created_by:
        q = q.filter(AuditFinding.created_by == created_by)
    if from_date:
        q = q.filter(AuditFinding.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        q = q.filter(AuditFinding.created_at <= datetime.combine(to_date, time.max))
    total = q.count()
    rows = (
        q.order_by(AuditFinding.created_at.desc(), AuditFinding.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_finding_to_dict(db, row) for row in rows],
    }


@router.get("/export.csv")
def export_findings_csv(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
    created_by: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READ_ROLES)),
):
    q = _base_query(db)
    if severity:
        q = q.filter(AuditFinding.severity == severity)
    if status:
        q = q.filter(AuditFinding.status == status)
    if entity_type:
        q = q.filter(AuditFinding.entity_type == entity_type)
    if created_by:
        q = q.filter(AuditFinding.created_by == created_by)
    if from_date:
        q = q.filter(AuditFinding.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        q = q.filter(AuditFinding.created_at <= datetime.combine(to_date, time.max))
    rows = q.order_by(AuditFinding.created_at.desc(), AuditFinding.id.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "finding_no",
        "entity_type",
        "entity_id",
        "severity",
        "status",
        "title",
        "description",
        "created_by",
        "created_by_name",
        "created_at",
        "acknowledged_by",
        "acknowledged_by_name",
        "acknowledged_at",
        "response_text",
    ])
    for row in rows:
        payload = _finding_to_dict(db, row)
        writer.writerow([
            payload["finding_no"],
            payload["entity_type"],
            payload["entity_id"],
            payload["severity"],
            payload["status"],
            payload["title"],
            payload["description"],
            payload["created_by"],
            payload["created_by_name"],
            payload["created_at"].isoformat() if payload["created_at"] else "",
            payload["acknowledged_by"],
            payload["acknowledged_by_name"],
            payload["acknowledged_at"].isoformat() if payload["acknowledged_at"] else "",
            payload["response_text"] or "",
        ])
    audit_service.log(
        db,
        user_id=current_user.id,
        action="audit_findings_export",
        module="audit",
        entity_type="audit_finding",
        entity_id=None,
        new_values={
            "severity": severity,
            "status": status,
            "entity_type": entity_type,
            "created_by": created_by,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "count": len(rows),
        },
        ip_address=_audit_ip(request),
    )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit_findings.csv"'},
    )


@router.get("/{finding_id}")
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_READ_ROLES)),
):
    row = db.query(AuditFinding).filter(AuditFinding.id == finding_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Audit finding not found")
    return _finding_to_dict(db, row)


@router.post("")
def create_finding(
    payload: AuditFindingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READ_ROLES)),
):
    roles = get_user_roles(current_user)
    if not can_create_audit_finding(roles):
        raise HTTPException(status_code=403, detail="You cannot create audit findings")
    row = AuditFinding(
        finding_no=_next_finding_no(db),
        entity_type=payload.entity_type.strip(),
        entity_id=payload.entity_id,
        severity=payload.severity,
        title=payload.title.strip(),
        description=payload.description.strip(),
        created_by=current_user.id,
        status="open",
    )
    db.add(row)
    db.flush()
    audit_service.log(
        db,
        user_id=current_user.id,
        action="audit_finding_create",
        module="audit",
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        new_values={"finding_no": row.finding_no, "severity": row.severity, "title": row.title},
        ip_address=_audit_ip(request),
    )
    db.commit()
    db.refresh(row)
    return _finding_to_dict(db, row)


@router.patch("/{finding_id}")
def update_finding(
    finding_id: int,
    payload: AuditFindingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READ_ROLES)),
):
    row = db.query(AuditFinding).filter(AuditFinding.id == finding_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Audit finding not found")
    if row.created_by != current_user.id and "super_admin" not in get_user_roles(current_user):
        raise HTTPException(status_code=403, detail="You can only edit your own finding")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _finding_to_dict(db, row)
    before = _finding_to_dict(db, row)
    for key, value in changes.items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    audit_service.log(
        db,
        user_id=current_user.id,
        action="audit_finding_update",
        module="audit",
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        old_values=before,
        new_values=changes,
        ip_address=_audit_ip(request),
    )
    db.commit()
    db.refresh(row)
    return _finding_to_dict(db, row)


@router.post("/{finding_id}/acknowledge")
def acknowledge_finding(
    finding_id: int,
    payload: AuditFindingAcknowledge,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READ_ROLES)),
):
    roles = get_user_roles(current_user)
    if not can_acknowledge_audit_finding(roles):
        raise HTTPException(status_code=403, detail="You cannot acknowledge findings")
    row = db.query(AuditFinding).filter(AuditFinding.id == finding_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Audit finding not found")
    row.acknowledged_by = current_user.id
    row.acknowledged_at = datetime.utcnow()
    row.response_text = payload.response_text.strip()
    row.status = "acknowledged"
    audit_service.log(
        db,
        user_id=current_user.id,
        action="audit_finding_acknowledge",
        module="audit",
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        new_values={"finding_no": row.finding_no, "response_text": row.response_text, "status": row.status},
        ip_address=_audit_ip(request),
    )
    db.commit()
    db.refresh(row)
    return _finding_to_dict(db, row)


@router.get("/by-entity/{entity_type}/{entity_id}")
def findings_by_entity(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_READ_ROLES)),
):
    rows = (
        db.query(AuditFinding)
        .filter(AuditFinding.entity_type == entity_type, AuditFinding.entity_id == entity_id)
        .order_by(AuditFinding.created_at.desc(), AuditFinding.id.desc())
        .all()
    )
    return [_finding_to_dict(db, row) for row in rows]


@router.get("/dashboard/summary")
def audit_dashboard_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_READ_ROLES)),
):
    now = datetime.utcnow()
    recent_threshold = now - timedelta(days=30)
    week_threshold = now - timedelta(days=7)
    open_findings_total = db.query(AuditFinding).filter(AuditFinding.status == "open").count()
    violations_open = db.query(AuditFinding).filter(AuditFinding.status == "open", AuditFinding.severity == "violation").count()
    warnings_open = db.query(AuditFinding).filter(AuditFinding.status == "open", AuditFinding.severity == "warning").count()
    info_open = db.query(AuditFinding).filter(AuditFinding.status == "open", AuditFinding.severity == "info").count()
    findings_created_last_7_days = db.query(AuditFinding).filter(AuditFinding.created_at >= week_threshold).count()
    unacknowledged_findings_older_than_7_days = db.query(AuditFinding).filter(
        AuditFinding.status == "open",
        AuditFinding.created_at < week_threshold,
    ).count()

    fast_approvals = (
        db.query(
            User.username.label("area_manager"),
            func.count(BranchRequest.id).label("count"),
        )
        .join(User, User.id == BranchRequest.approved_by)
        .filter(
            BranchRequest.status.in_([BranchRequestStatus.AREA_APPROVED, BranchRequestStatus.SPLIT, BranchRequestStatus.IN_EXECUTION, BranchRequestStatus.DELIVERED]),
            BranchRequest.submitted_at.isnot(None),
            BranchRequest.approved_at.isnot(None),
            BranchRequest.approved_at >= recent_threshold,
            func.extract("epoch", BranchRequest.approved_at - BranchRequest.submitted_at) < 30,
        )
        .group_by(User.username)
        .order_by(func.count(BranchRequest.id).desc(), User.username.asc())
        .limit(10)
        .all()
    )

    partial_issues_without_reason = db.query(WarehouseLine).filter(
        WarehouseLine.status == WarehouseLineStatus.PARTIAL,
        func.coalesce(WarehouseLine.delay_reason, "") == "",
    ).count()

    average_approval_time_seconds = (
        db.query(
            func.avg(
                func.extract("epoch", BranchRequest.approved_at - BranchRequest.submitted_at)
            )
        )
        .filter(
            BranchRequest.submitted_at.isnot(None),
            BranchRequest.approved_at.isnot(None),
            BranchRequest.approved_at >= recent_threshold,
        )
        .scalar()
    )

    top_variance_items = (
        db.query(
            Item.item_name_en.label("item_name"),
            func.count(WarehouseLine.id).label("count"),
        )
        .join(Item, Item.id == WarehouseLine.item_id)
        .filter(WarehouseLine.status.in_([WarehouseLineStatus.PARTIAL, WarehouseLineStatus.BACKORDER]))
        .group_by(Item.item_name_en)
        .order_by(func.count(WarehouseLine.id).desc(), Item.item_name_en.asc())
        .limit(10)
        .all()
    )

    findings_by_entity_type = (
        db.query(
            AuditFinding.entity_type.label("entity_type"),
            func.count(AuditFinding.id).label("count"),
        )
        .group_by(AuditFinding.entity_type)
        .order_by(func.count(AuditFinding.id).desc(), AuditFinding.entity_type.asc())
        .limit(10)
        .all()
    )

    oldest_open_findings = (
        db.query(AuditFinding)
        .filter(AuditFinding.status == "open")
        .order_by(AuditFinding.created_at.asc(), AuditFinding.id.asc())
        .limit(10)
        .all()
    )

    return {
        "open_findings_total": open_findings_total,
        "violations_open": violations_open,
        "warnings_open": warnings_open,
        "info_open": info_open,
        "findings_created_last_7_days": findings_created_last_7_days,
        "unacknowledged_findings_older_than_7_days": unacknowledged_findings_older_than_7_days,
        "average_approval_time_seconds": float(average_approval_time_seconds or 0),
        "delays_without_reason": partial_issues_without_reason,
        "fast_approvals_under_30_seconds": [
            {"area_manager": row.area_manager, "count": int(row.count)} for row in fast_approvals
        ],
        "partial_issues_without_reason": partial_issues_without_reason,
        "top_variance_items": [
            {"item_name": row.item_name, "count": int(row.count)} for row in top_variance_items
        ],
        "findings_by_entity_type": [
            {"entity_type": row.entity_type, "count": int(row.count)} for row in findings_by_entity_type
        ],
        "oldest_open_findings": [
            {
                "finding_no": row.finding_no,
                "title": row.title,
                "severity": row.severity,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "age_days": max(int((now - row.created_at).total_seconds() // 86400), 0) if row.created_at else 0,
            }
            for row in oldest_open_findings
        ],
        "active_supply_chain_backlog": {
            "branch_requests_submitted": db.query(BranchRequest).filter(BranchRequest.status == BranchRequestStatus.SUBMITTED).count(),
            "production_open": db.query(ProductionOrder).filter(
                ProductionOrder.status.in_([
                    ProductionOrderStatus.PENDING,
                    ProductionOrderStatus.IN_PROGRESS,
                    ProductionOrderStatus.WAITING_FOR_MATERIALS,
                    ProductionOrderStatus.PARTIAL_READY,
                ])
            ).count(),
            "warehouse_open": db.query(WarehouseLine).filter(
                WarehouseLine.status.in_([
                    WarehouseLineStatus.PENDING,
                    WarehouseLineStatus.AVAILABLE,
                    WarehouseLineStatus.PARTIAL,
                    WarehouseLineStatus.BACKORDER,
                    WarehouseLineStatus.READY_FOR_DISPATCH,
                ])
            ).count(),
            "delivery_open": db.query(DeliveryOrder).filter(
                DeliveryOrder.status.in_([
                    DeliveryOrderStatus.READY,
                    DeliveryOrderStatus.OUT_FOR_DELIVERY,
                    DeliveryOrderStatus.PARTIAL_DELIVERED,
                ])
            ).count(),
        },
    }
