"""
Pack A / Step 5: Seed sales_manager demo account.

- Idempotent: skips if username already exists.
- Fixed password (Raed@2025) for the demo account - rotate via /admin/users
  before any real deployment.
- Requires the sales_manager role to be seeded first (run
  seed_quality_training.py which seeds the full NEW_ROLES list).

Note: output is ASCII-only to keep this working on Windows PowerShell
(default cp1256/cp1252 terminal) without needing PYTHONIOENCODING=utf-8.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, Role, UserRole, RoleName
from app.core.security import get_password_hash


SALES_MANAGER = {
    "username": "sales.mgr",
    "email": "sales.mgr@onda.local",
    "full_name": "Sales and Delivery Manager",  # ASCII-safe; Arabic name set via /admin/users
    "password": "Raed@2025",
    "phone": None,
}


def seed_sales_manager(db: Session) -> tuple[str, str, str]:
    """Returns (username, full_name, status) where status is 'CREATED' or 'EXISTS'."""
    role = db.query(Role).filter(Role.name == RoleName.sales_manager).first()
    if not role:
        raise RuntimeError(
            "sales_manager role missing. Run seed_quality_training.py first "
            "(it now seeds sales_manager as part of NEW_ROLES)."
        )

    existing = db.query(User).filter(User.username == SALES_MANAGER["username"]).first()
    if existing:
        print(f"  [SKIP] {SALES_MANAGER['username']} already exists (id={existing.id})")
        return (SALES_MANAGER["username"], SALES_MANAGER["full_name"], "EXISTS")

    user = User(
        username=SALES_MANAGER["username"],
        email=SALES_MANAGER["email"],
        full_name=SALES_MANAGER["full_name"],
        hashed_password=get_password_hash(SALES_MANAGER["password"]),
        phone=SALES_MANAGER["phone"],
        status="active",
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    print(f"  [OK] Created {SALES_MANAGER['username']} (id={user.id})")
    return (SALES_MANAGER["username"], SALES_MANAGER["full_name"], "CREATED")


def main():
    print("=" * 60)
    print("  Pack A / Step 5 - Seed sales_manager demo account")
    print("=" * 60)
    db = SessionLocal()
    try:
        username, full_name, status = seed_sales_manager(db)
    finally:
        db.close()

    print()
    print("=" * 60)
    print(f"  {username}  ({full_name})  ->  {status}")
    print(f"  Password: {SALES_MANAGER['password']}")
    print("=" * 60)
    print("Next: rotate this password via /admin/users before production use.")


if __name__ == "__main__":
    main()
