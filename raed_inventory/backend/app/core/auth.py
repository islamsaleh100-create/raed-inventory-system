from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database import get_db
from app.core.security import decode_access_token
from app.models import User, UserRole, Role, RolePermission, Permission, Branch, UserStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Role hierarchy for permission checks
ROLE_PERMISSIONS = {
    "super_admin": ["*"],  # all
    "admin": [
        "users.*", "branches.*", "warehouses.*", "items.*",
        "inventory.*", "orders.*", "reports.*", "settings.*"
    ],
    "branch_manager": [
        "inventory.approve", "inventory.reject",
        "orders.approve_branch", "orders.submit",
        "reports.branch"
    ],
    "branch_user": [
        "inventory.create", "inventory.submit",
        "orders.review", "orders.receive",
        "reports.branch_view"
    ],
    "warehouse_manager": [
        "orders.approve_wh", "orders.reject",
        "orders.dispatch", "warehouse.*",
        "reports.warehouse", "reports.shortage"
    ],
    "warehouse_user": [
        "orders.view", "orders.pick",
        "orders.dispatch_execute", "reports.warehouse_view"
    ],
    "operations_manager": [
        "reports.*", "inventory.view", "orders.view",
        "dashboard.operations"
    ],
    "quality_manager": ["evaluations.*", "quality.*"],
    "evaluator": ["evaluations.create", "evaluations.submit"],
    "hr_manager": ["evaluations.employee_history"],
    "kitchen_section_manager": ["production.section"],
    "delivery_user": ["delivery.*"],
}


def _user_status_value(user: User) -> str:
    """Normalize SQLAlchemy enum/string user status values for auth checks."""
    status_value = getattr(user, "status", None)
    return getattr(status_value, "value", status_value)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_id: int = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = db.query(User).options(
        joinedload(User.user_roles).joinedload(UserRole.role)
    ).filter(User.id == int(user_id), User.is_deleted == False).first()
    if not user or _user_status_value(user) != UserStatus.active.value:
        raise credentials_exception
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if _user_status_value(current_user) != UserStatus.active.value:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_user_roles(user: User) -> List[str]:
    return [ur.role.name.value for ur in user.user_roles]


def _same_region(b1: Branch, b2: Branch) -> bool:
    """Two branches belong to the same area_manager scope if city (primary) or area (fallback) matches."""
    c1 = (getattr(b1, "city", None) or "").strip().lower()
    c2 = (getattr(b2, "city", None) or "").strip().lower()
    if c1 and c2 and c1 == c2:
        return True
    a1 = (getattr(b1, "area", None) or "").strip().lower()
    a2 = (getattr(b2, "area", None) or "").strip().lower()
    return bool(a1 and a2 and a1 == a2)


def can_access_branch(user: User, branch_id: int, db: Optional[Session] = None) -> bool:
    """
    Branch-level access check.

    area_manager scope is bounded by the city/area of the user's home branch.
    Callers that need area_manager access MUST pass `db` so the region comparison
    can be performed; without `db` area_manager is denied cross-branch access
    (safe default — prevents accidental global access).
    """
    user_roles = get_user_roles(user)
    if any(role in user_roles for role in ["super_admin", "admin", "operations_manager"]):
        return True
    if "area_manager" in user_roles:
        if not user.branch_id:
            return False
        if user.branch_id == branch_id:
            return True
        if db is None:
            return False
        user_branch = db.query(Branch).filter(Branch.id == user.branch_id).first()
        target_branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not user_branch or not target_branch:
            return False
        return _same_region(user_branch, target_branch)
    if any(role in user_roles for role in ["branch_user", "branch_manager"]):
        return user.branch_id == branch_id
    return False


def can_access_warehouse(user: User, warehouse_id: int) -> bool:
    user_roles = get_user_roles(user)
    if any(role in user_roles for role in ["super_admin", "admin", "operations_manager"]):
        return True
    if any(role in user_roles for role in ["warehouse_user", "warehouse_manager"]):
        return user.warehouse_id == warehouse_id
    return False


def require_roles(*roles: str):
    """
    FastAPI dependency that asserts the current user has at least one of the
    given role names.

    `super_admin` is the only central bypass.
    `admin` must be listed explicitly in the route's allowed tuple if the
    endpoint should allow it. This keeps the permission contract visible at
    the router layer and avoids accidental privilege bleed.
    """
    def checker(current_user: User = Depends(get_current_active_user)):
        user_roles = get_user_roles(current_user)
        if "super_admin" in user_roles:
            return current_user
        if not any(r in user_roles for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(roles)}"
            )
        return current_user
    return checker


def is_admin_or_superadmin(current_user: User = Depends(get_current_active_user)):
    user_roles = get_user_roles(current_user)
    if "super_admin" in user_roles or "admin" in user_roles:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied. Admin or super_admin required.",
    )
