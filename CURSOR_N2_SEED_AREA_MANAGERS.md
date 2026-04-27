# Cursor Handoff — N2: إنشاء حسابين `area_manager` (الرياض + الدمام)

## الهدف
المدراء الميدانيين محتاجين حسابات يسجّلوا بيها دخول من لابتوباتهم. دلوقتي مفيش أي user بدور `area_manager` في الـ DB. الخطوة دي بتضيف حسابين — واحد لكل منطقة من المناطق الموجودة فعلاً في `seed.py`.

## المناطق المعتمدة (من `seed.py`)
- **الرياض (Riyadh)** — مستودع `WH-RYD`
- **الدمام (Dammam)** — مستودع `WH-DMM`

> ملاحظة: في مدن تانية في الـ branches زي الخبر، رأس تنورة، الأحساء، الظهران — بس كلها بتنتمي لواحد من المستودعين (WH-RYD أو WH-DMM). لو إسلام عايز يقسّم بشكل مختلف لاحقاً، نعمل N2.5 — دلوقتي حسابين كافيين للتجربة.

## المتطلبات المسبقة
- `seed_quality_training.py` اتشغّل مرة على الأقل (عشان دور `area_manager` يكون موجود في جدول `roles`). لو مش متأكد:
  ```powershell
  cd C:\raed_inventory_system\raed_inventory\backend
  $env:PYTHONPATH = (Get-Location).Path
  python -c "from app.database import SessionLocal; from app.models import Role, RoleName; db=SessionLocal(); r=db.query(Role).filter(Role.name==RoleName.area_manager).first(); print('area_manager role:', 'OK' if r else 'MISSING')"
  ```
  لو طلع `MISSING`، شغّل `python seed_quality_training.py` الأول.

## الخطوات

### 1) اكتب السكريبت

ملف جديد: `raed_inventory/backend/seed_area_managers.py`

```python
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
```

### 2) شغّل السكريبت

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
$env:PYTHONPATH = (Get-Location).Path
python seed_area_managers.py
```

المتوقع:
```
============================================================
  N2 — Seeding area_manager accounts
============================================================
  ✅ Created am_riyadh (id=XX)
  ✅ Created am_dammam (id=YY)

============================================================
  Credentials (SHARE NOW — not stored elsewhere)
============================================================
Username       Full name                    Password
------------------------------------------------------------
am_riyadh      مدير منطقة الرياض            Onda47hT9x-kQ
am_dammam      مدير منطقة الدمام            Onda12pF3z_mR
============================================================
```

### 3) اختبار تسجيل الدخول

من لابتوب إسلام (الـ host) — قبل ما ندّي الـ credentials لحد:

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
$env:PYTHONPATH = (Get-Location).Path
python -c "
import requests
# غيّر password لواحد من اللي طلعوا فوق
r = requests.post('http://localhost:8010/api/v1/auth/login', json={'username': 'am_riyadh', 'password': 'PASTE_PASSWORD_HERE'})
print('status:', r.status_code)
print('body:', r.json() if r.status_code == 200 else r.text[:300])
"
```

المتوقع `status: 200` وـ body فيه `access_token`.

بعد كده:
- افتح `http://localhost:3000` (أو الـ LAN URL لو N1 اتطبّق)
- سجّل دخول بـ `am_riyadh` و الـ password
- لازم يدخل بدون مشاكل — يشوف واجهة الـ area_manager

### 4) الـ handover للمدير الحقيقي

لما إسلام يعدي الـ credentials للمدراء:
1. يقولهم: "سجّل دخول أول مرة بالـ password ده، وبعدين روح صفحة الملف الشخصي وغيّر كلمة المرور"
2. بدل كده، إسلام ممكن يفتح `/admin/users` ويحط أسماء حقيقية بدل "مدير منطقة الرياض/الدمام" (مثلاً اسم المدير الفعلي).

## الرد المطلوب

بعد التنفيذ، ابعت:
- ✅ output السكريبت (مع الـ passwords — هنحفظهم سريعاً ونمسحهم)
- ✅ نتيجة اختبار تسجيل الدخول (status 200?)
- ⚠️ أي خطأ في الـ role lookup (يعني `seed_quality_training.py` ما اتشغّلش)

## ملاحظة أمان

- الـ passwords اللي بيطلعوا راندوم ومناسبين للتجربة. مش آمنين بشكل مطلق لأنهم هيتبعتوا على واتساب أو تليجرام. الحل الأفضل لاحقاً: إضافة force_password_change flag على الـ user schema (task N3 لاحق).
- لو إسلام ضاع أي password، `/admin/users` فيها زرار reset password.
- الـ emails (`am.riyadh@onda.local`) وهمية — لأن الـ schema بيطلب email. لو عايز تغيّرها لإيميلات حقيقية، عدّل `AREA_MANAGERS` في السكريبت قبل ما تشغّله، أو عدّلها بعد كده من `/admin/users`.
