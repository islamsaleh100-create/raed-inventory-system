"""
Alerts Router — /api/v1/alerts
Epic 9: low-stock alerts, overdue orders, pending inventory approvals
"""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_current_active_user, require_roles
from app.database import get_db
from app.models import (
    Branch,
    BranchStock,
    DailyInventory,
    InventoryStatus,
    Item,
    OrderStatus,
    ReplenishmentOrder,
    User,
)

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])

_ALL_STAFF = (
    "branch_user", "branch_manager",
    "warehouse_user", "warehouse_manager",
    "admin", "super_admin",
)
_MGMT = ("branch_manager", "warehouse_manager", "admin", "super_admin")


# ──────────────────────────────────────────────────────────────────────────
# LOW-STOCK ALERTS
# ──────────────────────────────────────────────────────────────────────────

@router.get("/low-stock")
def low_stock_alerts(
    branch_id: Optional[int] = None,
    out_of_stock_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ALL_STAFF)),
):
    """
    Returns branch stock lines at or below item reorder point.
    Branch users are implicitly scoped to their own branch.
    """
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    if "branch_user" in user_roles or "branch_manager" in user_roles:
        branch_id = current_user.branch_id

    q = db.query(BranchStock).options(
        joinedload(BranchStock.item),
        joinedload(BranchStock.branch),
    ).join(Item, BranchStock.item_id == Item.id).filter(
        Item.is_deleted == False,
        Item.active == True,
    )

    if branch_id:
        q = q.filter(BranchStock.branch_id == branch_id)

    all_rows = q.all()

    if out_of_stock_only:
        filtered = [r for r in all_rows if r.current_qty <= 0]
    else:
        filtered = [
            r for r in all_rows
            if r.item and r.current_qty <= r.item.reorder_point
        ]

    total = len(filtered)
    page_rows = filtered[(page - 1) * page_size: page * page_size]

    return {
        "alert_type": "low_stock",
        "generated_at": datetime.utcnow().isoformat(),
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "branch_id": r.branch_id,
                "branch_name": r.branch.branch_name if r.branch else None,
                "item_id": r.item_id,
                "item_code": r.item.item_code if r.item else None,
                "item_name_ar": r.item.item_name_ar if r.item else None,
                "current_qty": float(r.current_qty),
                "reorder_point": float(r.item.reorder_point) if r.item else 0,
                "severity": "critical" if r.current_qty <= 0 else "warning",
            }
            for r in page_rows
        ],
    }


# ──────────────────────────────────────────────────────────────────────────
# OVERDUE ORDERS
# Orders that have been in a non-terminal status for too long
# ──────────────────────────────────────────────────────────────────────────

@router.get("/overdue-orders")
def overdue_orders_alerts(
    overdue_hours: int = Query(48, ge=1),
    branch_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT)),
):
    """
    Returns orders in non-terminal status that have not progressed
    for more than overdue_hours hours. Default: 48h.
    """
    _TERMINAL = {OrderStatus.closed, OrderStatus.cancelled, OrderStatus.received}
    cutoff = datetime.utcnow() - timedelta(hours=overdue_hours)

    q = db.query(ReplenishmentOrder).filter(
        ReplenishmentOrder.status.notin_([s.value for s in _TERMINAL]),
        ReplenishmentOrder.updated_at <= cutoff,
    )

    if branch_id:
        q = q.filter(ReplenishmentOrder.branch_id == branch_id)
    if warehouse_id:
        q = q.filter(ReplenishmentOrder.warehouse_id == warehouse_id)

    orders = q.order_by(ReplenishmentOrder.updated_at.asc()).all()

    return {
        "alert_type": "overdue_orders",
        "generated_at": datetime.utcnow().isoformat(),
        "overdue_threshold_hours": overdue_hours,
        "total": len(orders),
        "items": [
            {
                "order_id": o.id,
                "order_no": o.order_no,
                "branch_id": o.branch_id,
                "warehouse_id": o.warehouse_id,
                "status": o.status.value,
                "last_updated": o.updated_at.isoformat() if o.updated_at else None,
                "hours_stalled": round(
                    (datetime.utcnow() - o.updated_at).total_seconds() / 3600, 1
                ) if o.updated_at else None,
            }
            for o in orders
        ],
    }


# ──────────────────────────────────────────────────────────────────────────
# PENDING INVENTORY APPROVALS
# ──────────────────────────────────────────────────────────────────────────

@router.get("/pending-inventories")
def pending_inventory_alerts(
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT)),
):
    """
    Returns inventories in 'submitted' or 'pending_approval' status
    that are waiting for manager/admin approval.
    """
    _PENDING_STATUSES = [InventoryStatus.submitted, InventoryStatus.pending_approval]

    q = db.query(DailyInventory).filter(
        DailyInventory.status.in_(_PENDING_STATUSES)
    )
    if branch_id:
        q = q.filter(DailyInventory.branch_id == branch_id)

    inventories = q.order_by(DailyInventory.submitted_at.asc()).all()

    return {
        "alert_type": "pending_inventories",
        "generated_at": datetime.utcnow().isoformat(),
        "total": len(inventories),
        "items": [
            {
                "inventory_id": inv.id,
                "branch_id": inv.branch_id,
                "inventory_date": str(inv.inventory_date),
                "status": inv.status.value,
                "submitted_at": inv.submitted_at.isoformat() if inv.submitted_at else None,
                "hours_waiting": round(
                    (datetime.utcnow() - inv.submitted_at).total_seconds() / 3600, 1
                ) if inv.submitted_at else None,
            }
            for inv in inventories
        ],
    }


# ──────────────────────────────────────────────────────────────────────────
# MISSING TODAY'S INVENTORY
# Branches that haven't started today's inventory count
# ──────────────────────────────────────────────────────────────────────────

@router.get("/missing-inventory-today")
def missing_inventory_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT)),
):
    """
    Lists active branches that have NOT started today's inventory.
    """
    today = date.today()
    branches = db.query(Branch).filter(Branch.active == True, Branch.is_deleted == False).all()

    started_branch_ids = {
        inv.branch_id
        for inv in db.query(DailyInventory.branch_id).filter(
            DailyInventory.inventory_date == today
        ).all()
    }

    missing = [b for b in branches if b.id not in started_branch_ids]

    return {
        "alert_type": "missing_inventory_today",
        "date": str(today),
        "generated_at": datetime.utcnow().isoformat(),
        "total_active_branches": len(branches),
        "missing_count": len(missing),
        "missing_branches": [
            {"branch_id": b.id, "branch_name": b.branch_name}
            for b in missing
        ],
    }
