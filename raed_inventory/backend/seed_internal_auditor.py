from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ENV_FILE", ".env")

from sqlalchemy import text
from app.config import settings
from app.core.security import get_password_hash
from app.database import SessionLocal
from app.models import Role, RoleName, User, UserRole, UserStatus

USERNAME = "audit.officer"
EMAIL = "audit@raed.com"
FULL_NAME = "المراجع الداخلي"


def _password_from_env() -> str | None:
    raw = os.environ.get("INTERNAL_AUDITOR_PASSWORD") or settings.DEPLOYMENT_INTERNAL_AUDITOR_PASSWORD
    if raw is None:
        return None
    value = raw.strip()
    if len(value) < 12:
        return None
    return value


def main() -> None:
    password = _password_from_env()
    if password is None:
        print(
            "ERROR: Set INTERNAL_AUDITOR_PASSWORD or DEPLOYMENT_INTERNAL_AUDITOR_PASSWORD "
            "(minimum 12 characters) before running this seed.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    db = SessionLocal()
    try:
        bind = db.get_bind()
        if bind.dialect.name == "postgresql":
            db.execute(text("COMMIT"))
            db.execute(text("ALTER TYPE rolename ADD VALUE IF NOT EXISTS 'internal_auditor'"))
            db.commit()

        role = db.query(Role).filter(Role.name == RoleName.internal_auditor).first()
        if not role:
            role = Role(
                name=RoleName.internal_auditor,
                display_name="مراجع داخلي",
                description="Read-only audit oversight with finding creation",
            )
            db.add(role)
            db.flush()

        user = db.query(User).filter(User.username == USERNAME).first()
        if not user:
            user = User(
                username=USERNAME,
                email=EMAIL,
                full_name=FULL_NAME,
                hashed_password=get_password_hash(password),
                status=UserStatus.active,
            )
            db.add(user)
            db.flush()
            print("created_user=1")
        else:
            user.hashed_password = get_password_hash(password)
            user.status = UserStatus.active
            print("created_user=0")

        mapping = db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == role.id).first()
        if not mapping:
            db.add(UserRole(user_id=user.id, role_id=role.id))
            print("created_user_role=1")
        else:
            print("created_user_role=0")

        db.commit()
        print(f"username={USERNAME}")
        print("role=internal_auditor")
    finally:
        db.close()


if __name__ == "__main__":
    main()
