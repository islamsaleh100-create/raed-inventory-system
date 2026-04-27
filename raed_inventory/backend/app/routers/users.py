import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database import get_db
from app.core.auth import require_roles, get_current_active_user
from app.core.errors import AppError
from app.core.security import get_password_hash, verify_password
from app.models import User, Role, UserRole
from app.schemas import UserCreate, UserUpdate, UserOut

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise AppError(status_code=400, error_code="users.password_too_short", message="كلمة المرور لازم تكون 8 أحرف على الأقل", detail={})
    if not re.search(r'[A-Z]', password):
        raise AppError(status_code=400, error_code="users.password_no_uppercase", message="كلمة المرور لازم تحتوي حرف كبير واحد على الأقل", detail={})
    if not re.search(r'[0-9]', password):
        raise AppError(status_code=400, error_code="users.password_no_digit", message="كلمة المرور لازم تحتوي رقم واحد على الأقل", detail={})


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _format_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "status": user.status,
        "branch_id": user.branch_id,
        "warehouse_id": user.warehouse_id,
        "phone": user.phone,
        "roles": [ur.role.name.value for ur in user.user_roles],
        "created_at": user.created_at,
    }


# ──────────────────────────────────────────────────────────────────────────
# SELF-SERVICE ENDPOINTS  (must be BEFORE /{user_id} to avoid route conflict)
# ──────────────────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return the currently authenticated user's profile."""
    user = db.query(User).options(
        joinedload(User.user_roles).joinedload(UserRole.role)
    ).filter(User.id == current_user.id).first()
    return _format_user(user)


@router.post("/me/change-password")
def change_my_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Authenticated user changes their own password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise AppError(
            status_code=400,
            error_code="users.wrong_current_password",
            message="Current password is incorrect",
            detail={},
        )
    _validate_password(payload.new_password)
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return all available roles in the system."""
    roles = db.query(Role).all()
    return [
        {
            "id": r.id,
            "name": r.name.value,
            "display_name": r.display_name,
            "description": r.description,
        }
        for r in roles
    ]


@router.get("/lookup")
def users_lookup(
    search: Optional[str] = None,
    role: Optional[str] = None,
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "super_admin",
        "area_manager", "branch_manager",
        "quality_visitor", "quality_manager",
        "trainer", "operations_manager", "warehouse_manager",
    )),
):
    """
    Lightweight user lookup for form dropdowns (trainer/visitor/assessor pickers).
    Returns only id, full_name/username, roles, branch_id — no email/phone.
    """
    q = db.query(User).options(
        joinedload(User.user_roles).joinedload(UserRole.role)
    ).filter(User.is_deleted == False)

    if active_only:
        q = q.filter(User.status == "active")

    if search:
        term = f"%{search}%"
        q = q.filter(
            (User.username.ilike(term)) | (User.full_name.ilike(term))
        )

    if role:
        q = (
            q.join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(Role.name == role)
            .distinct()
        )

    users = (
        q.order_by(User.full_name.asc().nullslast(), User.username.asc())
        .limit(500)
        .all()
    )

    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "roles": [ur.role.name.value for ur in u.user_roles],
            "branch_id": u.branch_id,
        }
        for u in users
    ]


# ──────────────────────────────────────────────────────────────────────────

@router.get("/")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = None,
    branch_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "super_admin"))
):
    q = db.query(User).options(
        joinedload(User.user_roles).joinedload(UserRole.role)
    ).filter(User.is_deleted == False)

    if search:
        q = q.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.full_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )
    if branch_id:
        q = q.filter(User.branch_id == branch_id)
    if status:
        q = q.filter(User.status == status)
    if role:
        q = q.join(UserRole, UserRole.user_id == User.id)\
             .join(Role,     Role.id     == UserRole.role_id)\
             .filter(Role.name == role)

    total = q.count()
    users = q.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_format_user(u) for u in users]
    }


@router.post("/")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "super_admin"))
):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        phone=payload.phone,
        branch_id=payload.branch_id,
        warehouse_id=payload.warehouse_id,
        created_by=current_user.id,
    )
    db.add(user)
    db.flush()

    for role_name in payload.role_names:
        role = db.query(Role).filter(Role.name == role_name).first()
        if role:
            db.add(UserRole(user_id=user.id, role_id=role.id))

    db.commit()
    db.refresh(user)
    return _format_user(user)


@router.get("/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "super_admin"))
):
    user = db.query(User).options(
        joinedload(User.user_roles).joinedload(UserRole.role)
    ).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _format_user(user)


@router.put("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "super_admin"))
):
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for field, value in payload.model_dump(exclude_unset=True, exclude={"role_names"}).items():
        setattr(user, field, value)

    if payload.role_names is not None:
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        for role_name in payload.role_names:
            role = db.query(Role).filter(Role.name == role_name).first()
            if role:
                db.add(UserRole(user_id=user.id, role_id=role.id))

    db.commit()
    db.refresh(user)
    return _format_user(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user.is_deleted = True
    db.commit()
    return {"message": "User deleted"}


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "super_admin"))
):
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    new_password = payload.get("new_password")
    if not new_password:
        raise HTTPException(status_code=400, detail="new_password مطلوب")
    _validate_password(new_password)
    user.hashed_password = get_password_hash(new_password)
    db.commit()
    return {"message": "Password reset successfully"}
