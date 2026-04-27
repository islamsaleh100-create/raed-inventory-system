"""
Daily Inventory Router — /api/v1/inventory
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_roles
from app.database import get_db
from app.models import User
from app.schemas import (
    InventoryActionResponse,
    InventoryApprovalResponse,
    InventoryCreate,
    InventoryLinePartialUpdate,
    InventoryListResponse,
    InventoryOut,
    RejectInventoryRequest,
    TodayInventoryStatusOut,
)
from app.services import inventory_service, replenishment_service

router = APIRouter(prefix="/api/v1/inventory", tags=["Daily Inventory"])

_BRANCH_ROLES = ("branch_user", "branch_manager", "admin", "super_admin")
_APPROVAL_ROLES = ("branch_manager", "admin", "super_admin")


# ──────────────────────────────────────────────────────────────────────────
# LIST
# ──────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=InventoryListResponse)
def list_inventories(
    branch_id: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Branch users can only see their own branch
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    if "branch_user" in user_roles or "branch_manager" in user_roles:
        branch_id = current_user.branch_id

    return inventory_service.get_inventory_list(
        db,
        branch_id=branch_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


# ──────────────────────────────────────────────────────────────────────────
# TODAY STATUS  (must be above /{inventory_id} to avoid route conflict)
# ──────────────────────────────────────────────────────────────────────────

@router.get("/today", response_model=List[TodayInventoryStatusOut])
def get_today_inventory_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns today's inventory status for every active branch.
    Branch-scoped users see only their own branch.
    """
    return inventory_service.get_today_inventory_status(db, current_user)


# ──────────────────────────────────────────────────────────────────────────
# GET SINGLE
# ──────────────────────────────────────────────────────────────────────────

@router.get("/{inventory_id}", response_model=InventoryOut)
def get_inventory(
    inventory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return inventory_service.get_inventory_by_id(db, inventory_id, current_user)


# ──────────────────────────────────────────────────────────────────────────
# CREATE
# ──────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=InventoryOut, status_code=201)
def create_inventory(
    payload: InventoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_BRANCH_ROLES)),
):
    return inventory_service.create_inventory_for_user(db, payload, current_user)


# ──────────────────────────────────────────────────────────────────────────
# PATCH single inventory line
# ──────────────────────────────────────────────────────────────────────────

@router.patch("/{inventory_id}/lines/{line_id}", response_model=InventoryOut)
def patch_inventory_line(
    inventory_id: int,
    line_id: int,
    payload: InventoryLinePartialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_BRANCH_ROLES)),
):
    """
    Update a single line in a DRAFT inventory.
    Only the fields provided are changed; variance fields are recalculated.
    """
    return inventory_service.update_inventory_line(
        db,
        inventory_id=inventory_id,
        line_id=line_id,
        counted_qty=payload.counted_qty,
        variance_reason_id=payload.variance_reason_id,
        notes=payload.notes,
        current_user=current_user,
    )


# ──────────────────────────────────────────────────────────────────────────
# SUBMIT (idempotency-aware)
# ──────────────────────────────────────────────────────────────────────────

@router.post("/{inventory_id}/submit", response_model=InventoryOut)
def submit_inventory(
    inventory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_BRANCH_ROLES)),
):
    return inventory_service.submit_inventory_idempotent(
        db,
        inventory_id=inventory_id,
        current_user=current_user,
        client_request_id=request.headers.get("X-Client-Request-Id"),
    )


# ──────────────────────────────────────────────────────────────────────────
# APPROVE
# ──────────────────────────────────────────────────────────────────────────

@router.post("/{inventory_id}/approve", response_model=InventoryApprovalResponse)
def approve_inventory(
    inventory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_APPROVAL_ROLES)),
):
    return inventory_service.approve_inventory_for_user(
        db,
        inventory_id=inventory_id,
        current_user=current_user,
        client_request_id=request.headers.get("X-Client-Request-Id"),
    )


# ──────────────────────────────────────────────────────────────────────────
# REJECT
# ──────────────────────────────────────────────────────────────────────────

@router.post("/{inventory_id}/reject", response_model=InventoryActionResponse)
def reject_inventory(
    inventory_id: int,
    payload: RejectInventoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_APPROVAL_ROLES)),
):
    inventory = inventory_service.reject_inventory_for_user(
        db, inventory_id, payload.reason, current_user
    )
    return {"message": "Inventory rejected", "inventory": inventory}


# ──────────────────────────────────────────────────────────────────────────
# REOPEN (rejected → draft)
# ──────────────────────────────────────────────────────────────────────────

@router.post("/{inventory_id}/reopen", response_model=InventoryOut)
def reopen_inventory(
    inventory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_BRANCH_ROLES)),
):
    """Move a rejected inventory back to draft so the branch can correct and resubmit."""
    return inventory_service.reopen_inventory_for_user(db, inventory_id, current_user)


# ──────────────────────────────────────────────────────────────────────────
# DELETE (draft only)
# ──────────────────────────────────────────────────────────────────────────

@router.delete("/{inventory_id}")
def delete_inventory(
    inventory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_BRANCH_ROLES)),
):
    """Permanently delete a DRAFT inventory and all its lines."""
    return inventory_service.delete_draft_inventory(db, inventory_id, current_user)


# ──────────────────────────────────────────────────────────────────────────
# EPIC 10 — Auto-replenishment trigger & preview
# ──────────────────────────────────────────────────────────────────────────

@router.post("/{inventory_id}/trigger-replenishment", status_code=201)
def trigger_replenishment(
    inventory_id: int,
    days_of_cover: int = Query(3, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_APPROVAL_ROLES)),
):
    """
    Trigger auto-replenishment order generation after inventory approval.
    Idempotent: returns existing order if already generated for this inventory.
    Returns None (204-like body) if no items need replenishment.
    """
    order = replenishment_service.generate_replenishment_order(
        db, inventory_id, current_user, days_of_cover=days_of_cover
    )
    if order is None:
        return {"message": "No items need replenishment", "order_id": None}
    return {
        "message": "Replenishment order generated",
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "line_count": len(order.lines),
    }


@router.get("/branches/{branch_id}/replenishment-preview")
def replenishment_preview(
    branch_id: int,
    days_of_cover: int = Query(3, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_APPROVAL_ROLES)),
):
    """
    Dry-run replenishment calculation for a branch.
    Shows what would be ordered without creating any records.
    """
    return replenishment_service.preview_replenishment_order(
        db, branch_id=branch_id, days_of_cover=days_of_cover
    )
