"""Minimal response enrichment for supply-chain list/detail payloads."""
from __future__ import annotations

from app.models import Branch, DeliveryOrder, ProductionOrder, Warehouse, WarehouseLine
from app.schemas import DeliveryOrderOut, ProductionOrderOut, WarehouseLineOut


def branch_display_name(branch: Branch | None) -> str | None:
    if not branch:
        return None
    return branch.branch_name or None


def warehouse_display_name(warehouse: Warehouse | None) -> str | None:
    if not warehouse:
        return None
    return warehouse.warehouse_name or None


def warehouse_line_out(row: WarehouseLine) -> WarehouseLineOut:
    base = WarehouseLineOut.model_validate(row)
    branch = row.branch if hasattr(row, "branch") else None
    return base.model_copy(update={"branch_name": branch_display_name(branch)})


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
