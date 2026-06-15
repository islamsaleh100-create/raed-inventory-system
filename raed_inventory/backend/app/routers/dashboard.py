"""
Dashboard & Reports Router
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from typing import Optional
from datetime import date, datetime, timedelta
from app.database import get_db
from app.core.auth import (
    get_current_active_user,
    require_roles,
    can_access_branch,
    can_access_warehouse,
)
from app.models import (
    Branch,
    Warehouse,
    DailyInventory,
    ReplenishmentOrder,
    ReplenishmentOrderLine,
    BranchStock,
    WarehouseStock,
    Item,
    User,
    OrderStatus,
    InventoryStatus,
    StockTransaction,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/branch/{branch_id}")
def branch_dashboard(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not can_access_branch(current_user, branch_id, db):
        raise HTTPException(status_code=403, detail="Access denied for this branch")
    today = date.today()
    branch = db.query(Branch).filter(Branch.id == branch_id).first()

    # Today's inventory
    today_inv = (
        db.query(DailyInventory)
        .filter(
            DailyInventory.branch_id == branch_id,
            DailyInventory.inventory_date == today,
        )
        .first()
    )

    # Stock alerts
    stock = (
        db.query(BranchStock)
        .options(joinedload(BranchStock.item))
        .filter(BranchStock.branch_id == branch_id)
        .all()
    )
    items_below_min = sum(1 for s in stock if s.current_qty < s.item.min_qty if s.item)
    items_out_of_stock = sum(1 for s in stock if s.current_qty <= 0)

    # Open orders
    open_orders = (
        db.query(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.branch_id == branch_id,
            ReplenishmentOrder.status.in_(
                [
                    OrderStatus.system_generated,
                    OrderStatus.branch_reviewed,
                    OrderStatus.submitted_to_warehouse,
                    OrderStatus.under_review,
                    OrderStatus.approved,
                    OrderStatus.partially_approved,
                    OrderStatus.picking,
                ]
            ),
        )
        .count()
    )

    pending_receiving = (
        db.query(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.branch_id == branch_id,
            ReplenishmentOrder.status == OrderStatus.dispatched,
        )
        .count()
    )

    # Last 7 days inventory compliance
    week_ago = today - timedelta(days=7)
    inv_count = (
        db.query(DailyInventory)
        .filter(
            DailyInventory.branch_id == branch_id,
            DailyInventory.inventory_date >= week_ago,
            DailyInventory.status == InventoryStatus.approved,
        )
        .count()
    )
    compliance_rate = round(inv_count / 7 * 100)

    # Critical items below threshold
    critical_items_alert = (
        db.query(BranchStock)
        .join(Item)
        .filter(
            BranchStock.branch_id == branch_id,
            Item.critical_item == True,
            BranchStock.current_qty <= Item.reorder_point,
        )
        .count()
    )

    return {
        "branch_id": branch_id,
        "branch_name": branch.branch_name if branch else "",
        "today_inventory_status": today_inv.status if today_inv else None,
        "items_below_min": items_below_min,
        "items_out_of_stock": items_out_of_stock,
        "open_orders": open_orders,
        "pending_receiving": pending_receiving,
        "weekly_compliance_rate": compliance_rate,
        "critical_items_alert": critical_items_alert,
    }


@router.get("/warehouse/{warehouse_id}")
def warehouse_dashboard(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not can_access_warehouse(current_user, warehouse_id):
        raise HTTPException(status_code=403, detail="Access denied for this warehouse")
    today = date.today()
    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()

    pending_orders = (
        db.query(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.warehouse_id == warehouse_id,
            ReplenishmentOrder.status == OrderStatus.submitted_to_warehouse,
        )
        .count()
    )

    under_review = (
        db.query(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.warehouse_id == warehouse_id,
            ReplenishmentOrder.status == OrderStatus.under_review,
        )
        .count()
    )

    approved_orders = (
        db.query(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.warehouse_id == warehouse_id,
            ReplenishmentOrder.status.in_(
                [OrderStatus.approved, OrderStatus.partially_approved]
            ),
        )
        .count()
    )

    in_picking = (
        db.query(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.warehouse_id == warehouse_id,
            ReplenishmentOrder.status == OrderStatus.picking,
        )
        .count()
    )

    dispatched_today = (
        db.query(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.warehouse_id == warehouse_id,
            ReplenishmentOrder.status == OrderStatus.dispatched,
            func.date(ReplenishmentOrder.dispatched_at) == today,
        )
        .count()
    )

    shortage_items = (
        db.query(ReplenishmentOrderLine)
        .join(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.warehouse_id == warehouse_id,
            ReplenishmentOrderLine.shortage_flag == True,
            ReplenishmentOrder.status.in_(
                [OrderStatus.dispatched, OrderStatus.received]
            ),
        )
        .count()
    )

    # Fill rate: approved vs requested (آخر 7 أيام حسب order_date — كان مقيداً بـ «اليوم» فقط فيرجع 0 غالباً)
    week_ago = today - timedelta(days=7)
    total_requested = (
        db.query(func.sum(ReplenishmentOrderLine.branch_requested_qty))
        .join(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.warehouse_id == warehouse_id,
            ReplenishmentOrder.order_date >= week_ago,
            ReplenishmentOrder.order_date <= today,
        )
        .scalar()
        or 0
    )

    total_approved = (
        db.query(func.sum(ReplenishmentOrderLine.wh_approved_qty))
        .join(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.warehouse_id == warehouse_id,
            ReplenishmentOrder.order_date >= week_ago,
            ReplenishmentOrder.order_date <= today,
        )
        .scalar()
        or 0
    )

    fill_rate = (
        round(float(total_approved) / float(total_requested) * 100)
        if total_requested > 0
        else 0
    )

    return {
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse.warehouse_name if warehouse else "",
        "pending_orders": pending_orders,
        "under_review": under_review,
        "approved_orders": approved_orders,
        "orders_in_picking": in_picking,
        "ready_to_dispatch": in_picking,
        "dispatched_today": dispatched_today,
        "stock_shortage_items": shortage_items,
        "fill_rate": fill_rate,
    }


@router.get("/operations")
def operations_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("operations_manager", "admin", "super_admin")
    ),
):
    today = date.today()
    week_ago = today - timedelta(days=7)

    branches = db.query(Branch).filter(Branch.active == True).all()
    total_branches = len(branches)

    # Branch compliance
    branches_with_inventory = (
        db.query(DailyInventory.branch_id)
        .filter(
            DailyInventory.inventory_date == today,
            DailyInventory.status == InventoryStatus.approved,
        )
        .distinct()
        .count()
    )

    compliance_rate = (
        round(branches_with_inventory / total_branches * 100)
        if total_branches > 0
        else 0
    )

    # Global stock alerts
    total_out_of_stock = (
        db.query(BranchStock).filter(BranchStock.current_qty <= 0).count()
    )

    total_below_min = (
        db.query(BranchStock)
        .join(Item)
        .filter(BranchStock.current_qty < Item.min_qty, BranchStock.current_qty > 0)
        .count()
    )

    # Order stats
    total_orders_today = (
        db.query(ReplenishmentOrder)
        .filter(func.date(ReplenishmentOrder.created_at) == today)
        .count()
    )

    rejected_orders = (
        db.query(ReplenishmentOrder)
        .filter(
            func.date(ReplenishmentOrder.created_at) == today,
            ReplenishmentOrder.status == OrderStatus.rejected,
        )
        .count()
    )

    # Top requested items (last 7 days)
    top_items = (
        db.query(
            ReplenishmentOrderLine.item_id,
            func.sum(ReplenishmentOrderLine.branch_requested_qty).label(
                "total_requested"
            ),
        )
        .join(ReplenishmentOrder)
        .filter(ReplenishmentOrder.order_date >= week_ago)
        .group_by(ReplenishmentOrderLine.item_id)
        .order_by(func.sum(ReplenishmentOrderLine.branch_requested_qty).desc())
        .limit(10)
        .all()
    )

    top_items_data = []
    if top_items:
        item_ids = [row[0] for row in top_items]
        items_by_id = {
            row.id: row
            for row in db.query(Item).filter(Item.id.in_(item_ids)).all()
        }
        for item_id, total in top_items:
            item = items_by_id.get(item_id)
            if item:
                top_items_data.append(
                    {
                        "item_code": item.item_code,
                        "item_name_ar": item.item_name_ar,
                        "item_name_en": item.item_name_en,
                        "total_requested": float(total),
                    }
                )

    shortage_by_branch = (
        db.query(
            ReplenishmentOrder.branch_id,
            func.count(ReplenishmentOrderLine.id).label("shortage_count"),
        )
        .join(ReplenishmentOrderLine)
        .filter(
            ReplenishmentOrderLine.shortage_flag == True,
            ReplenishmentOrder.order_date >= week_ago,
        )
        .group_by(ReplenishmentOrder.branch_id)
        .order_by(func.count(ReplenishmentOrderLine.id).desc())
        .limit(5)
        .all()
    )

    shortage_branch_data = []
    if shortage_by_branch:
        branch_ids = [row[0] for row in shortage_by_branch]
        branches_by_id = {
            row.id: row
            for row in db.query(Branch).filter(Branch.id.in_(branch_ids)).all()
        }
        for branch_id, count in shortage_by_branch:
            branch = branches_by_id.get(branch_id)
            if branch:
                shortage_branch_data.append(
                    {
                        "branch_id": branch_id,
                        "branch_name": branch.branch_name
                        if hasattr(branch, "branch_name")
                        else "",
                        "shortage_count": count,
                    }
                )

    return {
        "total_branches": total_branches,
        "branches_with_inventory_today": branches_with_inventory,
        "compliance_rate": compliance_rate,
        "total_out_of_stock_items": total_out_of_stock,
        "total_below_min_items": total_below_min,
        "total_orders_today": total_orders_today,
        "rejected_orders_today": rejected_orders,
        "top_requested_items": top_items_data,
        "top_branches_by_shortages": shortage_branch_data,
    }


@router.get("/stock/branch/{branch_id}")
def branch_stock_status(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not can_access_branch(current_user, branch_id, db):
        raise HTTPException(status_code=403, detail="Access denied for this branch")
    stocks = (
        db.query(BranchStock)
        .options(joinedload(BranchStock.item))
        .filter(BranchStock.branch_id == branch_id)
        .all()
    )

    result = []
    for s in stocks:
        item = s.item
        if not item or not item.active:
            continue
        status = "ok"
        if float(s.current_qty) <= 0:
            status = "out_of_stock"
        elif float(s.current_qty) < float(item.min_qty):
            status = "below_min"
        elif float(s.current_qty) <= float(item.reorder_point):
            status = "reorder"

        result.append(
            {
                "item_id": item.id,
                "item_code": item.item_code,
                "item_name_ar": item.item_name_ar,
                "item_name_en": item.item_name_en,
                "current_qty": float(s.current_qty),
                "in_transit_qty": float(s.in_transit_qty),
                "min_qty": float(item.min_qty),
                "reorder_point": float(item.reorder_point),
                "critical_item": item.critical_item,
                "status": status,
            }
        )

    return result


@router.get("/stock/warehouse/{warehouse_id}")
def warehouse_stock_status(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not can_access_warehouse(current_user, warehouse_id):
        raise HTTPException(status_code=403, detail="Access denied for this warehouse")
    stocks = (
        db.query(WarehouseStock)
        .options(joinedload(WarehouseStock.item))
        .filter(WarehouseStock.warehouse_id == warehouse_id)
        .all()
    )

    return [
        {
            "item_id": s.item.id if s.item else s.item_id,
            "item_code": s.item.item_code,
            "item_name_ar": s.item.item_name_ar,
            "current_qty": float(s.current_qty),
            "reserved_qty": float(s.reserved_qty),
        }
        for s in stocks
        if s.item
    ]


# ──────────────────────────────────────────────────────────────────────────
# EPIC 11 — Enhanced dashboard endpoints
# ──────────────────────────────────────────────────────────────────────────


@router.get("/global")
def global_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "super_admin", "operations_manager")
    ),
):
    """
    Top-level platform KPIs: branches, orders, stock health, compliance.
    """
    today = date.today()

    total_branches = db.query(Branch).filter(Branch.active == True).count()
    total_warehouses = db.query(Warehouse).filter(Warehouse.active == True).count()

    # Inventory compliance today
    branches_done_today = (
        db.query(DailyInventory.branch_id)
        .filter(
            DailyInventory.inventory_date == today,
            DailyInventory.status.in_(
                [InventoryStatus.approved, InventoryStatus.submitted]
            ),
        )
        .distinct()
        .count()
    )

    # Orders in flight (non-terminal, non-cancelled)
    _ACTIVE_STATUSES = [
        OrderStatus.system_generated,
        OrderStatus.draft,
        OrderStatus.branch_reviewed,
        OrderStatus.submitted_to_warehouse,
        OrderStatus.under_review,
        OrderStatus.approved,
        OrderStatus.partially_approved,
        OrderStatus.picking,
        OrderStatus.dispatched,
    ]
    active_orders = (
        db.query(ReplenishmentOrder)
        .filter(ReplenishmentOrder.status.in_(_ACTIVE_STATUSES))
        .count()
    )

    # Stock health
    out_of_stock = db.query(BranchStock).filter(BranchStock.current_qty <= 0).count()
    low_stock = (
        db.query(BranchStock)
        .join(Item)
        .filter(
            BranchStock.current_qty > 0,
            BranchStock.current_qty <= Item.reorder_point,
        )
        .count()
    )

    # Pending approvals
    pending_inv = (
        db.query(DailyInventory)
        .filter(
            DailyInventory.status.in_(
                [InventoryStatus.submitted, InventoryStatus.pending_approval]
            )
        )
        .count()
    )

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "date": str(today),
        "total_branches": total_branches,
        "total_warehouses": total_warehouses,
        "branches_compliant_today": branches_done_today,
        "compliance_rate_today": round(branches_done_today / total_branches * 100, 1)
        if total_branches
        else 0,
        "active_orders": active_orders,
        "out_of_stock_items": out_of_stock,
        "low_stock_items": low_stock,
        "pending_inventory_approvals": pending_inv,
    }


@router.get("/branch/{branch_id}/trend")
def branch_trend(
    branch_id: int,
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Per-branch trend over the last N days:
    - inventory status per day
    - orders count per day
    """
    if not can_access_branch(current_user, branch_id, db):
        raise HTTPException(status_code=403, detail="Access denied for this branch")

    today = date.today()
    date_from = today - timedelta(days=days)

    inventories = (
        db.query(DailyInventory)
        .filter(
            DailyInventory.branch_id == branch_id,
            DailyInventory.inventory_date >= date_from,
        )
        .all()
    )
    inv_map = {inv.inventory_date: inv.status.value for inv in inventories}

    orders = (
        db.query(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.branch_id == branch_id,
            ReplenishmentOrder.order_date >= date_from,
        )
        .all()
    )
    from collections import Counter

    orders_per_day = Counter(str(o.order_date) for o in orders)

    trend = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        trend.append(
            {
                "date": str(d),
                "inventory_status": inv_map.get(d, "missing"),
                "orders_count": orders_per_day.get(str(d), 0),
            }
        )

    return {
        "branch_id": branch_id,
        "days": days,
        "trend": trend,
    }


@router.get("/alerts-summary")
def alerts_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "super_admin", "operations_manager")
    ),
):
    """Combined counts of all alert types for badge display."""
    today = date.today()

    low_stock_count = (
        db.query(BranchStock)
        .join(Item)
        .filter(
            BranchStock.current_qty <= Item.reorder_point,
            Item.is_deleted == False,
        )
        .count()
    )

    out_of_stock_count = (
        db.query(BranchStock).filter(BranchStock.current_qty <= 0).count()
    )

    pending_inv_count = (
        db.query(DailyInventory)
        .filter(
            DailyInventory.status.in_(
                [InventoryStatus.submitted, InventoryStatus.pending_approval]
            )
        )
        .count()
    )

    missing_today_count = (
        db.query(Branch).filter(Branch.active == True).count()
        - db.query(DailyInventory.branch_id)
        .filter(DailyInventory.inventory_date == today)
        .distinct()
        .count()
    )

    overdue_orders_count = (
        db.query(ReplenishmentOrder)
        .filter(
            ReplenishmentOrder.status.notin_(["closed", "cancelled", "received"]),
            ReplenishmentOrder.updated_at <= datetime.utcnow() - timedelta(hours=48),
        )
        .count()
    )

    total_alerts = (
        low_stock_count
        + out_of_stock_count
        + pending_inv_count
        + missing_today_count
        + overdue_orders_count
    )

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "low_stock": low_stock_count,
        "out_of_stock": out_of_stock_count,
        "pending_inventory_approvals": pending_inv_count,
        "missing_today": missing_today_count,
        # Backward-compatible alias (Epic 11 tests + older clients)
        "missing_inventory_today": missing_today_count,
        "overdue_orders": overdue_orders_count,
        "total_alerts": total_alerts,
    }


# ══════════════════════════════════════════════════════════════════════════
# G5 — Daily consumption trend per branch
# ══════════════════════════════════════════════════════════════════════════
@router.get("/branch/{branch_id}/consumption-trend")
def branch_consumption_trend(
    branch_id: int,
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Daily consumption trend for a branch over the last N days.

    Consumption source = negative `inventory_adjustment` stock transactions
    where source = this branch (same signal used by replenishment_service).

    Returns one point per day even if zero, so the chart is continuous.
    """
    if not can_access_branch(current_user, branch_id, db):
        raise HTTPException(status_code=403, detail="Access denied for this branch")

    today = date.today()
    date_from = today - timedelta(days=days - 1)
    # Upper bound = start of tomorrow → excludes any future-dated or clock-skewed rows
    date_to_excl = datetime.combine(today + timedelta(days=1), datetime.min.time())
    # build query: sum qty per day for negative inventory adjustments
    rows = (
        db.query(
            func.date(StockTransaction.transaction_date).label("d"),
            func.sum(StockTransaction.qty).label("total_qty"),
        )
        .filter(
            StockTransaction.source_type == "branch",
            StockTransaction.source_id == branch_id,
            StockTransaction.transaction_type == "inventory_adjustment",
            StockTransaction.qty < 0,
            StockTransaction.transaction_date
            >= datetime.combine(date_from, datetime.min.time()),
            StockTransaction.transaction_date < date_to_excl,
        )
        .group_by(func.date(StockTransaction.transaction_date))
        .all()
    )

    # SQLite returns date as str; Postgres as date — normalise.
    per_day: dict[str, float] = {}
    for r in rows:
        key = str(r.d)[:10] if r.d else ""
        per_day[key] = float(abs(r.total_qty or 0))

    # Build continuous series
    trend = []
    running_sum = 0.0
    for i in range(days):
        d = date_from + timedelta(days=i)
        consumed = per_day.get(str(d), 0.0)
        running_sum += consumed
        trend.append(
            {
                "date": str(d),
                "consumed_qty": round(consumed, 3),
            }
        )

    avg = round(running_sum / days, 3) if days else 0.0

    return {
        "branch_id": branch_id,
        "days": days,
        "total_consumed": round(running_sum, 3),
        "avg_daily": avg,
        "trend": trend,
    }


# ══════════════════════════════════════════════════════════════════════════
# G6 — Order-to-receive delay analytics
# ══════════════════════════════════════════════════════════════════════════
@router.get("/order-delay-analytics")
def order_delay_analytics(
    days: int = Query(30, ge=7, le=180),
    branch_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "admin",
            "super_admin",
            "operations_manager",
            "warehouse_manager",
            "area_manager",
        )
    ),
):
    """
    For received orders in the last N days, compute:
      - Average hours from submitted_to_warehouse -> dispatched_at (approval latency)
      - Average hours from dispatched_at -> received_at (transit latency)
      - Average total hours (submit -> receive)
      - Count of orders measured
      - Top branches by avg total delay
    """
    today = date.today()
    date_from = today - timedelta(days=days)

    q = db.query(ReplenishmentOrder).filter(
        ReplenishmentOrder.order_date >= date_from,
        ReplenishmentOrder.received_at.isnot(None),
        ReplenishmentOrder.dispatched_at.isnot(None),
        ReplenishmentOrder.submitted_to_warehouse_at.isnot(None),
    )
    if branch_id is not None:
        q = q.filter(ReplenishmentOrder.branch_id == branch_id)
    if warehouse_id is not None:
        q = q.filter(ReplenishmentOrder.warehouse_id == warehouse_id)

    orders = q.all()

    if not orders:
        return {
            "days": days,
            "total_orders_measured": 0,
            "avg_approval_hours": 0.0,
            "avg_transit_hours": 0.0,
            "avg_total_hours": 0.0,
            "top_delayed_branches": [],
        }

    approval_hours: list[float] = []
    transit_hours: list[float] = []
    total_hours: list[float] = []
    per_branch: dict[int, list[float]] = {}

    for o in orders:
        approve_h = (
            o.dispatched_at - o.submitted_to_warehouse_at
        ).total_seconds() / 3600.0
        transit_h = (o.received_at - o.dispatched_at).total_seconds() / 3600.0
        total_h = (o.received_at - o.submitted_to_warehouse_at).total_seconds() / 3600.0
        if approve_h < 0 or transit_h < 0:
            # Skip bad timestamp data rather than poisoning averages.
            continue
        approval_hours.append(approve_h)
        transit_hours.append(transit_h)
        total_hours.append(total_h)
        per_branch.setdefault(o.branch_id, []).append(total_h)

    n = len(total_hours)
    avg = lambda arr: round(sum(arr) / len(arr), 2) if arr else 0.0

    # Top 10 most-delayed branches (require ≥3 samples for statistical meaning)
    branch_ids = [bid for bid, hrs in per_branch.items() if len(hrs) >= 3]
    branches = (
        {b.id: b for b in db.query(Branch).filter(Branch.id.in_(branch_ids)).all()}
        if branch_ids
        else {}
    )
    top = []
    for bid, hrs in per_branch.items():
        if len(hrs) < 3:
            continue
        b = branches.get(bid)
        top.append(
            {
                "branch_id": bid,
                "branch_code": b.branch_code if b else None,
                "branch_name": b.branch_name if b else None,
                "orders_count": len(hrs),
                "avg_total_hours": round(sum(hrs) / len(hrs), 2),
                "max_total_hours": round(max(hrs), 2),
            }
        )
    top.sort(key=lambda x: x["avg_total_hours"], reverse=True)

    return {
        "days": days,
        "total_orders_measured": n,
        "avg_approval_hours": avg(approval_hours),
        "avg_transit_hours": avg(transit_hours),
        "avg_total_hours": avg(total_hours),
        "top_delayed_branches": top[:10],
    }


# ══════════════════════════════════════════════════════════════════════════
# G7 — Branches with most open corrective actions (quality)
# ══════════════════════════════════════════════════════════════════════════
@router.get("/branches-open-actions")
def branches_with_open_actions(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "admin",
            "super_admin",
            "area_manager",
            "quality_manager",
            "operations_manager",
        )
    ),
):
    """
    Aggregate open corrective actions by branch.

    An "open action" = QualityVisitResponse with status='no' AND is_resolved=False
    on a non-deleted QualityVisit. This matches quality_service.list_open_actions.
    """
    from app.models import QualityVisit, QualityVisitResponse, QualityResponseStatus

    rows = (
        db.query(
            QualityVisit.branch_id.label("branch_id"),
            func.count(QualityVisitResponse.id).label("total_open"),
            func.sum(
                case(
                    (QualityVisitResponse.due_date < date.today(), 1),
                    else_=0,
                )
            ).label("overdue"),
        )
        .join(QualityVisitResponse, QualityVisitResponse.visit_id == QualityVisit.id)
        .filter(
            QualityVisit.is_deleted == False,
            QualityVisitResponse.status == QualityResponseStatus.no,
            QualityVisitResponse.is_resolved == False,
        )
        .group_by(QualityVisit.branch_id)
        .order_by(func.count(QualityVisitResponse.id).desc())
        .limit(limit)
        .all()
    )

    branch_ids = [r.branch_id for r in rows if r.branch_id]
    branches = (
        {b.id: b for b in db.query(Branch).filter(Branch.id.in_(branch_ids)).all()}
        if branch_ids
        else {}
    )

    data = []
    for r in rows:
        b = branches.get(r.branch_id)
        data.append(
            {
                "branch_id": r.branch_id,
                "branch_code": b.branch_code if b else None,
                "branch_name": b.branch_name if b else None,
                "city": b.city if b else None,
                "open_actions": int(r.total_open or 0),
                "overdue_actions": int(r.overdue or 0),
            }
        )

    return {
        "limit": limit,
        "total_branches_with_actions": len(data),
        "branches": data,
    }
