"""
Daily Inventory Business Logic Service
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.auth import can_access_branch
from app.core.errors import AppError
from app.models import (
    DailyInventory, DailyInventoryLine, BranchStock, Item,
    ReplenishmentOrder, StockTransaction, TransactionType, InventoryStatus, Branch, User
)
from app.schemas import InventoryCreate, InventoryLineCreate
from app.services import idempotency_service, replenishment_service, stock_ledger_service, audit_service


VARIANCE_THRESHOLD_WARNING = Decimal("10")   # 10%
VARIANCE_THRESHOLD_CRITICAL = Decimal("25")  # 25%


def _calculate_variance_status(pct: Decimal) -> str:
    abs_pct = abs(pct)
    if abs_pct >= VARIANCE_THRESHOLD_CRITICAL:
        return "critical"
    elif abs_pct >= VARIANCE_THRESHOLD_WARNING:
        return "warning"
    return "ok"


def get_branch_book_qty(db: Session, branch_id: int, item_id: int) -> Decimal:
    stock = db.query(BranchStock).filter(
        BranchStock.branch_id == branch_id,
        BranchStock.item_id == item_id
    ).first()
    return stock.current_qty if stock else Decimal("0")


def _ensure_inventory_access(current_user: User, inventory: DailyInventory, db: Session):
    if not can_access_branch(current_user, inventory.branch_id, db):
        raise AppError(
            status_code=403,
            error_code="inventory.access_denied",
            message="Access denied for this inventory",
            detail={"inventory_id": inventory.id, "branch_id": inventory.branch_id},
        )


def _load_inventory_for_update(db: Session, inventory_id: int, *, with_lines: bool = False) -> DailyInventory:
    query = db.query(DailyInventory)
    if with_lines:
        query = query.options(selectinload(DailyInventory.lines).joinedload(DailyInventoryLine.item))
    inventory = query.filter(DailyInventory.id == inventory_id).first()
    if not inventory:
        raise AppError(
            status_code=404,
            error_code="inventory.not_found",
            message="Inventory not found",
            detail={"inventory_id": inventory_id},
        )
    return inventory


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
                error_code="inventory.duplicate_request_in_progress",
                message="Duplicate request is already in progress",
                detail={"operation_name": operation_name},
            )

    return None, None


def _build_approve_inventory_response(
    db: Session,
    *,
    inventory_id: int,
    order=None,
    note_message: str | None = None,
) -> dict:
    inventory = db.query(DailyInventory).options(
        selectinload(DailyInventory.lines).joinedload(DailyInventoryLine.item)
    ).filter(DailyInventory.id == inventory_id).first()
    order = order or db.query(ReplenishmentOrder).filter(
        ReplenishmentOrder.inventory_id == inventory_id
    ).first()

    return {
        "inventory": inventory,
        "replenishment_order": order,
        "message": note_message or "Inventory approved and replenishment order generated",
    }


def get_inventory_by_id(db: Session, inventory_id: int, current_user: User) -> DailyInventory:
    inventory = db.query(DailyInventory).options(
        selectinload(DailyInventory.lines)
    ).filter(DailyInventory.id == inventory_id).first()
    if not inventory:
        raise AppError(
            status_code=404,
            error_code="inventory.not_found",
            message="Inventory not found",
            detail={"inventory_id": inventory_id},
        )
    _ensure_inventory_access(current_user, inventory, db)
    return inventory


def create_inventory_for_user(db: Session, payload: InventoryCreate, current_user: User) -> DailyInventory:
    if not can_access_branch(current_user, payload.branch_id, db):
        raise AppError(
            status_code=403,
            error_code="inventory.branch_access_denied",
            message="Access denied for this branch",
            detail={"branch_id": payload.branch_id},
        )
    return create_or_update_inventory(db, payload, current_user)


def submit_inventory_for_user(db: Session, inventory_id: int, current_user: User) -> DailyInventory:
    inventory = _load_inventory_for_update(db, inventory_id)
    _ensure_inventory_access(current_user, inventory, db)
    return submit_inventory(db, inventory_id, current_user)


def approve_inventory_for_user(
    db: Session,
    *,
    inventory_id: int,
    current_user: User,
    client_request_id: str | None = None,
) -> dict:
    inventory = _load_inventory_for_update(db, inventory_id)
    _ensure_inventory_access(current_user, inventory, db)

    # Idempotency replay must run before the "already approved" guard so a
    # second request with the same X-Client-Request-Id returns 200 + replay.
    replay_payload = _build_approve_inventory_response(db, inventory_id=inventory_id)
    idempotency_record, replay_response = _try_begin_idempotent_operation(
        db,
        client_request_id=client_request_id,
        operation_name="inventory.approve",
        current_user=current_user,
        replay_payload=replay_payload,
    )
    if replay_response:
        return replay_response

    # ─── منع Double-Approval عندما لا يوجد مفتاح idempotency مكتمل ─────────
    if inventory.status == InventoryStatus.approved:
        raise AppError(
            status_code=409,
            error_code="inventory.already_approved",
            message="الجرد موافق عليه مسبقاً — لا يمكن الموافقة مرة أخرى",
            detail={"inventory_id": inventory_id, "status": inventory.status.value},
        )

    approved_inventory = approve_inventory(db, inventory_id, current_user)

    try:
        order = replenishment_service.generate_replenishment_order(db, inventory_id, current_user)
        response_payload = _build_approve_inventory_response(
            db,
            inventory_id=approved_inventory.id,
            order=order,
        )
    except Exception:
        response_payload = _build_approve_inventory_response(
            db,
            inventory_id=approved_inventory.id,
            note_message="Inventory approved. Order generation note: unable to generate replenishment order",
        )

    if idempotency_record:
        idempotency_service.complete_idempotency_request(
            db,
            record=idempotency_record,
            response_reference_type="daily_inventory",
            response_reference_id=approved_inventory.id,
        )
    return response_payload


def reject_inventory_for_user(db: Session, inventory_id: int, reason: str, current_user: User) -> DailyInventory:
    inventory = _load_inventory_for_update(db, inventory_id)
    _ensure_inventory_access(current_user, inventory, db)
    if not reason:
        raise AppError(
            status_code=400,
            error_code="inventory.rejection_reason_required",
            message="Rejection reason is required",
            detail={"inventory_id": inventory_id},
        )
    return reject_inventory(db, inventory_id, reason, current_user)


def create_or_update_inventory(
    db: Session,
    payload: InventoryCreate,
    user: User
) -> DailyInventory:
    # ─── قفل على مستوى (branch, date) لمنع إنشاء جلستين متوازيتين ─────────
    # نستخدم قفل ممتد على أي سجل موجود لنفس التاريخ — لو لم يوجد، الـ UNIQUE
    # constraint على (branch_id, inventory_date) في الـ DB يمنع التكرار
    # ويرفع IntegrityError (يُعالَج أدناه).
    from app.core.locking import lock_row
    from sqlalchemy.exc import IntegrityError

    existing_any = lock_row(
        db.query(DailyInventory).filter(
            DailyInventory.branch_id == payload.branch_id,
            DailyInventory.inventory_date == payload.inventory_date,
        )
    ).first()

    if existing_any and existing_any.status == InventoryStatus.approved:
        raise AppError(
            status_code=400,
            error_code="inventory.already_approved_for_date",
            message="Inventory already approved for this date",
            detail={"branch_id": payload.branch_id, "inventory_date": str(payload.inventory_date)},
        )
    if existing_any and existing_any.status == InventoryStatus.submitted:
        raise AppError(
            status_code=400,
            error_code="inventory.already_submitted_for_date",
            message="Inventory already submitted, waiting for approval",
            detail={"branch_id": payload.branch_id, "inventory_date": str(payload.inventory_date)},
        )

    existing = existing_any if existing_any and existing_any.status == InventoryStatus.draft else None

    # Validate critical items are all counted
    critical_items = db.query(Item).filter(
        Item.critical_item == True,
        Item.active == True,
        Item.branch_requestable == True,
        Item.is_deleted == False
    ).all()

    submitted_item_ids = {line.item_id for line in payload.lines}
    for ci in critical_items:
        if ci.id not in submitted_item_ids:
            raise AppError(
                status_code=400,
                error_code="inventory.missing_critical_item",
                message="Critical item must be included in inventory",
                detail={"item_id": ci.id, "item_code": ci.item_code, "item_name_ar": ci.item_name_ar},
            )

    if existing:
        # Update existing draft
        db.query(DailyInventoryLine).filter(
            DailyInventoryLine.inventory_id == existing.id
        ).delete()
        inventory = existing
        inventory.notes = payload.notes
        # H9: allow the branch to change the type while still a draft
        if getattr(payload, "inventory_type", None):
            inventory.inventory_type = payload.inventory_type
        inventory.updated_at = datetime.utcnow()
    else:
        inventory = DailyInventory(
            branch_id=payload.branch_id,
            inventory_date=payload.inventory_date,
            inventory_type=getattr(payload, "inventory_type", None) or "daily",
            status=InventoryStatus.draft,
            notes=payload.notes,
            created_by=user.id,
        )
        db.add(inventory)
        db.flush()

    # Create lines
    for line_data in payload.lines:
        item = db.query(Item).filter(Item.id == line_data.item_id, Item.is_deleted == False).first()
        if not item:
            continue

        book_qty = get_branch_book_qty(db, payload.branch_id, line_data.item_id)
        variance_qty = line_data.counted_qty - book_qty
        variance_pct = (
            (variance_qty / book_qty * 100) if book_qty != 0
            else (Decimal("100") if line_data.counted_qty > 0 else Decimal("0"))
        )

        line = DailyInventoryLine(
            inventory_id=inventory.id,
            item_id=line_data.item_id,
            book_qty=book_qty,
            counted_qty=line_data.counted_qty,
            variance_qty=variance_qty,
            variance_pct=variance_pct,
            variance_status=_calculate_variance_status(variance_pct),
            below_min_flag=line_data.counted_qty < item.min_qty,
            out_of_stock_flag=line_data.counted_qty <= 0,
            variance_reason_id=line_data.variance_reason_id,
            notes=line_data.notes,
        )
        db.add(line)

    db.commit()
    db.refresh(inventory)
    return inventory


def submit_inventory(db: Session, inventory_id: int, user: User) -> DailyInventory:
    inventory = db.query(DailyInventory).filter(DailyInventory.id == inventory_id).first()
    if not inventory:
        raise AppError(
            status_code=404,
            error_code="inventory.not_found",
            message="Inventory not found",
            detail={"inventory_id": inventory_id},
        )
    if inventory.status != InventoryStatus.draft:
        raise AppError(
            status_code=400,
            error_code="inventory.invalid_submit_status",
            message="Cannot submit inventory in the current status",
            detail={"inventory_id": inventory_id, "status": inventory.status.value},
        )

    # Validate critical items have variance reason if critical variance
    lines_with_critical_variance = [
        l for l in inventory.lines
        if l.variance_status == "critical" and not l.variance_reason_id
    ]
    if lines_with_critical_variance:
        item_names = [l.item.item_name_ar for l in lines_with_critical_variance]
        raise AppError(
            status_code=400,
            error_code="inventory.critical_variance_reason_required",
            message="Please provide variance reason for items with critical variance",
            detail={"inventory_id": inventory_id, "item_names": item_names},
        )

    inventory.status = InventoryStatus.submitted
    inventory.submitted_at = datetime.utcnow()
    inventory.submitted_by = user.id
    db.commit()
    return inventory


def approve_inventory(db: Session, inventory_id: int, user: User) -> DailyInventory:
    inventory = db.query(DailyInventory).options(
        selectinload(DailyInventory.lines)
    ).filter(DailyInventory.id == inventory_id).first()

    if not inventory:
        raise AppError(
            status_code=404,
            error_code="inventory.not_found",
            message="Inventory not found",
            detail={"inventory_id": inventory_id},
        )
    if inventory.status != InventoryStatus.submitted:
        raise AppError(
            status_code=400,
            error_code="inventory.invalid_approval_status",
            message="Inventory must be submitted before approval",
            detail={"inventory_id": inventory_id, "status": inventory.status.value},
        )

    # Update branch stock based on counted quantities
    # ─── قفل الصف لمنع race مع dispatches/receipts متزامنة ────────────────
    from app.core.locking import lock_row
    for line in inventory.lines:
        if line.counted_qty is None or line.counted_qty < 0:
            raise AppError(
                status_code=400,
                error_code="inventory.invalid_counted_qty",
                message="الكمية المجردة لا يمكن أن تكون فارغة أو سالبة",
                detail={"line_id": line.id, "counted_qty": str(line.counted_qty)},
            )
        stock = lock_row(db.query(BranchStock).filter(
            BranchStock.branch_id == inventory.branch_id,
            BranchStock.item_id == line.item_id
        )).first()

        if stock:
            stock.current_qty = line.counted_qty
            stock.last_updated = datetime.utcnow()
        else:
            stock = BranchStock(
                branch_id=inventory.branch_id,
                item_id=line.item_id,
                current_qty=line.counted_qty,
            )
            db.add(stock)

        # Post adjustment transaction
        if abs(line.variance_qty) > 0:
            tx = stock_ledger_service.post_transaction(
                db,
                transaction_type=TransactionType.inventory_adjustment,
                item_id=line.item_id,
                qty=line.variance_qty,
                source_type="branch",
                source_id=inventory.branch_id,
                destination_type="branch",
                destination_id=inventory.branch_id,
                reference_no=f"INV-{inventory_id}",
                notes=f"Inventory adjustment - date: {inventory.inventory_date}",
                created_by=user.id,
            )

    inventory.status = InventoryStatus.approved
    inventory.approved_at = datetime.utcnow()
    inventory.approved_by = user.id
    db.commit()
    audit_service.log(
        db,
        user_id=user.id,
        action="approve",
        module="inventory",
        entity_type="daily_inventory",
        entity_id=inventory_id,
        new_values={"status": "approved", "inventory_date": str(inventory.inventory_date)},
    )
    db.commit()
    return inventory


def reject_inventory(db: Session, inventory_id: int, reason: str, user: User) -> DailyInventory:
    inventory = db.query(DailyInventory).filter(DailyInventory.id == inventory_id).first()
    if not inventory:
        raise AppError(
            status_code=404,
            error_code="inventory.not_found",
            message="Inventory not found",
            detail={"inventory_id": inventory_id},
        )
    if inventory.status != InventoryStatus.submitted:
        raise AppError(
            status_code=400,
            error_code="inventory.invalid_reject_status",
            message="Inventory must be submitted to reject",
            detail={"inventory_id": inventory_id, "status": inventory.status.value},
        )

    inventory.status = InventoryStatus.rejected
    inventory.rejection_reason = reason
    db.commit()
    audit_service.log(
        db,
        user_id=user.id,
        action="reject",
        module="inventory",
        entity_type="daily_inventory",
        entity_id=inventory_id,
        new_values={"status": "rejected", "rejection_reason": reason},
    )
    db.commit()
    return inventory


def get_inventory_list(
    db: Session,
    branch_id: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
):
    q = db.query(DailyInventory).options(
        joinedload(DailyInventory.branch),
        selectinload(DailyInventory.lines),  # needed for surplus/line counts
    )
    if branch_id:
        q = q.filter(DailyInventory.branch_id == branch_id)
    if status:
        q = q.filter(DailyInventory.status == status)
    if date_from:
        q = q.filter(DailyInventory.inventory_date >= date_from)
    if date_to:
        q = q.filter(DailyInventory.inventory_date <= date_to)

    total = q.count()
    items = q.order_by(DailyInventory.inventory_date.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # H8: surface line counts + surplus marker on each summary row
    for inv in items:
        lines = inv.lines or []
        inv.line_count = len(lines)
        inv.surplus_lines_count = sum(
            1 for ln in lines if ln is not None and (ln.variance_qty or 0) > 0
        )

    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ─────────────────────────────────────────────────────────────────────────
# PATCH single inventory line
# ─────────────────────────────────────────────────────────────────────────

def update_inventory_line(
    db: Session,
    *,
    inventory_id: int,
    line_id: int,
    counted_qty: Decimal | None,
    variance_reason_id: int | None,
    notes: str | None,
    current_user: User,
) -> DailyInventory:
    """
    Update a single line in a DRAFT inventory.
    Recalculates variance fields after the update.
    Returns the full refreshed inventory.
    """
    inventory = _load_inventory_for_update(db, inventory_id, with_lines=False)
    _ensure_inventory_access(current_user, inventory, db)

    if inventory.status != InventoryStatus.draft:
        raise AppError(
            status_code=400,
            error_code="inventory.not_draft",
            message="Only draft inventories can be line-edited",
            detail={"inventory_id": inventory_id, "status": inventory.status.value},
        )

    line = db.query(DailyInventoryLine).filter(
        DailyInventoryLine.id == line_id,
        DailyInventoryLine.inventory_id == inventory_id,
    ).first()
    if not line:
        raise AppError(
            status_code=404,
            error_code="inventory.line_not_found",
            message="Inventory line not found",
            detail={"line_id": line_id, "inventory_id": inventory_id},
        )

    if counted_qty is not None:
        book_qty = line.book_qty if line.book_qty is not None else Decimal("0")
        variance_qty = counted_qty - book_qty
        variance_pct = (
            (variance_qty / book_qty * 100) if book_qty != 0
            else (Decimal("100") if counted_qty > 0 else Decimal("0"))
        )
        item = db.query(Item).filter(Item.id == line.item_id).first()

        line.counted_qty = counted_qty
        line.variance_qty = variance_qty
        line.variance_pct = variance_pct
        line.variance_status = _calculate_variance_status(variance_pct)
        line.below_min_flag = bool(item and counted_qty < item.min_qty)
        line.out_of_stock_flag = counted_qty <= 0

    if variance_reason_id is not None:
        line.variance_reason_id = variance_reason_id

    if notes is not None:
        line.notes = notes

    inventory.updated_at = datetime.utcnow()
    db.commit()

    # Return full inventory with lines for the response
    return db.query(DailyInventory).options(
        selectinload(DailyInventory.lines).joinedload(DailyInventoryLine.item)
    ).filter(DailyInventory.id == inventory_id).first()


# ─────────────────────────────────────────────────────────────────────────
# Reopen rejected inventory
# ─────────────────────────────────────────────────────────────────────────

def reopen_inventory_for_user(
    db: Session, inventory_id: int, current_user: User
) -> DailyInventory:
    inventory = _load_inventory_for_update(db, inventory_id)
    _ensure_inventory_access(current_user, inventory, db)

    if inventory.status != InventoryStatus.rejected:
        raise AppError(
            status_code=400,
            error_code="inventory.cannot_reopen",
            message="Only rejected inventories can be reopened",
            detail={"inventory_id": inventory_id, "status": inventory.status.value},
        )

    inventory.status = InventoryStatus.draft
    inventory.rejection_reason = None
    inventory.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(inventory)
    return inventory


# ─────────────────────────────────────────────────────────────────────────
# Delete draft inventory
# ─────────────────────────────────────────────────────────────────────────

def delete_draft_inventory(
    db: Session, inventory_id: int, current_user: User
) -> dict:
    inventory = _load_inventory_for_update(db, inventory_id)
    _ensure_inventory_access(current_user, inventory, db)

    if inventory.status != InventoryStatus.draft:
        raise AppError(
            status_code=400,
            error_code="inventory.cannot_delete",
            message="Only draft inventories can be deleted",
            detail={"inventory_id": inventory_id, "status": inventory.status.value},
        )

    db.query(DailyInventoryLine).filter(
        DailyInventoryLine.inventory_id == inventory_id
    ).delete()
    db.delete(inventory)
    db.commit()
    return {"message": "Draft inventory deleted", "inventory_id": inventory_id}


# ─────────────────────────────────────────────────────────────────────────
# Submit with idempotency
# ─────────────────────────────────────────────────────────────────────────

def submit_inventory_idempotent(
    db: Session,
    *,
    inventory_id: int,
    current_user: User,
    client_request_id: str | None = None,
) -> DailyInventory:
    """
    Idempotency-aware submit.  If the same client_request_id is replayed
    and the inventory is already submitted/approved, returns the current state
    without error.
    """
    inventory = _load_inventory_for_update(db, inventory_id)
    _ensure_inventory_access(current_user, inventory, db)

    # If already past submitted state and we have idempotency key → replay
    if client_request_id and inventory.status in (
        InventoryStatus.submitted, InventoryStatus.approved
    ):
        return inventory

    return submit_inventory(db, inventory_id, current_user)


# ─────────────────────────────────────────────────────────────────────────
# Today's inventory status across all branches
# ─────────────────────────────────────────────────────────────────────────

def get_today_inventory_status(db: Session, current_user: User) -> list[dict]:
    """
    Returns one record per active branch showing whether today's inventory
    has been started, submitted, or approved.
    Branch users only see their own branch.
    """
    from app.models import Branch as _Branch

    today = date.today()

    branches_q = db.query(_Branch).filter(
        _Branch.active == True, _Branch.is_deleted == False
    )

    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    is_branch_scoped = "branch_user" in user_roles or "branch_manager" in user_roles
    if is_branch_scoped and current_user.branch_id:
        branches_q = branches_q.filter(_Branch.id == current_user.branch_id)

    branches = branches_q.order_by(_Branch.id).all()

    # Load today's inventories in one query
    inv_map: dict[int, DailyInventory] = {}
    if branches:
        branch_ids = [b.id for b in branches]
        today_inventories = db.query(DailyInventory).filter(
            DailyInventory.inventory_date == today,
            DailyInventory.branch_id.in_(branch_ids),
        ).all()
        for inv in today_inventories:
            inv_map[inv.branch_id] = inv

    result = []
    for branch in branches:
        inv = inv_map.get(branch.id)
        items_below_min = 0
        items_oos = 0
        lines_count = 0
        if inv:
            lines = db.query(DailyInventoryLine).filter(
                DailyInventoryLine.inventory_id == inv.id
            ).all()
            lines_count = len(lines)
            items_below_min = sum(1 for l in lines if l.below_min_flag)
            items_oos = sum(1 for l in lines if l.out_of_stock_flag)

        result.append({
            "branch_id": branch.id,
            "branch_name": branch.branch_name,
            "inventory_id": inv.id if inv else None,
            "status": inv.status.value if inv else None,
            "submitted_at": inv.submitted_at if inv else None,
            "approved_at": inv.approved_at if inv else None,
            "lines_count": lines_count,
            "items_below_min": items_below_min,
            "items_out_of_stock": items_oos,
        })

    return result
