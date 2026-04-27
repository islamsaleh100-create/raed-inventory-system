"""
Sales Channels Router
/api/v1/sales-channels

RBAC policy — Model C "Delivery Accounts Manager" (2026-04-24):
    branch_manager    : own branch — writes daily sales, reads own branch data,
                        edits within fresh window (<=24h).
    area_manager      : own region — writes daily sales as SUBSTITUTE for a branch,
                        reads region data, approves late edits (24h-7d) with
                        edit_reason.
    sales_manager     : "Delivery Accounts Manager" — does NOT enter daily data.
                        Manages app statements, commission rates, monthly closures
                        (close + reopen with reason), views analytics across all
                        branches, and is the only non-admin editor allowed in the
                        stale window (>7d) with edit_reason.
    operations_manager: supervisory READ-only across all branches.
    admin             : explicit full access through permission predicates.
    super_admin       : platform-wide bypass.
    warehouse_manager : NOT authorized in this module.
"""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core import sales_permissions as perms
from app.core.auth import can_access_branch, get_current_active_user, get_user_roles
from app.database import get_db
from app.models import Branch
from app.models.sales_channels import BranchDailySale, MonthlyClosure
from app.schemas.sales_channels import (
    AppStatementCreate,
    AppStatementOut,
    CommissionRateUpdate,
    ComplianceReport,
    DailySaleBatchCreate,
    DailySaleOut,
    DailySaleUpdate,
    MonthlyClosureCreate,
    MonthlyClosureOut,
    MonthlyClosureReopen,
    ReconciliationReport,
    SalesChannelOut,
)
from app.services import sales_channels_service as svc

router = APIRouter(prefix="/api/v1/sales-channels", tags=["Sales Channels"])
logger = logging.getLogger(__name__)

def require_permission(predicate):
    """FastAPI dependency: pass iff predicate(user_roles) is True."""
    def checker(current_user=Depends(get_current_active_user)):
        if not predicate(get_user_roles(current_user)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {predicate.__name__}",
            )
        return current_user
    return checker


_CHANNELS_READ_ROLES = (
    "branch_manager",
    "area_manager",
    "operations_manager",
    "sales_manager",
)
# Superseded by app.core.sales_permissions.can_read_channels.
# Model C (2026-04-24): branch enters own data, area_manager substitutes for
# absent branch, sales_manager is NOT an operational entry role.
_DAILY_ENTRY_ROLES = ("branch_manager", "area_manager")
# Superseded by app.core.sales_permissions.can_create_daily_sales.
# PATCH /daily-sales/{id}: broader than create. The router only acts as a
# coarse gate; the service layer enforces per-window rules (fresh=branch_manager,
# 24h-7d=area_manager, >7d=sales_manager). We must admit all three at the
# router level so the stale-window edit is actually reachable.
_DAILY_EDIT_ROLES = ("branch_manager", "area_manager", "sales_manager")
# Superseded by app.core.sales_permissions.can_edit_daily_sales.
_DAILY_READ_ROLES = ("branch_manager", "area_manager", "operations_manager", "sales_manager")
# Superseded by app.core.sales_permissions.can_read_daily_sales.
_STATEMENT_WRITE_ROLES = ("sales_manager",)
# Superseded by app.core.sales_permissions.can_manage_statements / can_manage_commissions / can_close_month / can_reopen_month.
_RECON_READ_ROLES = ("branch_manager", "area_manager", "operations_manager", "sales_manager")
# Superseded by app.core.sales_permissions.can_read_reconciliation.
_COMPLIANCE_READ_ROLES = ("branch_manager", "area_manager", "operations_manager", "sales_manager")
# Superseded by app.core.sales_permissions.can_read_compliance.


def _month_bounds(month: str) -> tuple[date, date]:
    try:
        start = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM") from exc
    _, last_day = monthrange(start.year, start.month)
    end = date(start.year, start.month, last_day)
    return start, end


def _map_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, svc.MonthLockedError):
        return HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc))
    if isinstance(exc, svc.OrdersCountRuleError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, svc.EditWindowError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, svc.InvalidClosureError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, svc.SalesChannelsError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.exception("Unexpected sales channels exception: %s", exc)
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected sales channels error")


def _ensure_branch_scope(current_user, db: Session, branch_id: int) -> None:
    roles = set(get_user_roles(current_user))
    if "sales_manager" in roles or "operations_manager" in roles:
        return
    if not can_access_branch(current_user, branch_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for branch_id={branch_id}",
        )


def _resolve_branch_scope(current_user, db: Session, branch_id: Optional[int]) -> Optional[int]:
    roles = set(get_user_roles(current_user))
    if "sales_manager" in roles or "operations_manager" in roles:
        if branch_id is not None:
            _ensure_branch_scope(current_user, db, branch_id)
        return branch_id

    if "area_manager" in roles:
        if branch_id is None:
            return None
        _ensure_branch_scope(current_user, db, branch_id)
        return branch_id

    if "branch_manager" in roles:
        if current_user.branch_id is None:
            raise HTTPException(status_code=403, detail="branch_manager has no branch assigned")
        if branch_id is not None and branch_id != current_user.branch_id:
            raise HTTPException(status_code=403, detail="branch_manager can only access their own branch")
        return current_user.branch_id

    return branch_id


def _authorized_branch_ids(current_user, db: Session) -> Optional[list[int]]:
    roles = set(get_user_roles(current_user))
    if "sales_manager" in roles or "operations_manager" in roles:
        return None
    if "branch_manager" in roles:
        return [current_user.branch_id] if current_user.branch_id else []
    if "area_manager" in roles:
        if not current_user.branch_id:
            return []
        branches = db.query(Branch).filter(Branch.active.is_(True), Branch.is_deleted.is_(False)).all()
        return [branch.id for branch in branches if can_access_branch(current_user, branch.id, db)]
    return []


@router.get("/channels", response_model=list[SalesChannelOut])
def list_channels(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_read_channels)),
):
    return svc.list_channels(db)


@router.patch("/channels/{channel_id}/commission-rate", response_model=SalesChannelOut)
def patch_commission_rate(
    channel_id: int,
    payload: CommissionRateUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_manage_commissions)),
):
    try:
        channel = svc.update_commission_rate(
            db,
            channel_id=channel_id,
            commission_rate=payload.commission_rate,
        )
        db.commit()
        db.refresh(channel)
        return channel
    except Exception as exc:
        db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/daily-sales/batch", response_model=list[DailySaleOut], status_code=201)
def create_daily_sales_batch(
    payload: DailySaleBatchCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_create_daily_sales)),
):
    roles = set(get_user_roles(current_user))
    branch_id = payload.branch_id
    if "branch_manager" in roles:
        if current_user.branch_id is None:
            raise HTTPException(status_code=403, detail="branch_manager has no branch assigned")
        if branch_id != current_user.branch_id:
            raise HTTPException(status_code=403, detail="branch_manager can only submit for their own branch")
    else:
        _ensure_branch_scope(current_user, db, branch_id)

    try:
        rows = svc.create_daily_sale_batch(
            db,
            branch_id=branch_id,
            sales_date=payload.sales_date,
            lines=[line.model_dump() for line in payload.lines],
            submitted_by=current_user.id,
            submitter_roles=get_user_roles(current_user),
        )
        db.commit()
        for row in rows:
            db.refresh(row)
        return rows
    except Exception as exc:
        db.rollback()
        raise _map_service_error(exc) from exc


@router.patch("/daily-sales/{sale_id}", response_model=DailySaleOut)
def patch_daily_sale(
    sale_id: int,
    payload: DailySaleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_edit_daily_sales)),
):
    sale = db.query(BranchDailySale).filter(BranchDailySale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail=f"daily sale id={sale_id} not found")
    _ensure_branch_scope(current_user, db, sale.branch_id)

    try:
        updated = svc.update_daily_sale(
            db,
            sale_id=sale_id,
            amount=payload.amount,
            orders_count=payload.orders_count,
            edit_reason=payload.edit_reason,
            editor_id=current_user.id,
            editor_roles=get_user_roles(current_user),
        )
        db.commit()
        db.refresh(updated)
        return updated
    except Exception as exc:
        db.rollback()
        raise _map_service_error(exc) from exc


@router.get("/daily-sales", response_model=list[DailySaleOut])
def list_daily_sales(
    branch_id: Optional[int] = Query(default=None),
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_read_daily_sales)),
):
    scoped_branch_id = _resolve_branch_scope(current_user, db, branch_id)
    start, end = _month_bounds(month)

    q = db.query(BranchDailySale).filter(
        BranchDailySale.sales_date >= start,
        BranchDailySale.sales_date <= end,
    )
    if scoped_branch_id is not None:
        q = q.filter(BranchDailySale.branch_id == scoped_branch_id)
    else:
        allowed_ids = _authorized_branch_ids(current_user, db)
        if allowed_ids is not None:
            q = q.filter(BranchDailySale.branch_id.in_(allowed_ids or [-1]))

    return q.order_by(
        BranchDailySale.sales_date.desc(),
        BranchDailySale.branch_id.asc(),
        BranchDailySale.channel_id.asc(),
    ).all()


@router.post("/statements", response_model=AppStatementOut, status_code=201)
def create_statement(
    payload: AppStatementCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_manage_statements)),
):
    try:
        row = svc.create_monthly_statement(
            db,
            channel_id=payload.channel_id,
            branch_id=payload.branch_id,
            statement_month=payload.statement_month,
            app_reported_amount=payload.app_reported_amount,
            app_reported_count=payload.app_reported_count,
            commission_rate=payload.commission_rate,
            import_source=payload.import_source.value if hasattr(payload.import_source, "value") else str(payload.import_source),
            csv_filename=payload.csv_filename,
            created_by=current_user.id,
        )
        db.commit()
        db.refresh(row)
        return row
    except Exception as exc:
        db.rollback()
        raise _map_service_error(exc) from exc


@router.get("/reconciliation", response_model=ReconciliationReport)
def get_reconciliation(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    branch_id: Optional[int] = Query(default=None),
    channel_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_read_reconciliation)),
):
    scoped_branch_id = _resolve_branch_scope(current_user, db, branch_id)
    try:
        lines = svc.compute_reconciliation(
            db,
            month=month,
            branch_id=scoped_branch_id,
            channel_id=channel_id,
        )
        is_locked = False
        if scoped_branch_id is not None:
            is_locked = svc.is_month_locked(db, month, scoped_branch_id)
        return ReconciliationReport(
            month=month,
            branch_id=scoped_branch_id,
            lines=lines,
            generated_at=datetime.utcnow(),
            is_locked=is_locked,
        )
    except Exception as exc:
        raise _map_service_error(exc) from exc


@router.get("/closures", response_model=list[MonthlyClosureOut])
def list_closures(
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_read_reconciliation)),
):
    q = db.query(MonthlyClosure)
    if month:
        q = q.filter(MonthlyClosure.month == month)
    return q.order_by(MonthlyClosure.closed_at.desc(), MonthlyClosure.id.desc()).all()


@router.post("/closures", response_model=MonthlyClosureOut, status_code=201)
def create_closure(
    payload: MonthlyClosureCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_close_month)),
):
    if payload.branch_id is not None:
        _ensure_branch_scope(current_user, db, payload.branch_id)
    try:
        closure = svc.close_month(
            db,
            month=payload.month,
            scope_type=payload.scope_type.value if hasattr(payload.scope_type, "value") else str(payload.scope_type),
            branch_id=payload.branch_id,
            closed_by=current_user.id,
        )
        db.commit()
        db.refresh(closure)
        return closure
    except Exception as exc:
        db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/closures/{closure_id}/reopen", response_model=MonthlyClosureOut)
def reopen_closure(
    closure_id: int,
    payload: MonthlyClosureReopen,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_reopen_month)),
):
    try:
        closure = svc.reopen_month(
            db,
            closure_id=closure_id,
            reopened_by=current_user.id,
            reopen_reason=payload.reopen_reason,
        )
        db.commit()
        db.refresh(closure)
        return closure
    except Exception as exc:
        db.rollback()
        raise _map_service_error(exc) from exc


@router.get("/compliance", response_model=ComplianceReport)
def get_compliance(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(perms.can_read_compliance)),
):
    branch_ids = _authorized_branch_ids(current_user, db)
    rows = svc.compute_compliance(db, month=month, branch_ids=branch_ids)
    return ComplianceReport(month=month, rows=rows, generated_at=datetime.utcnow())
