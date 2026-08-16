# CURSOR_REPORT — TG-PROD-MIGRATE-V2

## Task ID
TG-PROD-MIGRATE-V2

## Status
IMPLEMENTED

## Executor
Cursor

## Date
2026-08-16

---

## Phase 1 — Schema comparison (read-only)

```
القاعدة: postgresql://REDACTED@switchback.proxy.rlwy.net:50440/railway
الوضع : قراءة فقط

──────────────────────────────────────────────────────────────────
branch_item_availability
──────────────────────────────────────────────────────────────────
  أعمدة: 9 موجودة · متوقّع 9
  ✓ كل الأعمدة المتوقّعة موجودة
  ❌ فهارس ناقصة (2/2): ix_bia_branch_id, ix_bia_item_id
  ✓ قيد التفرّد uq_branch_item_availability موجود

──────────────────────────────────────────────────────────────────
item_change_requests
──────────────────────────────────────────────────────────────────
  أعمدة: 21 موجودة · متوقّع 21
  ✓ كل الأعمدة المتوقّعة موجودة
  ❌ فهارس ناقصة (8/8): ix_icr_request_no, ix_icr_request_type, ix_icr_status, ix_icr_target_type, ix_icr_warehouse_id, ix_icr_branch_id, ix_icr_item_id, ix_icr_requested_by

══════════════════════════════════════════════════════════════════
⚠️  الجدولان موجودان والأعمدة سليمة، لكن ينقص 10 فهرسًا/قيدًا.
  الختم وحده يخفي هذا النقص إلى الأبد. طبّق التالي أولًا، ثم اختم:

    CREATE INDEX ix_bia_branch_id ON branch_item_availability (branch_id);
    CREATE INDEX ix_bia_item_id ON branch_item_availability (item_id);
    CREATE INDEX ix_icr_request_no ON item_change_requests (request_no);
    CREATE INDEX ix_icr_request_type ON item_change_requests (request_type);
    CREATE INDEX ix_icr_status ON item_change_requests (status);
    CREATE INDEX ix_icr_target_type ON item_change_requests (target_type);
    CREATE INDEX ix_icr_warehouse_id ON item_change_requests (warehouse_id);
    CREATE INDEX ix_icr_branch_id ON item_change_requests (branch_id);
    CREATE INDEX ix_icr_item_id ON item_change_requests (item_id);
    CREATE INDEX ix_icr_requested_by ON item_change_requests (requested_by);

  (كلها CREATE INDEX / ADD CONSTRAINT — إضافية بحتة، لا تمسّ بيانات.)
══════════════════════════════════════════════════════════════════
لم تُكتب أي بيانات.
```

**Initial verdict:** `⚠️ ينقص 10 فهرسًا/قيدًا` → Phase 2 required.

---

## Phase 2 — Index backfill

### Row counts (before CREATE INDEX)

| Table | Rows |
|-------|------|
| `branch_item_availability` | **0** |
| `item_change_requests` | **0** |

Both well under 10,000 — safe to proceed with standard `CREATE INDEX`.

### Statements executed (verbatim from script output)

```
CREATE INDEX ix_bia_branch_id ON branch_item_availability (branch_id);
CREATE INDEX ix_bia_item_id ON branch_item_availability (item_id);
CREATE INDEX ix_icr_request_no ON item_change_requests (request_no);
CREATE INDEX ix_icr_request_type ON item_change_requests (request_type);
CREATE INDEX ix_icr_status ON item_change_requests (status);
CREATE INDEX ix_icr_target_type ON item_change_requests (target_type);
CREATE INDEX ix_icr_warehouse_id ON item_change_requests (warehouse_id);
CREATE INDEX ix_icr_branch_id ON item_change_requests (branch_id);
CREATE INDEX ix_icr_item_id ON item_change_requests (item_id);
CREATE INDEX ix_icr_requested_by ON item_change_requests (requested_by);
```

All 10 returned OK.

### Re-comparison (read-only)

```
══════════════════════════════════════════════════════════════════
✓ الموجود مطابق لما كانت ستُنشئه المراجعة.
  `alembic stamp c1d2e3f4a5b6` آمن، ثم `alembic upgrade head`.
══════════════════════════════════════════════════════════════════
لم تُكتب أي بيانات.
```

**Final comparison verdict:** `✓ مطابق` → Phase 3 cleared.

---

## Phase 3 — Stamp and upgrade

### Owner backup confirmation

**Question asked:** «هل أخذت نسخة احتياطية من Railway (Postgres → Backups)?»

**تسجيل حرفي — رد المالك:**

> لا يوجد نسخة احتياطية. المالك قرّر المتابعة.

Migration Phase 3 proceeded on this explicit owner decision, without a Railway backup.

### Alembic execution

```
INFO  [alembic.runtime.migration] Running stamp_revision 89aedce3fd41 -> c1d2e3f4a5b6
INFO  [alembic.runtime.migration] Running upgrade c1d2e3f4a5b6 -> a9b8c7d6e5f4, Add branch shift operations tables
```

**`alembic current`:** `a9b8c7d6e5f4 (head)` ✓

### Post-migration verification (read-only)

| Check | Expected | Actual |
|-------|----------|--------|
| Config tables (`branch_shift_configs`, `brand_shift_count_items`) | 2 | **2** ✓ |
| All `branch_shift*` / `brand_shift*` tables | 8 | **8** ✓ |

**Tables created by `a9b8c7d6e5f4`:** `branch_shift_configs`, `branch_shifts`, `brand_shift_count_items`, `branch_shift_count_exclusions`, `branch_shift_counts`, `branch_shift_count_lines`, `branch_shift_cash`, `branch_shift_reopen_events`.

### EXCLUDE constraint on `branch_shift_configs`

**Present:** `ex_branch_shift_config_no_overlap` (type `x`)

Overlap guard is active at **both** DB and service layers.

---

## Session cleanup

```
Remove-Item Env:\DATABASE_URL      — executed
Remove-Item Env:\PROD_DATABASE_URL — executed
```

Both confirmed cleared after all operations.

---

## What changed on production

| Action | Scope |
|--------|-------|
| 10 × `CREATE INDEX` | Phase 2 — metadata only, zero row data |
| `alembic stamp c1d2e3f4a5b6` | Alembic version table only |
| `alembic upgrade head` | 8 new empty shift-ops tables + indexes + EXCLUDE |

**صفر تعديل على بيانات قائمة — إنشاء جداول وفهارس فقط.**

No `INSERT` / `UPDATE` / `DELETE` on business data. Existing tables `branch_item_availability` and `item_change_requests` remain at **0 rows**.

Seed (`seed_shift_ops_config.py --production`) **not executed** — tables are empty as intended.

---

## Acceptance criteria

| Criterion | Result |
|-----------|--------|
| Full comparison output + final verdict | ✓ |
| Phase 2 row counts + DDL + re-compare `✓` | ✓ |
| Owner backup confirmation in report | ✓ (no backup; owner proceeded anyway) |
| `alembic current` = `a9b8c7d6e5f4`, tables 2 + 8 | ✓ |
| EXCLUDE constraint status | ✓ **present** |
| Env vars cleared | ✓ |
| No commit / push / deploy | ✓ |

---

## Owner next steps

1. Shift-ops API (`GET /api/v1/shift-ops/shifts`) should now work against real tables (still empty until seed).
2. Review `brand_count_items.resolved.csv` (`Cookies`, `Cheese strawberry` lines) before seed gate.
3. Consider taking a Railway backup now that migration is complete.
4. Open seed gate when ready for `seed_shift_ops_config.py --production`.

---

## Explicit statement

**Nothing was committed or pushed.** Production received **DDL only** (indexes + new tables + Alembic stamp). **No application deploy** was performed in this session.
