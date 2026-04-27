"""
Seed demo accounts for all 8 operational roles.

Creates missing accounts for:
  - super_admin        → super.admin / Raed@2025
  - admin              → admin / Admin@2024        (already exists from seed.py)
  - operations_manager → ops.mgr / Raed@2025       (already exists from seed.py)
  - area_manager       → am_riyadh / Raed@2025     (already seeded earlier)
  - branch_manager     → branch.mgr1 / Raed@2025   (already exists from seed.py)
  - warehouse_manager  → wh.mgr1 / Raed@2025       (already exists from seed.py)
  - branch_user        → branch.user1 / Raed@2025  (already exists from seed.py)
  - quality_manager    → qa.mgr / Raed@2025        (NEW)

Idempotent — safe to run multiple times.
Run from backend/ directory:
    python seed_demo_all_roles.py
"""
from app.database import SessionLocal
from app.models import User, Role, UserRole, RoleName
from app.core.security import get_password_hash


DEMO_ACCOUNTS = [
    # (username, email, full_name, password, role_name)
    ("super.admin", "super@raed.com", "المدير الأعلى", "Raed@2025", RoleName.super_admin),
    ("qa.mgr",      "qa.mgr@raed.com", "مدير الجودة",    "Raed@2025", RoleName.quality_manager),
]


def main():
    db = SessionLocal()
    try:
        created = 0
        skipped = 0
        for username, email, full_name, password, role_name in DEMO_ACCOUNTS:
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                print(f"  ✓ {username} already exists (skipped)")
                skipped += 1
                continue

            role = db.query(Role).filter(Role.name == role_name).first()
            if role is None:
                print(f"  ! Role {role_name.value} not found — skipping {username}")
                continue

            user = User(
                username=username,
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash(password),
                status="active",
            )
            db.add(user)
            db.flush()

            db.add(UserRole(user_id=user.id, role_id=role.id))
            print(f"  + Created {username} ({role_name.value})")
            created += 1

        db.commit()
        print(f"\nDone. {created} created, {skipped} already existed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
