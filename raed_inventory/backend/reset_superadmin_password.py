"""
Emergency password reset for super.admin.

Run from the backend folder:
    python reset_superadmin_password.py

Resets super.admin's password to Raed@2025 (ASCII-safe, no Arabic).
If super.admin does not exist, creates it and attaches super_admin role.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import User, Role, UserRole, RoleName, UserStatus
from app.core.security import get_password_hash


NEW_PASSWORD = "Raed@2025"
USERNAME = "super.admin"


def main() -> int:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == USERNAME).first()

        if user is None:
            print(f"User '{USERNAME}' not found. Creating it now...")
            role = db.query(Role).filter(Role.name == RoleName.super_admin).first()
            if role is None:
                print("  ERROR: super_admin role not found in DB.")
                print("  Run seed_quality_training.py first to seed roles.")
                return 1
            user = User(
                username=USERNAME,
                email="super@raed.com",
                full_name="Super Admin",
                hashed_password=get_password_hash(NEW_PASSWORD),
                status=UserStatus.active,
                is_deleted=False,
            )
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role_id=role.id))
            db.commit()
            print(f"  CREATED user id={user.id}")
        else:
            user.hashed_password = get_password_hash(NEW_PASSWORD)
            # Make sure the account is active (not locked/suspended).
            user.status = UserStatus.active
            user.is_deleted = False
            # Clear any failed-login counter if the column exists.
            for attr in ("failed_login_attempts", "locked_until"):
                if hasattr(user, attr):
                    setattr(user, attr, 0 if attr == "failed_login_attempts" else None)
            db.commit()
            print(f"  Password reset for user id={user.id}")

        print("")
        print("================================================")
        print(f"  Username: {USERNAME}")
        print(f"  Password: {NEW_PASSWORD}")
        print("================================================")
        print("  Login should now work. Rotate password after first login.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"  ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
