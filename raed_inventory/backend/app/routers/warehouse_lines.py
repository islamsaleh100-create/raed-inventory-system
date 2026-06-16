from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.core.auth import get_user_roles, is_platform_admin, is_read_only_auditor, require_roles
from app.core.locking import lock_row
from app.database import get_db
from app.models import (
    Branch,
    BranchRequestLineStatus,
    TransactionType,
    User,
    WarehouseLine,
    WarehouseLineSourceType,
    WarehouseLineStatus,
    WarehouseStock,
)
from app.schemas import WarehouseDelayPayload, WarehouseIssuePayload, WarehouseLineOut
from app.services import audit_service, stock_ledger_service
from app.services import supply_chain_idempotency_service
from app.services.supply_chain_serializers import enrich_warehouse_lines, warehouse_line_out


router = APIRouter(prefix="/api/v1/warehouse-lines", tags=["Warehouse Lines"])

WAREHOUSE_ROLES = ("warehouse_user", "warehouse_manager", "internal_auditor", "admin", "super_admin")


def _as_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _get_line(db: Session, line_id: int) -> WarehouseLine:
    row = db.query(WarehouseLine).options(
        joinedload(WarehouseLine.item),
        joinedload(WarehouseLine.source_request_line),
        joinedload(WarehouseLine.branch),
    ).filter(WarehouseLine.id == line_id).first()
    if not row:
        raise AppError(
            status_code=404,
            error_code="warehouse_lines.not_found",
            message="Warehouse line not found",
            detail={"warehouse_line_id": line_id},
        )
    return row


def _audit(db: Session, request: Request, user: User, action: str, row: WarehouseLine, values: dict | None = None) -> None:
    audit_service.log(
        db,
        user_id=user.id,
        action=action,
        module="warehouse_lines",
        entity_type="warehouse_line",
        entity_id=row.id,
        new_values=values,
        ip_address=request.client.host if request.client else None,
    )


def _warehouse_id_for_line(row: WarehouseLine) -> int:
    branch = row.branch
    if not branch or not branch.warehouse_id:
        raise AppError(
            status_code=400,
            error_code="warehouse_lines.branch_warehouse_missing",
            message="Destination branch has no warehouse",
            detail={"branch_id": row.branch_id},
        )
    return branch.warehouse_id


def _has_global_access(user: User) -> bool:
    return is_platform_admin(user) or is_read_only_auditor(user)


def _require_warehouse_access(user: User, row: WarehouseLine) -> None:
    if _has_global_access(user):
        return
    warehouse_id = _warehouse_id_for_line(row)
    if user.warehouse_id == warehouse_id:
        return
    raise AppError(
        status_code=403,
        error_code="warehouse_lines.access_denied",
        message="Access denied for this warehouse line",
        detail={"warehouse_id": warehouse_id},
    )


def _deduct_stock(db: Session, row: WarehouseLine, qty: Decimal, user: User) -> None:
    warehouse_id = _warehouse_id_for_line(row)
    stock = lock_row(
        db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == warehouse_id,
            WarehouseStock.item_id == row.item_id,
        )
    ).first()
    if not stock or _as_decimal(stock.current_qty) < qty:
        raise AppError(
            status_code=400,
            error_code="warehouse_lines.insufficient_stock",
            message="Insufficient warehouse stock",
            detail={"warehouse_id": warehouse_id, "item_id": row.item_id, "qty": str(qty)},
        )
    stock.current_qty = _as_decimal(stock.current_qty) - qty
    if row.source_type == WarehouseLineSourceType.BRANCH_REQUEST:
        reserved = _as_decimal(stock.reserved_qty)
        if reserved < qty:
            raise AppError(
                status_code=400,
                error_code="warehouse_lines.reservation_release_exceeds_reserved",
                message="Cannot release more reserved stock than currently reserved",
                detail={
                    "warehouse_id": warehouse_id,
                    "item_id": row.item_id,
                    "reserved_qty": str(reserved),
                    "issue_qty": str(qty),
                },
            )
        stock.reserved_qty = reserved - qty
    stock.last_updated = datetime.utcnow()
    stock_ledger_service.post_transaction(
        db,
        transaction_type=TransactionType.warehouse_issue,
        item_id=row.item_id,
        qty=-qty,
        source_type="warehouse",
        source_id=warehouse_id,
        destination_type="branch_request",
        destination_id=row.source_request_id,
        reference_no=f"WL-{row.id}",
        notes="Supply Chain V1 warehouse issue",
        created_by=user.id,
    )


@router.get("", response_model=list[WarehouseLineOut])
def list_warehouse_lines(
    status: Optional[WarehouseLineStatus] = None,
    branch_id: Optional[int] = Query(None),
    item_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None, description="Item name/code or branch name"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WAREHOUSE_ROLES)),
):
    from app.models import Item

    q = db.query(WarehouseLine).options(joinedload(WarehouseLine.item), joinedload(WarehouseLine.branch))
    if status:
        q = q.filter(WarehouseLine.status == status)
    if branch_id:
        q = q.filter(WarehouseLine.branch_id == branch_id)
    if item_id:
        q = q.filter(WarehouseLine.item_id == item_id)
    if date_from:
        q = q.filter(WarehouseLine.created_at >= date_from)
    if date_to:
        q = q.filter(WarehouseLine.created_at <= date_to)
    scoped_wh = None if _has_global_access(current_user) else current_user.warehouse_id
    if scoped_wh is not None or search:
        q = q.join(Branch, Branch.id == WarehouseLine.branch_id)
        if scoped_wh is not None:
            q = q.filter(Branch.warehouse_id == scoped_wh)
    if search:
        term = f"%{search.strip()}%"
        q = q.join(Item, Item.id == WarehouseLine.item_id).filter(
            or_(
                Branch.branch_name.ilike(term),
                Item.item_name_ar.ilike(term),
                Item.item_name_en.ilike(term),
                Item.item_code.ilike(term),
            )
        )
    rows = q.order_by(WarehouseLine.created_at.desc()).all()
    return enrich_warehouse_lines(db, rows, warehouse_id_resolver=_warehouse_id_for_line)


@router.get("/{line_id}", response_model=WarehouseLineOut)
def get_warehouse_line(
    line_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WAREHOUSE_ROLES)),
):
    row = _get_line(db, line_id)
    _require_warehouse_access(current_user, row)
    wh_id = _warehouse_id_for_line(row)
    stock = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == wh_id,
        WarehouseStock.item_id == row.item_id,
    ).first()
    return warehouse_line_out(row, stock=stock)


@router.post("/{line_id}/receive", response_model=WarehouseLineOut)
def receive_line(
    line_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WAREHOUSE_ROLES)),
):
    """
    Supply-chain V1 warehouse receive / acknowledge step.

    - BRANCH_REQUEST + PENDING -> AVAILABLE (no stock movement; reservation unchanged).
    - BRANCH_REQUEST + AVAILABLE -> idempotent OK.
    - KITCHEN_OUTPUT already in stock path -> idempotent OK when line is fulfillable.
    - KITCHEN_MATERIAL_REQUEST -> not applicable (lines are issued in one shot elsewhere).
    """
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="warehouse_lines.receive",
        current_user=current_user,
    )
    row = _get_line(db, line_id)
    _require_warehouse_access(current_user, row)
    if replayed:
        return row

    if row.source_type == WarehouseLineSourceType.KITCHEN_MATERIAL_REQUEST:
        raise AppError(
            status_code=400,
            error_code="warehouse_lines.receive_not_applicable",
            message="Receive is not used for kitchen material warehouse lines",
            detail={"warehouse_line_id": line_id, "source_type": row.source_type.value},
        )

    if row.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT:
        if row.status in (
            WarehouseLineStatus.AVAILABLE,
            WarehouseLineStatus.PARTIAL,
            WarehouseLineStatus.READY_FOR_DISPATCH,
        ):
            supply_chain_idempotency_service.complete(
                db, record=idempotency_record, response_reference_type="warehouse_line", response_reference_id=row.id
            )
            return _get_line(db, row.id)
        raise AppError(
            status_code=400,
            error_code="warehouse_lines.receive_invalid_status",
            message="Kitchen output line is not in a receivable state",
            detail={"warehouse_line_id": line_id, "status": row.status.value},
        )

    if row.source_type != WarehouseLineSourceType.BRANCH_REQUEST:
        raise AppError(
            status_code=400,
            error_code="warehouse_lines.receive_not_applicable",
            message="Receive is only defined for branch-request warehouse lines",
            detail={"source_type": row.source_type.value},
        )

    if row.status == WarehouseLineStatus.PENDING:
        row.status = WarehouseLineStatus.AVAILABLE
        row.updated_at = datetime.utcnow()
        _audit(db, request, current_user, "warehouse_receive", row, {"status": row.status.value})
        db.commit()
        supply_chain_idempotency_service.complete(
            db, record=idempotency_record, response_reference_type="warehouse_line", response_reference_id=row.id
        )
        return _get_line(db, row.id)

    if row.status == WarehouseLineStatus.AVAILABLE:
        supply_chain_idempotency_service.complete(
            db, record=idempotency_record, response_reference_type="warehouse_line", response_reference_id=row.id
        )
        return _get_line(db, row.id)

    raise AppError(
        status_code=400,
        error_code="warehouse_lines.receive_invalid_status",
        message="Line cannot be received in its current status",
        detail={"warehouse_line_id": line_id, "status": row.status.value},
    )


@router.post("/{line_id}/issue", response_model=WarehouseLineOut)
def issue_line(
    line_id: int,
    payload: WarehouseIssuePayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WAREHOUSE_ROLES)),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="warehouse_lines.issue",
        current_user=current_user,
    )
    row = _get_line(db, line_id)
    _require_warehouse_access(current_user, row)
    if replayed or row.status == WarehouseLineStatus.READY_FOR_DISPATCH:
        return row
    if row.status not in (
        WarehouseLineStatus.AVAILABLE,
        WarehouseLineStatus.PARTIAL,
        WarehouseLineStatus.PENDING,
    ):
        raise AppError(
            status_code=400,
            error_code="warehouse_lines.issue_invalid_status",
            message="Warehouse line cannot be issued in its current status",
            detail={"warehouse_line_id": line_id, "status": row.status.value},
        )
    qty = Decimal(str(payload.qty)) if payload.qty is not None else _as_decimal(row.pending_qty)
    if qty <= 0 or qty != _as_decimal(row.pending_qty):
        raise AppError(
            status_code=400,
            error_code="warehouse_lines.full_issue_qty_invalid",
            message="Full issue must equal pending quantity",
            detail={"pending_qty": str(row.pending_qty), "qty": str(qty)},
        )
    _deduct_stock(db, row, qty, current_user)
    row.issued_qty = _as_decimal(row.issued_qty) + qty
    row.pending_qty = Decimal("0")
    row.status = WarehouseLineStatus.READY_FOR_DISPATCH
    row.updated_at = datetime.utcnow()
    if row.source_request_line:
        row.source_request_line.status = BranchRequestLineStatus.READY_IN_WAREHOUSE
    _audit(db, request, current_user, "warehouse_issue", row, {"qty": str(qty)})
    db.commit()
    supply_chain_idempotency_service.complete(db, record=idempotency_record, response_reference_type="warehouse_line", response_reference_id=row.id)
    return _get_line(db, row.id)


@router.post("/{line_id}/partial-issue", response_model=WarehouseLineOut)
def partial_issue_line(
    line_id: int,
    payload: WarehouseIssuePayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WAREHOUSE_ROLES)),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="warehouse_lines.partial_issue",
        current_user=current_user,
    )
    if not payload.delay_reason:
        raise AppError(status_code=400, error_code="warehouse_lines.delay_reason_required", message="Delay reason is required")
    if payload.qty is None:
        raise AppError(status_code=400, error_code="warehouse_lines.qty_required", message="Quantity is required")
    row = _get_line(db, line_id)
    _require_warehouse_access(current_user, row)
    if replayed:
        return row
    if row.status not in (
        WarehouseLineStatus.AVAILABLE,
        WarehouseLineStatus.PARTIAL,
        WarehouseLineStatus.PENDING,
    ):
        raise AppError(
            status_code=400,
            error_code="warehouse_lines.partial_issue_invalid_status",
            message="Warehouse line cannot be partially issued in its current status",
            detail={"warehouse_line_id": line_id, "status": row.status.value},
        )
    qty = Decimal(str(payload.qty))
    pending = _as_decimal(row.pending_qty)
    if qty <= 0 or qty > pending:
        raise AppError(
            status_code=400,
            error_code="warehouse_lines.partial_qty_invalid",
            message="Partial issue quantity must be greater than zero and less than pending quantity",
            detail={"pending_qty": str(row.pending_qty), "qty": str(qty)},
        )
    _deduct_stock(db, row, qty, current_user)
    row.issued_qty = _as_decimal(row.issued_qty) + qty
    row.pending_qty = pending - qty
    row.status = (
        WarehouseLineStatus.READY_FOR_DISPATCH
        if row.pending_qty == 0
        else WarehouseLineStatus.PARTIAL
    )
    row.delay_reason = payload.delay_reason
    row.updated_at = datetime.utcnow()
    if row.source_request_line:
        row.source_request_line.status = BranchRequestLineStatus.PARTIAL_WAREHOUSE
    _audit(db, request, current_user, "warehouse_partial_issue", row, {"qty": str(qty), "delay_reason": payload.delay_reason})
    db.commit()
    supply_chain_idempotency_service.complete(db, record=idempotency_record, response_reference_type="warehouse_line", response_reference_id=row.id)
    return _get_line(db, row.id)


@router.post("/{line_id}/delay-reason", response_model=WarehouseLineOut)
def add_delay_reason(
    line_id: int,
    payload: WarehouseDelayPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WAREHOUSE_ROLES)),
):
    row = _get_line(db, line_id)
    _require_warehouse_access(current_user, row)
    row.delay_reason = payload.delay_reason
    if _as_decimal(row.issued_qty) == 0:
        row.status = WarehouseLineStatus.BACKORDER
    row.updated_at = datetime.utcnow()
    _audit(db, request, current_user, "warehouse_delay_reason_added", row, {"delay_reason": payload.delay_reason})
    db.commit()
    return _get_line(db, row.id)
