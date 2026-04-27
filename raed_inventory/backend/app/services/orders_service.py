from datetime import datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.auth import can_access_branch, can_access_warehouse
from app.core.errors import AppError
from app.core.locking import lock_row
from app.models import (
    BranchStock,
    OrderStatus,
    ReplenishmentOrder,
    ReplenishmentOrderLine,
    TransactionType,
    User,
    WarehouseStock,
)
from app.services import idempotency_service, stock_ledger_service, audit_service


def _get_warehouse_stock_locked(db: Session, warehouse_id: int, item_id: int) -> WarehouseStock | None:
    return lock_row(
        db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == warehouse_id,
            WarehouseStock.item_id == item_id,
        )
    ).first()


def _get_branch_stock_locked(db: Session, branch_id: int, item_id: int) -> BranchStock | None:
    return lock_row(
        db.query(BranchStock).filter(
            BranchStock.branch_id == branch_id,
            BranchStock.item_id == item_id,
        )
    ).first()


def _ensure_order_branch_access(current_user: User, order: ReplenishmentOrder, db: Session):
    if not can_access_branch(current_user, order.branch_id, db):
        raise AppError(
            status_code=403,
            error_code="orders.branch_access_denied",
            message="Access denied for this branch order",
            detail={"order_id": order.id, "branch_id": order.branch_id},
        )


def _ensure_order_warehouse_access(current_user: User, order: ReplenishmentOrder):
    if not can_access_warehouse(current_user, order.warehouse_id):
        raise AppError(
            status_code=403,
            error_code="orders.warehouse_access_denied",
            message="Access denied for this warehouse order",
            detail={"order_id": order.id, "warehouse_id": order.warehouse_id},
        )


def _load_order_for_update(db: Session, order_id: int, *, with_lines: bool = False) -> ReplenishmentOrder:
    query = db.query(ReplenishmentOrder)
    if with_lines:
        query = query.options(joinedload(ReplenishmentOrder.lines))
    order = lock_row(query.filter(ReplenishmentOrder.id == order_id)).first()
    if not order:
        raise AppError(
            status_code=404,
            error_code="orders.not_found",
            message="Order not found",
            detail={"order_id": order_id},
        )
    return order


def _try_begin_idempotent_operation(
    db: Session,
    *,
    client_request_id: str | None,
    operation_name: str,
    current_user: User,
    replay_payload: dict,
):
    if not client_request_id:
        return None, None

    existing_record = idempotency_service.get_idempotency_request(
        db,
        tenant_id=settings.DEFAULT_TENANT_ID,
        client_request_id=client_request_id,
        operation_name=operation_name,
    )
    if existing_record and existing_record.status == "completed":
        return None, idempotency_service.replay_response(
            record=existing_record,
            response_payload=replay_payload,
        )

    if not existing_record:
        try:
            record = idempotency_service.register_idempotency_request(
                db,
                tenant_id=settings.DEFAULT_TENANT_ID,
                client_request_id=client_request_id,
                operation_name=operation_name,
                user_id=current_user.id,
            )
            return record, None
        except IntegrityError:
            duplicate_record = idempotency_service.get_idempotency_request(
                db,
                tenant_id=settings.DEFAULT_TENANT_ID,
                client_request_id=client_request_id,
                operation_name=operation_name,
            )
            if duplicate_record and duplicate_record.status == "completed":
                return None, idempotency_service.replay_response(
                    record=duplicate_record,
                    response_payload=replay_payload,
                )
            raise AppError(
                status_code=409,
                error_code="orders.duplicate_request_in_progress",
                message="Duplicate request is already in progress",
                detail={"operation_name": operation_name},
            )

    return None, None


def submit_to_warehouse(
    db: Session,
    *,
    order_id: int,
    current_user: User,
    client_request_id: str | None = None,
) -> dict:
    order = _load_order_for_update(db, order_id)
    _ensure_order_branch_access(current_user, order, db)

    replay_payload = {"message": "Order submitted to warehouse", "order_id": order.id}
    idempotency_record, replay_response = _try_begin_idempotent_operation(
        db,
        client_request_id=client_request_id,
        operation_name="orders.submit_to_warehouse",
        current_user=current_user,
        replay_payload=replay_payload,
    )
    if replay_response:
        return replay_response

    if order.status not in [
        OrderStatus.branch_reviewed,
        OrderStatus.system_generated,
        OrderStatus.draft,
        OrderStatus.area_manager_review,
    ]:
        raise AppError(
            status_code=400,
            error_code="orders.invalid_submit_status",
            message="Cannot submit order in the current status",
            detail={"order_id": order.id, "status": order.status.value},
        )

    order.status = OrderStatus.submitted_to_warehouse
    order.submitted_to_warehouse_at = datetime.utcnow()
    db.commit()

    if idempotency_record:
        idempotency_service.complete_idempotency_request(
            db,
            record=idempotency_record,
            response_reference_type="replenishment_order",
            response_reference_id=order.id,
        )
    return replay_payload


def branch_review_order(
    db: Session,
    *,
    order_id: int,
    payload: dict,
    current_user: User,
) -> dict:
    order = _load_order_for_update(db, order_id, with_lines=True)
    _ensure_order_branch_access(current_user, order, db)

    if order.status not in [OrderStatus.system_generated, OrderStatus.draft]:
        raise AppError(
            status_code=400,
            error_code="orders.invalid_branch_review_status",
            message="Cannot review order in the current status",
            detail={"order_id": order.id, "status": order.status.value},
        )

    for update in payload.get("lines", []):
        line = db.query(ReplenishmentOrderLine).filter(
            ReplenishmentOrderLine.id == update["line_id"],
            ReplenishmentOrderLine.order_id == order_id,
        ).first()
        if line:
            line.branch_requested_qty = Decimal(str(update.get("branch_requested_qty", line.branch_requested_qty)))

    order.status = OrderStatus.branch_reviewed
    order.branch_reviewed_at = datetime.utcnow()
    order.branch_reviewed_by = current_user.id
    db.commit()
    return {"message": "Order reviewed", "order_id": order_id}


def warehouse_review_order(
    db: Session,
    *,
    order_id: int,
    payload: dict,
    current_user: User,
) -> dict:
    order = _load_order_for_update(db, order_id, with_lines=True)
    _ensure_order_warehouse_access(current_user, order)

    if order.status != OrderStatus.submitted_to_warehouse:
        raise AppError(
            status_code=400,
            error_code="orders.invalid_warehouse_review_status",
            message="Order is not in submitted state",
            detail={"order_id": order.id, "status": order.status.value},
        )

    for update in payload.get("lines", []):
        line = db.query(ReplenishmentOrderLine).filter(
            ReplenishmentOrderLine.id == update["line_id"],
            ReplenishmentOrderLine.order_id == order_id,
        ).first()
        if line:
            line.wh_approved_qty = Decimal(str(update.get("wh_approved_qty", line.wh_approved_qty or line.branch_requested_qty)))
            if update.get("rejection_reason"):
                line.rejection_reason = update["rejection_reason"]
                line.line_status = "rejected"
            else:
                line.line_status = "approved"

    order.status = OrderStatus.under_review
    order.wh_reviewed_at = datetime.utcnow()
    order.wh_reviewed_by = current_user.id
    db.commit()
    return {"message": "Order reviewed by warehouse"}


def warehouse_approve_order(
    db: Session,
    *,
    order_id: int,
    current_user: User,
    client_request_id: str | None = None,
) -> dict:
    order = _load_order_for_update(db, order_id, with_lines=True)
    _ensure_order_warehouse_access(current_user, order)

    replay_payload = {
        "message": f"Order {order.status.value}",
        "order_id": order.id,
        "status": order.status.value,
    }
    idempotency_record, replay_response = _try_begin_idempotent_operation(
        db,
        client_request_id=client_request_id,
        operation_name="orders.approve",
        current_user=current_user,
        replay_payload=replay_payload,
    )
    if replay_response:
        return replay_response

    if order.status not in [OrderStatus.under_review, OrderStatus.submitted_to_warehouse]:
        raise AppError(
            status_code=400,
            error_code="orders.invalid_approval_status",
            message="Cannot approve order in the current status",
            detail={"order_id": order.id, "status": order.status.value},
        )

    # ─── فحص توفر الكمية في المستودع قبل الموافقة ─────────────────────────
    # نمنع المستودع من اعتماد كميات أكبر من المتاح (تصحيح "warehouse oversell")
    insufficient_lines = []
    for line in order.lines:
        if line.wh_approved_qty == 0 and line.branch_requested_qty > 0:
            line.wh_approved_qty = line.branch_requested_qty
            line.line_status = "approved"

        if line.wh_approved_qty > 0:
            wh_stock = _get_warehouse_stock_locked(db, order.warehouse_id, line.item_id)
            available = (wh_stock.current_qty - wh_stock.reserved_qty) if wh_stock else Decimal("0")
            if line.wh_approved_qty > available:
                insufficient_lines.append({
                    "line_id": line.id,
                    "item_id": line.item_id,
                    "requested": float(line.wh_approved_qty),
                    "available": float(available),
                })

    if insufficient_lines:
        raise AppError(
            status_code=400,
            error_code="orders.insufficient_warehouse_stock",
            message="الكمية المعتمدة تتجاوز المتاح في المستودع — راجع السطور وعدّل الكميات",
            detail={"order_id": order.id, "lines": insufficient_lines},
        )

    approved_lines = [l for l in order.lines if float(l.wh_approved_qty) > 0]
    all_approved = len(approved_lines) == len(order.lines)
    order.status = OrderStatus.approved if all_approved else OrderStatus.partially_approved
    order.wh_approved_at = datetime.utcnow()
    order.wh_approved_by = current_user.id
    db.commit()
    audit_service.log(
        db,
        user_id=current_user.id,
        action="approve",
        module="orders",
        entity_type="replenishment_order",
        entity_id=order.id,
        new_values={"status": order.status.value, "order_no": order.order_no},
    )
    db.commit()

    if idempotency_record:
        idempotency_service.complete_idempotency_request(
            db,
            record=idempotency_record,
            response_reference_type="replenishment_order",
            response_reference_id=order.id,
        )

    return {
        "message": f"Order {order.status.value}",
        "order_id": order.id,
        "status": order.status.value,
    }


def warehouse_reject_order(
    db: Session,
    *,
    order_id: int,
    payload: dict,
    current_user: User,
    client_request_id: str | None = None,
) -> dict:
    order = _load_order_for_update(db, order_id)
    _ensure_order_warehouse_access(current_user, order)

    replay_payload = {
        "message": f"Order {order.status.value}",
        "order_id": order.id,
        "status": order.status.value,
    }
    idempotency_record, replay_response = _try_begin_idempotent_operation(
        db,
        client_request_id=client_request_id,
        operation_name="orders.reject",
        current_user=current_user,
        replay_payload=replay_payload,
    )
    if replay_response:
        return replay_response

    reason = payload.get("reason", "")
    if not reason:
        raise AppError(
            status_code=400,
            error_code="orders.rejection_reason_required",
            message="Rejection reason required",
            detail={"order_id": order_id},
        )

    order.status = OrderStatus.rejected
    order.rejection_reason = reason
    db.commit()
    audit_service.log(
        db,
        user_id=current_user.id,
        action="reject",
        module="orders",
        entity_type="replenishment_order",
        entity_id=order_id,
        new_values={"status": "rejected", "rejection_reason": reason, "order_no": order.order_no},
    )
    db.commit()

    if idempotency_record:
        idempotency_service.complete_idempotency_request(
            db,
            record=idempotency_record,
            response_reference_type="replenishment_order",
            response_reference_id=order.id,
        )

    return {"message": "Order rejected", "order_id": order.id, "status": order.status.value}


def start_picking(
    db: Session,
    *,
    order_id: int,
    current_user: User,
    client_request_id: str | None = None,
) -> dict:
    order = _load_order_for_update(db, order_id)
    _ensure_order_warehouse_access(current_user, order)

    replay_payload = {
        "message": "Picking started",
        "order_id": order.id,
        "status": order.status.value if hasattr(order.status, "value") else str(order.status),
    }
    idempotency_record, replay_response = _try_begin_idempotent_operation(
        db,
        client_request_id=client_request_id,
        operation_name="orders.start_picking",
        current_user=current_user,
        replay_payload=replay_payload,
    )
    if replay_response:
        return replay_response

    if order.status not in [OrderStatus.approved, OrderStatus.partially_approved]:
        raise AppError(
            status_code=400,
            error_code="orders.invalid_start_picking_status",
            message="Cannot start picking in the current status",
            detail={"order_id": order.id, "status": order.status.value},
        )

    order.status = OrderStatus.picking
    order.picking_started_at = datetime.utcnow()
    db.commit()

    if idempotency_record:
        idempotency_service.complete_idempotency_request(
            db,
            record=idempotency_record,
            response_reference_type="replenishment_order",
            response_reference_id=order.id,
        )

    return {"message": "Picking started", "order_id": order.id, "status": order.status.value}


def dispatch_order(
    db: Session,
    *,
    order_id: int,
    payload: dict,
    current_user: User,
    client_request_id: str | None = None,
) -> dict:
    order = _load_order_for_update(db, order_id, with_lines=True)
    _ensure_order_warehouse_access(current_user, order)

    replay_payload = {
        "message": "Order dispatched",
        "order_id": order.id,
        "dispatch_note_no": order.dispatch_note_no,
    }
    idempotency_record, replay_response = _try_begin_idempotent_operation(
        db,
        client_request_id=client_request_id,
        operation_name="orders.dispatch",
        current_user=current_user,
        replay_payload=replay_payload,
    )
    if replay_response:
        return replay_response

    if order.status != OrderStatus.picking:
        raise AppError(
            status_code=400,
            error_code="orders.invalid_dispatch_status",
            message="Order is not in picking status",
            detail={"order_id": order.id, "status": order.status.value},
        )

    line_dispatches = payload.get("lines", [])
    dispatch_note = payload.get("dispatch_note_no", f"DN-{order.order_no}")

    for disp in line_dispatches:
        line = db.query(ReplenishmentOrderLine).filter(
            ReplenishmentOrderLine.id == disp["line_id"],
            ReplenishmentOrderLine.order_id == order_id,
        ).first()
        if not line:
            continue

        dispatched_qty = Decimal(str(disp.get("dispatched_qty", line.wh_approved_qty)))
        if dispatched_qty < 0:
            raise AppError(
                status_code=400,
                error_code="orders.negative_dispatch_qty",
                message="الكمية المصروفة لا يمكن أن تكون سالبة",
                detail={"line_id": line.id, "dispatched_qty": float(dispatched_qty)},
            )

        line.picked_qty = dispatched_qty
        line.dispatched_qty = dispatched_qty
        line.line_status = "dispatched"

        if dispatched_qty < line.wh_approved_qty:
            line.shortage_flag = True
            line.shortage_reason = disp.get("shortage_reason", "Insufficient stock")

        # قفل الصف لمنع سباق — لا تستخدم max(0, ...) لأنه يُخفي النقص
        wh_stock = _get_warehouse_stock_locked(db, order.warehouse_id, line.item_id)
        if not wh_stock or wh_stock.current_qty < dispatched_qty:
            raise AppError(
                status_code=400,
                error_code="orders.insufficient_warehouse_stock_on_dispatch",
                message=(
                    f"الكمية المطلوب صرفها ({float(dispatched_qty)}) تتجاوز المتاح في المستودع "
                    f"({float(wh_stock.current_qty) if wh_stock else 0})"
                ),
                detail={
                    "line_id": line.id,
                    "item_id": line.item_id,
                    "requested": float(dispatched_qty),
                    "available": float(wh_stock.current_qty) if wh_stock else 0,
                },
            )
        wh_stock.current_qty -= dispatched_qty

        br_stock = _get_branch_stock_locked(db, order.branch_id, line.item_id)
        if br_stock:
            br_stock.in_transit_qty += dispatched_qty
        else:
            br_stock = BranchStock(
                branch_id=order.branch_id,
                item_id=line.item_id,
                current_qty=Decimal("0"),
                in_transit_qty=dispatched_qty,
            )
            db.add(br_stock)

        stock_ledger_service.post_transaction(
            db,
            transaction_type=TransactionType.warehouse_dispatch,
            source_type="warehouse",
            source_id=order.warehouse_id,
            destination_type="branch",
            destination_id=order.branch_id,
            item_id=line.item_id,
            qty=dispatched_qty,
            reference_no=order.order_no,
            notes=f"Dispatch for order {order.order_no}",
            created_by=current_user.id,
        )

    order.status = OrderStatus.dispatched
    order.dispatched_at = datetime.utcnow()
    order.dispatched_by = current_user.id
    order.dispatch_note_no = dispatch_note
    db.commit()

    if idempotency_record:
        idempotency_service.complete_idempotency_request(
            db,
            record=idempotency_record,
            response_reference_type="replenishment_order",
            response_reference_id=order.id,
        )

    return {
        "message": "Order dispatched",
        "order_id": order.id,
        "dispatch_note_no": dispatch_note,
    }


def receive_order(
    db: Session,
    *,
    order_id: int,
    payload: dict,
    current_user: User,
    client_request_id: str | None = None,
) -> dict:
    order = _load_order_for_update(db, order_id, with_lines=True)
    _ensure_order_branch_access(current_user, order, db)

    replay_payload = {
        "message": "Order received",
        "order_id": order.id,
        "status": order.status.value if hasattr(order.status, "value") else str(order.status),
    }
    idempotency_record, replay_response = _try_begin_idempotent_operation(
        db,
        client_request_id=client_request_id,
        operation_name="orders.receive",
        current_user=current_user,
        replay_payload=replay_payload,
    )
    if replay_response:
        return replay_response

    if order.status != OrderStatus.dispatched:
        raise AppError(
            status_code=400,
            error_code="orders.invalid_receive_status",
            message="Order is not dispatched yet",
            detail={"order_id": order.id, "status": order.status.value},
        )

    line_receipts = payload.get("lines", [])

    for receipt in line_receipts:
        line = db.query(ReplenishmentOrderLine).filter(
            ReplenishmentOrderLine.id == receipt["line_id"],
            ReplenishmentOrderLine.order_id == order_id,
        ).first()
        if not line:
            continue

        received_qty = Decimal(str(receipt.get("received_qty", line.dispatched_qty)))
        damaged_qty = Decimal(str(receipt.get("damaged_qty", 0)))
        missing_qty = Decimal(str(receipt.get("missing_qty", 0)))

        # ─── التحقق من صحة القيم (منع القيم السالبة أو غير المنطقية) ────
        if received_qty < 0 or damaged_qty < 0 or missing_qty < 0:
            raise AppError(
                status_code=400,
                error_code="orders.negative_qty_on_receipt",
                message="الكميات لا يمكن أن تكون سالبة",
                detail={"line_id": line.id},
            )
        # received + missing يجب أن = dispatched (مع تسامح بسيط)
        dispatched = line.dispatched_qty or Decimal("0")
        if received_qty + missing_qty > dispatched + Decimal("0.001"):
            raise AppError(
                status_code=400,
                error_code="orders.receipt_exceeds_dispatch",
                message="الكمية المستلمة + المفقودة تتجاوز الكمية المصروفة",
                detail={
                    "line_id": line.id,
                    "dispatched": float(dispatched),
                    "received": float(received_qty),
                    "missing": float(missing_qty),
                },
            )
        if damaged_qty > received_qty:
            raise AppError(
                status_code=400,
                error_code="orders.damaged_exceeds_received",
                message="الكمية التالفة تتجاوز المستلمة",
                detail={"line_id": line.id},
            )

        accepted_qty = received_qty - damaged_qty  # ما يضاف فعلياً لمخزون الفرع

        line.received_qty = received_qty
        line.damaged_qty = damaged_qty
        line.missing_qty = missing_qty
        line.line_status = "received"
        if receipt.get("receiving_variance_reason_id"):
            line.receiving_variance_reason_id = receipt["receiving_variance_reason_id"]
        if receipt.get("notes"):
            line.notes = receipt["notes"]

        # ─── تحديث مخزون الفرع مع lock ────────────────────────────────────
        br_stock = _get_branch_stock_locked(db, order.branch_id, line.item_id)
        if br_stock:
            br_stock.current_qty += accepted_qty
            # تحرير الكمية من in_transit بالكامل (صُرفت ولم تعد في الطريق)
            br_stock.in_transit_qty = max(Decimal("0"), (br_stock.in_transit_qty or Decimal("0")) - dispatched)
        else:
            br_stock = BranchStock(
                branch_id=order.branch_id,
                item_id=line.item_id,
                current_qty=accepted_qty,
            )
            db.add(br_stock)

        # ─── إعادة المفقود والتالف للمستودع (Reconciliation) ──────────────
        # كان هذا السيناريو يُخفي الخسارة: dispatched=100, received=70, missing=20, damaged=10
        # نسجل adjustment_in للمستودع للكمية المفقودة + التالفة إن وُجدت
        lost_or_damaged = missing_qty + damaged_qty
        if lost_or_damaged > 0:
            wh_stock = _get_warehouse_stock_locked(db, order.warehouse_id, line.item_id)
            if wh_stock:
                # نُرجع القيمة افتراضياً إلى "stock adjustment / investigation"
                # بدلاً من رفعها مباشرة للمخزون، نعتمد على receiving_variance_reason_id
                # لتحديد: إذا السبب = "lost_in_transit" → لا نرجعها. إذا = "counted_wrong" → نرجعها.
                auto_return = receipt.get("auto_return_to_warehouse", False)
                if auto_return:
                    wh_stock.current_qty += lost_or_damaged
                    stock_ledger_service.post_transaction(
                        db,
                        transaction_type=TransactionType.adjustment_in,
                        source_type="branch",
                        source_id=order.branch_id,
                        destination_type="warehouse",
                        destination_id=order.warehouse_id,
                        item_id=line.item_id,
                        qty=lost_or_damaged,
                        reference_no=order.order_no,
                        notes=f"Auto-return of missing/damaged on receipt of {order.order_no}",
                        created_by=current_user.id,
                    )

        stock_ledger_service.post_transaction(
            db,
            transaction_type=TransactionType.branch_receipt,
            source_type="warehouse",
            source_id=order.warehouse_id,
            destination_type="branch",
            destination_id=order.branch_id,
            item_id=line.item_id,
            qty=accepted_qty,
            reference_no=order.order_no,
            notes=f"Receipt for order {order.order_no}",
            created_by=current_user.id,
        )

    order.status = OrderStatus.received
    order.received_at = datetime.utcnow()
    order.notes = (order.notes or "") + f" | Received by {current_user.username}"
    db.commit()

    all_received = all(l.line_status == "received" for l in order.lines)
    if all_received:
        order.status = OrderStatus.closed
        order.closed_at = datetime.utcnow()
        db.commit()

    if idempotency_record:
        idempotency_service.complete_idempotency_request(
            db,
            record=idempotency_record,
            response_reference_type="replenishment_order",
            response_reference_id=order.id,
        )

    return {
        "message": "Order received",
        "order_id": order.id,
        "status": order.status.value if hasattr(order.status, "value") else str(order.status),
    }


# ──────────────────────────────────────────────────────────────────────────
# CANCEL ORDER  (branch can cancel before warehouse approval)
# ──────────────────────────────────────────────────────────────────────────

_CANCELLABLE_BY_BRANCH = {
    OrderStatus.system_generated,
    OrderStatus.draft,
    OrderStatus.branch_reviewed,
    OrderStatus.area_manager_review,
}

_CANCELLABLE_BY_WAREHOUSE = {
    OrderStatus.submitted_to_warehouse,
    OrderStatus.under_review,
    OrderStatus.approved,
    OrderStatus.partially_approved,
}


def cancel_order(
    db: Session,
    *,
    order_id: int,
    reason: str,
    current_user: User,
    client_request_id: str | None = None,
) -> dict:
    order = _load_order_for_update(db, order_id)

    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    is_branch_actor = any(r in user_roles for r in ("branch_user", "branch_manager"))
    is_wh_actor = any(r in user_roles for r in ("warehouse_user", "warehouse_manager"))
    is_admin = any(r in user_roles for r in ("admin", "super_admin"))

    if is_branch_actor and not is_admin:
        _ensure_order_branch_access(current_user, order, db)
        if order.status not in _CANCELLABLE_BY_BRANCH:
            raise AppError(
                status_code=400,
                error_code="orders.cannot_cancel_status",
                message="Order cannot be cancelled at this stage by branch",
                detail={"order_id": order.id, "status": order.status.value},
            )
    elif is_wh_actor and not is_admin:
        _ensure_order_warehouse_access(current_user, order)
        if order.status not in _CANCELLABLE_BY_WAREHOUSE:
            raise AppError(
                status_code=400,
                error_code="orders.cannot_cancel_status",
                message="Order cannot be cancelled at this stage by warehouse",
                detail={"order_id": order.id, "status": order.status.value},
            )
    elif not is_admin:
        raise AppError(
            status_code=403,
            error_code="orders.cancel_access_denied",
            message="You are not allowed to cancel orders",
            detail={},
        )

    if not reason:
        raise AppError(
            status_code=400,
            error_code="orders.cancellation_reason_required",
            message="Cancellation reason is required",
            detail={"order_id": order_id},
        )

    replay_payload = {
        "message": "Order cancelled",
        "order_id": order.id,
        "status": "cancelled",
    }
    idempotency_record, replay_response = _try_begin_idempotent_operation(
        db,
        client_request_id=client_request_id,
        operation_name="orders.cancel",
        current_user=current_user,
        replay_payload=replay_payload,
    )
    if replay_response:
        return replay_response

    order.status = OrderStatus.cancelled
    order.cancellation_reason = reason
    order.cancelled_at = datetime.utcnow()
    order.cancelled_by = current_user.id
    db.commit()
    audit_service.log(
        db,
        user_id=current_user.id,
        action="cancel",
        module="orders",
        entity_type="replenishment_order",
        entity_id=order_id,
        new_values={"status": "cancelled", "cancellation_reason": reason, "order_no": order.order_no},
    )
    db.commit()

    if idempotency_record:
        idempotency_service.complete_idempotency_request(
            db,
            record=idempotency_record,
            response_reference_type="replenishment_order",
            response_reference_id=order.id,
        )

    return replay_payload


# ──────────────────────────────────────────────────────────────────────────
# CLOSE ORDER  (manually close a received/partially-received order)
# ──────────────────────────────────────────────────────────────────────────

def close_order(
    db: Session,
    *,
    order_id: int,
    current_user: User,
    client_request_id: str | None = None,
) -> dict:
    order = _load_order_for_update(db, order_id)

    closable_statuses = {OrderStatus.received, OrderStatus.dispatched}
    if order.status not in closable_statuses:
        raise AppError(
            status_code=400,
            error_code="orders.cannot_close_status",
            message="Only received or dispatched orders can be closed manually",
            detail={"order_id": order.id, "status": order.status.value},
        )

    replay_payload = {"message": "Order closed", "order_id": order.id, "status": "closed"}
    idempotency_record, replay_response = _try_begin_idempotent_operation(
        db,
        client_request_id=client_request_id,
        operation_name="orders.close",
        current_user=current_user,
        replay_payload=replay_payload,
    )
    if replay_response:
        return replay_response

    order.status = OrderStatus.closed
    order.closed_at = datetime.utcnow()
    db.commit()

    if idempotency_record:
        idempotency_service.complete_idempotency_request(
            db,
            record=idempotency_record,
            response_reference_type="replenishment_order",
            response_reference_id=order.id,
        )

    return replay_payload


# ──────────────────────────────────────────────────────────────────────────
# ORDER TIMELINE  (status history with timestamps)
# ──────────────────────────────────────────────────────────────────────────

def get_order_timeline(db: Session, *, order_id: int, current_user: User) -> dict:
    order = _load_order_for_update(db, order_id)

    # Build timeline from nullable timestamp fields
    events = []

    def _add(event_name: str, ts, actor_id=None):
        if ts:
            events.append({"event": event_name, "timestamp": ts, "actor_id": actor_id})

    _add("created", order.created_at, order.created_by)
    _add("branch_reviewed", order.branch_reviewed_at, order.branch_reviewed_by)
    _add("submitted_to_warehouse", order.submitted_to_warehouse_at)
    _add("warehouse_reviewed", order.wh_reviewed_at, order.wh_reviewed_by)
    _add("approved", order.wh_approved_at, order.wh_approved_by)
    _add("picking_started", order.picking_started_at)
    _add("dispatched", order.dispatched_at, order.dispatched_by)
    _add("received", order.received_at)
    _add("closed", order.closed_at)
    _add("cancelled", order.cancelled_at, order.cancelled_by)

    events.sort(key=lambda e: e["timestamp"])

    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value if order.status else None,
        "events": events,
    }

       