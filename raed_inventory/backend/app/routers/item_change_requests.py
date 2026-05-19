from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.auth import can_access_branch, can_access_warehouse, get_user_roles, require_roles
from app.database import get_db
from app.models import BranchItemAvailability, Item, ItemChangeRequest, User, WarehouseStock


router = APIRouter(prefix="/api/v1/item-change-requests", tags=["item-change-requests"])

REQUEST_ROLES = ("warehouse_manager", "area_manager", "admin", "super_admin")
REVIEW_ROLES = ("internal_auditor", "admin", "super_admin")
READ_ROLES = REQUEST_ROLES + REVIEW_ROLES + ("operations_manager",)


class WarehouseRemovePayload(BaseModel):
    warehouse_id: int | None = None
    item_id: int
    reason: str | None = None


class BranchItemPayload(BaseModel):
    branch_id: int
    item_id: int
    reason: str | None = None


class NewItemPayload(BaseModel):
    target_type: str = "system"
    warehouse_id: int | None = None
    branch_id: int | None = None
    proposed_item_name_ar: str
    proposed_item_name_en: str | None = None
    proposed_item_code: str | None = None
    proposed_unit: str | None = None
    proposed_source_type: str | None = None
    reason: str | None = None


class ItemRenamePayload(BaseModel):
    warehouse_id: int | None = None
    item_id: int
    item_name_ar: str | None = None
    item_name_en: str | None = None


class ReviewPayload(BaseModel):
    review_note: str | None = None


def _request_no(db: Session) -> str:
    last_id = db.query(ItemChangeRequest.id).order_by(ItemChangeRequest.id.desc()).limit(1).scalar() or 0
    return f"ICR-{datetime.utcnow():%Y%m%d}-{last_id + 1:04d}"


def _roles(user: User) -> set[str]:
    return set(get_user_roles(user))


def _is_reviewer(user: User) -> bool:
    return bool(_roles(user).intersection(REVIEW_ROLES + ("operations_manager",)))


def _item_label(item: Item | None) -> str | None:
    if not item:
        return None
    return item.item_name_ar or item.item_name_en or item.item_code


def _row_to_dict(row: ItemChangeRequest) -> dict:
    return {
        "id": row.id,
        "request_no": row.request_no,
        "request_type": row.request_type,
        "status": row.status,
        "target_type": row.target_type,
        "warehouse_id": row.warehouse_id,
        "warehouse_name": getattr(row.warehouse, "warehouse_name", None),
        "branch_id": row.branch_id,
        "branch_name": getattr(row.branch, "branch_name", None),
        "item_id": row.item_id,
        "item_code": getattr(row.item, "item_code", None),
        "item_name": _item_label(row.item),
        "proposed_item_name_ar": row.proposed_item_name_ar,
        "proposed_item_name_en": row.proposed_item_name_en,
        "proposed_item_code": row.proposed_item_code,
        "proposed_unit": row.proposed_unit,
        "proposed_source_type": row.proposed_source_type,
        "reason": row.reason,
        "review_note": row.review_note,
        "failure_reason": row.failure_reason,
        "requested_by": row.requested_by,
        "requested_by_name": getattr(row.requester, "full_name", None),
        "reviewed_by": row.reviewed_by,
        "reviewed_by_name": getattr(row.reviewer, "full_name", None),
        "created_at": row.created_at,
        "reviewed_at": row.reviewed_at,
        "executed_at": row.executed_at,
    }


def _assert_item_exists(db: Session, item_id: int) -> Item:
    item = db.query(Item).filter(Item.id == item_id, Item.is_deleted == False).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("")
def list_requests(
    status: str | None = Query(None),
    request_type: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    q = db.query(ItemChangeRequest).options(
        joinedload(ItemChangeRequest.warehouse),
        joinedload(ItemChangeRequest.branch),
        joinedload(ItemChangeRequest.item),
        joinedload(ItemChangeRequest.requester),
        joinedload(ItemChangeRequest.reviewer),
    )
    if status:
        q = q.filter(ItemChangeRequest.status == status)
    if request_type:
        q = q.filter(ItemChangeRequest.request_type == request_type)
    if not _is_reviewer(current_user):
        q = q.filter(ItemChangeRequest.requested_by == current_user.id)
    rows = q.order_by(ItemChangeRequest.created_at.desc(), ItemChangeRequest.id.desc()).limit(300).all()
    return [_row_to_dict(row) for row in rows]


@router.post("/warehouse-remove")
def request_warehouse_remove(
    payload: WarehouseRemovePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_manager", "admin", "super_admin")),
):
    warehouse_id = payload.warehouse_id or current_user.warehouse_id
    if not warehouse_id or not can_access_warehouse(current_user, warehouse_id):
        raise HTTPException(status_code=403, detail="No access to warehouse")
    _assert_item_exists(db, payload.item_id)
    stock = db.query(WarehouseStock).filter(WarehouseStock.warehouse_id == warehouse_id, WarehouseStock.item_id == payload.item_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Item is not in this warehouse")
    row = ItemChangeRequest(
        request_no=_request_no(db),
        request_type="warehouse_remove",
        target_type="warehouse",
        warehouse_id=warehouse_id,
        item_id=payload.item_id,
        reason=payload.reason,
        requested_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)


@router.post("/branch-add")
def add_item_to_branch(
    payload: BranchItemPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("area_manager", "admin", "super_admin")),
):
    if not can_access_branch(current_user, payload.branch_id, db):
        raise HTTPException(status_code=403, detail="No access to branch")
    _assert_item_exists(db, payload.item_id)
    row = (
        db.query(BranchItemAvailability)
        .filter(BranchItemAvailability.branch_id == payload.branch_id, BranchItemAvailability.item_id == payload.item_id)
        .first()
    )
    if not row:
        row = BranchItemAvailability(branch_id=payload.branch_id, item_id=payload.item_id, added_by=current_user.id)
        db.add(row)
    row.active = True
    row.added_by = current_user.id
    row.removed_by = None
    row.reason = payload.reason
    row.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "branch_id": payload.branch_id, "item_id": payload.item_id, "active": True}


@router.post("/branch-remove")
def request_branch_remove(
    payload: BranchItemPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("area_manager", "admin", "super_admin")),
):
    if not can_access_branch(current_user, payload.branch_id, db):
        raise HTTPException(status_code=403, detail="No access to branch")
    _assert_item_exists(db, payload.item_id)
    row = ItemChangeRequest(
        request_no=_request_no(db),
        request_type="branch_remove",
        target_type="branch",
        branch_id=payload.branch_id,
        item_id=payload.item_id,
        reason=payload.reason,
        requested_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)


@router.post("/new-item")
def request_new_item(
    payload: NewItemPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REQUEST_ROLES)),
):
    if payload.warehouse_id and not can_access_warehouse(current_user, payload.warehouse_id):
        raise HTTPException(status_code=403, detail="No access to warehouse")
    if payload.branch_id and not can_access_branch(current_user, payload.branch_id, db):
        raise HTTPException(status_code=403, detail="No access to branch")
    row = ItemChangeRequest(
        request_no=_request_no(db),
        request_type="new_item",
        target_type=payload.target_type,
        warehouse_id=payload.warehouse_id,
        branch_id=payload.branch_id,
        proposed_item_name_ar=payload.proposed_item_name_ar.strip(),
        proposed_item_name_en=(payload.proposed_item_name_en or payload.proposed_item_name_ar).strip(),
        proposed_item_code=payload.proposed_item_code,
        proposed_unit=payload.proposed_unit,
        proposed_source_type=payload.proposed_source_type,
        reason=payload.reason,
        requested_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)


@router.post("/rename-item")
def rename_item(
    payload: ItemRenamePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_manager", "admin", "super_admin")),
):
    item = _assert_item_exists(db, payload.item_id)
    warehouse_id = payload.warehouse_id or current_user.warehouse_id
    if "warehouse_manager" in _roles(current_user):
        if not warehouse_id or not can_access_warehouse(current_user, warehouse_id):
            raise HTTPException(status_code=403, detail="No access to warehouse")
        stock = db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == warehouse_id,
            WarehouseStock.item_id == payload.item_id,
        ).first()
        if not stock:
            raise HTTPException(status_code=404, detail="Item is not in this warehouse")

    new_ar = (payload.item_name_ar or "").strip()
    new_en = (payload.item_name_en or "").strip()
    if not new_ar and not new_en:
        raise HTTPException(status_code=400, detail="Item name is required")
    if new_ar:
        item.item_name_ar = new_ar
    if new_en:
        item.item_name_en = new_en
    elif new_ar and not item.item_name_en:
        item.item_name_en = new_ar
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return {
        "ok": True,
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name_ar": item.item_name_ar,
        "item_name_en": item.item_name_en,
    }


@router.post("/{request_id}/approve")
def approve_request(
    request_id: int,
    payload: ReviewPayload | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    row = db.query(ItemChangeRequest).filter(ItemChangeRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Request is not pending")

    note = payload.review_note if payload else None
    now = datetime.utcnow()
    row.reviewed_by = current_user.id
    row.reviewed_at = now
    row.review_note = note

    if row.request_type == "warehouse_remove":
        stock = db.query(WarehouseStock).filter(WarehouseStock.warehouse_id == row.warehouse_id, WarehouseStock.item_id == row.item_id).first()
        if not stock:
            row.status = "executed"
            row.executed_at = now
        elif (stock.current_qty or Decimal("0")) != 0 or (stock.reserved_qty or Decimal("0")) != 0:
            row.status = "failed"
            row.failure_reason = "لا يمكن حذف صنف من المستودع وله كمية أو كمية محجوزة."
        else:
            db.delete(stock)
            row.status = "executed"
            row.executed_at = now
    elif row.request_type == "branch_remove":
        availability = (
            db.query(BranchItemAvailability)
            .filter(BranchItemAvailability.branch_id == row.branch_id, BranchItemAvailability.item_id == row.item_id)
            .first()
        )
        if not availability:
            availability = BranchItemAvailability(branch_id=row.branch_id, item_id=row.item_id)
            db.add(availability)
        availability.active = False
        availability.removed_by = current_user.id
        availability.reason = note or row.reason
        availability.updated_at = now
        row.status = "executed"
        row.executed_at = now
    elif row.request_type == "new_item":
        row.status = "approved"
    else:
        raise HTTPException(status_code=400, detail="Unsupported request type")

    db.commit()
    db.refresh(row)
    return _row_to_dict(row)


@router.post("/{request_id}/reject")
def reject_request(
    request_id: int,
    payload: ReviewPayload | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    row = db.query(ItemChangeRequest).filter(ItemChangeRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Request is not pending")
    row.status = "rejected"
    row.reviewed_by = current_user.id
    row.reviewed_at = datetime.utcnow()
    row.review_note = payload.review_note if payload else None
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)
