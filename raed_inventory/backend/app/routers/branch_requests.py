from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_user_roles, is_platform_admin, is_read_only_auditor, require_roles
from app.core.errors import AppError
from app.core.locking import lock_row
from app.database import get_db
from app.models import (
    AreaManagerAssignment,
    Branch,
    BranchBrand,
    BranchRequest,
    BranchRequestLine,
    BranchRequestLineStatus,
    BranchRequestStatus,
    Brand,
    Item,
    ItemBrand,
    ItemType,
    ProductionOrder,
    ProductionOrderStatus,
    SupplyDefaultSource,
    SupplySourceType,
    User,
    WarehouseLine,
    WarehouseLineSourceType,
    WarehouseLineStatus,
)
from app.schemas import (
    BranchRequestApprovePayload,
    BranchRequestCreate,
    BranchRequestListResponse,
    BranchRequestModifyApprovePayload,
    BranchRequestOut,
    BranchRequestRejectPayload,
    BranchRequestUpdate,
    ItemOut,
)
from app.services import audit_service
from app.services.branch_request_split_service import split_branch_request as _split_request_service
from app.services import supply_chain_idempotency_service


router = APIRouter(prefix="/api/v1/branch-requests", tags=["Branch Requests"])

SCOPED_ROLES = ("branch_user", "branch_manager", "area_manager", "internal_auditor", "admin", "super_admin")


def _roles(user: User) -> list[str]:
    return get_user_roles(user)


def _is_admin(user: User) -> bool:
    return is_platform_admin(user)


def _is_branch_role(user: User) -> bool:
    return any(r in _roles(user) for r in ("branch_user", "branch_manager"))


def _is_area_manager(user: User) -> bool:
    return "area_manager" in _roles(user)


def _get_request(db: Session, request_id: int) -> BranchRequest:
    row = db.query(BranchRequest).options(
        joinedload(BranchRequest.branch),
        joinedload(BranchRequest.brand),
        joinedload(BranchRequest.lines).joinedload(BranchRequestLine.item).joinedload(Item.category),
        joinedload(BranchRequest.lines).joinedload(BranchRequestLine.item).joinedload(Item.unit),
    ).filter(BranchRequest.id == request_id).first()
    if not row:
        raise AppError(
            status_code=404,
            error_code="branch_requests.not_found",
            message="Branch request not found",
            detail={"request_id": request_id},
        )
    return row


def _get_request_for_update(db: Session, request_id: int) -> BranchRequest:
    """
    PostgreSQL cannot apply FOR UPDATE to the nullable side of the eager-load
    outer joins used by _get_request(). Lock the base BranchRequest row first,
    then load the full graph in a second query within the same transaction.
    """
    locked = lock_row(
        db.query(BranchRequest).filter(BranchRequest.id == request_id)
    ).first()
    if not locked:
        raise AppError(
            status_code=404,
            error_code="branch_requests.not_found",
            message="Branch request not found",
            detail={"request_id": request_id},
        )
    return _get_request(db, request_id)


def _branch_brand_allowed(db: Session, branch_id: int, brand_id: int) -> None:
    exists = db.query(BranchBrand).filter(
        BranchBrand.branch_id == branch_id,
        BranchBrand.brand_id == brand_id,
    ).first()
    if not exists:
        raise AppError(
            status_code=400,
            error_code="branch_requests.brand_not_allowed_for_branch",
            message="Request brand is not assigned to this branch",
            detail={"branch_id": branch_id, "brand_id": brand_id},
        )


def _resolve_allowed_items_brand_id(db: Session, branch_id: int, brand_id: int | None) -> int:
    if brand_id is not None:
        _branch_brand_allowed(db, branch_id, brand_id)
        return brand_id
    rows = db.query(BranchBrand).filter(BranchBrand.branch_id == branch_id).all()
    brand_ids = sorted({row.brand_id for row in rows})
    if len(brand_ids) == 1:
        return brand_ids[0]
    raise AppError(
        status_code=400,
        error_code="branch_requests.brand_id_required",
        message="Brand must be selected for this branch",
        detail={"branch_id": branch_id},
    )


def _area_scope_filter(db: Session, user: User, q):
    now = datetime.utcnow()
    return (
        q.join(Branch, Branch.id == BranchRequest.branch_id)
        .join(
            AreaManagerAssignment,
            (AreaManagerAssignment.brand_id == BranchRequest.brand_id)
            & (AreaManagerAssignment.city == Branch.city)
            & (AreaManagerAssignment.user_id == user.id)
            & (AreaManagerAssignment.active == True)
            & ((AreaManagerAssignment.ended_at.is_(None)) | (AreaManagerAssignment.ended_at > now)),
        )
        .filter(BranchRequest.status != BranchRequestStatus.DRAFT)
    )


def _can_view(db: Session, user: User, row: BranchRequest) -> bool:
    if _is_admin(user):
        return True
    if is_read_only_auditor(user):
        return True
    if _is_branch_role(user):
        return user.branch_id == row.branch_id
    if _is_area_manager(user):
        q = db.query(BranchRequest).filter(BranchRequest.id == row.id)
        return _area_scope_filter(db, user, q).first() is not None
    return False


def _require_view(db: Session, user: User, row: BranchRequest) -> None:
    if not _can_view(db, user, row):
        raise AppError(
            status_code=403,
            error_code="branch_requests.access_denied",
            message="Access denied",
            detail={"request_id": row.id},
        )


def _require_branch_write(user: User, branch_id: int) -> None:
    if _is_admin(user):
        return
    if _is_branch_role(user) and user.branch_id == branch_id:
        return
    raise AppError(
        status_code=403,
        error_code="branch_requests.branch_write_denied",
        message="Cannot write requests for this branch",
        detail={"branch_id": branch_id},
    )


def _require_branch_active_for_new_requests(db: Session, branch_id: int) -> None:
    """Inactive branches stay in DB for history but must not accept new supply-chain requests."""
    row = db.query(Branch).filter(Branch.id == branch_id, Branch.is_deleted == False).first()  # noqa: E712
    if not row or not row.active:
        raise AppError(
            status_code=400,
            error_code="branch_requests.branch_inactive",
            message="Branch is inactive or unavailable for new requests",
            detail={"branch_id": branch_id},
        )


def _require_area_review(db: Session, user: User, row: BranchRequest) -> None:
    if _is_admin(user):
        return
    if _is_area_manager(user) and _can_view(db, user, row):
        return
    raise AppError(
        status_code=403,
        error_code="branch_requests.review_denied",
        message="Cannot review this branch request",
        detail={"request_id": row.id},
    )


def _source_for_line(item: Item, explicit: Optional[SupplySourceType]) -> tuple[SupplySourceType, Optional[SupplyDefaultSource]]:
    chosen = explicit or item.source_type
    if chosen == SupplySourceType.NOT_REQUESTABLE or item.source_type == SupplySourceType.NOT_REQUESTABLE:
        raise AppError(
            status_code=400,
            error_code="branch_requests.item_not_requestable",
            message="Item is not requestable",
            detail={"item_id": item.id},
        )
    if item.source_type != SupplySourceType.BOTH and chosen != item.source_type:
        raise AppError(
            status_code=400,
            error_code="branch_requests.invalid_line_source",
            message="Requested source is not allowed for this item",
            detail={"item_id": item.id, "item_source_type": item.source_type.value, "requested_source_type": chosen.value},
        )
    resolved = item.default_source if chosen == SupplySourceType.BOTH else SupplyDefaultSource(chosen.value)
    return chosen, resolved


def _validate_lines(db: Session, brand_id: int, lines) -> list[BranchRequestLine]:
    result: list[BranchRequestLine] = []
    seen: set[int] = set()
    for line in lines:
        if line.item_id in seen:
            raise AppError(
                status_code=400,
                error_code="branch_requests.duplicate_item",
                message="Duplicate item in request",
                detail={"item_id": line.item_id},
            )
        seen.add(line.item_id)
        item = db.query(Item).filter(
            Item.id == line.item_id,
            Item.active == True,
            Item.branch_requestable == True,
            Item.is_deleted == False,
        ).first()
        if not item:
            raise AppError(
                status_code=400,
                error_code="branch_requests.item_not_requestable",
                message="Item is not requestable",
                detail={"item_id": line.item_id},
            )
        allowed = db.query(ItemBrand).filter(
            ItemBrand.item_id == item.id,
            ItemBrand.brand_id == brand_id,
        ).first()
        if not allowed:
            raise AppError(
                status_code=400,
                error_code="branch_requests.item_not_allowed_for_brand",
                message="Item is not assigned to request brand",
                detail={"item_id": item.id, "brand_id": brand_id},
            )
        source_type, resolved_source_type = _source_for_line(item, line.source_type)
        result.append(BranchRequestLine(
            item_id=item.id,
            qty_requested=line.qty_requested,
            source_type=source_type,
            resolved_source_type=resolved_source_type,
            status=BranchRequestLineStatus.DRAFT,
            notes=line.notes,
        ))
    return result


def _ensure_submitted(row: BranchRequest) -> None:
    if row.status != BranchRequestStatus.SUBMITTED:
        raise AppError(
            status_code=400,
            error_code="branch_requests.not_submitted",
            message="Only submitted requests can be reviewed",
            detail={"request_id": row.id, "status": row.status.value},
        )


def _ensure_approved(row: BranchRequest) -> None:
    if row.status not in (BranchRequestStatus.AREA_APPROVED, BranchRequestStatus.SPLIT, BranchRequestStatus.IN_EXECUTION):
        raise AppError(
            status_code=400,
            error_code="branch_requests.not_area_approved",
            message="Only area-approved or already split requests can be split",
            detail={"request_id": row.id, "status": row.status.value},
        )


def _audit(db: Session, request: Request, user: User, action: str, row: BranchRequest, values: dict | None = None) -> None:
    audit_service.log(
        db,
        user_id=user.id,
        action=action,
        module="branch_requests",
        entity_type="branch_request",
        entity_id=row.id,
        new_values=values,
        ip_address=request.client.host if request.client else None,
    )


def _state_snapshot(row: BranchRequest) -> dict:
    return {
        "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "approved_by": row.approved_by,
        "rejected_at": row.rejected_at.isoformat() if row.rejected_at else None,
        "rejected_by": row.rejected_by,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
    }


def _audit_state_change(db: Session, request: Request, user: User, action: str, row: BranchRequest, old_state: dict, extra: dict | None = None) -> None:
    new_state = _state_snapshot(row)
    if extra:
        new_state.update(extra)
    audit_service.log(
        db,
        user_id=user.id,
        action=action,
        module="branch_requests",
        entity_type="branch_request",
        entity_id=row.id,
        old_values=old_state,
        new_values=new_state,
        ip_address=request.client.host if request.client else None,
    )


def _populate_request_snapshots(row: BranchRequest) -> None:
    if row.brand and not row.brand_name_snapshot:
        row.brand_name_snapshot = row.brand.name
    for line in row.lines:
        item = line.item
        if not item:
            continue
        if not line.item_name_ar_snapshot:
            line.item_name_ar_snapshot = item.item_name_ar
        if not line.item_name_en_snapshot:
            line.item_name_en_snapshot = item.item_name_en
        if not line.item_code_snapshot:
            line.item_code_snapshot = item.item_code
        if not line.unit_code_snapshot and item.unit:
            line.unit_code_snapshot = item.unit.code


@router.get("/allowed-items", response_model=list[ItemOut])
def list_allowed_items(
    branch_id: int = Query(...),
    brand_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*SCOPED_ROLES)),
):
    _require_branch_write(current_user, branch_id)
    _require_branch_active_for_new_requests(db, branch_id)
    resolved_brand_id = _resolve_allowed_items_brand_id(db, branch_id, brand_id)
    return db.query(Item).options(
        joinedload(Item.category),
        joinedload(Item.unit),
    ).join(ItemBrand, ItemBrand.item_id == Item.id).filter(
        ItemBrand.brand_id == resolved_brand_id,
        Item.active == True,
        Item.branch_requestable == True,
        Item.visible_in_branch_ui == True,
        Item.source_type != SupplySourceType.NOT_REQUESTABLE,
        Item.item_type != ItemType.raw_material,
        Item.item_code.notlike("DEMO-%"),
        Item.is_deleted == False,
    ).order_by(Item.category_id.asc(), Item.item_name_ar.asc(), Item.item_code.asc()).all()


@router.post("", response_model=BranchRequestOut, status_code=201)
def create_branch_request(
    payload: BranchRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*SCOPED_ROLES)),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="branch_requests.create",
        current_user=current_user,
    )
    if replayed:
        existing = db.query(BranchRequest).filter(
            BranchRequest.branch_id == payload.branch_id,
            BranchRequest.brand_id == payload.brand_id,
            BranchRequest.created_by == current_user.id,
        ).order_by(BranchRequest.id.desc()).first()
        if existing:
            return _get_request(db, existing.id)

    _require_branch_write(current_user, payload.branch_id)
    _require_branch_active_for_new_requests(db, payload.branch_id)
    _branch_brand_allowed(db, payload.branch_id, payload.brand_id)
    db.query(Branch).filter(Branch.id == payload.branch_id).first() or _missing_branch(payload.branch_id)
    db.query(Brand).filter(Brand.id == payload.brand_id, Brand.active == True).first() or _missing_brand(payload.brand_id)

    row = BranchRequest(
        request_no=f"BR-TMP-{int(datetime.utcnow().timestamp() * 1000000)}",
        branch_id=payload.branch_id,
        brand_id=payload.brand_id,
        priority=payload.priority,
        created_by=current_user.id,
        status=BranchRequestStatus.DRAFT,
    )
    row.lines = _validate_lines(db, payload.brand_id, payload.lines)
    _populate_request_snapshots(row)
    db.add(row)
    db.flush()
    row.request_no = f"BR-{row.id:06d}"
    _audit(db, request, current_user, "request_created", row, {"status": row.status.value})
    db.commit()
    supply_chain_idempotency_service.complete(
        db,
        record=idempotency_record,
        response_reference_type="branch_request",
        response_reference_id=row.id,
    )
    return _get_request(db, row.id)


@router.get("", response_model=BranchRequestListResponse)
def list_branch_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[BranchRequestStatus] = None,
    brand_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*SCOPED_ROLES)),
):
    q = db.query(BranchRequest).options(
        joinedload(BranchRequest.lines).joinedload(BranchRequestLine.item),
    )
    if status:
        q = q.filter(BranchRequest.status == status)
    if brand_id:
        q = q.filter(BranchRequest.brand_id == brand_id)
    if branch_id:
        q = q.filter(BranchRequest.branch_id == branch_id)

    if _is_admin(current_user):
        pass
    elif _is_branch_role(current_user):
        q = q.filter(BranchRequest.branch_id == current_user.branch_id)
    elif _is_area_manager(current_user):
        q = _area_scope_filter(db, current_user, q)

    total = q.count()
    items = q.order_by(BranchRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{request_id}", response_model=BranchRequestOut)
def get_branch_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*SCOPED_ROLES)),
):
    row = _get_request(db, request_id)
    _require_view(db, current_user, row)
    return row


@router.patch("/{request_id}", response_model=BranchRequestOut)
def update_branch_request(
    request_id: int,
    payload: BranchRequestUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*SCOPED_ROLES)),
):
    row = _get_request(db, request_id)
    _require_branch_write(current_user, row.branch_id)
    if row.status != BranchRequestStatus.DRAFT:
        raise AppError(status_code=400, error_code="branch_requests.not_draft", message="Only draft requests can be edited")
    row.priority = payload.priority
    row.lines = _validate_lines(db, row.brand_id, payload.lines)
    row.updated_at = datetime.utcnow()
    _audit(db, request, current_user, "request_updated", row, {"status": row.status.value})
    db.commit()
    return _get_request(db, row.id)


@router.post("/{request_id}/submit", response_model=BranchRequestOut)
def submit_branch_request(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*SCOPED_ROLES)),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="branch_requests.submit",
        current_user=current_user,
    )
    row = _get_request(db, request_id)
    _require_branch_write(current_user, row.branch_id)
    if replayed or row.status != BranchRequestStatus.DRAFT:
        return row
    old_state = _state_snapshot(row)
    if row.status != BranchRequestStatus.DRAFT:
        raise AppError(status_code=400, error_code="branch_requests.not_draft", message="Only draft requests can be submitted")
    _populate_request_snapshots(row)
    row.status = BranchRequestStatus.SUBMITTED
    row.submitted_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    for line in row.lines:
        line.status = BranchRequestLineStatus.SUBMITTED
    _audit_state_change(db, request, current_user, "request_submitted", row, old_state)
    db.commit()
    supply_chain_idempotency_service.complete(
        db,
        record=idempotency_record,
        response_reference_type="branch_request",
        response_reference_id=row.id,
    )
    return _get_request(db, row.id)


@router.post("/{request_id}/approve", response_model=BranchRequestOut)
def approve_branch_request(
    request_id: int,
    payload: BranchRequestApprovePayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("area_manager", "admin", "super_admin")),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="branch_requests.approve",
        current_user=current_user,
    )
    row = _get_request_for_update(db, request_id)
    _require_area_review(db, current_user, row)
    if replayed or row.status in (BranchRequestStatus.AREA_APPROVED, BranchRequestStatus.SPLIT, BranchRequestStatus.IN_EXECUTION, BranchRequestStatus.DELIVERED):
        return row
    _ensure_submitted(row)
    old_state = _state_snapshot(row)
    row.status = BranchRequestStatus.AREA_APPROVED
    row.approved_at = datetime.utcnow()
    row.approved_by = current_user.id
    row.approval_note = payload.approval_note
    row.updated_at = datetime.utcnow()
    for line in row.lines:
        line.qty_approved = line.qty_requested
        line.status = BranchRequestLineStatus.APPROVED
    _audit_state_change(db, request, current_user, "request_approved", row, old_state)
    # Auto-split (2026-04-24 demo readiness): split immediately on approve
    # so demo flow does not require a separate /split call.
    _split_request_service(db, row)
    _audit_state_change(db, request, current_user, "request_auto_split", row, {"status": BranchRequestStatus.AREA_APPROVED.value})
    db.commit()
    supply_chain_idempotency_service.complete(
        db,
        record=idempotency_record,
        response_reference_type="branch_request",
        response_reference_id=row.id,
    )
    return _get_request(db, row.id)


@router.post("/{request_id}/modify-and-approve", response_model=BranchRequestOut)
def modify_and_approve_branch_request(
    request_id: int,
    payload: BranchRequestModifyApprovePayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("area_manager", "admin", "super_admin")),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="branch_requests.modify_and_approve",
        current_user=current_user,
    )
    row = _get_request_for_update(db, request_id)
    _require_area_review(db, current_user, row)
    if replayed or row.status in (BranchRequestStatus.AREA_APPROVED, BranchRequestStatus.SPLIT, BranchRequestStatus.IN_EXECUTION, BranchRequestStatus.DELIVERED):
        return row
    _ensure_submitted(row)
    old_state = _state_snapshot(row)
    by_id = {line.id: line for line in row.lines}
    for patch in payload.lines:
        line = by_id.get(patch.line_id)
        if not line:
            raise AppError(
                status_code=400,
                error_code="branch_requests.line_not_found",
                message="Request line not found",
                detail={"line_id": patch.line_id},
            )
        if Decimal(str(patch.qty_approved)) > Decimal(str(line.qty_requested)):
            raise AppError(
                status_code=400,
                error_code="branch_requests.qty_approved_exceeds_requested",
                message="Approved quantity cannot exceed requested quantity",
                detail={
                    "line_id": line.id,
                    "qty_requested": str(line.qty_requested),
                    "qty_approved": str(patch.qty_approved),
                },
            )
        line.qty_approved = patch.qty_approved
        line.approval_note = patch.approval_note or payload.approval_note
    for line in row.lines:
        if line.qty_approved is None:
            line.qty_approved = line.qty_requested
        line.status = BranchRequestLineStatus.APPROVED
    row.status = BranchRequestStatus.AREA_APPROVED
    row.approved_at = datetime.utcnow()
    row.approved_by = current_user.id
    row.approval_note = payload.approval_note
    row.updated_at = datetime.utcnow()
    _audit_state_change(db, request, current_user, "request_modified_and_approved", row, old_state)
    # Auto-split (2026-04-24 demo readiness)
    _split_request_service(db, row)
    _audit_state_change(db, request, current_user, "request_auto_split", row, {"status": BranchRequestStatus.AREA_APPROVED.value})
    db.commit()
    supply_chain_idempotency_service.complete(
        db,
        record=idempotency_record,
        response_reference_type="branch_request",
        response_reference_id=row.id,
    )
    return _get_request(db, row.id)


@router.post("/{request_id}/split", response_model=BranchRequestOut)
def split_branch_request(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("area_manager", "admin", "super_admin")),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="branch_requests.split",
        current_user=current_user,
    )
    """
    Manual split endpoint — kept for backward compatibility and recovery
    paths. Now an idempotent thin wrapper around the split service:
    if the request is already split, returns the current state with 200
    (does NOT raise). The auto-split fired by /approve and
    /modify-and-approve makes this endpoint optional in the demo flow.
    """
    row = _get_request_for_update(db, request_id)
    _require_area_review(db, current_user, row)
    if replayed or row.status in (BranchRequestStatus.SPLIT, BranchRequestStatus.IN_EXECUTION, BranchRequestStatus.DELIVERED):
        return row
    _ensure_approved(row)
    old_state = _state_snapshot(row)
    # If it's already split, the service short-circuits silently — no error.
    _split_request_service(db, row)
    _audit_state_change(db, request, current_user, "request_split", row, old_state)
    db.commit()
    supply_chain_idempotency_service.complete(
        db,
        record=idempotency_record,
        response_reference_type="branch_request",
        response_reference_id=row.id,
    )
    return _get_request(db, row.id)


@router.post("/{request_id}/reject", response_model=BranchRequestOut)
def reject_branch_request(
    request_id: int,
    payload: BranchRequestRejectPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("area_manager", "admin", "super_admin")),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="branch_requests.reject",
        current_user=current_user,
    )
    row = _get_request(db, request_id)
    _require_area_review(db, current_user, row)
    if replayed or row.status == BranchRequestStatus.AREA_REJECTED:
        return row
    _ensure_submitted(row)
    old_state = _state_snapshot(row)
    row.status = BranchRequestStatus.AREA_REJECTED
    row.rejected_at = datetime.utcnow()
    row.rejected_by = current_user.id
    row.rejection_note = payload.rejection_note
    row.updated_at = datetime.utcnow()
    for line in row.lines:
        line.status = BranchRequestLineStatus.REJECTED
    _audit_state_change(db, request, current_user, "request_rejected", row, old_state)
    db.commit()
    supply_chain_idempotency_service.complete(
        db,
        record=idempotency_record,
        response_reference_type="branch_request",
        response_reference_id=row.id,
    )
    return _get_request(db, row.id)


def _missing_branch(branch_id: int):
    raise AppError(
        status_code=404,
        error_code="branch_requests.branch_not_found",
        message="Branch not found",
        detail={"branch_id": branch_id},
    )


def _missing_brand(brand_id: int):
    raise AppError(
        status_code=404,
        error_code="branch_requests.brand_not_found",
        message="Brand not found",
        detail={"brand_id": brand_id},
    )
