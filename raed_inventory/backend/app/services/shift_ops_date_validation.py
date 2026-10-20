"""Shift open date validation (D1–D3). Clock is patchable via ``shift_open_today`` for tests."""
from __future__ import annotations

from datetime import date
from typing import Optional, Set

from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_user_roles
from app.core.errors import AppError
from app.models import User
from app.models.branch_shift_ops import BranchShift

MAX_BACKDATE_DAYS = 7
BACKDATE_ROLES = {"area_manager", "operations_manager", "admin", "super_admin"}


def shift_open_today() -> date:
    """Business today (Asia/Riyadh). Tests monkeypatch this symbol only."""
    from app.core.timezone import today_tz

    return today_tz()


def _server_today_detail(today: date) -> dict[str, str]:
    return {"server_today": today.isoformat()}


def _user_roles(user: User) -> Set[str]:
    return set(get_user_roles(user))


def validate_shift_open_date(
    user: User,
    shift_date: date,
    backdate_reason: Optional[str],
) -> Optional[dict]:
    """D1 + D2. Returns audit payload for backdate when applicable, else None."""
    if not settings.SHIFT_DATE_VALIDATION_ENABLED:
        return None

    today = shift_open_today()
    detail_base = _server_today_detail(today)

    if shift_date > today:
        raise AppError(
            status_code=422,
            error_code="shift_ops.date_in_future",
            message="Shift date cannot be in the future",
            detail={**detail_base, "shift_date": shift_date.isoformat()},
        )

    roles = _user_roles(user)
    age_days = (today - shift_date).days

    if roles & BACKDATE_ROLES:
        if age_days > MAX_BACKDATE_DAYS:
            raise AppError(
                status_code=422,
                error_code="shift_ops.date_beyond_max_backdate",
                message="Shift date is too far in the past",
                detail={
                    **detail_base,
                    "shift_date": shift_date.isoformat(),
                    "max_backdate_days": MAX_BACKDATE_DAYS,
                    "age_days": age_days,
                },
            )
        if shift_date < today:
            reason = (backdate_reason or "").strip()
            if len(reason) < 5:
                raise AppError(
                    status_code=422,
                    error_code="shift_ops.backdate_reason_required",
                    message="Backdate reason required (5-300 chars)",
                    detail={**detail_base, "shift_date": shift_date.isoformat(), "age_days": age_days},
                )
            return {
                "reason": reason[:300],
                "age_days": age_days,
                "shift_date": shift_date.isoformat(),
            }
        return None

    if "branch_manager" in roles or not roles:
        if age_days > 1:
            raise AppError(
                status_code=422,
                error_code="shift_ops.date_too_old",
                message="Branch manager may only open today or yesterday",
                detail={**detail_base, "shift_date": shift_date.isoformat(), "age_days": age_days},
            )
        return None

    raise AppError(
        status_code=422,
        error_code="shift_ops.date_too_old",
        message="Shift date not allowed for this role",
        detail={**detail_base, "shift_date": shift_date.isoformat(), "age_days": age_days},
    )


def validate_shift_chronology(
    db: Session,
    branch_id: int,
    shift_date: date,
    shift_number: int,
) -> None:
    """D3: new tuple must be strictly greater than the latest existing shift."""
    if not settings.SHIFT_DATE_VALIDATION_ENABLED:
        return

    today = shift_open_today()
    latest = (
        db.query(BranchShift)
        .filter(BranchShift.branch_id == branch_id)
        .order_by(BranchShift.shift_date.desc(), BranchShift.shift_number.desc())
        .first()
    )
    if not latest:
        return
    if (shift_date, shift_number) <= (latest.shift_date, latest.shift_number):
        raise AppError(
            status_code=409,
            error_code="shift_ops.date_not_after_latest",
            message="Shift date/number must be after the latest shift for this branch",
            detail={
                **_server_today_detail(today),
                "shift_date": shift_date.isoformat(),
                "shift_number": shift_number,
                "latest_shift_date": latest.shift_date.isoformat(),
                "latest_shift_number": latest.shift_number,
                "latest_shift_id": latest.id,
            },
        )
