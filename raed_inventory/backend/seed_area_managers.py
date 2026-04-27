"""
N2: Seed two area_manager accounts (Riyadh + Dammam).

- Idempotent: skips users that already exist by username.
- Generates strong temp passwords (8+ chars, uppercase, digit) and prints them ONCE.
- Does NOT store the plaintext anywhere else — Islam must share them immediately
  or reset via /admin/users.
"""
import sys
import os
import secrets
import string
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, Role, UserRole, RoleName
from app.core.security import get_password_hash


AREA_MANAGERS = [
    {
        "username": "am_riyadh",
        "email": "am.riyadh@onda.local",
        "full_name": "مدير منطقة الرياض",
        "phone": None,
    },
    {
        "username": "am_dammam",
        "email": "am.dammam@onda.local",
        "full_name": "مدير منطقة الدمام",
        "phone": None,
    },
]


def generate_temp_password() -> str:
    """
    Generate a 12-char password with guaranteed:
    - 1+ uppercase (satisfies users.password_no_uppercase)
    - 1+ digit     (satisfies users.password_no_digit)
    - 8+ chars     (satisfies users.password_too_short)
    Format: Onda + 2 digits + 6 random url-safe chars  →  e.g. Onda47hT9x-kQ
    """
    digits = "".join(secrets.choice(string.digits) for _ in range(2))
    tail = secrets.token_urlsafe(6)  # mix of letters/digits/-/_
    return f"Onda{digits}{tail}"


def seed_area_managers(db: Session) -> list[tuple[str, str, str]]:
    """Returns list of (username, full_name, plaintext_password_or_SKIPPED)."""
    role = db.query(Role).filter(Role.name == RoleName.area_manager).first()
    if not role:
        raise RuntimeError(
            "area_manager role missing. Run seed_quality_training.py first."
        )

    results: list[tuple[str, str, str]] = []
    for spec in AREA_MANAGERS:
        existing = db.query(User).filter(User.username == spec["username"]).first()
        if existing:
            print(f"  ⏩ Skipping {spec['username']} — already exists (id={existing.id})")
            results.append((spec["username"], spec["full_name"], "SKIPPED (exists)"))
            continue

        plain = generate_temp_password()
        user = User(
            username=spec["username"],
            email=spec["email"],
            full_name=spec["full_name"],
            hashed_password=get_password_hash(plain),
            phone=spec["phone"],
            status="active",
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        print(f"  ✅ Created {spec['username']} (id={user.id})")
        results.append((spec["username"], spec["full_name"], plain))

    db.commit()
    return results


def main():
    print("=" * 60)
    print("  N2 — Seeding area_manager accounts")
    print("=" * 60)
    db = SessionLocal()
    try:
        results = seed_area_managers(db)
    finally:
        db.close()

    print()
    print("=" * 60)
    print("  Credentials (SHARE NOW — not stored elsewhere)")
    print("=" * 60)
    print(f"{'Username':<14} {'Full name':<28} Password")
    print("-" * 60)
    for username, full_name, pw in results:
        print(f"{username:<14} {full_name:<28} {pw}")
    print("=" * 60)
    print("Next: reset any of these via /admin/users whenever you want.")


if __name__ == "__main__":
    main()
