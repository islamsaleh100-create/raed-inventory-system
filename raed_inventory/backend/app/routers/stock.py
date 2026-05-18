"""
Stock Adjustment & Transfer Router — /api/v1/stock
Epic 5: manual adjustments, transfers between locations
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_roles
from app.database import get_db
from app.models import User
from app.services import stock_adjustment_service

router = APIRouter(prefix="/api/v1/stock", tags=["Stock Adjustments & Transfers"])

_WH_ROLES = ("warehouse_user", "warehouse_manager", "admin", "super_admin")
_BR_ROLES = ("branch_user", "branch_manager", "admin", "super_admin")
_MGMT_ROLES = ("branch_manager", "warehouse_manager", "admin", "super_admin")
# تحويل بين فرعين: مطلوب صلاحية cross-branch (area_manager / admin)
_INTER_BRANCH_ROLES = ("area_manager", "operations_manager", "admin", "super_admin")


# ── Schemas (inline to avoid polluting global schemas module) ─────────────

class BranchAdjustmentRequest(BaseModel):
    item_id: int
    adjustment_type: str           # increase | decrease | set
    qty: Decimal
    reason: str
    reference_no: Optional[str] = None

    @field_validator("qty")
    @classmethod
    def qty_non_negative(cls, v):
        if v < 0:
            raise ValueError("qty must be >= 0")
        return v


class WarehouseAdjustmentRequest(BaseModel):
    item_id: int
    adjustment_type: str
    qty: Decimal
    reason: str
    reference_no: Optional[str] = None

    @field_validator("qty")
    @classmethod
    def qty_non_negative(cls, v):
        if v < 0:
            raise ValueError("qty must be >= 0")
        return v


class WarehouseBulkAdjustmentLine(BaseModel):
    item_id: int
    qty: Decimal

    @field_validator("qty")
    @classmethod
    def qty_non_negative(cls, v):
        if v < 0:
            raise ValueError("qty must be >= 0")
        return v


class WarehouseBulkAdjustmentRequest(BaseModel):
    lines: list[WarehouseBulkAdjustmentLine]
    adjustment_type: str = "set"
    reason: str = "Warehouse stock bulk update"
    reference_no: Optional[str] = None


class TransferWHToBranchRequest(BaseModel):
    item_id: int
    qty: Decimal
    reason: str
    reference_no: Optional[str] = None

    @field_validator("qty")
    @classmethod
    def qty_positive(cls, v):
        if v <= 0:
            raise ValueError("qty must be > 0")
        return v


class TransferBranchToWHRequest(BaseModel):
    item_id: int
    qty: Decimal
    reason: str
    reference_no: Optional[str] = None

    @field_validator("qty")
    @classmethod
    def qty_positive(cls, v):
        if v <= 0:
            raise ValueError("qty must be > 0")
        return v


class TransferBranchToBranchRequest(BaseModel):
    source_branch_id: int
    destination_branch_id: int
    item_id: int
    qty: Decimal
    reason: str
    reference_no: Optional[str] = None

    @field_validator("qty")
    @classmethod
    def qty_positive(cls, v):
        if v <= 0:
            raise ValueError("qty must be > 0")
        return v


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/branches/{branch_id}/adjust")
def adjust_branch_stock(
    branch_id: int,
    payload: BranchAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_BR_ROLES)),
):
    """Manually increase, decrease, or set stock for an item at a branch."""
    return stock_adjustment_service.adjust_branch_stock(
        db,
        branch_id=branch_id,
        item_id=payload.item_id,
        adjustment_type=payload.adjustment_type,
        qty=payload.qty,
        reason=payload.reason,
        reference_no=payload.reference_no,
        current_user=current_user,
    )


@router.post("/warehouses/{warehouse_id}/adjust")
def adjust_warehouse_stock(
    warehouse_id: int,
    payload: WarehouseAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_WH_ROLES)),
):
    """Manually increase, decrease, or set stock for an item at a warehouse."""
    return stock_adjustment_service.adjust_warehouse_stock(
        db,
        warehouse_id=warehouse_id,
        item_id=payload.item_id,
        adjustment_type=payload.adjustment_type,
        qty=payload.qty,
        reason=payload.reason,
        reference_no=payload.reference_no,
        current_user=current_user,
    )


@router.post("/warehouses/{warehouse_id}/bulk-adjust")
def bulk_adjust_warehouse_stock(
    warehouse_id: int,
    payload: WarehouseBulkAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_WH_ROLES)),
):
    """Bulk set/increase/decrease warehouse stock for Excel imports."""
    if payload.adjustment_type not in ("increase", "decrease", "set"):
        from app.core.errors import AppError
        raise AppError(
            status_code=400,
            error_code="stock.invalid_adjustment_type",
            message="adjustment_type must be 'increase', 'decrease', or 'set'",
            detail={"adjustment_type": payload.adjustment_type},
        )

    updated = 0
    errors = []
    for line in payload.lines:
        try:
            stock_adjustment_service.adjust_warehouse_stock(
                db,
                warehouse_id=warehouse_id,
                item_id=line.item_id,
                adjustment_type=payload.adjustment_type,
                qty=line.qty,
                reason=payload.reason,
                reference_no=payload.reference_no,
                current_user=current_user,
            )
            updated += 1
        except Exception as exc:
            errors.append({"item_id": line.item_id, "message": str(exc)})

    return {"warehouse_id": warehouse_id, "updated": updated, "errors": errors}


@router.post("/transfer/warehouse-to-branch")
def transfer_warehouse_to_branch(
    payload: TransferWHToBranchRequest,
    warehouse_id: int,
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT_ROLES)),
):
    """Transfer stock directly from a warehouse to a branch (no order required)."""
    return stock_adjustment_service.transfer_warehouse_to_branch(
        db,
        warehouse_id=warehouse_id,
        branch_id=branch_id,
        item_id=payload.item_id,
        qty=payload.qty,
        reason=payload.reason,
        reference_no=payload.reference_no,
        current_user=current_user,
    )


@router.post("/transfer/branch-to-warehouse")
def transfer_branch_to_warehouse(
    payload: TransferBranchToWHRequest,
    branch_id: int,
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_MGMT_ROLES)),
):
    """Return stock from a branch back to a warehouse."""
    return stock_adjustment_service.transfer_branch_to_warehouse(
        db,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        item_id=payload.item_id,
        qty=payload.qty,
        reason=payload.reason,
        reference_no=payload.reference_no,
        current_user=current_user,
    )


@router.post("/transfer/branch-to-branch")
def transfer_branch_to_branch(
    payload: TransferBranchToBranchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_INTER_BRANCH_ROLES)),
):
    """
    Inter-branch transfer — تحويل مباشر من فرع إلى فرع.
    الصلاحية: area_manager / operations_manager / admin / super_admin.
    """
    return stock_adjustment_service.transfer_branch_to_branch(
        db,
        source_branch_id=payload.source_branch_id,
        destination_branch_id=payload.destination_branch_id,
        item_id=payload.item_id,
        qty=payload.qty,
        reason=payload.reason,
        reference_no=payload.reference_no,
        current_user=current_user,
    )
