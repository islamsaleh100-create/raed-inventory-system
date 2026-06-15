"""
Supply Chain V1 — in-app notification sections (poll-from-entity-state).

Each section returns { key, count, items, target_url } for the notifications bell.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, load_only

from app.core.area_manager_scope import get_area_manager_branch_ids
from app.models import (
    Branch,
    BranchRequest,
    BranchRequestStatus,
    DeliveryOrder,
    DeliveryOrderStatus,
    Item,
    KitchenSectionAssignment,
    ProductionOrder,
    ProductionOrderStatus,
    User,
    WarehouseLine,
    WarehouseLineSourceType,
    WarehouseLineStatus,
    WarehouseStock,
)

_RECENT_LIMIT = 20
_RECENT_DAYS = 7


def _count(q) -> int:
    entity = q.column_descriptions[0]["entity"]
    return int(q.with_entities(func.count(entity.id)).order_by(None).scalar() or 0)


def _branch_request_item(row: BranchRequest) -> Dict[str, Any]:
    return {
        "id": row.id,
        "request_no": row.request_no,
        "branch_id": row.branch_id,
        "brand_id": row.brand_id,
        "status": row.status.value if row.status else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "target_url": f"/supply-chain/branch-requests/{row.id}",
    }


def _production_item(row: ProductionOrder) -> Dict[str, Any]:
    return {
        "id": row.id,
        "source_request_id": row.source_request_id,
        "destination_branch_id": row.destination_branch_id,
        "kitchen_section_id": row.kitchen_section_id,
        "item_id": row.item_id,
        "status": row.status.value if row.status else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "target_url": f"/supply-chain/production-orders/{row.id}",
    }


def _warehouse_line_item(row: WarehouseLine) -> Dict[str, Any]:
    return {
        "id": row.id,
        "source_request_id": row.source_request_id,
        "branch_id": row.branch_id,
        "item_id": row.item_id,
        "status": row.status.value if row.status else None,
        "pending_qty": str(row.pending_qty),
        "issued_qty": str(row.issued_qty),
        "delay_reason": row.delay_reason,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "target_url": f"/supply-chain/warehouse-lines/{row.id}",
    }


def _delivery_item(row: DeliveryOrder) -> Dict[str, Any]:
    return {
        "id": row.id,
        "branch_id": row.branch_id,
        "brand_id": row.brand_id,
        "status": row.status.value if row.status else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "target_url": f"/supply-chain/delivery-orders/{row.id}",
    }


def _kitchen_section_ids(user: User, db: Session) -> List[int]:
    now = datetime.utcnow()
    rows = (
        db.query(KitchenSectionAssignment.kitchen_section_id)
        .filter(
            KitchenSectionAssignment.user_id == user.id,
            KitchenSectionAssignment.active == True,  # noqa: E712
            or_(
                KitchenSectionAssignment.ended_at.is_(None),
                KitchenSectionAssignment.ended_at > now,
            ),
        )
        .distinct()
        .all()
    )
    return [int(r[0]) for r in rows]


# ── Branch user sections ──────────────────────────────────────────────────────

def _section_sc_request_approved(db: Session, branch_id: int) -> Dict[str, Any]:
    cutoff = datetime.utcnow() - timedelta(days=_RECENT_DAYS)
    q = (
        db.query(BranchRequest)
        .options(load_only(BranchRequest.id, BranchRequest.request_no, BranchRequest.branch_id, BranchRequest.brand_id, BranchRequest.status, BranchRequest.updated_at))
        .filter(
            BranchRequest.branch_id == branch_id,
            BranchRequest.status.in_([BranchRequestStatus.SPLIT, BranchRequestStatus.IN_EXECUTION]),
            BranchRequest.approved_at >= cutoff,
        )
        .order_by(BranchRequest.approved_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_request_approved", "count": _count(q), "items": [_branch_request_item(r) for r in rows], "target_url": "/supply-chain/branch-requests"}


def _section_sc_request_rejected(db: Session, branch_id: int) -> Dict[str, Any]:
    cutoff = datetime.utcnow() - timedelta(days=_RECENT_DAYS)
    q = (
        db.query(BranchRequest)
        .options(load_only(BranchRequest.id, BranchRequest.request_no, BranchRequest.branch_id, BranchRequest.brand_id, BranchRequest.status, BranchRequest.updated_at))
        .filter(
            BranchRequest.branch_id == branch_id,
            BranchRequest.status == BranchRequestStatus.AREA_REJECTED,
            BranchRequest.rejected_at >= cutoff,
        )
        .order_by(BranchRequest.rejected_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_request_rejected", "count": _count(q), "items": [_branch_request_item(r) for r in rows], "target_url": "/supply-chain/branch-requests"}


def _section_sc_production_started(db: Session, branch_id: int) -> Dict[str, Any]:
    q = (
        db.query(ProductionOrder)
        .options(load_only(ProductionOrder.id, ProductionOrder.source_request_id, ProductionOrder.destination_branch_id, ProductionOrder.kitchen_section_id, ProductionOrder.item_id, ProductionOrder.status, ProductionOrder.updated_at))
        .filter(
            ProductionOrder.destination_branch_id == branch_id,
            ProductionOrder.status == ProductionOrderStatus.IN_PROGRESS,
        )
        .order_by(ProductionOrder.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_production_started", "count": _count(q), "items": [_production_item(r) for r in rows], "target_url": "/supply-chain/production-orders"}


def _section_sc_production_ready(db: Session, branch_id: int) -> Dict[str, Any]:
    q = (
        db.query(ProductionOrder)
        .options(load_only(ProductionOrder.id, ProductionOrder.source_request_id, ProductionOrder.destination_branch_id, ProductionOrder.kitchen_section_id, ProductionOrder.item_id, ProductionOrder.status, ProductionOrder.updated_at))
        .filter(
            ProductionOrder.destination_branch_id == branch_id,
            ProductionOrder.status.in_([ProductionOrderStatus.READY, ProductionOrderStatus.PARTIAL_READY]),
        )
        .order_by(ProductionOrder.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_production_ready", "count": _count(q), "items": [_production_item(r) for r in rows], "target_url": "/supply-chain/production-orders"}


def _section_sc_warehouse_delay(db: Session, branch_id: int) -> Dict[str, Any]:
    q = (
        db.query(WarehouseLine)
        .options(load_only(WarehouseLine.id, WarehouseLine.source_request_id, WarehouseLine.branch_id, WarehouseLine.item_id, WarehouseLine.status, WarehouseLine.pending_qty, WarehouseLine.issued_qty, WarehouseLine.delay_reason, WarehouseLine.updated_at))
        .filter(
            WarehouseLine.branch_id == branch_id,
            WarehouseLine.delay_reason.isnot(None),
            WarehouseLine.delay_reason != "",
        )
        .order_by(WarehouseLine.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_warehouse_delay", "count": _count(q), "items": [_warehouse_line_item(r) for r in rows], "target_url": "/supply-chain/warehouse-lines"}


def _section_sc_partial_fulfillment(db: Session, branch_id: int) -> Dict[str, Any]:
    q = (
        db.query(WarehouseLine)
        .options(load_only(WarehouseLine.id, WarehouseLine.source_request_id, WarehouseLine.branch_id, WarehouseLine.item_id, WarehouseLine.status, WarehouseLine.pending_qty, WarehouseLine.issued_qty, WarehouseLine.delay_reason, WarehouseLine.updated_at))
        .filter(
            WarehouseLine.branch_id == branch_id,
            WarehouseLine.status.in_([WarehouseLineStatus.PARTIAL, WarehouseLineStatus.BACKORDER]),
        )
        .order_by(WarehouseLine.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_partial_fulfillment", "count": _count(q), "items": [_warehouse_line_item(r) for r in rows], "target_url": "/supply-chain/warehouse-lines"}


def _section_sc_delivery_created(db: Session, branch_id: int) -> Dict[str, Any]:
    q = (
        db.query(DeliveryOrder)
        .options(load_only(DeliveryOrder.id, DeliveryOrder.branch_id, DeliveryOrder.brand_id, DeliveryOrder.status, DeliveryOrder.updated_at))
        .filter(
            DeliveryOrder.branch_id == branch_id,
            DeliveryOrder.status == DeliveryOrderStatus.READY,
        )
        .order_by(DeliveryOrder.ready_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_delivery_created", "count": _count(q), "items": [_delivery_item(r) for r in rows], "target_url": "/supply-chain/delivery-orders"}


def _section_sc_delivered(db: Session, branch_id: int) -> Dict[str, Any]:
    cutoff = datetime.utcnow() - timedelta(days=_RECENT_DAYS)
    q = (
        db.query(DeliveryOrder)
        .options(load_only(DeliveryOrder.id, DeliveryOrder.branch_id, DeliveryOrder.brand_id, DeliveryOrder.status, DeliveryOrder.updated_at))
        .filter(
            DeliveryOrder.branch_id == branch_id,
            DeliveryOrder.status.in_([DeliveryOrderStatus.DELIVERED, DeliveryOrderStatus.PARTIAL_DELIVERED]),
            DeliveryOrder.delivered_at >= cutoff,
        )
        .order_by(DeliveryOrder.delivered_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_delivered", "count": _count(q), "items": [_delivery_item(r) for r in rows], "target_url": "/supply-chain/delivery-orders"}


# ── Area manager sections ─────────────────────────────────────────────────────

def _section_sc_pending_requests(db: Session, branch_ids: List[int]) -> Dict[str, Any]:
    if not branch_ids:
        return {"key": "sc_pending_requests", "count": 0, "items": [], "target_url": "/supply-chain/branch-requests"}
    q = (
        db.query(BranchRequest)
        .options(load_only(BranchRequest.id, BranchRequest.request_no, BranchRequest.branch_id, BranchRequest.brand_id, BranchRequest.status, BranchRequest.updated_at))
        .filter(
            BranchRequest.branch_id.in_(branch_ids),
            BranchRequest.status == BranchRequestStatus.SUBMITTED,
        )
        .order_by(BranchRequest.submitted_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_pending_requests", "count": _count(q), "items": [_branch_request_item(r) for r in rows], "target_url": "/supply-chain/branch-requests"}


def _section_sc_delayed_requests(db: Session, branch_ids: List[int]) -> Dict[str, Any]:
    if not branch_ids:
        return {"key": "sc_delayed_requests", "count": 0, "items": [], "target_url": "/supply-chain/warehouse-lines"}
    q = (
        db.query(WarehouseLine)
        .options(load_only(WarehouseLine.id, WarehouseLine.source_request_id, WarehouseLine.branch_id, WarehouseLine.item_id, WarehouseLine.status, WarehouseLine.pending_qty, WarehouseLine.issued_qty, WarehouseLine.delay_reason, WarehouseLine.updated_at))
        .filter(
            WarehouseLine.branch_id.in_(branch_ids),
            WarehouseLine.delay_reason.isnot(None),
            WarehouseLine.delay_reason != "",
        )
        .order_by(WarehouseLine.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_delayed_requests", "count": _count(q), "items": [_warehouse_line_item(r) for r in rows], "target_url": "/supply-chain/warehouse-lines"}


def _section_sc_partial_orders(db: Session, branch_ids: List[int]) -> Dict[str, Any]:
    if not branch_ids:
        return {"key": "sc_partial_orders", "count": 0, "items": [], "target_url": "/supply-chain/warehouse-lines"}
    q = (
        db.query(WarehouseLine)
        .options(load_only(WarehouseLine.id, WarehouseLine.source_request_id, WarehouseLine.branch_id, WarehouseLine.item_id, WarehouseLine.status, WarehouseLine.pending_qty, WarehouseLine.issued_qty, WarehouseLine.delay_reason, WarehouseLine.updated_at))
        .filter(
            WarehouseLine.branch_id.in_(branch_ids),
            WarehouseLine.status.in_([WarehouseLineStatus.PARTIAL, WarehouseLineStatus.BACKORDER]),
        )
        .order_by(WarehouseLine.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_partial_orders", "count": _count(q), "items": [_warehouse_line_item(r) for r in rows], "target_url": "/supply-chain/warehouse-lines"}


def _section_sc_backorders(db: Session, branch_ids: List[int]) -> Dict[str, Any]:
    if not branch_ids:
        return {"key": "sc_backorders", "count": 0, "items": [], "target_url": "/supply-chain/warehouse-lines"}
    q = (
        db.query(WarehouseLine)
        .options(load_only(WarehouseLine.id, WarehouseLine.source_request_id, WarehouseLine.branch_id, WarehouseLine.item_id, WarehouseLine.status, WarehouseLine.pending_qty, WarehouseLine.issued_qty, WarehouseLine.delay_reason, WarehouseLine.updated_at))
        .filter(
            WarehouseLine.branch_id.in_(branch_ids),
            or_(
                WarehouseLine.status == WarehouseLineStatus.BACKORDER,
                WarehouseLine.status == WarehouseLineStatus.PARTIAL,
            ),
            WarehouseLine.pending_qty > 0,
        )
        .order_by(WarehouseLine.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_backorders", "count": _count(q), "items": [_warehouse_line_item(r) for r in rows], "target_url": "/supply-chain/warehouse-lines"}


def _section_sc_delivery_delays(db: Session, branch_ids: List[int]) -> Dict[str, Any]:
    if not branch_ids:
        return {"key": "sc_delivery_delays", "count": 0, "items": [], "target_url": "/supply-chain/delivery-orders"}
    stale = datetime.utcnow() - timedelta(hours=24)
    q = (
        db.query(DeliveryOrder)
        .options(load_only(DeliveryOrder.id, DeliveryOrder.branch_id, DeliveryOrder.brand_id, DeliveryOrder.status, DeliveryOrder.updated_at))
        .filter(
            DeliveryOrder.branch_id.in_(branch_ids),
            DeliveryOrder.status.in_([
                DeliveryOrderStatus.OUT_FOR_DELIVERY,
                DeliveryOrderStatus.PARTIAL_DELIVERED,
            ]),
            DeliveryOrder.updated_at <= stale,
        )
        .order_by(DeliveryOrder.updated_at.asc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_delivery_delays", "count": _count(q), "items": [_delivery_item(r) for r in rows], "target_url": "/supply-chain/delivery-orders"}


# ── Kitchen sections ──────────────────────────────────────────────────────────

def _section_sc_production_order_created(db: Session, section_ids: List[int]) -> Dict[str, Any]:
    if not section_ids:
        return {"key": "sc_production_order_created", "count": 0, "items": [], "target_url": "/supply-chain/production-orders"}
    q = (
        db.query(ProductionOrder)
        .options(load_only(ProductionOrder.id, ProductionOrder.source_request_id, ProductionOrder.destination_branch_id, ProductionOrder.kitchen_section_id, ProductionOrder.item_id, ProductionOrder.status, ProductionOrder.updated_at))
        .filter(
            ProductionOrder.kitchen_section_id.in_(section_ids),
            ProductionOrder.status == ProductionOrderStatus.PENDING,
        )
        .order_by(ProductionOrder.created_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_production_order_created", "count": _count(q), "items": [_production_item(r) for r in rows], "target_url": "/supply-chain/production-orders"}


def _section_sc_material_shortage(db: Session, section_ids: List[int]) -> Dict[str, Any]:
    if not section_ids:
        return {"key": "sc_material_shortage", "count": 0, "items": [], "target_url": "/supply-chain/production-orders"}
    q = (
        db.query(ProductionOrder)
        .options(load_only(ProductionOrder.id, ProductionOrder.source_request_id, ProductionOrder.destination_branch_id, ProductionOrder.kitchen_section_id, ProductionOrder.item_id, ProductionOrder.status, ProductionOrder.updated_at))
        .filter(
            ProductionOrder.kitchen_section_id.in_(section_ids),
            ProductionOrder.status == ProductionOrderStatus.WAITING_FOR_MATERIALS,
        )
        .order_by(ProductionOrder.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_material_shortage", "count": _count(q), "items": [_production_item(r) for r in rows], "target_url": "/supply-chain/production-orders"}


def _section_sc_ready_for_warehouse(db: Session, section_ids: List[int]) -> Dict[str, Any]:
    if not section_ids:
        return {"key": "sc_ready_for_warehouse", "count": 0, "items": [], "target_url": "/supply-chain/production-orders"}
    q = (
        db.query(ProductionOrder)
        .options(load_only(ProductionOrder.id, ProductionOrder.source_request_id, ProductionOrder.destination_branch_id, ProductionOrder.kitchen_section_id, ProductionOrder.item_id, ProductionOrder.status, ProductionOrder.updated_at))
        .filter(
            ProductionOrder.kitchen_section_id.in_(section_ids),
            ProductionOrder.status.in_([ProductionOrderStatus.READY, ProductionOrderStatus.PARTIAL_READY]),
        )
        .order_by(ProductionOrder.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_ready_for_warehouse", "count": _count(q), "items": [_production_item(r) for r in rows], "target_url": "/supply-chain/production-orders"}


# ── Warehouse sections ────────────────────────────────────────────────────────

def _section_sc_kitchen_output_ready(db: Session, warehouse_id: int) -> Dict[str, Any]:
    q = (
        db.query(WarehouseLine)
        .options(load_only(WarehouseLine.id, WarehouseLine.source_request_id, WarehouseLine.branch_id, WarehouseLine.item_id, WarehouseLine.status, WarehouseLine.pending_qty, WarehouseLine.issued_qty, WarehouseLine.delay_reason, WarehouseLine.updated_at))
        .join(Branch, Branch.id == WarehouseLine.branch_id)
        .filter(
            Branch.warehouse_id == warehouse_id,
            WarehouseLine.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT,
            WarehouseLine.status.in_([WarehouseLineStatus.AVAILABLE, WarehouseLineStatus.PENDING]),
            WarehouseLine.pending_qty > 0,
        )
        .order_by(WarehouseLine.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_kitchen_output_ready", "count": _count(q), "items": [_warehouse_line_item(r) for r in rows], "target_url": "/supply-chain/warehouse-lines"}


def _section_sc_warehouse_receive_required(db: Session, warehouse_id: int) -> Dict[str, Any]:
    q = (
        db.query(WarehouseLine)
        .options(load_only(WarehouseLine.id, WarehouseLine.source_request_id, WarehouseLine.branch_id, WarehouseLine.item_id, WarehouseLine.status, WarehouseLine.pending_qty, WarehouseLine.issued_qty, WarehouseLine.delay_reason, WarehouseLine.updated_at))
        .join(Branch, Branch.id == WarehouseLine.branch_id)
        .filter(
            Branch.warehouse_id == warehouse_id,
            WarehouseLine.source_type == WarehouseLineSourceType.BRANCH_REQUEST,
            WarehouseLine.status == WarehouseLineStatus.PENDING,
        )
        .order_by(WarehouseLine.created_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_warehouse_receive_required", "count": _count(q), "items": [_warehouse_line_item(r) for r in rows], "target_url": "/supply-chain/warehouse-lines"}


def _section_sc_warehouse_partial_fulfillment(db: Session, warehouse_id: int) -> Dict[str, Any]:
    q = (
        db.query(WarehouseLine)
        .options(load_only(WarehouseLine.id, WarehouseLine.source_request_id, WarehouseLine.branch_id, WarehouseLine.item_id, WarehouseLine.status, WarehouseLine.pending_qty, WarehouseLine.issued_qty, WarehouseLine.delay_reason, WarehouseLine.updated_at))
        .join(Branch, Branch.id == WarehouseLine.branch_id)
        .filter(
            Branch.warehouse_id == warehouse_id,
            WarehouseLine.status.in_([WarehouseLineStatus.PARTIAL, WarehouseLineStatus.BACKORDER]),
        )
        .order_by(WarehouseLine.updated_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_warehouse_partial_fulfillment", "count": _count(q), "items": [_warehouse_line_item(r) for r in rows], "target_url": "/supply-chain/warehouse-lines"}


def _section_sc_low_stock(db: Session, warehouse_id: int) -> Dict[str, Any]:
    rows_raw = (
        db.query(WarehouseStock, Item)
        .join(Item, Item.id == WarehouseStock.item_id)
        .filter(
            WarehouseStock.warehouse_id == warehouse_id,
            Item.reorder_point.isnot(None),
            Item.reorder_point > 0,
        )
        .all()
    )
    items = []
    for stock, item in rows_raw:
        available = Decimal(str(stock.current_qty or 0)) - Decimal(str(stock.reserved_qty or 0))
        reorder = Decimal(str(item.reorder_point or 0))
        if available < reorder:
            items.append({
                "item_id": item.id,
                "item_code": item.item_code,
                "warehouse_id": warehouse_id,
                "available_qty": str(available),
                "reorder_point": str(reorder),
                "target_url": f"/master/items/{item.id}",
            })
    items.sort(key=lambda x: Decimal(x["available_qty"]))
    return {
        "key": "sc_low_stock",
        "count": len(items),
        "items": items[:_RECENT_LIMIT],
        "target_url": "/supply-chain/warehouse-stock",
    }


# ── Delivery sections ─────────────────────────────────────────────────────────

def _section_sc_delivery_ready(db: Session, warehouse_id: int) -> Dict[str, Any]:
    q = (
        db.query(DeliveryOrder)
        .options(load_only(DeliveryOrder.id, DeliveryOrder.branch_id, DeliveryOrder.brand_id, DeliveryOrder.status, DeliveryOrder.updated_at))
        .join(Branch, Branch.id == DeliveryOrder.branch_id)
        .filter(
            Branch.warehouse_id == warehouse_id,
            DeliveryOrder.status == DeliveryOrderStatus.READY,
        )
        .order_by(DeliveryOrder.ready_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_delivery_ready", "count": _count(q), "items": [_delivery_item(r) for r in rows], "target_url": "/supply-chain/delivery-orders"}


def _section_sc_out_for_delivery(db: Session, warehouse_id: int) -> Dict[str, Any]:
    q = (
        db.query(DeliveryOrder)
        .options(load_only(DeliveryOrder.id, DeliveryOrder.branch_id, DeliveryOrder.brand_id, DeliveryOrder.status, DeliveryOrder.updated_at))
        .join(Branch, Branch.id == DeliveryOrder.branch_id)
        .filter(
            Branch.warehouse_id == warehouse_id,
            DeliveryOrder.status == DeliveryOrderStatus.OUT_FOR_DELIVERY,
        )
        .order_by(DeliveryOrder.out_for_delivery_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_out_for_delivery", "count": _count(q), "items": [_delivery_item(r) for r in rows], "target_url": "/supply-chain/delivery-orders"}


def _section_sc_delivery_shortage(db: Session, warehouse_id: int) -> Dict[str, Any]:
    cutoff = datetime.utcnow() - timedelta(days=_RECENT_DAYS)
    q = (
        db.query(DeliveryOrder)
        .options(load_only(DeliveryOrder.id, DeliveryOrder.branch_id, DeliveryOrder.brand_id, DeliveryOrder.status, DeliveryOrder.updated_at))
        .join(Branch, Branch.id == DeliveryOrder.branch_id)
        .filter(
            Branch.warehouse_id == warehouse_id,
            DeliveryOrder.status == DeliveryOrderStatus.PARTIAL_DELIVERED,
            DeliveryOrder.delivered_at >= cutoff,
        )
        .order_by(DeliveryOrder.delivered_at.desc())
    )
    rows = q.limit(_RECENT_LIMIT).all()
    return {"key": "sc_delivery_shortage", "count": _count(q), "items": [_delivery_item(r) for r in rows], "target_url": "/supply-chain/delivery-orders"}


def build_supply_chain_sections(user: User, db: Session, roles: Set[str]) -> List[Dict[str, Any]]:
    """Return supply-chain notification sections scoped to the user's roles."""
    sections: List[Dict[str, Any]] = []
    is_global = bool({"admin", "super_admin", "operations_manager"} & roles)

    if ({"branch_user", "branch_manager"} & roles) and user.branch_id:
        bid = user.branch_id
        sections.extend([
            _section_sc_request_approved(db, bid),
            _section_sc_request_rejected(db, bid),
            _section_sc_production_started(db, bid),
            _section_sc_production_ready(db, bid),
            _section_sc_warehouse_delay(db, bid),
            _section_sc_partial_fulfillment(db, bid),
            _section_sc_delivery_created(db, bid),
            _section_sc_delivered(db, bid),
        ])

    if "area_manager" in roles:
        branch_ids = get_area_manager_branch_ids(user, db)
        sections.extend([
            _section_sc_pending_requests(db, branch_ids),
            _section_sc_delayed_requests(db, branch_ids),
            _section_sc_partial_orders(db, branch_ids),
            _section_sc_backorders(db, branch_ids),
            _section_sc_delivery_delays(db, branch_ids),
        ])

    if "kitchen_section_manager" in roles or is_global:
        section_ids = _kitchen_section_ids(user, db) if "kitchen_section_manager" in roles else None
        if is_global:
            all_sections = [r[0] for r in db.query(ProductionOrder.kitchen_section_id).distinct().all()]
            sections.extend([
                _section_sc_production_order_created(db, all_sections),
                _section_sc_material_shortage(db, all_sections),
                _section_sc_ready_for_warehouse(db, all_sections),
            ])
        elif section_ids:
            sections.extend([
                _section_sc_production_order_created(db, section_ids),
                _section_sc_material_shortage(db, section_ids),
                _section_sc_ready_for_warehouse(db, section_ids),
            ])

    if {"warehouse_user", "warehouse_manager"} & roles:
        wh_id = user.warehouse_id
        if wh_id:
            sections.extend([
                _section_sc_kitchen_output_ready(db, wh_id),
                _section_sc_warehouse_receive_required(db, wh_id),
                _section_sc_warehouse_partial_fulfillment(db, wh_id),
                _section_sc_low_stock(db, wh_id),
            ])
        elif is_global:
            pass

    if "delivery_user" in roles:
        wh_id = user.warehouse_id
        if wh_id:
            sections.extend([
                _section_sc_delivery_ready(db, wh_id),
                _section_sc_out_for_delivery(db, wh_id),
                _section_sc_delivery_shortage(db, wh_id),
            ])

    if is_global:
        q = (
            db.query(BranchRequest)
            .options(load_only(BranchRequest.id, BranchRequest.request_no, BranchRequest.branch_id, BranchRequest.brand_id, BranchRequest.status, BranchRequest.updated_at))
            .filter(BranchRequest.status == BranchRequestStatus.SUBMITTED)
            .order_by(BranchRequest.submitted_at.desc())
        )
        rows = q.limit(_RECENT_LIMIT).all()
        sections.append({
            "key": "sc_all_pending_requests",
            "count": _count(q),
            "items": [_branch_request_item(r) for r in rows],
            "target_url": "/supply-chain/branch-requests",
        })

    return sections
