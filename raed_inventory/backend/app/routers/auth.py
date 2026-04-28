from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.core.security import verify_password, create_access_token
from app.core.auth import get_current_active_user
from app.core.limiter import limit as rate_limit
from app.models import User
from app.schemas import Token, LoginRequest
from app.config import settings
from app.services.deployment_admin_service import ensure_deployment_admin_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(
        (User.username == username) | (User.email == username),
        User.is_deleted == False
    ).first()
    if not user or not verify_password(password, user.hashed_password):
        is_deployment_admin_attempt = settings.is_deployment_env and username in {
            settings.ADMIN_USERNAME,
            settings.ADMIN_EMAIL,
        }
        if is_deployment_admin_attempt:
            repaired_user = ensure_deployment_admin_user(db)
            if repaired_user:
                user = db.query(User).filter(
                    (User.username == username) | (User.email == username),
                    User.is_deleted == False
                ).first()
                if user and verify_password(password, user.hashed_password):
                    return user
        return None
    return user


@router.post("/login", response_model=Token)
@rate_limit(settings.RATE_LIMIT_AUTH)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    # Stricter per-route rate limit (RATE_LIMIT_AUTH = "20/minute" by default)
    # مطبّق عبر slowapi decorator لمنع brute-force على كلمات المرور.
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    roles = [ur.role.name.value for ur in user.user_roles]
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "roles": roles,
            "branch_id": user.branch_id,
            "warehouse_id": user.warehouse_id,
        }
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    roles = [ur.role.name.value for ur in current_user.user_roles]
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "roles": roles,
        "branch_id": current_user.branch_id,
        "warehouse_id": current_user.warehouse_id,
        "status": current_user.status,
    }


@router.post("/change-password")
def change_password(
    payload: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.core.security import get_password_hash
    # نستورد محليّاً لتجنّب circular import
    from app.routers.users import _validate_password

    old_pw = payload.get("old_password")
    new_pw = payload.get("new_password")
    if not old_pw or not new_pw:
        raise HTTPException(status_code=400, detail="old_password and new_password are required")
    if not verify_password(old_pw, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    # استخدام نفس قواعد التحقق الخاصة بإنشاء المستخدم: 8 أحرف + كبير + رقم
    _validate_password(new_pw)
    current_user.hashed_password = get_password_hash(new_pw)
    db.commit()
    return {"message": "Password changed successfully"}
