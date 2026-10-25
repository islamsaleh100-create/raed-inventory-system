"""POS terminal registry — internal audit only."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Branch, BranchBrand, Brand
from app.models.pos_terminal import PosTerminal
from app.models.pos_terminal import PosTerminalProvider, PosTerminalStatus
from app.schemas.pos_terminal import PosTerminalCreate, PosTerminalUpdate
from app.services import audit_service
from app.services.pos_terminal_utils import normalize_terminal_text

_AUDIT_FIELDS = ("provider", "terminal_number", "serial_number", "branch_id", "status", "notes")


def _brand_names(db: Session, branch_id: int) -> list[str]:
    rows = (
        db.query(Brand.name)
        .join(BranchBrand, BranchBrand.brand_id == Brand.id)
        .filter(BranchBrand.branch_id == branch_id)
        .order_by(Brand.name)
        .all()
    )
    return [r[0] for r in rows if r[0]]


def _snapshot(row: PosTerminal) -> dict[str, Any]:
    return {k: getattr(row, k) for k in _AUDIT_FIELDS}


def serialize_terminal(db: Session, row: PosTerminal) -> dict[str, Any]:
    branch = db.query(Branch).filter(Branch.id == row.branch_id).first()
    return {
        "id": row.id,
        "provider": row.provider,
        "terminal_number": row.terminal_number,
        "serial_number": row.serial_number,
        "branch_id": row.branch_id,
        "branch_name": branch.branch_name if branch else None,
        "city": branch.city if branch else None,
        "brand_names": _brand_names(db, row.branch_id),
        "status": row.status,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _get_branch(db: Session, branch_id: int) -> Branch:
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_deleted == False).first()  # noqa: E712
    if not branch:
        raise AppError(
            status_code=422,
            error_code="POS_TERMINAL_BRANCH_NOT_FOUND",
            message="Branch not found",
            detail={"branch_id": branch_id},
        )
    return branch


def _flush_or_raise_duplicate(db: Session, provider: str, terminal_number: str) -> None:
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _duplicate_error(db, provider, terminal_number)


def _reject_null_patch_fields(data: dict[str, Any]) -> None:
    if "provider" in data and data["provider"] is None:
        raise AppError(
            status_code=422,
            error_code="POS_TERMINAL_NULL_PROVIDER",
            message="Provider cannot be null; omit the field or send a valid value.",
            detail={"field": "provider"},
        )
    if "status" in data and data["status"] is None:
        raise AppError(
            status_code=422,
            error_code="POS_TERMINAL_NULL_STATUS",
            message="Status cannot be null; omit the field or send a valid value.",
            detail={"field": "status"},
        )


def _assert_unique(db: Session, provider: str, terminal_number: str, *, exclude_id: Optional[int] = None) -> None:
    q = db.query(PosTerminal).filter(
        PosTerminal.provider == provider,
        PosTerminal.terminal_number == terminal_number,
    )
    if exclude_id is not None:
        q = q.filter(PosTerminal.id != exclude_id)
    if q.first():
        raise _duplicate_error(db, provider, terminal_number)


def _duplicate_error(db: Session, provider: str, terminal_number: str) -> AppError:
    existing = (
        db.query(PosTerminal)
        .filter(PosTerminal.provider == provider, PosTerminal.terminal_number == terminal_number)
        .first()
    )
    detail: dict[str, Any] = {"provider": provider, "terminal_number": terminal_number}
    if existing:
        branch = db.query(Branch).filter(Branch.id == existing.branch_id).first()
        detail["existing_branch_id"] = existing.branch_id
        detail["existing_branch_name"] = branch.branch_name if branch else None
        detail["existing_terminal_id"] = existing.id
    return AppError(
        status_code=409,
        error_code="POS_TERMINAL_DUPLICATE_NUMBER",
        message="This terminal number is already registered for this provider",
        detail=detail,
    )


def list_terminals(
    db: Session,
    *,
    search: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    q = db.query(PosTerminal).join(Branch, Branch.id == PosTerminal.branch_id)
    if provider:
        q = q.filter(PosTerminal.provider == provider)
    if status:
        q = q.filter(PosTerminal.status == status)
    if search:
        norm = normalize_terminal_text(search) or search.strip()
        like = f"%{norm}%"
        q = q.filter(
            or_(
                PosTerminal.terminal_number.ilike(like),
                PosTerminal.serial_number.ilike(like),
                Branch.branch_name.ilike(f"%{search.strip()}%"),
            )
        )
    total = q.count()
    rows = (
        q.order_by(PosTerminal.provider, PosTerminal.terminal_number)
        .offset((page - 1) * page_size)
        .limit(min(page_size, 100))
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialize_terminal(db, r) for r in rows],
    }


def create_terminal(
    db: Session,
    *,
    user_id: int,
    payload: PosTerminalCreate,
    ip_address: Optional[str],
) -> dict[str, Any]:
    _get_branch(db, payload.branch_id)
    terminal_number = normalize_terminal_text(payload.terminal_number)
    if not terminal_number:
        raise AppError(
            status_code=422,
            error_code="POS_TERMINAL_INVALID_NUMBER",
            message="Terminal number is required",
            detail={},
        )
    serial = normalize_terminal_text(payload.serial_number) if payload.serial_number else None
    _assert_unique(db, payload.provider, terminal_number)
    row = PosTerminal(
        provider=payload.provider,
        terminal_number=terminal_number,
        serial_number=serial,
        branch_id=payload.branch_id,
        status=payload.status,
        notes=(payload.notes or "").strip() or None,
    )
    db.add(row)
    _flush_or_raise_duplicate(db, payload.provider, terminal_number)
    audit_service.log(
        db,
        user_id=user_id,
        action="pos_terminal_create",
        module="audit",
        entity_type="pos_terminal",
        entity_id=row.id,
        new_values=_snapshot(row),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(row)
    return serialize_terminal(db, row)


def update_terminal(
    db: Session,
    *,
    user_id: int,
    terminal_id: int,
    payload: PosTerminalUpdate,
    ip_address: Optional[str],
) -> dict[str, Any]:
    row = db.query(PosTerminal).filter(PosTerminal.id == terminal_id).first()
    if not row:
        raise AppError(
            status_code=404,
            error_code="POS_TERMINAL_NOT_FOUND",
            message="POS terminal not found",
            detail={"id": terminal_id},
        )
    old = _snapshot(row)
    data = payload.model_dump(exclude_unset=True)
    _reject_null_patch_fields(data)
    if "branch_id" in data:
        _get_branch(db, data["branch_id"])
    if "terminal_number" in data:
        data["terminal_number"] = normalize_terminal_text(data["terminal_number"])
        if not data["terminal_number"]:
            raise AppError(
                status_code=422,
                error_code="POS_TERMINAL_INVALID_NUMBER",
                message="Terminal number is required",
                detail={},
            )
    if "serial_number" in data:
        data["serial_number"] = normalize_terminal_text(data["serial_number"]) if data["serial_number"] else None
    if "notes" in data:
        data["notes"] = (data["notes"] or "").strip() or None
    for key, val in data.items():
        setattr(row, key, val)
    _assert_unique(db, row.provider, row.terminal_number, exclude_id=row.id)
    _flush_or_raise_duplicate(db, row.provider, row.terminal_number)
    audit_service.log(
        db,
        user_id=user_id,
        action="pos_terminal_update",
        module="audit",
        entity_type="pos_terminal",
        entity_id=row.id,
        old_values=old,
        new_values=_snapshot(row),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(row)
    return serialize_terminal(db, row)
