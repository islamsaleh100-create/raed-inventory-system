"""
Auto Replenishment Engine
Generates suggested orders based on stock levels, consumption patterns, and configured rules
"""
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models import (
    DailyInventory, DailyInventoryLine, BranchStock, WarehouseStock,
    ReplenishmentOrder, ReplenishmentOrderLine, StockTransaction,
    Item, Branch, OrderType, OrderStatus, TransactionType, User,
    AvgConsumptionMode
)
from app.core.errors import AppError


def _get_avg_daily_consumption(
    db: Session,
    branch_id: int,
    item_id: int,
    mode: AvgConsumptionMode
) -> Decimal:
    """
    Calculate average daily consumption from inventory adjustments.
    Falls back to 0 if no data available.
    """
    days_map = {
        AvgConsumptionMode.last_7_days: 7,
        AvgConsumptionMode.last_14_days: 14,
        AvgConsumptionMode.last_30_days: 30,
    }
    days = days_map.get(mode, 7)
    since = datetime.utcnow() - timedelta(days=days)

    # Sum negative adjustments (consumption) from stock transactions
    result = db.query(func.sum(StockTransaction.qty)).filter(
        StockTransaction.item_id == item_id,
        StockTransaction.source_id == branch_id,
        StockTransaction.source_type == "branch",
        StockTransaction.transaction_type == TransactionType.inventory_adjustment,
        StockTransaction.qty < 0,
        StockTransaction.transaction_date >= since
    ).scalar()

    if result and days > 0:
        return abs(Decimal(str(result))) / Decimal(str(days))
    return Decimal("0")


def _get_in_transit_qty(db: Session, branch_id: int, item_id: int) -> Decimal:
    """Sum quantities in active orders that are dispatched but not yet received"""
    result = db.query(func.sum(ReplenishmentOrderLine.dispatched_qty)).join(
        ReplenishmentOrder
    ).filter(
        ReplenishmentOrder.branch_id == branch_id,
        ReplenishmentOrder.status.in_([OrderStatus.dispatched]),
        ReplenishmentOrderLine.item_id == item_id,
    ).scalar()
    return Decimal(str(result)) if result else Decimal("0")


def _get_open_order_qty(db: Session, branch_id: int, item_id: int) -> Decimal:
    """Sum quantities in pending/approved orders"""
    result = db.query(func.sum(ReplenishmentOrderLine.branch_requested_qty)).join(
        ReplenishmentOrder
    ).filter(
        ReplenishmentOrder.branch_id == branch_id,
        ReplenishmentOrder.status.in_([
            OrderStatus.area_manager_review,
            OrderStatus.submitted_to_warehouse,
            OrderStatus.under_review,
            OrderStatus.approved,
            OrderStatus.picking,
        ]),
        ReplenishmentOrderLine.item_id == item_id,
    ).scalar()
    return Decimal(str(result)) if result else Decimal("0")


def calculate_suggested_qty(
    db: Session,
    branch_id: int,
    item: Item,
    days_of_cover_target: int = 3
) -> Decimal:
    """
    Main replenishment formula:
    suggested_qty = max(0, target_qty - available_qty)
    target_qty = (avg_daily_usage * days_of_cover_target) + safety_stock
    available_qty = current_stock + in_transit_qty - reserved_qty
    """
    # Get current stock
    stock = db.query(BranchStock).filter(
        BranchStock.branch_id == branch_id,
        BranchStock.item_id == item.id
    ).first()
    current_stock = stock.current_qty if stock else Decimal("0")
    reserved_qty = stock.reserved_qty if stock else Decimal("0")

    # Get movement data
    in_transit_qty = _get_in_transit_qty(db, branch_id, item.id)
    open_order_qty = _get_open_order_qty(db, branch_id, item.id)

    # Calculate avg daily usage
    avg_daily_usage = _get_avg_daily_consumption(db, branch_id, item.id, item.average_consumption_mode)

    # Use item min_qty as fallback if no consumption history
    if avg_daily_usage == 0 and item.min_qty > 0:
        avg_daily_usage = item.min_qty / Decimal("3")  # assume 3-day coverage for min stock

    # Core formula
    safety_stock = item.safety_stock
    target_qty = (avg_daily_usage * Decimal(str(days_of_cover_target))) + safety_stock
    available_qty = current_stock + in_transit_qty + open_order_qty - reserved_qty

    suggested = max(Decimal("0"), target_qty - available_qty)

    # Cap at max_qty
    if item.max_qty > 0:
        warehouse_stock_qty = current_stock + in_transit_qty
        max_order = item.max_qty - warehouse_stock_qty
        suggested = min(suggested, max(Decimal("0"), max_order))

    # Round to item's unit: if min_qty is integer, round to integer; otherwise 0.5
    if item.min_qty == int(item.min_qty):
        return Decimal(str(int(suggested)))
    else:
        return Decimal(str(round(float(suggested) * 2) / 2))


def generate_replenishment_order(
    db: Session,
    inventory_id: int,
    user: User,
    days_of_cover: int = 3
) -> Optional[ReplenishmentOrder]:
    """
    After inventory approval, generate an auto replenishment order.
    Only creates an order if there are items that need replenishment.
    """
    inventory = db.query(DailyInventory).filter(DailyInventory.id == inventory_id).first()
    if not inventory:
        raise AppError(
            status_code=404,
            error_code="replenishment.inventory_not_found",
            message="Inventory not found",
            detail={"inventory_id": inventory_id},
        )
    if inventory.status.value != "approved":
        raise AppError(
            status_code=400,
            error_code="replenishment.inventory_not_approved",
            message="Inventory must be approved before triggering replenishment",
            detail={"inventory_id": inventory_id, "status": inventory.status.value},
        )

    # Check if order already exists for this inventory
    existing_order = db.query(ReplenishmentOrder).filter(
        ReplenishmentOrder.inventory_id == inventory_id,
        ReplenishmentOrder.order_type == OrderType.auto_replenishment,
        ReplenishmentOrder.status != OrderStatus.rejected
    ).first()
    if existing_order:
        return existing_order  # Idempotent

    branch = db.query(Branch).filter(Branch.id == inventory.branch_id).first()

    # Get all active requestable items
    items = db.query(Item).filter(
        Item.active == True,
        Item.branch_requestable == True,
        Item.is_deleted == False
    ).all()

    order_lines = []
    for item in items:
        suggested_qty = calculate_suggested_qty(db, inventory.branch_id, item, days_of_cover)

        # Only include items that need replenishment
        # Always include items at or below reorder_point or out of stock
        stock = db.query(BranchStock).filter(
            BranchStock.branch_id == inventory.branch_id,
            BranchStock.item_id == item.id
        ).first()
        current = stock.current_qty if stock else Decimal("0")

        should_include = (
            suggested_qty > 0 or
            current <= item.reorder_point or
            current <= 0
        )

        if should_include and suggested_qty >= 0:
            final_qty = max(suggested_qty, Decimal("0"))
            if final_qty == 0 and current <= 0:
                final_qty = item.min_qty  # At minimum order min_qty if out of stock

            if final_qty > 0:
                order_lines.append({
                    "item_id": item.id,
                    "suggested_qty": final_qty,
                    "branch_requested_qty": final_qty,
                })

    if not order_lines:
        return None  # No replenishment needed

    # Generate order number — suffix عشوائي لتجنب race condition
    today = date.today()
    order_no = f"ORD-{today.strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    order = ReplenishmentOrder(
        order_no=order_no,
        branch_id=inventory.branch_id,
        warehouse_id=branch.warehouse_id,
        order_type=OrderType.auto_replenishment,
        status=OrderStatus.system_generated,
        inventory_id=inventory_id,
        order_date=today,
        created_by=user.id,
    )
    db.add(order)
    db.flush()

    for line_data in order_lines:
        line = ReplenishmentOrderLine(
            order_id=order.id,
            item_id=line_data["item_id"],
            suggested_qty=line_data["suggested_qty"],
            branch_requested_qty=line_data["branch_requested_qty"],
            wh_approved_qty=Decimal("0"),
            line_status="pending",
        )
        db.add(line)

    db.commit()
    db.refresh(order)
    return order


# ──────────────────────────────────────────────────────────────────────────
# PREVIEW  (dry-run — same logic as generate but no DB writes)
# ──────────────────────────────────────────────────────────────────────────

def preview_replenishment_order(
    db: Session,
    *,
    branch_id: int,
    days_of_cover: int = 3,
) -> dict:
    """
    Simulates what generate_replenishment_order would produce without
    creating any records. Returns proposed lines with suggested quantities.
    """
    items = db.query(Item).filter(
        Item.active == True,
        Item.branch_requestable == True,
        Item.is_deleted == False,
    ).all()

    preview_lines = []
    for item in items:
        stock = db.query(BranchStock).filter(
            BranchStock.branch_id == branch_id,
            BranchStock.item_id == item.id,
        ).first()
        current_qty = stock.current_qty if stock else Decimal("0")
        in_transit = _get_in_transit_qty(db, branch_id, item.id)
        open_orders = _get_open_order_qty(db, branch_id, item.id)
        avg_usage = _get_avg_daily_consumption(db, branch_id, item.id, item.average_consumption_mode)
        suggested = calculate_suggested_qty(db, branch_id, item, days_of_cover)

        if suggested > 0 or current_qty <= item.reorder_point:
            preview_lines.append({
                "item_id": item.id,
                "item_code": item.item_code,
                "item_name_ar": item.item_name_ar,
                "current_qty": float(current_qty),
                "in_transit_qty": float(in_transit),
                "open_order_qty": float(open_orders),
                "avg_daily_usage": float(avg_usage),
                "reorder_point": float(item.reorder_point),
                "suggested_qty": float(suggested),
                "would_include": suggested > 0,
            })

    return {
        "branch_id": branch_id,
        "days_of_cover": days_of_cover,
        "items_evaluated": len(items),
        "items_needing_replenishment": sum(1 for l in preview_lines if l["would_include"]),
        "preview_lines": preview_lines,
    }


def create_exceptional_order(
    db: Session,
    branch_id: int,
    items: List[dict],
    notes: Optional[str],
    user: User
) -> ReplenishmentOrder:
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="replenishment.branch_not_found",
            message="Branch not found",
            detail={"branch_id": branch_id},
        )

    today = date.today()
    order_no = f"EXC-{today.strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    order = ReplenishmentOrder(
        order_no=order_no,
        branch_id=branch_id,
        warehouse_id=branch.warehouse_id,
        order_type=OrderType.exceptional,
        status=OrderStatus.draft,
        order_date=today,
        notes=notes,
        created_by=user.id,
    )
    db.add(order)
    db.flush()

    for item_data in items:
        raw_qty = item_data.get("branch_requested_qty")
        br_qty = Decimal(str(raw_qty)) if raw_qty is not None else Decimal("0")
        line = ReplenishmentOrderLine(
            order_id=order.id,
            item_id=item_data["item_id"],
            suggested_qty=Decimal("0"),
            branch_requested_qty=br_qty,
            wh_approved_qty=Decimal("0"),
            line_status="pending",
            notes=item_data.get("notes"),
        )
        db.add(line)

    db.commit()
    db.refresh(order)
    return order


def create_daily_order(
    db: Session,
    branch_id: int,
    items: List[dict],
    notes: Optional[str],
    user: User,
) -> ReplenishmentOrder:
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="replenishment.branch_not_found",
            message="Branch not found",
            detail={"branch_id": branch_id},
        )
    today = date.today()
    order_no = f"DLY-{today.strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    order = ReplenishmentOrder(
        order_no=order_no,
        branch_id=branch_id,
        warehouse_id=branch.warehouse_id,
        order_type=OrderType.daily_order,
        status=OrderStatus.branch_reviewed,
        order_date=today,
        notes=notes,
        created_by=user.id,
    )
    db.add(order)
    db.flush()

    for item_data in items:
        raw_qty = item_data.get("branch_requested_qty")
        if not raw_qty or float(raw_qty) <= 0:
            continue
        br_qty = Decimal(str(raw_qty))
        line = ReplenishmentOrderLine(
            order_id=order.id,
            item_id=item_data["item_id"],
            suggested_qty=Decimal("0"),
            branch_requested_qty=br_qty,
            wh_approved_qty=Decimal("0"),
            line_status="pending",
            notes=item_data.get("notes"),
        )
        db.add(line)

    db.commit()
    db.refresh(order)
    return order
