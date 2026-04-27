"""
Inter-branch transfer workflow (OrderType.inter_branch).

الـ flow:
    1. مدير الفرع ينشئ طلب تحويل   → POST /orders/inter-branch
       - status = area_manager_review
       - لا تتحرّك الكميّات فورًا (خيار 2: التحقق من التوفر وقت الموافقة)

    2. مدير المنطقة يوافق           → POST /orders/{id}/inter-branch-approve
       - يتحقّق من توفر الكميّة في المصدر
       - ينقل المخزون فعليًا (transfer_branch_to_branch)
       - status = closed

    3. مدير المنطقة يرفض            → POST /orders/{id}/inter-branch-reject
       - status = rejected + rejection_reason

RBAC:
    - الإنشاء: branch_manager (الفرع الخاص به) / admin / super_admin / operations_manager
    - الموافقة: area_manager (داخل منطقته) / admin / super_admin / operations_manager
"""
from __future__ import annotations

import secrets
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.auth import can_access_branch, get_user_roles
from app.core.errors import AppError
from app.core.locking import lock_row
from app.models import (
    Branch,
    BranchStock,
    Item,
    OrderStatus,
    OrderType,
    ReplenishmentOrder,
    ReplenishmentOrderLine,
    TransactionType,
    User,
)
from app.services import stock_ledger_service


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _get_branch_or_404(db: Session, branch_id: int) -> Branch:
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_deleted == False).first()  # noqa: E712
    if not branch or not branch.active:
        raise AppError(
            status_code=404,
            error_code="inter_branch.branch_not_found",
            message="الفرع غير موجود أو غير مُفعَّل",
            detail={"branch_id": branch_id},
        )
    return branch


def _get_item_or_404(db: Session, item_id: int) -> Item:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise AppError(
            status_code=404,
            error_code="inter_branch.item_not_found",
            message="الصنف غير موجود",
            detail={"item_id": item_id},
        )
    return item


def _locked_branch_stock(db: Session, branch_id: int, item_id: int) -> BranchStock | None:
    return lock_row(
        db.query(BranchStock).filter(
            BranchStock.branch_id == branch_id,
            BranchStock.item_id == item_id,
        )
    ).first()


def _get_or_create_locked_branch_stock(db: Session, branch_id: int, item_id: int) -> BranchStock:
    existing = _locked_branch_stock(db, branch_id, item_id)
    if existing is not None:
        return existing
    bs = BranchStock(
        branch_id=branch_id,
        item_id=item_id,
        current_qty=Decimal("0"),
        reserved_qty=Decimal("0"),
    )
    db.add(bs)
    db.flush()
    return bs


def _is_elevated(user: User) -> bool:
    roles = get_user_roles(user)
    return any(r in roles for r in ("super_admin", "admin", "operations_manager"))


def _order_to_dict(order: ReplenishmentOrder) -> dict:
    src = order.branch
    dst = order.destination_branch
    return {
        "id": order.id,
        "order_no": order.order_no,
        "source_branch_id": order.branch_id,
        "source_branch_name": src.branch_name if src else None,
        "destination_branch_id": order.destination_branch_id,
        "destination_branch_name": dst.branch_name if dst else None,
        "status": order.status.value if hasattr(order.status, "value") else str(order.status),
        "reason": None,  # stored in notes — exposed below
        "reference_no": order.dispatch_note_no,
        "notes": order.notes,
        "rejection_reason": order.rejection_reason,
        "order_date": str(order.order_date),
        "created_at": order.created_at,
        "created_by": order.created_by,
        "lines": [
            {
                "id": line.id,
                "item_id": line.item_id,
                "item_code": line.item.item_code if line.item else None,
                "item_name_ar": line.item.item_name_ar if line.item else None,
                "qty": float(line.branch_requested_qty or 0),
                "line_status": line.line_status,
            }
            for line in order.lines
        ],
    }


# ─────────────────────────────────────────────────────────────────
# Create request (branch_manager)
# ─────────────────────────────────────────────────────────────────

def create_inter_branch_order(
    db: Session,
    *,
    source_branch_id: Optional[int],
    destination_branch_id: int,
    items: List[dict],
    reason: str,
    reference_no: Optional[str],
    notes: Optional[str],
    current_user: User,
) -> dict:
    # 1. Resolve source — default to the user's home branch
    resolved_source = source_branch_id or current_user.branch_id
    if resolved_source is None:
        raise AppError(
            status_code=400,
            error_code="inter_branch.source_required",
            message="يجب تحديد الفرع المصدر",
            detail={},
        )

    if resolved_source == destination_branch_id:
        raise AppError(
            status_code=400,
            error_code="inter_branch.same_branch",
            message="الفرع المصدر والهدف لا يمكن أن يكونا نفس الفرع",
            detail={"branch_id": resolved_source},
        )

    # 2. Permissions — creator must own/control the source branch
    if not can_access_branch(current_user, resolved_source, db):
        raise AppError(
            status_code=403,
            error_code="inter_branch.source_access_denied",
            message="ليس لديك صلاحية على الفرع المصدر",
            detail={"branch_id": resolved_source},
        )

    # Validate branches exist & are active
    source = _get_branch_or_404(db, resolved_source)
    _ = _get_branch_or_404(db, destination_branch_id)

    if not items:
        raise AppError(
            status_code=400,
            error_code="inter_branch.no_items",
            message="يجب إضافة صنف واحد على الأقل",
            detail={},
        )

    # 3. Normalize lines
    normalized: list[tuple[int, Decimal]] = []
    seen_ids: set[int] = set()
    for entry in items:
        item_id = int(entry["item_id"])
        if item_id in seen_ids:
            raise AppError(
                status_code=400,
                error_code="inter_branch.duplicate_item",
                message="الصنف مكرّر في الطلب",
                detail={"item_id": item_id},
            )
        seen_ids.add(item_id)
        qty = Decimal(str(entry.get("qty") or 0))
        if qty <= 0:
            raise AppError(
                status_code=400,
                error_code="inter_branch.qty_must_be_positive",
                message="الكميّة يجب أن تكون > 0",
                detail={"item_id": item_id, "qty": str(qty)},
            )
        _get_item_or_404(db, item_id)
        normalized.append((item_id, qty))

    # 4. Persist
    today = date.today()
    order_no = f"IBT-{today.strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    order = ReplenishmentOrder(
        order_no=order_no,
        branch_id=resolved_source,
        warehouse_id=source.warehouse_id,  # home warehouse of source
        destination_branch_id=destination_branch_id,
        order_type=OrderType.inter_branch,
        status=OrderStatus.area_manager_review,
        order_date=today,
        notes=f"[reason] {reason}" + (f"\n{notes}" if notes else ""),
        dispatch_note_no=reference_no,
        created_by=current_user.id,
    )
    db.add(order)
    db.flush()

    for item_id, qty in normalized:
        db.add(
            ReplenishmentOrderLine(
                order_id=order.id,
                item_id=item_id,
                suggested_qty=Decimal("0"),
                branch_requested_qty=qty,
                wh_approved_qty=Decimal("0"),
                line_status="pending",
            )
        )

    db.commit()
    db.refresh(order)

    # Load relationships for response
    order = (
        db.query(ReplenishmentOrder)
        .options(
            selectinload(ReplenishmentOrder.lines).selectinload(ReplenishmentOrderLine.item),
            joinedload(ReplenishmentOrder.branch),
            joinedload(ReplenishmentOrder.destination_branch),
        )
        .filter(ReplenishmentOrder.id == order.id)
        .first()
    )

    out = _order_to_dict(order)
    out["reason"] = reason
    return out


# ─────────────────────────────────────────────────────────────────
# List pending (area_manager)
# ─────────────────────────────────────────────────────────────────

def list_pending_inter_branch(db: Session, *, current_user: User) -> list[dict]:
    q = (
        db.query(ReplenishmentOrder)
        .options(
            selectinload(ReplenishmentOrder.lines).selectinload(ReplenishmentOrderLine.item),
            joinedload(ReplenishmentOrder.branch),
            joinedload(ReplenishmentOrder.destination_branch),
        )
        .filter(
            ReplenishmentOrder.order_type == OrderType.inter_branch,
            ReplenishmentOrder.status == OrderStatus.area_manager_review,
        )
        .order_by(ReplenishmentOrder.created_at.desc())
    )

    orders = q.all()
    # Filter by regional scope — area_manager sees only requests where they have access to SOURCE branch
    if not _is_elevated(current_user):
        orders = [o for o in orders if can_access_branch(current_user, o.branch_id, db)]

    results: list[dict] = []
    for o in orders:
        d = _order_to_dict(o)
        # Extract reason from notes prefix "[reason] "
        if o.notes and o.notes.startswith("[reason] "):
            first_line = o.notes.split("\n", 1)[0]
            d["reason"] = first_line[len("[reason] "):]
        results.append(d)
    return results


# ─────────────────────────────────────────────────────────────────
# Approve (area_manager) — moves the stock
# ─────────────────────────────────────────────────────────────────

def approve_inter_branch_order(
    db: Session,
    *,
    order_id: int,
    notes: Optional[str],
    current_user: User,
) -> dict:
    order = lock_row(
        db.query(ReplenishmentOrder).filter(ReplenishmentOrder.id == order_id)
    ).first()

    if not order or order.order_type != OrderType.inter_branch:
        raise AppError(
            status_code=404,
            error_code="inter_branch.not_found",
            message="طلب التحويل غير موجود",
            detail={"order_id": order_id},
        )

    if order.status != OrderStatus.area_manager_review:
        raise AppError(
            status_code=400,
            error_code="inter_branch.invalid_status",
            message="الطلب ليس في حالة انتظار الموافقة",
            detail={"order_id": order_id, "status": str(order.status)},
        )

    # Permission: area_manager must have access to the SOURCE branch (scope = region)
    if not can_access_branch(current_user, order.branch_id, db):
        raise AppError(
            status_code=403,
            error_code="inter_branch.approval_access_denied",
            message="ليس لديك صلاحية اعتماد هذا الطلب (خارج منطقتك)",
            detail={"order_id": order_id, "branch_id": order.branch_id},
        )

    lines = (
        db.query(ReplenishmentOrderLine)
        .filter(ReplenishmentOrderLine.order_id == order.id)
        .all()
    )
    if not lines:
        raise AppError(
            status_code=400,
            error_code="inter_branch.no_lines",
            message="الطلب لا يحتوي على أصناف",
            detail={"order_id": order_id},
        )

    # Lock both branches' stock rows in deterministic order to avoid deadlock
    first_id, second_id = sorted([order.branch_id, order.destination_branch_id])

    # Pre-validate availability + move stock atomically
    transferred: list[dict] = []
    for line in lines:
        # Touch rows in deterministic order
        _ = _get_or_create_locked_branch_stock(db, first_id, line.item_id)
        _ = _get_or_create_locked_branch_stock(db, second_id, line.item_id)

        src_stock = _get_or_create_locked_branch_stock(db, order.branch_id, line.item_id)
        dst_stock = _get_or_create_locked_branch_stock(db, order.destination_branch_id, line.item_id)

        qty = Decimal(str(line.branch_requested_qty or 0))
        if qty <= 0:
            continue

        available = (src_stock.current_qty or Decimal("0")) - (src_stock.reserved_qty or Decimal("0"))
        if available < qty:
            # Do not call db.rollback() here: tests (and some callers) share one outer
            # transaction per request/session — a full rollback would undo seeded rows.
            item_id = line.item_id
            avail_f = float(available)
            req_f = float(qty)
            raise AppError(
                status_code=400,
                error_code="inter_branch.insufficient_stock",
                message="المخزون غير كافٍ في الفرع المصدر لإتمام التحويل",
                detail={
                    "order_id": order_id,
                    "item_id": item_id,
                    "available": avail_f,
                    "requested": req_f,
                },
            )

        src_stock.current_qty = (src_stock.current_qty or Decimal("0")) - qty
        dst_stock.current_qty = (dst_stock.current_qty or Decimal("0")) + qty

        stock_ledger_service.post_transaction(
            db,
            transaction_type=TransactionType.transfer,
            source_type="branch",
            source_id=order.branch_id,
            destination_type="branch",
            destination_id=order.destination_branch_id,
            item_id=line.item_id,
            qty=qty,
            reference_no=order.order_no,
            notes=f"Inter-branch order {order.order_no}",
            created_by=current_user.id,
        )

        line.line_status = "dispatched"
        line.dispatched_qty = qty
        line.received_qty = qty
        transferred.append({"item_id": line.item_id, "qty": float(qty)})

    order.status = OrderStatus.closed
    order.wh_approved_at = datetime.utcnow()
    order.wh_approved_by = current_user.id
    order.closed_at = datetime.utcnow()
    if notes:
        order.notes = (order.notes or "") + f"\n[approval] {notes}"

    db.commit()

    return {
        "message": "تمت الموافقة والتحويل",
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "transferred": transferred,
    }


# ─────────────────────────────────────────────────────────────────
# Reject (area_manager)
# ─────────────────────────────────────────────────────────────────

def reject_inter_branch_order(
    db: Session,
    *,
    order_id: int,
    reason: str,
    current_user: User,
) -> dict:
    order = lock_row(
        db.query(ReplenishmentOrder).filter(ReplenishmentOrder.id == order_id)
    ).first()

    if not order or order.order_type != OrderType.inter_branch:
        raise AppError(
            status_code=404,
            error_code="inter_branch.not_found",
            message="طلب التحويل غير موجود",
            detail={"order_id": order_id},
        )

    if order.status != OrderStatus.area_manager_review:
        raise AppError(
            status_code=400,
            error_code="inter_branch.invalid_status",
            message="الطلب ليس في حالة انتظار الموافقة",
            detail={"order_id": order_id, "status": str(order.status)},
        )

    if not can_access_branch(current_user, order.branch_id, db):
        raise AppError(
            status_code=403,
            error_code="inter_branch.approval_access_denied",
            message="ليس لديك صلاحية رفض هذا الطلب",
            detail={"order_id": order_id, "branch_id": order.branch_id},
        )

    order.status = OrderStatus.rejected
    order.rejection_reason = reason
    db.commit()

    return {
        "message": "تم رفض طلب التحويل",
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status.value,
        "reason": reason,
    }
