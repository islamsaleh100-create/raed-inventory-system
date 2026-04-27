"""
Create users for branches that currently have no user.

- يعمل idempotent: لو الفرع عنده مستخدم واحد بدور branch_user/branch_manager،
  السكريبت يتجاوزه.
- الباسورد الافتراضي يقرأ من متغير البيئة DEFAULT_BRANCH_PASSWORD (وإن لم
  يوجد، يولّد قيمة عشوائية قوية ويطبعها في stdout + ملف CSV مؤقت).
- البيانات المولَّدة تُسجَّل في ملف CSV في نفس مجلد السكريبت
  (`branch_users_generated_<ts>.csv`) لتوزيعها على الفروع لاحقاً.

الاستخدام:
    python create_branch_users.py                 # إنشاء منشئ واحد لكل فرع ينقصه
    python create_branch_users.py --role manager  # إنشاء مدير فرع
    python create_branch_users.py --dry-run       # بدون كتابة قاعدة البيانات

مخرجات:
    branch_users_generated_YYYYMMDD_HHMMSS.csv   (username, full_name, password, branch_code)
"""
from __future__ import annotations

import argparse
import csv
import os
import secrets
import string
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import get_password_hash  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Branch, Role, RoleName, User, UserRole, UserStatus  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────

def _gen_password() -> str:
    """
    ينتج باسورد يحقق قواعد التحقق في users.py:
    - >= 8 chars
    - يحتوي على حرف كبير وحرف صغير ورقم
    """
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(12))
        if (
            any(c.isupper() for c in pw)
            and any(c.islower() for c in pw)
            and any(c.isdigit() for c in pw)
        ):
            return f"Raed{pw}!"  # نضيف علامة لضمان تعقيد إضافي


def _branch_has_users(db: Session, branch_id: int, role_name: RoleName) -> bool:
    return (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            User.branch_id == branch_id,
            User.is_deleted == False,  # noqa: E712
            Role.name == role_name,
        )
        .count()
        > 0
    )


def _unique_username(db: Session, base: str) -> str:
    """إذا الـ username موجود نضيف suffix رقمي صغير."""
    candidate = base
    suffix = 2
    while db.query(User).filter(User.username == candidate).first() is not None:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def _unique_email(db: Session, base_local: str, domain: str) -> str:
    email = f"{base_local}@{domain}"
    suffix = 2
    while db.query(User).filter(User.email == email).first() is not None:
        email = f"{base_local}{suffix}@{domain}"
        suffix += 1
    return email


def _role_for(name: RoleName, db: Session) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        raise RuntimeError(
            f"Role {name.value} missing — run seed.py first to create roles."
        )
    return role


# ─────────────────────────────────────────────────────────────────────────
# core
# ─────────────────────────────────────────────────────────────────────────

def create_users_for_branches(
    db: Session,
    *,
    role: str = "user",
    email_domain: str = "raed.com",
    dry_run: bool = False,
) -> list[dict]:
    """
    ينشئ مستخدماً واحداً لكل فرع ليس عنده مستخدم من الدور المطلوب.
    role: "user" (branch_user) أو "manager" (branch_manager)
    """
    role_enum = RoleName.branch_manager if role == "manager" else RoleName.branch_user
    role_prefix = "mgr" if role == "manager" else "user"
    role_obj = _role_for(role_enum, db)

    branches = (
        db.query(Branch)
        .filter(Branch.active == True, Branch.is_deleted == False)  # noqa: E712
        .order_by(Branch.branch_code.asc())
        .all()
    )

    generated: list[dict] = []
    for br in branches:
        if _branch_has_users(db, br.id, role_enum):
            continue

        base_username = f"{role_prefix}.{br.branch_code.lower()}"
        username = _unique_username(db, base_username)
        email = _unique_email(db, username.replace(".", "-"), email_domain)
        full_name = (
            f"{'مدير' if role == 'manager' else 'موظف'} {br.branch_name}"
        ).strip()
        password = os.environ.get("DEFAULT_BRANCH_PASSWORD") or _gen_password()

        record = {
            "branch_code": br.branch_code,
            "branch_name": br.branch_name,
            "username": username,
            "email": email,
            "full_name": full_name,
            "password": password,
            "role": role_enum.value,
        }
        generated.append(record)

        if dry_run:
            continue

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            status=UserStatus.active,
            branch_id=br.id,
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role_obj.id))

    if not dry_run:
        db.commit()
    return generated


def _write_csv(rows: list[dict]) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"branch_users_generated_{ts}.csv",
    )
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "branch_code",
                "branch_name",
                "role",
                "username",
                "email",
                "full_name",
                "password",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create one user per branch that has no user"
    )
    parser.add_argument(
        "--role",
        choices=["user", "manager"],
        default="user",
        help="branch_user (default) or branch_manager",
    )
    parser.add_argument("--domain", default="raed.com", help="email domain")
    parser.add_argument(
        "--dry-run", action="store_true", help="don't write to database"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = create_users_for_branches(
            db,
            role=args.role,
            email_domain=args.domain,
            dry_run=args.dry_run,
        )
    finally:
        db.close()

    if not rows:
        print("✅ All branches already have a user of this role — nothing to create.")
        return 0

    path = _write_csv(rows)
    action = "[DRY-RUN] would create" if args.dry_run else "Created"
    print(f"✅ {action} {len(rows)} user(s).")
    print(f"📄 CSV saved at: {path}")
    for r in rows:
        print(
            f"   - {r['branch_code']:<10s}  {r['username']:<25s}  {r['password']}"
        )
    print("\n⚠️  احفظ ملف الـ CSV بمكان آمن ثم احذفه بعد توزيع البيانات.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
