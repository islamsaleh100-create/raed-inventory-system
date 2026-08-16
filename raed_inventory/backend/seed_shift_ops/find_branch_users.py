#!/usr/bin/env python3
"""أسماء مستخدمي الفروع في الإنتاج — قراءة فقط.

يعرض: اسم المستخدم · الدور · الحالة · كود الفرع واسمه.
**لا يعرض كلمات المرور ولا يستطيع.** الجدول يخزّن `hashed_password` فقط، والتشفير
في اتجاه واحد — لا يوجد مسار لاستخراج كلمة المرور الأصلية من القاعدة، لأي أحد.
كلمة المرور تُعاد تعيينها من واجهة الأدمن، ولا تُقرأ.

قراءة فقط: لا يقرأ .env · default_transaction_read_only = on · SELECT بلا commit.

    $env:PROD_DATABASE_URL = (railway variables --service Postgres --json | ConvertFrom-Json).DATABASE_PUBLIC_URL
    python find_branch_users.py             # كل مستخدمي الفروع
    python find_branch_users.py BR-DMM-04   # فرع واحد
"""
from __future__ import annotations

import os
import re
import sys

from sqlalchemy import create_engine, text


def main() -> None:
    url = (os.environ.get("PROD_DATABASE_URL") or "").strip()
    if not url or url.startswith("<"):
        print('\n✗ PROD_DATABASE_URL غير مضبوط بقيمة حقيقية.\n', file=sys.stderr)
        sys.exit(1)

    wanted = (sys.argv[1].strip().upper() if len(sys.argv) > 1 else None)

    print(f"القاعدة: {re.sub(r'://([^:/@]+):[^@]*@', '://REDACTED@', url)}")
    print("الوضع : قراءة فقط · كلمات المرور غير قابلة للعرض\n")

    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SET default_transaction_read_only = on"))
        rows = conn.execute(text("""
            SELECT b.branch_code, b.branch_name, u.username, u.full_name,
                   r.name::text AS role, u.status::text AS status, u.is_deleted
            FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id
            LEFT JOIN branches b ON b.id = u.branch_id
            WHERE r.name::text IN ('branch_manager', 'branch_user')
            ORDER BY b.branch_code NULLS LAST, r.name, u.username
        """)).all()

    if wanted:
        rows = [r for r in rows if (r[0] or "").upper() == wanted]
        if not rows:
            print(f"لا يوجد مستخدم مرتبط بالفرع {wanted}.")
            print("جرّب بلا وسيط لعرض كل الفروع ومعرفة الكود الصحيح.")
            return

    print("─" * 96)
    print(f"{'كود الفرع':12} {'الفرع':26} {'اسم المستخدم':24} {'الدور':16} الحالة")
    print("─" * 96)
    for code, bname, username, _full, role, status, deleted in rows:
        flag = "  (محذوف)" if deleted else ""
        print(f"{(code or '—'):12} {(bname or '—')[:25]:26} {username:24} {role:16} {status}{flag}")
    print("─" * 96)
    print(f"الإجمالي: {len(rows)}")
    print("\nكلمة المرور: تُعاد تعيينها من واجهة الأدمن (إدارة المستخدمين)، ولا تُقرأ من القاعدة.")
    print("لم تُكتب أي بيانات.")


if __name__ == "__main__":
    main()
