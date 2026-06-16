"""Minimal response enrichment for supply-chain list/detail payloads."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Branch, DeliveryOrder, ProductionOrder, Warehouse, WarehouseLine, WarehouseStock
from app.schemas import DeliveryOrderOut, ProductionOrderOut, WarehouseLineOut


def branch_display_name(branch: Branch | None) -> str | None:
    if not branch:
        return None
    return branch.branch_name or None


def warehouse_display_name(warehouse: Warehouse | None) -> str | None:
    if not warehouse:
        return None
    return warehouse.warehouse_name or None


def _stock_fields(stock: WarehouseStock | None) -> dict:
    if not stock:
        return {
            "current_stock": None,
            "reserved_stock": None,
            "available_stock": None,
        }
    current = Decimal(str(stock.current_qty or 0))
    reserved = Decimal(str(stock.reserved_qty or 0))
    available = max(Decimal("0"), current - reserved)
    return {
        "current_stock": current,
        "reserved_stock": reserved,
        "available_stock": available,
    }


def warehouse_line_out(
    row: WarehouseLine,
    *,
    stock: WarehouseStock | None = None,
) -> WarehouseLineOut:
    base = WarehouseLineOut.model_validate(row)
    branch = row.branch if hasattr(row, "branch") else None
    return base.model_copy(update={
        "branch_name": branch_display_name(branch),
        **_stock_fields(stock),
    })


def enrich_warehouse_lines(
    db: Session,
    rows: list[WarehouseLine],
    *,
    warehouse_id_resolver,
) -> list[WarehouseLineOut]:
    """Batch-load warehouse stock for list responses."""
    if not rows:
        return []
    pairs: set[tuple[int, int]] = set()
    for row in rows:
        try:
            wh_id = warehouse_id_resolver(row)
            pairs.add((wh_id, row.item_id))
        except Exception:
            continue
    if not pairs:
        return [warehouse_line_out(row) for row in rows]
    wh_ids = {p[0] for p in pairs}
    item_ids = {p[1] for p in pairs}
    stocks = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id.in_(wh_ids),
            WarehouseStock.item_id.in_(item_ids),
        )
        .all()
    )
    stock_map = {(s.warehouse_id, s.item_id): s for s in stocks}
    out: list[WarehouseLineOut] = []
    for row in rows:
        stock = None
        try:
            wh_id = warehouse_id_resolver(row)
            stock = stock_map.get((wh_id, row.item_id))
        except Exception:
            pass
        out.append(warehouse_line_out(row, stock=stock))
    return out


def production_order_out(row: ProductionOrder) -> ProductionOrderOut:
    base = ProductionOrderOut.model_validate(row)
    branch = row.destination_branch if hasattr(row, "destination_branch") else None
    warehouse_name = None
    if branch and getattr(branch, "warehouse", None):
        warehouse_name = warehouse_display_name(branch.warehouse)
    elif branch and branch.warehouse_id:
        warehouse_name = None
    return base.model_copy(update={
        "branch_name": branch_display_name(branch),
        "destination_warehouse_name": warehouse_name,
    })


def delivery_order_out(row: DeliveryOrder) -> DeliveryOrderOut:
    base = DeliveryOrderOut.model_validate(row)
    branch = row.branch if hasattr(row, "branch") else None
    return base.model_copy(update={"branch_name": branch_display_name(branch)})
