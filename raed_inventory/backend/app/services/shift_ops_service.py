"""Business logic for branch shift operations."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.auth import can_access_branch, get_user_roles
from app.core.errors import AppError
from app.core.timezone import now_tz, utcnow_aware
from app.models import Branch, BranchBrand, Brand, Item, User
from app.models.branch_shift_ops import (
    BranchShift,
    BranchShiftCash,
    BranchShiftConfig,
    BranchShiftCount,
    BranchShiftCountExclusion,
    BranchShiftCountLine,
    BranchShiftExceptionType,
    BranchShiftReopenEvent,
    BranchShiftStatus,
    BrandShiftCountItem,
    ShiftCountRowStatus,
    ShiftReopenTarget,
    ShiftSectionStatus,
)
from app.services import audit_service
from app.services.shift_ops_validation import evaluate_count_line, validate_cash_payload

OVERRIDE_ROLES = {"area_manager", "operations_manager", "admin", "super_admin"}
REOPEN_ROLES = OVERRIDE_ROLES
# 2026-08-16 owner decision: only branch_manager may write shift-ops at branch level.
# Existing non-manager branch accounts (25 in prod) lose shift-ops access; accounts are not deleted.
BRANCH_WRITE_ROLES = {"branch_manager"}
# Read vs write are separate permissions. Write stays branch_manager-only (owner 2026-08-16).
# Read for oversight: admin + audit/management roles (owner 2026-08-20). Scope via can_access_branch.
BRANCH_READ_ROLES = BRANCH_WRITE_ROLES | {
    "admin",
    "super_admin",
    "operations_manager",
    "internal_auditor",
    "area_manager",
}
REOPEN_LIMIT = 2
REOPEN_WINDOW_HOURS = 48


def _roles(user: User) -> set[str]:
    return set(get_user_roles(user))


def _require_branch_write(user: User, branch_id: int, db: Session) -> None:
    if not any(r in _roles(user) for r in BRANCH_WRITE_ROLES):
        raise AppError(status_code=403, error_code="shift_ops.forbidden", message="Access denied", detail={})
    if not can_access_branch(user, branch_id, db):
        raise AppError(status_code=403, error_code="shift_ops.cross_branch_forbidden", message="Access denied for this branch", detail={"branch_id": branch_id})


def _require_branch_read(user: User, branch_id: int, db: Session) -> None:
    if not (_roles(user) & BRANCH_READ_ROLES):
        raise AppError(status_code=403, error_code="shift_ops.forbidden", message="Access denied", detail={})
    if not can_access_branch(user, branch_id, db):
        raise AppError(status_code=403, error_code="shift_ops.cross_branch_forbidden", message="Access denied for this branch", detail={"branch_id": branch_id})


def _require_override_role(user: User) -> None:
    if not _roles(user) & OVERRIDE_ROLES:
        raise AppError(status_code=403, error_code="shift_ops.override_forbidden", message="Override not permitted for this role", detail={})


def _require_reopen_role(user: User, db: Session, branch_id: int) -> None:
    if not _roles(user) & REOPEN_ROLES:
        raise AppError(status_code=403, error_code="shift_ops.reopen_forbidden", message="Reopen not permitted for this role", detail={})
    if not can_access_branch(user, branch_id, db):
        raise AppError(status_code=403, error_code="shift_ops.cross_branch_forbidden", message="Access denied for this branch", detail={"branch_id": branch_id})


def _get_shift(db: Session, shift_id: int) -> BranchShift:
    shift = (
        db.query(BranchShift)
        .options(
            joinedload(BranchShift.count).joinedload(BranchShiftCount.lines),
            joinedload(BranchShift.cash),
            joinedload(BranchShift.reopen_events),
        )
        .filter(BranchShift.id == shift_id)
        .first()
    )
    if not shift:
        raise AppError(status_code=404, error_code="shift_ops.not_found", message="Shift not found", detail={"shift_id": shift_id})
    return shift


def _shift_closed_at(shift: BranchShift) -> Optional[datetime]:
    if shift.status == BranchShiftStatus.submitted.value:
        times = []
        if shift.count and shift.count.submitted_at:
            times.append(shift.count.submitted_at)
        if shift.cash and shift.cash.submitted_at:
            times.append(shift.cash.submitted_at)
        return max(times) if times else shift.submitted_at
    if shift.status == BranchShiftStatus.exception_locked.value:
        return shift.exception_at
    return None


def _count_status(shift: BranchShift) -> Optional[str]:
    return shift.count.status if shift.count else None


def _cash_status(shift: BranchShift) -> Optional[str]:
    return shift.cash.status if shift.cash else None


def _is_partial(shift: BranchShift) -> bool:
    cs, ks = _count_status(shift), _cash_status(shift)
    if shift.status == BranchShiftStatus.exception_locked.value:
        return False
    if not settings.SHIFT_CASH_ENABLED:
        return False
    submitted_parts = sum(1 for s in (cs, ks) if s == ShiftSectionStatus.submitted.value)
    return submitted_parts == 1


def available_shift_numbers(db: Session, branch_id: int, on_date: date) -> list[int]:
    """Active shift numbers configured for a branch on a given date.

    Respects effective_from / effective_to so historical shifts are read with the
    configuration that applied at the time, not today's.
    """
    rows = (
        db.query(BranchShiftConfig.shift_number)
        .filter(
            BranchShiftConfig.branch_id == branch_id,
            BranchShiftConfig.is_active.is_(True),
            BranchShiftConfig.effective_from <= on_date,
            or_(
                BranchShiftConfig.effective_to.is_(None),
                BranchShiftConfig.effective_to >= on_date,
            ),
        )
        .distinct()
        .all()
    )
    return sorted({int(r[0]) for r in rows})


def _branch_names_by_id(db: Session, branch_ids: set[int]) -> dict[int, dict[str, str]]:
    if not branch_ids:
        return {}
    rows = db.query(Branch.id, Branch.branch_name).filter(Branch.id.in_(branch_ids)).all()
    return {
        bid: {"branch_name": name, "branch_name_ar": name}
        for bid, name in rows
    }


def _serialize_shift_summary(
    shift: BranchShift,
    db: Optional[Session] = None,
    *,
    branch_names: Optional[dict[int, dict[str, str]]] = None,
) -> dict[str, Any]:
    payload = {
        "id": shift.id,
        "branch_id": shift.branch_id,
        "shift_date": shift.shift_date.isoformat(),
        "shift_number": shift.shift_number,
        "status": shift.status,
        "count_status": _count_status(shift),
        "cash_status": _cash_status(shift),
        "is_partial": _is_partial(shift),
        "exception_type": shift.exception_type,
        "exception_reason": shift.exception_reason,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
        "submitted_at": shift.submitted_at.isoformat() if shift.submitted_at else None,
    }
    if branch_names and shift.branch_id in branch_names:
        info = branch_names[shift.branch_id]
        payload["branch_name"] = info["branch_name"]
        payload["branch_name_ar"] = info["branch_name_ar"]
    elif db is not None and shift.branch_id:
        row = db.query(Branch.branch_name).filter(Branch.id == shift.branch_id).first()
        if row:
            payload["branch_name"] = row[0]
            payload["branch_name_ar"] = row[0]
    if db is not None:
        payload["available_shift_numbers"] = available_shift_numbers(db, shift.branch_id, shift.shift_date)
    return payload


def _find_open_previous(db: Session, branch_id: int, before_date: date, before_shift_number: int) -> Optional[BranchShift]:
    return (
        db.query(BranchShift)
        .filter(
            BranchShift.branch_id == branch_id,
            BranchShift.status.notin_(
                [BranchShiftStatus.submitted.value, BranchShiftStatus.exception_locked.value]
            ),
            or_(
                BranchShift.shift_date < before_date,
                and_(BranchShift.shift_date == before_date, BranchShift.shift_number < before_shift_number),
            ),
        )
        .order_by(BranchShift.shift_date.desc(), BranchShift.shift_number.desc())
        .first()
    )


def _lock_previous_as_stuck(db: Session, previous: BranchShift, user: User, reason: str) -> None:
    previous.status = BranchShiftStatus.exception_locked.value
    previous.exception_type = BranchShiftExceptionType.stuck_previous.value
    previous.exception_reason = reason[:300]
    previous.exception_by = user.id
    previous.exception_at = utcnow_aware().replace(tzinfo=None)


def _maybe_complete_shift(db: Session, shift: BranchShift) -> None:
    if shift.status == BranchShiftStatus.exception_locked.value:
        return
    cs, ks = _count_status(shift), _cash_status(shift)
    cash_done = (ks == ShiftSectionStatus.submitted.value) if settings.SHIFT_CASH_ENABLED else True
    if cs == ShiftSectionStatus.submitted.value and cash_done:
        shift.status = BranchShiftStatus.submitted.value
        times = []
        if shift.count and shift.count.submitted_at:
            times.append(shift.count.submitted_at)
        if settings.SHIFT_CASH_ENABLED and shift.cash and shift.cash.submitted_at:
            times.append(shift.cash.submitted_at)
        shift.submitted_at = max(times) if times else utcnow_aware().replace(tzinfo=None)


def _ranges_overlap(
    a_from: date,
    a_to: Optional[date],
    b_from: date,
    b_to: Optional[date],
) -> bool:
    a_end = a_to or date.max
    b_end = b_to or date.max
    return a_from <= b_end and b_from <= a_end


def validate_config_no_overlap(
    db: Session,
    *,
    branch_id: int,
    shift_number: int,
    effective_from: date,
    effective_to: Optional[date],
    exclude_id: Optional[int] = None,
) -> None:
    q = db.query(BranchShiftConfig).filter(
        BranchShiftConfig.branch_id == branch_id,
        BranchShiftConfig.shift_number == shift_number,
    )
    if exclude_id:
        q = q.filter(BranchShiftConfig.id != exclude_id)
    for row in q.all():
        if _ranges_overlap(row.effective_from, row.effective_to, effective_from, effective_to):
            raise AppError(
                status_code=409,
                error_code="shift_ops.config_overlap",
                message="Shift config date ranges overlap",
                detail={"existing_id": row.id},
            )


def open_shift(
    db: Session,
    user: User,
    *,
    branch_id: Optional[int],
    shift_date: date,
    shift_number: int,
    override: bool = False,
    override_reason: Optional[str] = None,
) -> BranchShift:
    effective_branch = branch_id or user.branch_id
    if not effective_branch:
        raise AppError(status_code=400, error_code="shift_ops.branch_missing", message="Branch is required", detail={})
    if override:
        _require_override_role(user)
    else:
        _require_branch_write(user, effective_branch, db)

    existing = (
        db.query(BranchShift)
        .filter_by(branch_id=effective_branch, shift_date=shift_date, shift_number=shift_number)
        .first()
    )
    if existing:
        raise AppError(status_code=409, error_code="shift_ops.already_exists", message="Shift already exists", detail={"shift_id": existing.id})

    previous = _find_open_previous(db, effective_branch, shift_date, shift_number)
    if previous:
        if not override:
            raise AppError(
                status_code=409,
                error_code="PREVIOUS_SHIFT_NOT_CLOSED",
                message="Previous shift is not closed",
                detail={"previous_shift_id": previous.id},
            )
        _require_override_role(user)
        reason = (override_reason or "").strip()
        if len(reason) < 5:
            raise AppError(status_code=422, error_code="shift_ops.override_reason_required", message="Override reason required (5-300 chars)", detail={})
        _lock_previous_as_stuck(db, previous, user, reason)

    shift = BranchShift(
        branch_id=effective_branch,
        shift_date=shift_date,
        shift_number=shift_number,
        status=BranchShiftStatus.draft.value,
        opened_by=user.id,
        opened_at=utcnow_aware().replace(tzinfo=None),
    )
    db.add(shift)
    db.flush()
    return shift


def close_no_activity(
    db: Session,
    user: User,
    shift_id: int,
    *,
    exception_type: str,
    reason: str,
) -> BranchShift:
    shift = _get_shift(db, shift_id)
    _require_override_role(user)
    if not can_access_branch(user, shift.branch_id, db):
        raise AppError(status_code=403, error_code="shift_ops.cross_branch_forbidden", message="Access denied", detail={})

    if exception_type not in (
        BranchShiftExceptionType.branch_closed.value,
        BranchShiftExceptionType.manual_gap.value,
    ):
        raise AppError(status_code=422, error_code="shift_ops.invalid_exception_type", message="Invalid exception_type", detail={})

    cleaned = reason.strip()
    if len(cleaned) < 5:
        raise AppError(status_code=422, error_code="shift_ops.reason_required", message="Reason required (5-300 chars)", detail={})

    shift.status = BranchShiftStatus.exception_locked.value
    shift.exception_type = exception_type
    shift.exception_reason = cleaned[:300]
    shift.exception_by = user.id
    shift.exception_at = utcnow_aware().replace(tzinfo=None)
    db.flush()
    return shift


def _brand_ids_for_branch(db: Session, branch_id: int) -> list[int]:
    return [row.brand_id for row in db.query(BranchBrand).filter(BranchBrand.branch_id == branch_id).all()]


def _frozen_item_ids(db: Session, branch_id: int) -> list[tuple[int, str, str, int]]:
    brand_ids = _brand_ids_for_branch(db, branch_id)
    if not brand_ids:
        return []
    excluded = {
        row.item_id
        for row in db.query(BranchShiftCountExclusion).filter(BranchShiftCountExclusion.branch_id == branch_id).all()
    }
    rows = (
        db.query(BrandShiftCountItem, Item)
        .join(Item, Item.id == BrandShiftCountItem.item_id)
        .options(joinedload(Item.unit))
        .filter(
            BrandShiftCountItem.brand_id.in_(brand_ids),
            BrandShiftCountItem.is_active == True,
            Item.active == True,
            Item.is_deleted == False,
        )
        .order_by(BrandShiftCountItem.display_order, BrandShiftCountItem.id)
        .all()
    )
    seen: set[int] = set()
    result: list[tuple[int, str, str, int]] = []
    for cfg, item in rows:
        if item.id in excluded or item.id in seen:
            continue
        seen.add(item.id)
        unit_name = item.unit.name_ar if item.unit else ""
        result.append((item.id, item.item_name_ar, unit_name, cfg.display_order))
    return result


def _opening_for_item(db: Session, branch_id: int, item_id: int, current_shift: BranchShift) -> Decimal:
    prior_lines = (
        db.query(BranchShiftCountLine, BranchShift)
        .join(BranchShiftCount, BranchShiftCount.id == BranchShiftCountLine.count_id)
        .join(BranchShift, BranchShift.id == BranchShiftCount.shift_id)
        .filter(
            BranchShift.branch_id == branch_id,
            BranchShiftCountLine.item_id == item_id,
            BranchShiftCount.status == ShiftSectionStatus.submitted.value,
            or_(
                BranchShift.shift_date < current_shift.shift_date,
                and_(
                    BranchShift.shift_date == current_shift.shift_date,
                    BranchShift.shift_number < current_shift.shift_number,
                ),
            ),
        )
        .order_by(BranchShift.shift_date.desc(), BranchShift.shift_number.desc())
        .all()
    )
    for line, shift in prior_lines:
        if shift.status == BranchShiftStatus.exception_locked.value:
            continue
        if line.closing_balance is not None:
            return Decimal(str(line.closing_balance))
    return Decimal("0")


def create_or_get_count(db: Session, user: User, shift_id: int) -> tuple[BranchShiftCount, bool]:
    shift = _get_shift(db, shift_id)
    _require_branch_write(user, shift.branch_id, db)

    if shift.count:
        return shift.count, False

    frozen_at = utcnow_aware().replace(tzinfo=None)
    count = BranchShiftCount(
        shift_id=shift.id,
        status=ShiftSectionStatus.draft.value,
        items_frozen_at=frozen_at,
        created_by=user.id,
    )
    try:
        with db.begin_nested():
            db.add(count)
            db.flush()
    except IntegrityError:
        # Another request won the unique shift_id race between the relationship
        # check and insert. Keep the outer transaction alive and return the winner.
        db.expire_all()
        winner = db.query(BranchShiftCount).filter_by(shift_id=shift.id).first()
        if winner is None:
            raise
        return winner, False

    for item_id, name, unit, _order in _frozen_item_ids(db, shift.branch_id):
        opening = _opening_for_item(db, shift.branch_id, item_id, shift)
        db.add(
            BranchShiftCountLine(
                count_id=count.id,
                item_id=item_id,
                item_name_snapshot=name,
                unit_snapshot=unit,
                opening_balance=opening,
                row_status=ShiftCountRowStatus.incomplete.value,
            )
        )
    db.flush()
    db.refresh(count)
    return count, True


def patch_count_lines(db: Session, user: User, shift_id: int, lines: list[dict[str, Any]]) -> BranchShiftCount:
    shift = _get_shift(db, shift_id)
    _require_branch_write(user, shift.branch_id, db)
    count = shift.count
    if not count:
        raise AppError(status_code=404, error_code="shift_ops.count_not_found", message="Count not created yet", detail={})
    if count.status == ShiftSectionStatus.submitted.value:
        raise AppError(status_code=409, error_code="shift_ops.count_already_submitted", message="Count already submitted", detail={})

    by_item = {line.item_id: line for line in count.lines}
    for payload in lines:
        item_id = payload["item_id"]
        line = by_item.get(item_id)
        if not line:
            raise AppError(status_code=409, error_code="SHIFT_COUNT_FOREIGN_ITEM", message="Item not in frozen count list", detail={"item_id": item_id})

        opening = Decimal(str(line.opening_balance))
        received = payload.get("received_qty")
        returned = payload.get("returned_qty")
        damaged = payload.get("damaged_qty")
        closing = payload.get("closing_balance")
        reason = payload.get("movement_exception_reason")

        neg = [n for n, v in [("received_qty", received), ("returned_qty", returned), ("damaged_qty", damaged), ("closing_balance", closing)] if v is not None and Decimal(str(v)) < 0]
        if neg:
            raise AppError(status_code=422, error_code="shift_ops.negative_qty", message="Quantities must be non-negative", detail={"fields": neg})

        eval_result = evaluate_count_line(
            opening_balance=opening,
            received_qty=Decimal(str(received)) if received is not None else None,
            returned_qty=Decimal(str(returned)) if returned is not None else None,
            damaged_qty=Decimal(str(damaged)) if damaged is not None else None,
            closing_balance=Decimal(str(closing)) if closing is not None else None,
            movement_exception_reason=reason,
        )
        if eval_result.get("error_code") == "MOVEMENT_EXCEPTION_REASON_REQUIRED":
            raise AppError(status_code=422, error_code="MOVEMENT_EXCEPTION_REASON_REQUIRED", message="Movement exception reason required", detail={"item_id": item_id})

        line.received_qty = received
        line.returned_qty = returned
        line.damaged_qty = damaged
        line.closing_balance = closing
        line.movement_exception_reason = reason
        line.item_notes = payload.get("item_notes")
        line.movement_diff = eval_result.get("movement_diff")
        line.row_status = eval_result["row_status"]

    count.updated_by = user.id
    db.flush()
    return count


def submit_count(db: Session, user: User, shift_id: int) -> BranchShiftCount:
    shift = _get_shift(db, shift_id)
    _require_branch_write(user, shift.branch_id, db)
    count = shift.count
    if not count:
        raise AppError(status_code=404, error_code="shift_ops.count_not_found", message="Count not created yet", detail={})
    if count.status == ShiftSectionStatus.submitted.value:
        return count

    invalid = [l for l in count.lines if l.row_status != ShiftCountRowStatus.valid.value]
    if invalid:
        raise AppError(status_code=409, error_code="SHIFT_COUNT_INCOMPLETE", message="All count lines must be valid before submit", detail={"invalid_lines": len(invalid)})

    now = utcnow_aware().replace(tzinfo=None)
    count.status = ShiftSectionStatus.submitted.value
    count.submitted_by = user.id
    count.submitted_at = now
    _maybe_complete_shift(db, shift)
    db.flush()
    return count


def get_or_create_cash_draft(db: Session, user: User, shift_id: int) -> BranchShiftCash:
    shift = _get_shift(db, shift_id)
    _require_branch_write(user, shift.branch_id, db)
    if shift.cash:
        return shift.cash
    cash = BranchShiftCash(shift_id=shift.id, created_by=user.id)
    db.add(cash)
    db.flush()
    return cash


def save_cash(db: Session, user: User, shift_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    shift = _get_shift(db, shift_id)
    _require_branch_write(user, shift.branch_id, db)
    cash = get_or_create_cash_draft(db, user, shift_id)
    if cash.status == ShiftSectionStatus.submitted.value:
        raise AppError(status_code=409, error_code="shift_ops.cash_already_submitted", message="Cash already submitted", detail={})

    for field in (
        "total_sale", "bill_count", "mada_sales", "cash_sales", "app_sales",
        "refund_bill", "exchange_amount", "expiry_amount", "cash_expense",
        "cash_float_carried_forward", "cash_deposited", "expense_type",
        "expense_details", "shift_notes", "cash_variance_reason",
    ):
        if field in payload:
            setattr(cash, field, payload[field])

    merged_payload = {
        "total_sale": cash.total_sale,
        "bill_count": cash.bill_count,
        "mada_sales": cash.mada_sales,
        "cash_sales": cash.cash_sales,
        "app_sales": cash.app_sales,
        "refund_bill": cash.refund_bill,
        "exchange_amount": cash.exchange_amount,
        "expiry_amount": cash.expiry_amount,
        "cash_expense": cash.cash_expense,
        "cash_float_carried_forward": cash.cash_float_carried_forward,
        "cash_deposited": cash.cash_deposited,
        "expense_type": cash.expense_type,
        "expense_details": cash.expense_details,
        "cash_variance_reason": cash.cash_variance_reason,
    }
    result = validate_cash_payload(merged_payload)

    cash.cash_variance = result["cash_variance"]
    cash.updated_by = user.id
    db.flush()
    out = _serialize_cash(cash)
    out["expected_deposited"] = f"{result['expected_deposited']:.2f}"
    out["informational_fields"] = result["informational_fields"]
    out["validation_errors"] = result["errors"]
    return out


def submit_cash(db: Session, user: User, shift_id: int) -> dict[str, Any]:
    shift = _get_shift(db, shift_id)
    _require_branch_write(user, shift.branch_id, db)
    cash = shift.cash
    if not cash:
        raise AppError(status_code=404, error_code="shift_ops.cash_not_found", message="Cash record not found", detail={})
    if cash.status == ShiftSectionStatus.submitted.value:
        return _serialize_cash(cash)

    payload = {
        "total_sale": cash.total_sale,
        "bill_count": cash.bill_count,
        "mada_sales": cash.mada_sales,
        "cash_sales": cash.cash_sales,
        "app_sales": cash.app_sales,
        "refund_bill": cash.refund_bill,
        "exchange_amount": cash.exchange_amount,
        "expiry_amount": cash.expiry_amount,
        "cash_expense": cash.cash_expense,
        "cash_float_carried_forward": cash.cash_float_carried_forward,
        "cash_deposited": cash.cash_deposited,
        "expense_type": cash.expense_type,
        "expense_details": cash.expense_details,
        "cash_variance_reason": cash.cash_variance_reason,
    }
    result = validate_cash_payload(payload)
    if result["errors"]:
        raise AppError(status_code=422, error_code=result["errors"][0]["code"], message="Cash validation failed", detail={"errors": result["errors"]})

    now = utcnow_aware().replace(tzinfo=None)
    cash.status = ShiftSectionStatus.submitted.value
    cash.submitted_by = user.id
    cash.submitted_at = now
    cash.cash_variance = result["cash_variance"]
    _maybe_complete_shift(db, shift)
    db.flush()
    return _serialize_cash(cash)


def _money_str(value) -> Optional[str]:
    if value is None:
        return None
    return f"{Decimal(str(value)):.2f}"


def _serialize_cash(cash: BranchShiftCash) -> dict[str, Any]:
    return {
        "id": cash.id,
        "shift_id": cash.shift_id,
        "status": cash.status,
        "total_sale": _money_str(cash.total_sale),
        "bill_count": cash.bill_count,
        "mada_sales": _money_str(cash.mada_sales),
        "cash_sales": _money_str(cash.cash_sales),
        "app_sales": _money_str(cash.app_sales),
        "refund_bill": _money_str(cash.refund_bill),
        "exchange_amount": _money_str(cash.exchange_amount),
        "expiry_amount": _money_str(cash.expiry_amount),
        "cash_expense": _money_str(cash.cash_expense),
        "cash_float_carried_forward": _money_str(cash.cash_float_carried_forward),
        "cash_deposited": _money_str(cash.cash_deposited),
        "expense_type": cash.expense_type,
        "expense_details": cash.expense_details,
        "shift_notes": cash.shift_notes,
        "cash_variance": _money_str(cash.cash_variance),
        "cash_variance_reason": cash.cash_variance_reason,
        "submitted_by": cash.submitted_by,
        "submitted_at": cash.submitted_at.isoformat() if cash.submitted_at else None,
        "informational_fields": {
            "refund_bill": _money_str(cash.refund_bill),
            "exchange_amount": _money_str(cash.exchange_amount),
            "expiry_amount": _money_str(cash.expiry_amount),
            "informational": True,
        },
    }


def _serialize_count(count: BranchShiftCount, db: Optional[Session] = None) -> dict[str, Any]:
    # Membership is frozen at count creation; order must stay at creation order (line.id),
    # not the live brand_shift_count_items display_order map.
    lines = sorted(count.lines, key=lambda ln: ln.id)

    serialized_lines = []
    for idx, line in enumerate(lines, start=1):
        entry: dict[str, Any] = {
            "id": line.id,
            "item_id": line.item_id,
            "item_name_snapshot": line.item_name_snapshot,
            "unit_snapshot": line.unit_snapshot,
            "opening_balance": str(line.opening_balance),
            "received_qty": str(line.received_qty) if line.received_qty is not None else None,
            "returned_qty": str(line.returned_qty) if line.returned_qty is not None else None,
            "damaged_qty": str(line.damaged_qty) if line.damaged_qty is not None else None,
            "closing_balance": str(line.closing_balance) if line.closing_balance is not None else None,
            "movement_diff": str(line.movement_diff) if line.movement_diff is not None else None,
            "movement_exception_reason": line.movement_exception_reason,
            "item_notes": line.item_notes,
            "row_status": line.row_status,
            "display_order": idx,
        }
        serialized_lines.append(entry)

    return {
        "id": count.id,
        "shift_id": count.shift_id,
        "status": count.status,
        "items_frozen_at": count.items_frozen_at.isoformat() if count.items_frozen_at else None,
        "general_notes": count.general_notes,
        "lines": serialized_lines,
    }


def reopen_shift(
    db: Session,
    user: User,
    shift_id: int,
    *,
    target: str,
    reason: str,
    admin_override: bool = False,
    ip_address: Optional[str] = None,
) -> BranchShift:
    shift = _get_shift(db, shift_id)
    _require_reopen_role(user, db, shift.branch_id)

    cleaned = reason.strip()
    if len(cleaned) < 5:
        raise AppError(status_code=422, error_code="REOPEN_REASON_REQUIRED", message="Reopen reason required", detail={})

    if target not in (ShiftReopenTarget.count.value, ShiftReopenTarget.cash.value, ShiftReopenTarget.both.value):
        raise AppError(status_code=422, error_code="shift_ops.invalid_reopen_target", message="Invalid reopen target", detail={})

    closed_at = _shift_closed_at(shift)
    if not closed_at:
        raise AppError(status_code=409, error_code="NOT_SUBMITTED", message="Shift is not in a closed state", detail={})

    event_count = db.query(BranchShiftReopenEvent).filter(BranchShiftReopenEvent.shift_id == shift.id).count()
    window_expired = utcnow_aware().replace(tzinfo=None) > closed_at + timedelta(hours=REOPEN_WINDOW_HOURS)
    limit_reached = event_count >= REOPEN_LIMIT
    is_admin = _roles(user) & {"admin", "super_admin"}

    if (window_expired or limit_reached) and not (admin_override and is_admin):
        if limit_reached:
            raise AppError(status_code=409, error_code="REOPEN_LIMIT_REACHED", message="Reopen limit reached", detail={})
        raise AppError(status_code=409, error_code="REOPEN_WINDOW_EXPIRED", message="Reopen window expired", detail={})

    if target in (ShiftReopenTarget.count.value, ShiftReopenTarget.both.value):
        if not shift.count or shift.count.status != ShiftSectionStatus.submitted.value:
            raise AppError(status_code=409, error_code="NOT_SUBMITTED", message="Count is not submitted", detail={})
        shift.count.status = ShiftSectionStatus.draft.value
        shift.status = BranchShiftStatus.draft.value
        shift.submitted_at = None

    if target in (ShiftReopenTarget.cash.value, ShiftReopenTarget.both.value):
        if not shift.cash or shift.cash.status != ShiftSectionStatus.submitted.value:
            raise AppError(status_code=409, error_code="NOT_SUBMITTED", message="Cash is not submitted", detail={})
        shift.cash.status = ShiftSectionStatus.draft.value
        shift.status = BranchShiftStatus.draft.value
        shift.submitted_at = None

    event = BranchShiftReopenEvent(
        shift_id=shift.id,
        target=target,
        reason=cleaned[:300],
        reopened_by=user.id,
        reopened_at=utcnow_aware().replace(tzinfo=None),
    )
    db.add(event)
    audit_service.log(
        db,
        user_id=user.id,
        action="shift_reopened",
        module="shift_ops",
        entity_type="branch_shift",
        entity_id=shift.id,
        new_values={"target": target, "reason": cleaned[:300]},
        ip_address=ip_address,
    )
    db.flush()
    return shift


def list_shifts(
    db: Session,
    user: User,
    *,
    branch_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    partial_only: bool = False,
    exception_only: bool = False,
) -> list[dict[str, Any]]:
    q = db.query(BranchShift).options(joinedload(BranchShift.count), joinedload(BranchShift.cash))
    if branch_id:
        if not can_access_branch(user, branch_id, db):
            raise AppError(status_code=403, error_code="shift_ops.forbidden", message="Access denied", detail={})
        q = q.filter(BranchShift.branch_id == branch_id)
    else:
        if _roles(user) & {"branch_manager"}:
            if not user.branch_id:
                return []
            q = q.filter(BranchShift.branch_id == user.branch_id)
        elif "area_manager" in _roles(user):
            from app.core.area_manager_scope import get_area_manager_branch_ids

            ids = get_area_manager_branch_ids(user, db)
            if not ids:
                return []
            q = q.filter(BranchShift.branch_id.in_(ids))

    if date_from:
        q = q.filter(BranchShift.shift_date >= date_from)
    if date_to:
        q = q.filter(BranchShift.shift_date <= date_to)
    if exception_only:
        q = q.filter(BranchShift.status == BranchShiftStatus.exception_locked.value)

    rows = q.order_by(BranchShift.shift_date.desc(), BranchShift.shift_number.desc()).all()
    branch_names = _branch_names_by_id(db, {s.branch_id for s in rows})
    items = [_serialize_shift_summary(s, db, branch_names=branch_names) for s in rows]
    if partial_only:
        items = [i for i in items if i["is_partial"]]
    return items


def _chain_gap_for_shift(db: Session, shift: BranchShift) -> Optional[dict[str, Any]]:
    skipped = (
        db.query(BranchShift)
        .filter(
            BranchShift.branch_id == shift.branch_id,
            BranchShift.status == BranchShiftStatus.exception_locked.value,
            or_(
                BranchShift.shift_date < shift.shift_date,
                and_(BranchShift.shift_date == shift.shift_date, BranchShift.shift_number < shift.shift_number),
            ),
        )
        .order_by(BranchShift.shift_date.desc(), BranchShift.shift_number.desc())
        .first()
    )
    if not skipped:
        return None
    count_submitted = skipped.count and skipped.count.status == ShiftSectionStatus.submitted.value
    if count_submitted:
        return None
    return {
        "skipped_shift_id": skipped.id,
        "skipped_shift_date": skipped.shift_date.isoformat(),
        "skipped_shift_number": skipped.shift_number,
        "skipped_reason": skipped.exception_reason,
        "skipped_exception_type": skipped.exception_type,
    }


def build_shift_report(db: Session, user: User, **filters: Any) -> list[dict[str, Any]]:
    read_roles = {"internal_auditor", "admin", "super_admin", "operations_manager", "area_manager"}
    if not _roles(user) & read_roles:
        raise AppError(status_code=403, error_code="shift_ops.report_forbidden", message="Report access denied", detail={})

    shifts = list_shifts(
        db,
        user,
        branch_id=filters.get("branch_id"),
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
        partial_only=filters.get("partial_only", False),
        exception_only=filters.get("exception_only", False),
    )

    out: list[dict[str, Any]] = []
    for summary in shifts:
        shift = _get_shift(db, summary["id"])
        movement_total = Decimal("0")
        negative_exceptions: list[dict[str, Any]] = []
        damaged_total = Decimal("0")

        if shift.count:
            for line in shift.count.lines:
                if line.damaged_qty:
                    damaged_total += Decimal(str(line.damaged_qty))
                if line.movement_diff is None:
                    continue
                diff = Decimal(str(line.movement_diff))
                if diff < 0:
                    negative_exceptions.append(
                        {
                            "item_id": line.item_id,
                            "item_name_snapshot": line.item_name_snapshot,
                            "movement_diff": str(diff),
                            "reason": line.movement_exception_reason or "",
                        }
                    )
                else:
                    movement_total += diff

        cash_block = _serialize_cash(shift.cash) if shift.cash else None
        reopen_events = [
            {
                "id": e.id,
                "target": e.target,
                "reason": e.reason,
                "reopened_by": e.reopened_by,
                "reopened_at": e.reopened_at.isoformat() if e.reopened_at else None,
            }
            for e in (shift.reopen_events or [])
        ]

        row = {
            **summary,
            "cash": cash_block,
            "movement_diff_total": str(movement_total),
            "negative_movement_exceptions": negative_exceptions,
            "damaged_total": str(damaged_total),
            "reopen_events": reopen_events,
            "chain_gap": _chain_gap_for_shift(db, shift),
            # يميّز الجرد الفارغ عن الجرد الحقيقي. 13 فرعًا (Ronaldos · Shawarma) بلا أصناف عدّ
            # في الإنتاج عند إطلاق 2026-08، فترحّل جردًا بصفر أسطر يبدو في التقرير مطابقًا لجرد
            # مكتمل. بدون هذا الحقل يقرأ المراجع "23 فرعًا رحّلوا الجرد" وهي ليست الحقيقة.
            "count_lines_total": len(shift.count.lines) if shift.count else 0,
            "count_lines_filled": sum(
                1 for l in shift.count.lines if l.row_status == ShiftCountRowStatus.valid.value
            ) if shift.count else 0,
        }

        if filters.get("cash_variance_only") and shift.cash and shift.cash.cash_variance is not None:
            if abs(Decimal(str(shift.cash.cash_variance))) <= Decimal(str(settings.CASH_VARIANCE_TOLERANCE)):
                continue
        if filters.get("reopened_only") and not reopen_events:
            continue
        if filters.get("negative_movement_only") and not negative_exceptions:
            continue

        out.append(row)
    return out
