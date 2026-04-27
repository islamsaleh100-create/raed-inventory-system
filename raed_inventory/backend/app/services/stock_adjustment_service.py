"""
Stock Adjustment & Transfer Service — Epic 5

Handles:
- Manual branch stock adjustment (increase / decrease / set)
- Manual warehouse stock adjustment
- Branch → Warehouse transfer (return)
- Warehouse → Branch transfer (manual, no order needed)
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import can_access_branch, can_access_warehouse
from app.core.errors import AppError
from app.core.locking import lock_row
from app.models import (
    Branch,
    BranchStock,
    Item,
    TransactionType,
    User,
    Warehouse,
    WarehouseStock,
)
from app.services import stock_ledger_service


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────

def _get_item(db: Session, item_id: int) -> Item:
    item = db.query(Item).filter(Item.id == item_id, Item.is_deleted == False).first()
    if not item:
        raise AppError(
            status_code=404,
            error_code="stock.item_not_found",
            message="Item not found",
            detail={"item_id": item_id},
        )
    return item


def _get_branch(db: Session, branch_id: int) -> Branch:
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.active == True).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="stock.branch_not_found",
            message="Branch not found",
            detail={"branch_id": branch_id},
        )
    return branch


def _get_warehouse(db: Session, warehouse_id: int) -> Warehouse:
    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id, Warehouse.active == True).first()
    if not wh:
        raise AppError(
            status_code=404,
            error_code="stock.warehouse_not_found",
            message="Warehouse not found",
            detail={"warehouse_id": warehouse_id},
        )
    return wh


def _get_or_create_branch_stock(db: Session, branch_id: int, item_id: int, *, for_update: bool = True) -> BranchStock:
    """يُرجِع سجل BranchStock مع قفل الصف (for_update) بشكل افتراضي لمنع race conditions."""
    q = db.query(BranchStock).filter(
        BranchStock.branch_id == branch_id,
        BranchStock.item_id == item_id,
    )
    if for_update:
        q = lock_row(q)
    record = q.first()
    if not record:
        record = BranchStock(branch_id=branch_id, item_id=item_id, current_qty=Decimal("0"))
        db.add(record)
        db.flush()
    return record


def _get_or_create_warehouse_stock(db: Session, warehouse_id: int, item_id: int, *, for_update: bool = True) -> WarehouseStock:
    """يُرجِع سجل WarehouseStock مع قفل الصف (for_update) بشكل افتراضي."""
    q = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == warehouse_id,
        WarehouseStock.item_id == item_id,
    )
    if for_update:
        q = lock_row(q)
    record = q.first()
    if not record:
        record = WarehouseStock(warehouse_id=warehouse_id, item_id=item_id, current_qty=Decimal("0"))
        db.add(record)
        db.flush()
    return record


# ──────────────────────────────────────────────────────────────────────────
# BRANCH STOCK ADJUSTMENT
# ──────────────────────────────────────────────────────────────────────────

def adjust_branch_stock(
    db: Session,
    *,
    branch_id: int,
    item_id: int,
    adjustment_type: str,   # "increase" | "decrease" | "set"
    qty: Decimal,
    reason: str,
    reference_no: str | None = None,
    current_user: User,
) -> dict:
    """
    Manual adjustment of branch stock.
    adjustment_type:
      - increase: add qty to current stock
      - decrease: subtract qty (floor at 0)
      - set: override to exact qty
    """
    if not can_access_branch(current_user, branch_id, db):
        raise AppError(
            status_code=403,
            error_code="stock.branch_access_denied",
            message="Access denied for this branch",
            detail={"branch_id": branch_id},
        )

    if adjustment_type not in ("increase", "decrease", "set"):
        raise AppError(
            status_code=400,
            error_code="stock.invalid_adjustment_type",
            message="adjustment_type must be 'increase', 'decrease', or 'set'",
            detail={"adjustment_type": adjustment_type},
        )

    if qty < 0:
        raise AppError(
            status_code=400,
            error_code="stock.negative_qty",
            message="qty must be >= 0",
            detail={"qty": str(qty)},
        )

    _get_branch(db, branch_id)
    _get_item(db, item_id)
    stock = _get_or_create_branch_stock(db, branch_id, item_id)

    old_qty = stock.current_qty

    if adjustment_type == "increase":
        delta = qty
        stock.current_qty += qty
        tx_type = TransactionType.adjustment_in
    elif adjustment_type == "decrease":
        delta = -qty
        stock.current_qty = max(Decimal("0"), stock.current_qty - qty)
        tx_type = TransactionType.adjustment_out
    else:  # set
        delta = qty - old_qty
        stock.current_qty = qty
        tx_type = TransactionType.adjustment_in if delta >= 0 else TransactionType.adjustment_out

    if delta != 0:
        stock_ledger_service.post_transaction(
            db,
            transaction_type=tx_type,
            source_type="branch",
            source_id=branch_id,
            item_id=item_id,
            qty=abs(delta),
            reference_no=reference_no,
            notes=f"Manual {adjustment_type}: {reason}",
            created_by=current_user.id,
        )

    db.commit()

    return {
        "branch_id": branch_id,
        "item_id": item_id,
        "adjustment_type": adjustment_type,
        "old_qty": float(old_qty),
        "new_qty": float(stock.current_qty),
        "delta": float(delta),
        "reason": reason,
    }


# ──────────────────────────────────────────────────────────────────────────
# WAREHOUSE STOCK ADJUSTMENT
# ──────────────────────────────────────────────────────────────────────────

def adjust_warehouse_stock(
    db: Session,
    *,
    warehouse_id: int,
    item_id: int,
    adjustment_type: str,   # "increase" | "decrease" | "set"
    qty: Decimal,
    reason: str,
    reference_no: str | None = None,
    current_user: User,
) -> dict:
    if not can_access_warehouse(current_user, warehouse_id):
        raise AppError(
            status_code=403,
            error_code="stock.warehouse_access_denied",
            message="Access denied for this warehouse",
            detail={"warehouse_id": warehouse_id},
        )

    if adjustment_type not in ("increase", "decrease", "set"):
        raise AppError(
            status_code=400,
            error_code="stock.invalid_adjustment_type",
            message="adjustment_type must be 'increase', 'decrease', or 'set'",
            detail={"adjustment_type": adjustment_type},
        )

    if qty < 0:
        raise AppError(
            status_code=400,
            error_code="stock.negative_qty",
            message="qty must be >= 0",
            detail={"qty": str(qty)},
        )

    _get_warehouse(db, warehouse_id)
    _get_item(db, item_id)
    stock = _get_or_create_warehouse_stock(db, warehouse_id, item_id)

    old_qty = stock.current_qty

    if adjustment_type == "increase":
        delta = qty
        stock.current_qty += qty
        tx_type = TransactionType.adjustment_in
    elif adjustment_type == "decrease":
        delta = -qty
        stock.current_qty = max(Decimal("0"), stock.current_qty - qty)
        tx_type = TransactionType.adjustment_out
    else:  # set
        delta = qty - old_qty
        stock.current_qty = qty
        tx_type = TransactionType.adjustment_in if delta >= 0 else TransactionType.adjustment_out

    if delta != 0:
        stock_ledger_service.post_transaction(
            db,
            transaction_type=tx_type,
            source_type="warehouse",
            source_id=warehouse_id,
            item_id=item_id,
            qty=abs(delta),
            reference_no=reference_no,
            notes=f"Manual {adjustment_type}: {reason}",
            created_by=current_user.id,
        )

    db.commit()

    return {
        "warehouse_id": warehouse_id,
        "item_id": item_id,
        "adjustment_type": adjustment_type,
        "old_qty": float(old_qty),
        "new_qty": float(stock.current_qty),
        "delta": float(delta),
        "reason": reason,
    }


# ──────────────────────────────────────────────────────────────────────────
# WAREHOUSE → BRANCH TRANSFER  (manual, no replenishment order)
# ──────────────────────────────────────────────────────────────────────────

def transfer_warehouse_to_branch(
    db: Session,
    *,
    warehouse_id: int,
    branch_id: int,
    item_id: int,
    qty: Decimal,
    reason: str,
    reference_no: str | None = None,
    current_user: User,
) -> dict:
    if qty <= 0:
        raise AppError(
            status_code=400,
            error_code="stock.qty_must_be_positive",
            message="qty must be > 0",
            detail={"qty": str(qty)},
        )

    # ─── RBAC: تأكد أن المستخدم يملك صلاحية على المستودع المصدر ─────────────
    if not can_access_warehouse(current_user, warehouse_id):
        raise AppError(
            status_code=403,
            error_code="stock.warehouse_access_denied",
            message="ليس لديك صلاحية على المستودع المصدر",
            detail={"warehouse_id": warehouse_id},
        )
    # مدير/مستخدم الفرع لا يستطيع سحب لفرع آخر
    if not can_access_branch(current_user, branch_id, db):
        # نسمح لمستخدم المستودع بالتحويل لأي فرع (warehouse_manager عادي)
        from app.core.auth import get_user_roles
        roles = get_user_roles(current_user)
        if not any(r in roles for r in ("warehouse_user", "warehouse_manager", "admin", "super_admin", "operations_manager")):
            raise AppError(
                status_code=403,
                error_code="stock.branch_access_denied",
                message="ليس لديك صلاحية على الفرع الوجهة",
                detail={"branch_id": branch_id},
            )

    _get_warehouse(db, warehouse_id)
    _get_branch(db, branch_id)
    _get_item(db, item_id)

    wh_stock = _get_or_create_warehouse_stock(db, warehouse_id, item_id)
    if wh_stock.current_qty < qty:
        raise AppError(
            status_code=400,
            error_code="stock.insufficient_warehouse_qty",
            message="Insufficient warehouse stock for transfer",
            detail={
                "warehouse_id": warehouse_id,
                "item_id": item_id,
                "available": float(wh_stock.current_qty),
                "requested": float(qty),
            },
        )

    br_stock = _get_or_create_branch_stock(db, branch_id, item_id)

    wh_stock.current_qty -= qty
    br_stock.current_qty += qty

    stock_ledger_service.post_transaction(
        db,
        transaction_type=TransactionType.warehouse_dispatch,
        source_type="warehouse",
        source_id=warehouse_id,
        destination_type="branch",
        destination_id=branch_id,
        item_id=item_id,
        qty=qty,
        reference_no=reference_no,
        notes=f"Manual transfer: {reason}",
        created_by=current_user.id,
    )

    db.commit()

    return {
        "warehouse_id": warehouse_id,
        "branch_id": branch_id,
        "item_id": item_id,
        "qty_transferred": float(qty),
        "warehouse_qty_after": float(wh_stock.current_qty),
        "branch_qty_after": float(br_stock.current_qty),
        "reason": reason,
    }


# ──────────────────────────────────────────────────────────────────────────
# BRANCH → WAREHOUSE RETURN
# ──────────────────────────────────────────────────────────────────────────

def transfer_branch_to_warehouse(
    db: Session,
    *,
    branch_id: int,
    warehouse_id: int,
    item_id: int,
    qty: Decimal,
    reason: str,
    reference_no: str | None = None,
    current_user: User,
) -> dict:
    if qty <= 0:
        raise AppError(
            status_code=400,
            error_code="stock.qty_must_be_positive",
            message="qty must be > 0",
            detail={"qty": str(qty)},
        )

    if not can_access_branch(current_user, branch_id, db):
        raise AppError(
            status_code=403,
            error_code="stock.branch_access_denied",
            message="Access denied for this branch",
            detail={"branch_id": branch_id},
        )
    # لا نلزم can_access_warehouse هنا لأن الفرع يُرجِع للمستودع
    # ولكن نتحقق من وجود المستودع.

    _get_branch(db, branch_id)
    _get_warehouse(db, warehouse_id)
    _get_item(db, item_id)

    # ترتيب القفل ثابت لمنع deadlock: warehouse أولاً ثم branch.
    wh_stock = _get_or_create_warehouse_stock(db, warehouse_id, item_id)
    br_stock = _get_or_create_branch_stock(db, branch_id, item_id)
    if br_stock.current_qty < qty:
        raise AppError(
            status_code=400,
            error_code="stock.insufficient_branch_qty",
            message="Insufficient branch stock for return",
            detail={
                "branch_id": branch_id,
                "item_id": item_id,
                "available": float(br_stock.current_qty),
                "requested": float(qty),
            },
        )

    br_stock.current_qty -= qty
    wh_stock.current_qty += qty

    stock_ledger_service.post_transaction(
        db,
        transaction_type=TransactionType.branch_receipt,
        source_type="branch",
        source_id=branch_id,
        destination_type="warehouse",
        destination_id=warehouse_id,
        item_id=item_id,
        qty=qty,
        reference_no=reference_no,
        notes=f"Branch return: {reason}",
        created_by=current_user.id,
    )

    db.commit()

    return {
        "branch_id": branch_id,
        "warehouse_id": warehouse_id,
        "item_id": item_id,
        "qty_returned": float(qty),
        "branch_qty_after": float(br_stock.current_qty),
        "warehouse_qty_after": float(wh_stock.current_qty),
        "reason": reason,
    }


# ──────────────────────────────────────────────────────────────────────────
# BRANCH → BRANCH TRANSFER (inter-branch)
# ──────────────────────────────────────────────────────────────────────────

def transfer_branch_to_branch(
    db: Session,
    *,
    source_branch_id: int,
    destination_branch_id: int,
    item_id: int,
    qty: Decimal,
    reason: str,
    reference_no: str | None = None,
    current_user: User,
) -> dict:
    """
    تحويل كميّة من فرع إلى فرع آخر مباشرةً (inter-branch transfer).

    قواعد:
    - يتطلّب صلاحية على الفرعين (super_admin / admin / operations_manager /
      area_manager — المستخدمون العاديون لا يملكون صلاحية على فرع آخر).
    - قفل الصفوف بترتيب ثابت (الفرع ذو المعرّف الأقل أولاً) لمنع deadlock.
    - ينشئ transaction واحدة بنوع `transfer` في الـ ledger.
    """
    if qty <= 0:
        raise AppError(
            status_code=400,
            error_code="stock.qty_must_be_positive",
            message="qty must be > 0",
            detail={"qty": str(qty)},
        )
    if source_branch_id == destination_branch_id:
        raise AppError(
            status_code=400,
            error_code="stock.same_branch_transfer",
            message="Source and destination branches must differ",
            detail={"source_branch_id": source_branch_id},
        )

    # صلاحية: نحتاج وصول على الفرعين (area_manager يُسمح له فقط داخل منطقته)
    if not can_access_branch(current_user, source_branch_id, db):
        raise AppError(
            status_code=403,
            error_code="stock.branch_access_denied",
            message="Access denied for source branch",
            detail={"branch_id": source_branch_id},
        )
    if not can_access_branch(current_user, destination_branch_id, db):
        raise AppError(
            status_code=403,
            error_code="stock.branch_access_denied",
            message="Access denied for destination branch",
            detail={"branch_id": destination_branch_id},
        )

    _get_branch(db, source_branch_id)
    _get_branch(db, destination_branch_id)
    _get_item(db, item_id)

    # قفل الصفوف بترتيب deterministic (أصغر id أولاً) لمنع deadlock
    first_id, second_id = sorted([source_branch_id, destination_branch_id])
    _ = _get_or_create_branch_stock(db, first_id, item_id)
    _ = _get_or_create_branch_stock(db, second_id, item_id)

    src = _get_or_create_branch_stock(db, source_branch_id, item_id)
    dst = _get_or_create_branch_stock(db, destination_branch_id, item_id)

    available = src.current_qty - src.reserved_qty
    if available < qty:
        raise AppError(
            status_code=400,
            error_code="stock.insufficient_branch_qty",
            message="Insufficient available stock in source branch",
            detail={
                "source_branch_id": source_branch_id,
                "item_id": item_id,
                "available": float(available),
                "requested": float(qty),
            },
        )

    src.current_qty -= qty
    dst.current_qty += qty

    stock_ledger_service.post_transaction(
        db,
        transaction_type=TransactionType.transfer,
        source_type="branch",
        source_id=source_branch_id,
        destination_type="branch",
        destination_id=destination_branch_id,
        item_id=item_id,
        qty=qty,
        reference_no=reference_no,
        notes=f"Inter-branch transfer: {reason}",
        created_by=current_user.id,
    )

    db.commit()

    return {
        "source_branch_id": source_branch_id,
        "destination_branch_id": destination_branch_id,
        "item_id": item_id,
        "qty_transferred": float(qty),
        "source_qty_after": float(src.current_qty),
        "destination_qty_after": float(dst.current_qty),
        "reason": reason,
    }
