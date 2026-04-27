"""
Branch Request Split Service.

Extracts the split logic from the manual /split endpoint into a reusable,
idempotent service so it can be called automatically from approve and
modify-and-approve, and from the manual endpoint without behaviour drift.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.locking import lock_row
from app.models import (
    BranchRequest,
    BranchRequestLineStatus,
    BranchRequestStatus,
    ProductionOrder,
    ProductionOrderStatus,
    SupplyDefaultSource,
    WarehouseLine,
    WarehouseLineSourceType,
    WarehouseLineStatus,
    WarehouseStock,
)


_ALREADY_SPLIT_STATES = (
    BranchRequestStatus.SPLIT,
    BranchRequestStatus.IN_EXECUTION,
    BranchRequestStatus.DELIVERED,
)


def split_branch_request(db: Session, request: BranchRequest) -> BranchRequest:
    """Split an area-approved branch request into warehouse lines and production orders."""
    if request.status in _ALREADY_SPLIT_STATES:
        return request

    if request.status != BranchRequestStatus.AREA_APPROVED:
        raise AppError(
            status_code=400,
            error_code="branch_requests.not_area_approved_for_split",
            message="Only area-approved requests can be split",
            detail={"request_id": request.id, "status": request.status.value},
        )

    warehouse_id = request.branch.warehouse_id if request.branch else None

    for line in request.lines:
        qty = line.qty_approved if line.qty_approved is not None else line.qty_requested

        if line.resolved_source_type == SupplyDefaultSource.WAREHOUSE:
            if not warehouse_id:
                raise AppError(
                    status_code=400,
                    error_code="branch_requests.branch_warehouse_missing",
                    message="Branch request warehouse source requires branch warehouse mapping",
                    detail={"request_id": request.id, "branch_id": request.branch_id},
                )

            exists = db.query(WarehouseLine).filter(
                WarehouseLine.source_request_line_id == line.id,
                WarehouseLine.source_type == WarehouseLineSourceType.BRANCH_REQUEST,
            ).first()
            if not exists:
                stock = lock_row(
                    db.query(WarehouseStock).filter(
                        WarehouseStock.warehouse_id == warehouse_id,
                        WarehouseStock.item_id == line.item_id,
                    )
                ).first()
                if stock:
                    stock.reserved_qty = Decimal(str(stock.reserved_qty or 0)) + qty
                    stock.last_updated = datetime.utcnow()
                else:
                    db.add(
                        WarehouseStock(
                            warehouse_id=warehouse_id,
                            item_id=line.item_id,
                            current_qty=Decimal("0"),
                            reserved_qty=qty,
                        )
                    )

                db.add(
                    WarehouseLine(
                        source_request_id=request.id,
                        source_request_line_id=line.id,
                        source_type=WarehouseLineSourceType.BRANCH_REQUEST,
                        branch_id=request.branch_id,
                        brand_id=request.brand_id,
                        item_id=line.item_id,
                        requested_qty=qty,
                        issued_qty=Decimal("0"),
                        pending_qty=qty,
                        status=WarehouseLineStatus.PENDING,
                    )
                )
            line.status = BranchRequestLineStatus.SPLIT_TO_WAREHOUSE

        elif line.resolved_source_type == SupplyDefaultSource.KITCHEN:
            item = line.item
            if not item.kitchen_section_id:
                raise AppError(
                    status_code=400,
                    error_code="branch_requests.kitchen_section_required",
                    message="Kitchen-sourced items require kitchen_section_id",
                    detail={"item_id": item.id},
                )

            exists = db.query(ProductionOrder).filter(
                ProductionOrder.source_request_line_id == line.id,
            ).first()
            if not exists:
                db.add(
                    ProductionOrder(
                        source_request_id=request.id,
                        source_request_line_id=line.id,
                        destination_branch_id=request.branch_id,
                        brand_id=request.brand_id,
                        kitchen_section_id=item.kitchen_section_id,
                        item_id=line.item_id,
                        qty_requested=qty,
                        qty_ready=Decimal("0"),
                        status=ProductionOrderStatus.PENDING,
                        priority=request.priority,
                    )
                )
            line.status = BranchRequestLineStatus.SPLIT_TO_PRODUCTION

    request.status = BranchRequestStatus.SPLIT
    request.updated_at = datetime.utcnow()
    db.flush()
    return request
