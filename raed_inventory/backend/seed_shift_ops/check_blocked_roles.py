#!/usr/bin/env python3
"""هل يوجد مستخدمون حقيقيون تأثّروا بحظر الشاشات القديمة؟ — قراءة فقط.

TrialLegacyRouteGuard نُشر على الإنتاج بلا شرط بيئة، فيمنع سبعة أدوار من
شاشات /orders و /receiving و /warehouse/* و /delivery/*.
هذا السكربت يجيب على السؤال الوحيد الذي يقرّر: هل لهذه الأدوار مستخدمون؟

نفس ضمانات القراءة فقط: لا يقرأ .env · default_transaction_read_only = on ·
كل الجمل SELECT بلا commit.

    $env:PROD_DATABASE_URL = "postgresql://..."
    python check_blocked_roles.py
"""
from __future__ import annotations

import os
import re
import sys

from sqlalchemy import create_engine, text

BLOCKED_ROLES = [
    "branch_user", "branch_manager", "area_manager", "kitchen_section_manager",
    "warehouse_user", "warehouse_manager", "delivery_user",
]


def main() -> None:
    url = (os.environ.get("PROD_DATABASE_URL") or "").strip()
    if not url:
        print('\n✗ PROD_DATABASE_URL غير مضبوط.\n'
              '  $env:PROD_DATABASE_URL = "postgresql://..."\n', file=sys.stderr)
        sys.exit(1)

    masked = re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url)
    print(f"القاعدة: {masked}")
    print("الوضع : قراءة فقط\n")

    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SET default_transaction_read_only = on"))
        rows = conn.execute(text("""
            SELECT r.name::text AS role, u.status::text AS status, count(*) AS n
            FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id
            GROUP BY r.name, u.status
            ORDER BY n DESC
        """)).all()

    print("─" * 58)
    print(f"{'الدور':28} {'الحالة':12} {'عدد':>5}")
    print("─" * 58)
    for role, status, n in rows:
        mark = "  ← محظور" if role in BLOCKED_ROLES else ""
        print(f"{role:28} {status:12} {n:>5}{mark}")

    affected = sum(n for role, status, n in rows
                   if role in BLOCKED_ROLES and (status or "").lower() == "active")

    print("═" * 58)
    if affected == 0:
        print("✓ صفر مستخدمين نشطين على الأدوار المحظورة.")
        print("  الحظر لا يؤذي أحدًا الآن — كمّل النشر.")
    else:
        print(f"❌ {affected} مستخدمًا نشطًا على أدوار محظورة.")
        print("  هؤلاء مقفول عليهم شاشات الطلبات/المستودع/التوصيل الآن.")
        print("  الإصلاح قبل أي خطوة أخرى.")
    print("═" * 58)
    print("لم تُكتب أي بيانات.")


if __name__ == "__main__":
    main()
