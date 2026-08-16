"""Shift operations API — branch inventory count + cash settlement."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, get_user_roles, require_roles
from app.core.errors import AppError
from app.database import get_db
from app.models import User
from app.schemas import (
    ShiftCloseNoActivityPayload,
    ShiftCountLinesPatchPayload,
    ShiftOpenPayload,
    ShiftOpsCashSavePayload,
    ShiftReopenPayload,
)
from app.services import shift_ops_service as svc

router = APIRouter(prefix="/api/v1/shift-ops", tags=["Shift Operations"])


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
def open_shift(
    payload: ShiftOpenPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    roles = set(get_user_roles(current_user))
    if payload.override:
        if not roles & {"area_manager", "operations_manager", "admin", "super_admin"}:
            raise AppError(status_code=403, error_code="shift_ops.override_forbidden", message="Override not permitted for this role", detail={})
    elif not roles & {"branch_user", "branch_manager"}:
        raise AppError(status_code=403, error_code="shift_ops.forbidden", message="Access denied", detail={})

    if payload.override:
        effective_branch = payload.branch_id
        if not effective_branch:
            raise AppError(status_code=400, error_code="shift_ops.branch_missing", message="branch_id required for override open", detail={})
        if "area_manager" in roles and not (
            roles & {"operations_manager", "admin", "super_admin"}
        ):
            from app.core.auth import can_access_branch

            if not can_access_branch(current_user, effective_branch, db):
                raise AppError(status_code=403, error_code="shift_ops.cross_branch_forbidden", message="Access denied for this branch", detail={})

    shift = svc.open_shift(
        db,
        current_user,
        branch_id=payload.branch_id or current_user.branch_id,
        shift_date=payload.shift_date,
        shift_number=payload.shift_number,
        override=payload.override,
        override_reason=payload.override_reason,
    )
    db.commit()
    return svc._serialize_shift_summary(shift, db)


@router.get("/shifts")
def list_shifts(
    branch_id: Optional[int] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    partial_only: bool = Query(default=False),
    exception_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    items = svc.list_shifts(
        db,
        current_user,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
        partial_only=partial_only,
        exception_only=exception_only,
    )
    # يُرسَل على مستوى الرد لا داخل العناصر: الفرع الذي لم يفتح شفتًا قط ليس له عنصر
    # يحمل الحقل، فتُقفل شاشة الفتح ولا يستطيع فتح أول شفت إطلاقًا. وأخذه من أول عنصر
    # يعطي الأدمن أرقام شفتات فرع آخر. المصدر هنا هو الفرع المطلوب صراحةً.
    scope_branch = branch_id or current_user.branch_id
    available = (
        svc.available_shift_numbers(db, scope_branch, date_to or date.today())
        if scope_branch else []
    )
    return {
        "total": len(items),
        "items": items,
        "available_shift_numbers": available,
    }


@router.get("/shifts/{shift_id}")
def get_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.core.auth import can_access_branch

    shift = svc._get_shift(db, shift_id)
    if not can_access_branch(current_user, shift.branch_id, db):
        raise AppError(status_code=403, error_code="shift_ops.forbidden", message="Access denied", detail={})
    return svc._serialize_shift_summary(shift, db)


@router.post("/shifts/{shift_id}/reopen")
def reopen_shift(
    shift_id: int,
    payload: ShiftReopenPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("area_manager", "operations_manager", "admin", "super_admin")),
):
    shift = svc.reopen_shift(
        db,
        current_user,
        shift_id,
        target=payload.target,
        reason=payload.reason,
        admin_override=payload.admin_override,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return svc._serialize_shift_summary(shift, db)


@router.post("/shifts/{shift_id}/close-no-activity")
def close_no_activity(
    shift_id: int,
    payload: ShiftCloseNoActivityPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("area_manager", "operations_manager", "admin", "super_admin")),
):
    shift = svc.close_no_activity(
        db,
        current_user,
        shift_id,
        exception_type=payload.exception_type,
        reason=payload.reason,
    )
    db.commit()
    return svc._serialize_shift_summary(shift, db)


@router.post("/shifts/{shift_id}/count")
def create_or_get_count(
    shift_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager")),
):
    count, created = svc.create_or_get_count(db, current_user, shift_id)
    db.commit()
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return svc._serialize_count(count)


@router.get("/shifts/{shift_id}/count")
def get_count(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager")),
):
    shift = svc._get_shift(db, shift_id)
    svc._require_branch_write(current_user, shift.branch_id, db)
    if not shift.count:
        raise AppError(status_code=404, error_code="shift_ops.count_not_found", message="Count not created yet", detail={})
    return svc._serialize_count(shift.count)


@router.patch("/shifts/{shift_id}/count/lines")
def patch_count_lines(
    shift_id: int,
    payload: ShiftCountLinesPatchPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager")),
):
    count = svc.patch_count_lines(db, current_user, shift_id, [line.model_dump() for line in payload.lines])
    db.commit()
    return svc._serialize_count(count)


@router.post("/shifts/{shift_id}/count/submit")
def submit_count(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager")),
):
    count = svc.submit_count(db, current_user, shift_id)
    db.commit()
    return svc._serialize_count(count)


@router.get("/shifts/{shift_id}/cash")
def get_cash(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager")),
):
    shift = svc._get_shift(db, shift_id)
    svc._require_branch_write(current_user, shift.branch_id, db)
    if not shift.cash:
        raise AppError(status_code=404, error_code="shift_ops.cash_not_found", message="Cash record not found", detail={})
    return svc._serialize_cash(shift.cash)


@router.put("/shifts/{shift_id}/cash")
def save_cash(
    shift_id: int,
    payload: ShiftOpsCashSavePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager")),
):
    body = svc.save_cash(db, current_user, shift_id, payload.model_dump(exclude_none=True))
    db.commit()
    return body


@router.post("/shifts/{shift_id}/cash/submit")
def submit_cash(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_user", "branch_manager")),
):
    body = svc.submit_cash(db, current_user, shift_id)
    db.commit()
    return body


@router.get("/reports/shift-operations")
def shift_operations_report(
    branch_id: Optional[int] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    partial_only: bool = Query(default=False),
    exception_only: bool = Query(default=False),
    cash_variance_only: bool = Query(default=False),
    reopened_only: bool = Query(default=False),
    negative_movement_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("internal_auditor", "admin", "super_admin", "operations_manager", "area_manager")
    ),
):
    items = svc.build_shift_report(
        db,
        current_user,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
        partial_only=partial_only,
        exception_only=exception_only,
        cash_variance_only=cash_variance_only,
        reopened_only=reopened_only,
        negative_movement_only=negative_movement_only,
    )
    return {"total": len(items), "items": items}
