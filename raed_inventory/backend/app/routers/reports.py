"""
Reports Router — /api/v1/reports
Epic 8: compliance report, order summary, variance trend
"""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_roles
from app.core.errors import AppError
from app.database import get_db
from app.models import (
    Branch,
    DailyInventory,
    DailyInventoryLine,
    InventoryStatus,
    OrderStatus,
    ReplenishmentOrder,
    User,
)

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

_MGMT_ROLES = ("branch_manager", "warehouse_manager", "admin", "super_admin")


# ──────────────────────────────────────────────────────────────────────────
# INVENTORY COMPLIANCE REPORT
# Reports which branches submitted/approved inventories in a date range.
# ──────────────────────────────────────────────────────────────────────────

@router.get("/inventory-compliance")
def inventory_compliance_report(
    date_from: date,
    date_to: date,
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT_ROLES)),
):
    """
    Returns per-branch, per-day compliance: whether an inventory was submitted/approved.
    date_from → date_to inclusive (max 90 days).
    """
    delta_days = (date_to - date_from).days
    if delta_days < 0:
        raise AppError(
            status_code=400,
            error_code="reports.invalid_date_range",
            message="date_from must be <= date_to",
            detail={},
        )
    if delta_days > 90:
        raise AppError(
            status_code=400,
            error_code="reports.date_range_too_wide",
            message="Date range cannot exceed 90 days",
            detail={"max_days": 90},
        )

    # Fetch all active branches
    branch_q = db.query(Branch).filter(Branch.active == True)
    if branch_id:
        branch_q = branch_q.filter(Branch.id == branch_id)
    branches = branch_q.all()

    # Fetch all inventories in range
    inv_q = db.query(DailyInventory).filter(
        DailyInventory.inventory_date >= date_from,
        DailyInventory.inventory_date <= date_to,
    )
    if branch_id:
        inv_q = inv_q.filter(DailyInventory.branch_id == branch_id)
    inventories = inv_q.all()

    # Index: (branch_id, date) → inventory
    inv_map = {(i.branch_id, i.inventory_date): i for i in inventories}

    # Build date list
    day_count = delta_days + 1
    dates = [date_from + timedelta(days=d) for d in range(day_count)]

    rows = []
    for branch in branches:
        branch_row = {
            "branch_id": branch.id,
            "branch_name": branch.branch_name,
            "days": [],
        }
        submitted_count = 0
        approved_count = 0
        missing_count = 0

        for d in dates:
            inv = inv_map.get((branch.id, d))
            if inv is None:
                status = "missing"
                missing_count += 1
            elif inv.status == InventoryStatus.approved:
                status = "approved"
                approved_count += 1
            elif inv.status in (InventoryStatus.submitted, InventoryStatus.pending_approval):
                status = "submitted"
                submitted_count += 1
            else:
                status = inv.status.value

            branch_row["days"].append({
                "date": str(d),
                "status": status,
                "inventory_id": inv.id if inv else None,
            })

        branch_row["summary"] = {
            "total_days": day_count,
            "approved": approved_count,
            "submitted": submitted_count,
            "missing": missing_count,
            "compliance_pct": round(approved_count / day_count * 100, 1) if day_count > 0 else 0,
        }
        rows.append(branch_row)

    return {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "branches": rows,
    }


# ──────────────────────────────────────────────────────────────────────────
# ORDER SUMMARY REPORT
# ──────────────────────────────────────────────────────────────────────────

@router.get("/order-summary")
def order_summary_report(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    branch_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT_ROLES)),
):
    """
    Summary of orders grouped by status in the given date range.
    """
    q = db.query(ReplenishmentOrder)
    if date_from:
        q = q.filter(ReplenishmentOrder.order_date >= date_from)
    if date_to:
        q = q.filter(ReplenishmentOrder.order_date <= date_to)
    if branch_id:
        q = q.filter(ReplenishmentOrder.branch_id == branch_id)
    if warehouse_id:
        q = q.filter(ReplenishmentOrder.warehouse_id == warehouse_id)

    orders = q.all()

    status_counts = {}
    for order in orders:
        key = order.status.value
        status_counts[key] = status_counts.get(key, 0) + 1

    total = len(orders)
    closed = status_counts.get("closed", 0)
    cancelled = status_counts.get("cancelled", 0)
    pending = total - closed - cancelled

    return {
        "date_from": str(date_from) if date_from else None,
        "date_to": str(date_to) if date_to else None,
        "total_orders": total,
        "closed_orders": closed,
        "cancelled_orders": cancelled,
        "pending_orders": pending,
        "by_status": status_counts,
    }


# ──────────────────────────────────────────────────────────────────────────
# VARIANCE TREND REPORT
# Average variance % per branch per week/month
# ──────────────────────────────────────────────────────────────────────────

@router.get("/variance-trend")
def variance_trend_report(
    branch_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT_ROLES)),
):
    """
    Returns average absolute variance % per branch for approved inventories.
    Useful for spotting systematic counting issues over time.
    """
    q = db.query(
        DailyInventory.branch_id,
        Branch.branch_name.label("branch_name"),
        DailyInventory.inventory_date,
        DailyInventory.inventory_type.label("inventory_type"),
        func.avg(func.abs(DailyInventoryLine.variance_pct)).label("avg_variance_pct"),
        func.count(DailyInventoryLine.id).label("line_count"),
        func.sum(
            case((DailyInventoryLine.variance_status == "critical", 1), else_=0)
        ).label("critical_lines"),
        func.sum(
            case((DailyInventoryLine.variance_qty > 0, 1), else_=0)
        ).label("surplus_lines"),
    ).join(
        DailyInventoryLine,
        DailyInventoryLine.inventory_id == DailyInventory.id,
    ).join(
        Branch,
        Branch.id == DailyInventory.branch_id,
    ).filter(
        DailyInventory.status == InventoryStatus.approved,
        DailyInventoryLine.variance_qty != 0,
    )

    if branch_id:
        q = q.filter(DailyInventory.branch_id == branch_id)
    if date_from:
        q = q.filter(DailyInventory.inventory_date >= date_from)
    if date_to:
        q = q.filter(DailyInventory.inventory_date <= date_to)

    rows = q.group_by(
        DailyInventory.branch_id,
        Branch.branch_name,
        DailyInventory.inventory_date,
        DailyInventory.inventory_type,
    ).order_by(
        DailyInventory.inventory_date.desc(),
    ).all()

    return {
        "date_from": str(date_from) if date_from else None,
        "date_to": str(date_to) if date_to else None,
        "items": [
            {
                "branch_id": r.branch_id,
                "branch_name": r.branch_name,
                "inventory_date": str(r.inventory_date),
                "inventory_type": r.inventory_type or "daily",
                "avg_variance_pct": round(float(r.avg_variance_pct or 0), 2),
                "line_count": r.line_count,
                "critical_lines": r.critical_lines or 0,
                "surplus_lines": r.surplus_lines or 0,
            }
            for r in rows
        ],
    }
