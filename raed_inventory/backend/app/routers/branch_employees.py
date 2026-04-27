from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_current_active_user, get_user_roles, require_roles
from app.core.errors import AppError
from app.database import get_db
from app.models import Branch, BranchEmployee, User
from app.schemas import (
    BranchEmployeeCreate,
    BranchEmployeeDeactivatePayload,
    BranchEmployeeUpdate,
)
from app.services import audit_service

router = APIRouter(prefix="/api/v1/branch-employees", tags=["Branch Employees"])


def _is_admin(user: User) -> bool:
    roles = get_user_roles(user)
    return "admin" in roles or "super_admin" in roles


def _require_branch_scope(user: User) -> int:
    if not user.branch_id:
        raise AppError(
            status_code=400,
            error_code="branch_employees.branch_missing",
            message="Current user is not assigned to a branch",
            detail={},
        )
    return user.branch_id


def _serialize(row: BranchEmployee) -> dict:
    return {
        "id": row.id,
        "branch_id": row.branch_id,
        "branch_name": row.branch.branch_name if row.branch else None,
        "full_name": row.full_name,
        "job_title": row.job_title,
        "work_number": row.work_number,
        "phone": row.phone,
        "active": row.active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _get_row(db: Session, employee_id: int) -> BranchEmployee:
    row = (
        db.query(BranchEmployee)
        .options(joinedload(BranchEmployee.branch))
        .filter(BranchEmployee.id == employee_id)
        .first()
    )
    if not row:
        raise AppError(
            status_code=404,
            error_code="branch_employees.not_found",
            message="Branch employee not found",
            detail={},
        )
    return row


def _enforce_access(user: User, branch_id: int) -> None:
    if _is_admin(user):
        return
    if "branch_manager" not in get_user_roles(user):
        raise AppError(
            status_code=403,
            error_code="branch_employees.forbidden",
            message="Access denied",
            detail={},
        )
    if _require_branch_scope(user) != branch_id:
        raise AppError(
            status_code=403,
            error_code="branch_employees.cross_branch_forbidden",
            message="Branch manager can only manage employees in their own branch",
            detail={"branch_id": branch_id},
        )


@router.get("/")
def list_branch_employees(
    branch_id: int | None = Query(default=None),
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_manager", "admin", "super_admin")),
):
    effective_branch_id = branch_id
    if not _is_admin(current_user):
        effective_branch_id = _require_branch_scope(current_user)

    q = db.query(BranchEmployee).options(joinedload(BranchEmployee.branch))
    if effective_branch_id:
        q = q.filter(BranchEmployee.branch_id == effective_branch_id)
    if active_only:
        q = q.filter(BranchEmployee.active == True)

    rows = q.order_by(BranchEmployee.created_at.desc(), BranchEmployee.id.desc()).all()
    return {
        "total": len(rows),
        "items": [_serialize(row) for row in rows],
    }


@router.post("/")
def create_branch_employee(
    payload: BranchEmployeeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_manager", "admin", "super_admin")),
):
    effective_branch_id = payload.branch_id
    if _is_admin(current_user):
        if not effective_branch_id:
            raise AppError(
                status_code=400,
                error_code="branch_employees.branch_required",
                message="branch_id is required for admin users",
                detail={},
            )
    else:
        manager_branch_id = _require_branch_scope(current_user)
        if effective_branch_id is not None and int(effective_branch_id) != manager_branch_id:
            raise AppError(
                status_code=403,
                error_code="branch_employees.cross_branch_forbidden",
                message="Branch manager can only add employees to their own branch",
                detail={"branch_id": effective_branch_id},
            )
        effective_branch_id = manager_branch_id

    _enforce_access(current_user, int(effective_branch_id))

    branch = db.query(Branch).filter(Branch.id == effective_branch_id, Branch.is_deleted == False).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="branch_employees.branch_not_found",
            message="Branch not found",
            detail={},
        )

    existing = db.query(BranchEmployee).filter(BranchEmployee.work_number == payload.work_number).first()
    if existing:
        raise AppError(
            status_code=409,
            error_code="branch_employees.work_number_exists",
            message="Work number already exists",
            detail={"work_number": payload.work_number},
        )

    row = BranchEmployee(
        branch_id=effective_branch_id,
        full_name=payload.full_name.strip(),
        job_title=payload.job_title.strip(),
        work_number=payload.work_number.strip(),
        phone=(payload.phone or None),
        active=payload.active,
        created_by=current_user.id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)

    audit_service.log(
        db,
        user_id=current_user.id,
        action="branch_employee_created",
        module="branch_employees",
        entity_type="branch_employee",
        entity_id=row.id,
        new_values=_serialize(row),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(row)
    return _serialize(_get_row(db, row.id))


@router.patch("/{employee_id}")
def update_branch_employee(
    employee_id: int,
    payload: BranchEmployeeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_manager", "admin", "super_admin")),
):
    row = _get_row(db, employee_id)
    _enforce_access(current_user, row.branch_id)
    old_values = _serialize(row)

    if payload.branch_id is not None and payload.branch_id != row.branch_id:
        if not _is_admin(current_user):
            raise AppError(
                status_code=403,
                error_code="branch_employees.transfer_forbidden",
                message="Only admin can transfer employees to another branch",
                detail={},
            )
        target_branch = db.query(Branch).filter(Branch.id == payload.branch_id, Branch.is_deleted == False).first()
        if not target_branch:
            raise AppError(
                status_code=404,
                error_code="branch_employees.target_branch_not_found",
                message="Target branch not found",
                detail={},
            )
        row.branch_id = payload.branch_id

    if payload.work_number and payload.work_number != row.work_number:
        existing = (
            db.query(BranchEmployee)
            .filter(BranchEmployee.work_number == payload.work_number, BranchEmployee.id != row.id)
            .first()
        )
        if existing:
            raise AppError(
                status_code=409,
                error_code="branch_employees.work_number_exists",
                message="Work number already exists",
                detail={"work_number": payload.work_number},
            )
        row.work_number = payload.work_number.strip()

    if payload.full_name is not None:
        row.full_name = payload.full_name.strip()
    if payload.job_title is not None:
        row.job_title = payload.job_title.strip()
    if payload.phone is not None:
        row.phone = payload.phone or None
    if payload.active is not None:
        row.active = payload.active

    db.flush()
    audit_service.log(
        db,
        user_id=current_user.id,
        action="branch_employee_updated",
        module="branch_employees",
        entity_type="branch_employee",
        entity_id=row.id,
        old_values=old_values,
        new_values=_serialize(_get_row(db, row.id)),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _serialize(_get_row(db, row.id))


@router.post("/{employee_id}/deactivate")
def deactivate_branch_employee(
    employee_id: int,
    payload: BranchEmployeeDeactivatePayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("branch_manager", "admin", "super_admin")),
):
    row = _get_row(db, employee_id)
    _enforce_access(current_user, row.branch_id)
    old_values = _serialize(row)
    row.active = payload.active
    db.flush()
    audit_service.log(
        db,
        user_id=current_user.id,
        action="branch_employee_deactivated" if payload.active is False else "branch_employee_reactivated",
        module="branch_employees",
        entity_type="branch_employee",
        entity_id=row.id,
        old_values=old_values,
        new_values=_serialize(_get_row(db, row.id)),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _serialize(_get_row(db, row.id))
