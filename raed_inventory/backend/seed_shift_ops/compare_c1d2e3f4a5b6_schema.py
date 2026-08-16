#!/usr/bin/env python3
"""يقارن الجدولين الموجودين على الإنتاج بما كانت ستُنشئه المراجعة c1d2e3f4a5b6 — قراءة فقط.

لماذا هذا السكربت موجود:
  `branch_item_availability` و `item_change_requests` أُنشئا على الإنتاج **وقت التشغيل**
  عبر `Base.metadata.create_all` في نسخة قديمة من `startup_schema.py`، قبل أن يُنقلا إلى
  المراجعة c1d2e3f4a5b6. فالجدولان موجودان، وAlembic لا يعرف ذلك (مراجعة الإنتاج 89aedce3fd41).

  الحل المعتاد `alembic stamp c1d2e3f4a5b6` يقول لAlembic «هذه المراجعة مطبَّقة».
  **وهو صحيح فقط إذا كان الموجود مطابقًا لما كانت ستُنشئه.** وهذا غير مضمون هنا:
  `create_all` يبني من الموديل، والمراجعة تضيف **عشرة فهارس مسمّاة صراحةً** قد لا يعلنها
  الموديل أصلًا. الختم بلا مقارنة يجعل Alembic يعتقد أن الفهارس موجودة وهي ليست كذلك،
  ويبقى الفرق مخفيًا إلى الأبد.

قراءة فقط: لا يقرأ .env · default_transaction_read_only = on · كل الجمل SELECT بلا commit.

    $env:PROD_DATABASE_URL = "postgresql://..."
    python compare_c1d2e3f4a5b6_schema.py
"""
from __future__ import annotations

import os
import re
import sys

from sqlalchemy import create_engine, text

# مستخرَج حرفيًا من upgrade() في
# alembic/versions/20260614_0001_c1d2e3f4a5b6_branch_item_availability_and_item_change_requests.py
EXPECTED = {
    "branch_item_availability": {
        "columns": [
            "id", "branch_id", "item_id", "active", "added_by", "removed_by",
            "reason", "created_at", "updated_at",
        ],
        "indexes": ["ix_bia_branch_id", "ix_bia_item_id"],
        "index_ddl": {
            "ix_bia_branch_id": "CREATE INDEX ix_bia_branch_id ON branch_item_availability (branch_id)",
            "ix_bia_item_id": "CREATE INDEX ix_bia_item_id ON branch_item_availability (item_id)",
        },
        "unique": {"uq_branch_item_availability": ["branch_id", "item_id"]},
    },
    "item_change_requests": {
        "columns": [
            "id", "request_no", "request_type", "status", "target_type",
            "warehouse_id", "branch_id", "item_id",
            "proposed_item_name_ar", "proposed_item_name_en", "proposed_item_code",
            "proposed_unit", "proposed_source_type",
            "reason", "review_note", "failure_reason",
            "requested_by", "reviewed_by",
            "created_at", "reviewed_at", "executed_at",
        ],
        "indexes": [
            "ix_icr_request_no", "ix_icr_request_type", "ix_icr_status",
            "ix_icr_target_type", "ix_icr_warehouse_id", "ix_icr_branch_id",
            "ix_icr_item_id", "ix_icr_requested_by",
        ],
        "index_ddl": {
            "ix_icr_request_no": "CREATE INDEX ix_icr_request_no ON item_change_requests (request_no)",
            "ix_icr_request_type": "CREATE INDEX ix_icr_request_type ON item_change_requests (request_type)",
            "ix_icr_status": "CREATE INDEX ix_icr_status ON item_change_requests (status)",
            "ix_icr_target_type": "CREATE INDEX ix_icr_target_type ON item_change_requests (target_type)",
            "ix_icr_warehouse_id": "CREATE INDEX ix_icr_warehouse_id ON item_change_requests (warehouse_id)",
            "ix_icr_branch_id": "CREATE INDEX ix_icr_branch_id ON item_change_requests (branch_id)",
            "ix_icr_item_id": "CREATE INDEX ix_icr_item_id ON item_change_requests (item_id)",
            "ix_icr_requested_by": "CREATE INDEX ix_icr_requested_by ON item_change_requests (requested_by)",
        },
        "unique": {},
    },
}


def main() -> None:
    url = (os.environ.get("PROD_DATABASE_URL") or "").strip()
    if not url or url.startswith("<"):
        print('\n✗ PROD_DATABASE_URL غير مضبوط بقيمة حقيقية.\n'
              '  الصق القيمة كاملة بلا أقواس مدبَّبة:\n'
              '  $env:PROD_DATABASE_URL = "postgresql://postgres:...@...proxy.rlwy.net:PORT/railway"\n',
              file=sys.stderr)
        sys.exit(1)

    print(f"القاعدة: {re.sub(r'://([^:/@]+):[^@]*@', '://REDACTED@', url)}")
    print("الوضع : قراءة فقط\n")

    fixes: list[str] = []
    verdict_ok = True

    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SET default_transaction_read_only = on"))

        for table, spec in EXPECTED.items():
            print("─" * 66)
            print(table)
            print("─" * 66)

            cols = {r[0] for r in conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
            ), {"t": table}).all()}
            if not cols:
                print("  ⚠️  الجدول غير موجود أصلًا — لا تختمه، دع المراجعة تُنشئه.")
                verdict_ok = False
                continue

            missing_cols = [c for c in spec["columns"] if c not in cols]
            extra_cols = sorted(cols - set(spec["columns"]))
            print(f"  أعمدة: {len(cols)} موجودة · متوقّع {len(spec['columns'])}")
            if missing_cols:
                print(f"  ❌ أعمدة ناقصة: {', '.join(missing_cols)}")
                verdict_ok = False
            if extra_cols:
                print(f"  ℹ️  أعمدة زائدة (لا تمنع الختم): {', '.join(extra_cols)}")
            if not missing_cols:
                print("  ✓ كل الأعمدة المتوقّعة موجودة")

            idx = {r[0] for r in conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename = :t"
            ), {"t": table}).all()}
            missing_idx = [i for i in spec["indexes"] if i not in idx]
            if missing_idx:
                print(f"  ❌ فهارس ناقصة ({len(missing_idx)}/{len(spec['indexes'])}): {', '.join(missing_idx)}")
                fixes += [spec["index_ddl"][i] + ";" for i in missing_idx]
            else:
                print(f"  ✓ الفهارس المتوقّعة موجودة ({len(spec['indexes'])})")

            for name, cols_expected in spec["unique"].items():
                found = conn.execute(text("""
                    SELECT tc.constraint_name
                    FROM information_schema.table_constraints tc
                    WHERE tc.table_name = :t AND tc.constraint_type = 'UNIQUE'
                """), {"t": table}).all()
                names = {r[0] for r in found}
                if name in names:
                    print(f"  ✓ قيد التفرّد {name} موجود")
                elif names:
                    print(f"  ℹ️  قيد تفرّد باسم مختلف: {', '.join(sorted(names))} "
                          f"(متوقّع {name} على {', '.join(cols_expected)}) — تحقّق يدويًا")
                else:
                    print(f"  ❌ لا يوجد قيد تفرّد على {', '.join(cols_expected)}")
                    fixes.append(
                        f"ALTER TABLE {table} ADD CONSTRAINT {name} "
                        f"UNIQUE ({', '.join(cols_expected)});"
                    )
            print()

    print("═" * 66)
    if not fixes and verdict_ok:
        print("✓ الموجود مطابق لما كانت ستُنشئه المراجعة.")
        print("  `alembic stamp c1d2e3f4a5b6` آمن، ثم `alembic upgrade head`.")
    elif not verdict_ok:
        print("❌ فرق في الأعمدة أو جدول مفقود — لا تختم. الحالة تحتاج قرارًا، لا أمرًا.")
    else:
        print(f"⚠️  الجدولان موجودان والأعمدة سليمة، لكن ينقص {len(fixes)} فهرسًا/قيدًا.")
        print("  الختم وحده يخفي هذا النقص إلى الأبد. طبّق التالي أولًا، ثم اختم:\n")
        for f in fixes:
            print(f"    {f}")
        print("\n  (كلها CREATE INDEX / ADD CONSTRAINT — إضافية بحتة، لا تمسّ بيانات.)")
    print("═" * 66)
    print("لم تُكتب أي بيانات.")


if __name__ == "__main__":
    main()
