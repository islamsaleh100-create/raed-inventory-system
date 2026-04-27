from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_user_roles, require_roles
from app.core.errors import AppError
from app.core.locking import lock_row
from app.database import get_db
from app.models import (
    Branch,
    BranchRequestStatus,
    BranchRequestLineStatus,
    BranchStock,
    DeliveryOrder,
    DeliveryOrderLine,
    DeliveryOrderLineStatus,
    DeliveryOrderStatus,
    TransactionType,
    User,
    WarehouseLine,
    WarehouseLineStatus,
)
from app.schemas import DeliveryOrderCreate, DeliveryOrderDeliverPayload, DeliveryOrderOut
from app.services import audit_service, stock_ledger_service
from app.services import supply_chain_idempotency_service


router = APIRouter(prefix="/api/v1/delivery-orders", tags=["Delivery Orders"])

DELIVERY_VIEW_ROLES = ("delivery_user", "warehouse_user", "warehouse_manager", "internal_auditor", "admin", "super_admin")
DELIVERY_CREATE_ROLES = ("warehouse_user", "warehouse_manager", "admin", "super_admin")
DELIVERY_EXECUTE_ROLES = ("delivery_user", "admin", "super_admin")


def _as_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _roles(user: User) -> list[str]:
    return get_user_roles(user)


def _is_admin(user: User) -> bool:
    return any(r in _roles(user) for r in ("admin", "super_admin", "internal_auditor"))


def _is_warehouse_role(user: User) -> bool:
    return any(r in _roles(user) for r in ("warehouse_user", "warehouse_manager"))


def _line_warehouse_id(row: WarehouseLine) -> int:
    if not row.branch or not row.branch.warehouse_id:
        raise AppError(
            status_code=400,
            error_code="delivery_orders.branch_warehouse_missing",
            message="Destination branch has no warehouse",
            detail={"branch_id": row.branch_id},
        )
    return row.branch.warehouse_id


def _load_delivery_order(db: Session, order_id: int) -> DeliveryOrder:
    row = db.query(DeliveryOrder).options(
        joinedload(DeliveryOrder.branch),
        joinedload(DeliveryOrder.brand),
        joinedload(DeliveryOrder.lines).joinedload(DeliveryOrderLine.item),
        joinedload(DeliveryOrder.lines).joinedload(DeliveryOrderLine.warehouse_line).joinedload(WarehouseLine.kitchen_section),
    ).filter(DeliveryOrder.id == order_id).first()
    if not row:
        raise AppError(
            status_code=404,
            error_code="delivery_orders.not_found",
            message="Delivery order not found",
            detail={"delivery_order_id": order_id},
        )
    return row


def _require_order_access(user: User, row: DeliveryOrder) -> None:
    if _is_admin(user):
        return
    if "delivery_user" in _roles(user):
        if user.warehouse_id is None:
            return
        if row.branch and row.branch.warehouse_id == user.warehouse_id:
            return
        raise AppError(
            status_code=403,
            error_code="delivery_orders.access_denied",
            message="Access denied for this delivery order",
            detail={"delivery_order_id": row.id},
        )
    if _is_warehouse_role(user) and row.branch and row.branch.warehouse_id == user.warehouse_id:
        return
    raise AppError(
        status_code=403,
        error_code="delivery_orders.access_denied",
        message="Access denied for this delivery order",
        detail={"delivery_order_id": row.id},
    )


def _audit(db: Session, request: Request, user: User, action: str, row: DeliveryOrder, values: dict | None = None) -> None:
    audit_service.log(
        db,
        user_id=user.id,
        action=action,
        module="delivery_orders",
        entity_type="delivery_order",
        entity_id=row.id,
        new_values=values,
        ip_address=request.client.host if request.client else None,
    )


def _refresh_request_statuses(row: DeliveryOrder) -> None:
    touched_requests = set()
    for line in row.lines:
        wh_line = line.warehouse_line
        if wh_line and wh_line.source_request_line:
            request_line = wh_line.source_request_line
            request_line.status = (
                BranchRequestLineStatus.DELIVERED
                if line.status == DeliveryOrderLineStatus.DELIVERED
                else BranchRequestLineStatus.PARTIAL_WAREHOUSE
            )
            if request_line.request:
                touched_requests.add(request_line.request)

    for request in touched_requests:
        line_statuses = {line.status for line in request.lines}
        if line_statuses and line_statuses.issubset({BranchRequestLineStatus.DELIVERED, BranchRequestLineStatus.REJECTED}):
            request.status = BranchRequestStatus.DELIVERED
            request.updated_at = datetime.utcnow()
        else:
            request.status = BranchRequestStatus.IN_EXECUTION
            request.updated_at = datetime.utcnow()


@router.get("/ready", response_model=list[DeliveryOrderOut])
def list_ready_delivery_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*DELIVERY_VIEW_ROLES)),
):
    q = db.query(DeliveryOrder).options(
        joinedload(DeliveryOrder.branch),
        joinedload(DeliveryOrder.lines).joinedload(DeliveryOrderLine.item),
    ).filter(DeliveryOrder.status == DeliveryOrderStatus.READY)
    if "delivery_user" in _roles(current_user) and current_user.warehouse_id and not _is_admin(current_user):
        q = q.join(Branch, Branch.id == DeliveryOrder.branch_id).filter(Branch.warehouse_id == current_user.warehouse_id)
    if _is_warehouse_role(current_user) and not _is_admin(current_user):
        q = q.join(Branch, Branch.id == DeliveryOrder.branch_id).filter(Branch.warehouse_id == current_user.warehouse_id)
    return q.order_by(DeliveryOrder.created_at.desc()).all()


@router.get("", response_model=list[DeliveryOrderOut])
def list_delivery_orders(
    status: Optional[DeliveryOrderStatus] = None,
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*DELIVERY_VIEW_ROLES)),
):
    q = db.query(DeliveryOrder).options(
        joinedload(DeliveryOrder.branch),
        joinedload(DeliveryOrder.lines).joinedload(DeliveryOrderLine.item),
    )
    if status:
        q = q.filter(DeliveryOrder.status == status)
    if branch_id:
        q = q.filter(DeliveryOrder.branch_id == branch_id)
    if "delivery_user" in _roles(current_user) and current_user.warehouse_id and not _is_admin(current_user):
        q = q.join(Branch, Branch.id == DeliveryOrder.branch_id).filter(Branch.warehouse_id == current_user.warehouse_id)
    if _is_warehouse_role(current_user) and not _is_admin(current_user):
        q = q.join(Branch, Branch.id == DeliveryOrder.branch_id).filter(Branch.warehouse_id == current_user.warehouse_id)
    return q.order_by(DeliveryOrder.created_at.desc()).all()


@router.post("", response_model=DeliveryOrderOut, status_code=201)
def create_delivery_order(
    payload: DeliveryOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*DELIVERY_CREATE_ROLES)),
):
    lines = db.query(WarehouseLine).options(
        joinedload(WarehouseLine.branch),
        joinedload(WarehouseLine.item),
    ).filter(WarehouseLine.id.in_(payload.warehouse_line_ids)).all()
    if len(lines) != len(set(payload.warehouse_line_ids)):
        raise AppError(status_code=400, error_code="delivery_orders.invalid_lines", message="One or more warehouse lines are invalid")

    branch_ids = {line.branch_id for line in lines}
    brand_ids = {line.brand_id for line in lines}
    if len(branch_ids) != 1:
        raise AppError(status_code=400, error_code="delivery_orders.mixed_branches", message="Delivery order lines must target one branch")
    if len(brand_ids) != 1:
        raise AppError(status_code=400, error_code="delivery_orders.mixed_brands", message="Delivery order lines must target one brand")

    for line in lines:
        if line.status != WarehouseLineStatus.READY_FOR_DISPATCH or Decimal(str(line.issued_qty or 0)) <= 0:
            raise AppError(
                status_code=400,
                error_code="delivery_orders.line_not_ready",
                message="Only READY_FOR_DISPATCH warehouse lines can be delivered",
                detail={"warehouse_line_id": line.id, "status": line.status.value},
            )
        if _is_warehouse_role(current_user) and not _is_admin(current_user) and _line_warehouse_id(line) != current_user.warehouse_id:
            raise AppError(
                status_code=403,
                error_code="delivery_orders.warehouse_access_denied",
                message="Cannot create delivery for another warehouse",
                detail={"warehouse_line_id": line.id},
            )
        duplicate = db.query(DeliveryOrderLine).filter(DeliveryOrderLine.warehouse_line_id == line.id).first()
        if duplicate:
            raise AppError(
                status_code=400,
                error_code="delivery_orders.line_already_in_delivery",
                message="Warehouse line already belongs to a delivery order",
                detail={"warehouse_line_id": line.id},
            )

    now = datetime.utcnow()
    source_request_ids = {line.source_request_id for line in lines}
    source_request_id = source_request_ids.pop() if len(source_request_ids) == 1 else None
    order = DeliveryOrder(
        source_request_id=source_request_id,
        branch_id=lines[0].branch_id,
        brand_id=lines[0].brand_id,
        status=DeliveryOrderStatus.READY,
        ready_at=now,
        created_at=now,
        updated_at=now,
        created_by=current_user.id,
    )
    db.add(order)
    db.flush()
    for line in lines:
        db.add(DeliveryOrderLine(
            delivery_order_id=order.id,
            warehouse_line_id=line.id,
            item_id=line.item_id,
            qty_dispatched=Decimal(str(line.issued_qty)),
            qty_delivered=Decimal("0"),
            status=DeliveryOrderLineStatus.READY,
        ))
    _audit(db, request, current_user, "delivery_order_created", order, {"warehouse_line_ids": payload.warehouse_line_ids})
    db.commit()
    return _load_delivery_order(db, order.id)


@router.get("/{order_id}", response_model=DeliveryOrderOut)
def get_delivery_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*DELIVERY_VIEW_ROLES)),
):
    row = _load_delivery_order(db, order_id)
    _require_order_access(current_user, row)
    return row


@router.post("/{order_id}/out-for-delivery", response_model=DeliveryOrderOut)
def out_for_delivery(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*DELIVERY_EXECUTE_ROLES)),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="delivery_orders.out_for_delivery",
        current_user=current_user,
    )
    row = _load_delivery_order(db, order_id)
    _require_order_access(current_user, row)
    if replayed or row.status == DeliveryOrderStatus.OUT_FOR_DELIVERY:
        if idempotency_record and not replayed:
            supply_chain_idempotency_service.complete(
                db,
                record=idempotency_record,
                response_reference_type="delivery_order",
                response_reference_id=row.id,
            )
        return _load_delivery_order(db, row.id)
    if row.status != DeliveryOrderStatus.READY:
        raise AppError(status_code=400, error_code="delivery_orders.invalid_status", message="Only READY orders can go out for delivery")
    row.status = DeliveryOrderStatus.OUT_FOR_DELIVERY
    row.out_for_delivery_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    for line in row.lines:
        line.status = DeliveryOrderLineStatus.OUT_FOR_DELIVERY
    _audit(db, request, current_user, "delivery_out_for_delivery", row, {"status": row.status.value})
    db.commit()
    supply_chain_idempotency_service.complete(db, record=idempotency_record, response_reference_type="delivery_order", response_reference_id=row.id)
    return _load_delivery_order(db, row.id)


@router.post("/{order_id}/deliver", response_model=DeliveryOrderOut)
def deliver_order(
    order_id: int,
    payload: DeliveryOrderDeliverPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*DELIVERY_EXECUTE_ROLES)),
):
    idempotency_record, replayed = supply_chain_idempotency_service.begin(
        db,
        client_request_id=request.headers.get("X-Idempotency-Key"),
        operation_name="delivery_orders.deliver",
        current_user=current_user,
    )
    row = _load_delivery_order(db, order_id)
    _require_order_access(current_user, row)
    if replayed or row.status in (DeliveryOrderStatus.DELIVERED, DeliveryOrderStatus.PARTIAL_DELIVERED):
        if idempotency_record and not replayed:
            supply_chain_idempotency_service.complete(
                db,
                record=idempotency_record,
                response_reference_type="delivery_order",
                response_reference_id=row.id,
            )
        return _load_delivery_order(db, row.id)
    if row.status != DeliveryOrderStatus.OUT_FOR_DELIVERY:
        raise AppError(status_code=400, error_code="delivery_orders.invalid_status", message="Only OUT_FOR_DELIVERY orders can be delivered")

    receipts_by_line_id = {line.line_id: line for line in (payload.lines or [])}
    if receipts_by_line_id and set(receipts_by_line_id) != {line.id for line in row.lines}:
        raise AppError(
            status_code=400,
            error_code="delivery_orders.invalid_receipt_lines",
            message="Receipt lines must match the delivery order lines exactly",
            detail={"delivery_order_id": row.id},
        )

    any_partial = False
    for line in row.lines:
        dispatched_qty = Decimal(str(line.qty_dispatched))
        receipt = receipts_by_line_id.get(line.id)
        qty = dispatched_qty if receipt is None else Decimal(str(receipt.qty_received))
        if qty < 0 or qty > dispatched_qty:
            raise AppError(
                status_code=400,
                error_code="delivery_orders.invalid_received_qty",
                message="Received quantity must be between zero and dispatched quantity",
                detail={"line_id": line.id, "qty_received": str(qty), "qty_dispatched": str(dispatched_qty)},
            )
        shortage_qty = dispatched_qty - qty
        is_partial = shortage_qty > 0
        any_partial = any_partial or is_partial
        line.qty_delivered = qty
        line.shortage_qty = shortage_qty
        line.shortage_reason = receipt.shortage_reason if receipt else None
        line.status = DeliveryOrderLineStatus.PARTIAL_DELIVERED if is_partial else DeliveryOrderLineStatus.DELIVERED
        if payload.delivery_note:
            line.delivery_note = payload.delivery_note
        if line.warehouse_line:
            line.warehouse_line.status = WarehouseLineStatus.PARTIAL if is_partial else WarehouseLineStatus.DELIVERED
            line.warehouse_line.updated_at = datetime.utcnow()
        stock = lock_row(
            db.query(BranchStock).filter(
                BranchStock.branch_id == row.branch_id,
                BranchStock.item_id == line.item_id,
            )
        ).first()
        if not stock:
            stock = BranchStock(branch_id=row.branch_id, item_id=line.item_id, current_qty=Decimal("0"), reserved_qty=Decimal("0"), in_transit_qty=Decimal("0"))
            db.add(stock)
        stock.current_qty = _as_decimal(stock.current_qty) + qty
        stock.last_updated = datetime.utcnow()
        if qty > 0:
            stock_ledger_service.post_transaction(
                db,
                transaction_type=TransactionType.branch_receipt,
                item_id=line.item_id,
                qty=qty,
                source_type="warehouse_delivery",
                source_id=line.warehouse_line_id,
                destination_type="branch",
                destination_id=row.branch_id,
                reference_no=f"DO-{row.id}",
                notes="Supply Chain V1 delivery received by branch",
                created_by=current_user.id,
            )

    _refresh_request_statuses(row)
    row.status = DeliveryOrderStatus.PARTIAL_DELIVERED if any_partial else DeliveryOrderStatus.DELIVERED
    row.delivered_at = datetime.utcnow()
    row.delivered_by = current_user.id
    row.receiver_name = payload.receiver_name
    row.delivery_note = payload.delivery_note
    row.updated_at = datetime.utcnow()
    _audit(db, request, current_user, "delivery_delivered", row, {"receiver_name": payload.receiver_name})
    db.commit()
    supply_chain_idempotency_service.complete(db, record=idempotency_record, response_reference_type="delivery_order", response_reference_id=row.id)
    return _load_delivery_order(db, row.id)


@router.get("/{order_id}/labels", response_class=HTMLResponse)
def delivery_labels(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*DELIVERY_VIEW_ROLES)),
):
    row = _load_delivery_order(db, order_id)
    _require_order_access(current_user, row)
    cards = []
    for line in row.lines:
        wh = line.warehouse_line
        section = wh.kitchen_section.name if wh and wh.kitchen_section else "-"
        item_name = line.item.item_name_en if line.item else str(line.item_id)
        cards.append(
            f"""
            <section class="label">
              <h2>{escape(row.branch.branch_name if row.branch else str(row.branch_id))}</h2>
              <p><strong>Brand:</strong> {escape(row.brand.name if row.brand else str(row.brand_id))}</p>
              <p><strong>Item:</strong> {escape(item_name)}</p>
              <p><strong>Qty:</strong> {escape(str(line.qty_dispatched))}</p>
              <p><strong>Date:</strong> {datetime.utcnow().date().isoformat()}</p>
              <p><strong>Section:</strong> {escape(section)}</p>
            </section>
            """
        )
    _audit(db, request, current_user, "label_generated", row, {"delivery_order_id": row.id})
    db.commit()
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <title>Delivery Labels DO-{row.id}</title>
          <style>
            body {{ font-family: Arial, sans-serif; margin: 16px; }}
            .label {{ border: 1px solid #222; border-radius: 8px; padding: 16px; margin: 0 0 16px; page-break-inside: avoid; width: 360px; }}
            h2 {{ margin: 0 0 12px; font-size: 20px; }}
            p {{ margin: 6px 0; font-size: 14px; }}
            @media print {{ button {{ display: none; }} .label {{ page-break-after: always; }} }}
          </style>
        </head>
        <body>
          <button onclick="window.print()">Print</button>
          {''.join(cards)}
        </body>
        </html>
        """
    )
