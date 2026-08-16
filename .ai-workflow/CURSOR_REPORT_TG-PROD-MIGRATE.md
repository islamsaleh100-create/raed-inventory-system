# CURSOR_REPORT — TG-PROD-MIGRATE

## Task ID
TG-PROD-MIGRATE

## Status
IMPLEMENTED — **Phase 2 NOT executed** (blocked at Phase 1.2)

## Executor
Cursor

## Date
2026-08-16

---

## Phase 0 — Commit verification

```
commit 0d619e60521069cba348ddb9d54bef75e2e508c7
Author: Islam Saleh <islamsaleh100@gmail.com>
Date:   Sun Aug 16 15:31:52 2026 +0300

    fix(trial-guard): legacy screen block is opt-in via VITE_TRIAL_LEGACY_BLOCK

 .ai-workflow/CURSOR_REPORT_TG-TRIAL-GUARD-CHECK.md | 140 +++++++++++++++++++++
 .ai-workflow/TASK_GATE_TG-TRIAL-GUARD-CHECK.md     | 134 ++++++++++++++++++++
 .../backend/seed_shift_ops/check_blocked_roles.py  |  74 +++++++++++
 raed_inventory/frontend/src/utils/trialLegacy.js   |   4 +
 4 files changed, 352 insertions(+)
```

```
On branch main
Your branch is up to date with 'origin/main'.

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	.ai-workflow/TASK_GATE_TG-PROD-MIGRATE.md

nothing added to commit but untracked files present (use "git add" to track)
```

**Result:** ✓ `raed_inventory/frontend/src/utils/trialLegacy.js` **present by name** in `git show --stat HEAD`. Trial-guard fix is on `main` at `0d619e6`. Proceed to Phase 1.

---

## Phase 1 — Pre-flight

### 1.1 Connection

- Railway linked: project `efficient-harmony`, Postgres service, `production` environment.
- `DATABASE_URL` set from `DATABASE_PUBLIC_URL` (session only; not written to any file).

### 1.2 Backup — **FAILED (stop condition)**

Attempt 1 — `pg_dump` not on PATH.

Attempt 2 — full path `C:\Program Files\PostgreSQL\16\bin\pg_dump.exe`:

```
pg_dump: error: aborting because of server version mismatch
pg_dump: detail: server version: 18.4 (Debian 18.4-1.pgdg13+1); pg_dump version: 16.13
```

Resulting file was **0 bytes** (invalid). File **deleted** — no backup on disk.

Attempt 3 — `railway run pg_dump`: not available in Railway shell context.

Docker: not installed on this machine.

**Per gate:** backup mandatory before any write. **Phase 2 not started.**

### 1.3 Production revision + pending migrations

**Production `alembic current`:** `89aedce3fd41`

**Head (local):** `a9b8c7d6e5f4`

**Pending revisions (in order):**

| # | Revision | File | Description |
|---|----------|------|-------------|
| 1 | `c1d2e3f4a5b6` | `20260614_0001_c1d2e3f4a5b6_branch_item_availability_and_item_change_requests.py` | branch_item_availability + item_change_requests |
| 2 | `a9b8c7d6e5f4` | `20260815_0001_d4e5f6a7b8c9_branch_shift_operations.py` | branch shift operations (8 tables) |

### 1.4 Migration content review (additive-only)

| Revision | Verdict |
|----------|---------|
| `c1d2e3f4a5b6` | **2 جدولًا جديدًا** — `create_table` ×2, `create_index`, `UniqueConstraint`, FKs only — **إضافي بحت ✔** |
| `a9b8c7d6e5f4` | **8 جداول جديدة** — `create_table` ×8, indexes, CHECK, `CREATE EXTENSION IF NOT EXISTS btree_gist`, EXCLUDE on `branch_shift_configs` (same migration) — **إضافي بحت ✔** |

No `drop_table`, `drop_column`, `alter_column` on existing tables, or data `INSERT`/`UPDATE`/`DELETE` in either pending revision.

### 1.4b — Additional runtime blocker (discovered during pre-flight)

Read-only query on production **before** any migration:

| Table | Exists on prod? |
|-------|-----------------|
| `branch_item_availability` | **Yes (1)** |
| `item_change_requests` | **Yes (1)** |
| `branch_shift_configs` | No (0) |
| `brand_shift_count_items` | No (0) |
| All `branch_shift*` / `brand_shift*` | **0 tables** |

These two tables were created at runtime by `startup_schema.py` (as documented in migration `c1d2e3f4a5b6`). Running `alembic upgrade head` as-is would **fail** at revision `c1d2e3f4a5b6` with “relation already exists”, even after a valid backup.

**Owner action needed (outside this gate's allowed commands):** after backup, either `alembic stamp c1d2e3f4a5b6` (if schema matches) then `upgrade head`, or adjust migration to be idempotent — **human decision**.

---

## Phase 2 — Migration execution

**NOT EXECUTED.**

Reasons (both must be resolved before retry):

1. No valid `pg_dump` backup (client 16 vs server 18.4).
2. Pending revision `c1d2e3f4a5b6` would collide with existing tables.

No `alembic upgrade head` was run. **Zero DDL applied to production in this session.**

---

## Session cleanup

- `Remove-Item Env:\DATABASE_URL` — **executed**, confirmed cleared.

---

## Other changes (gate-allowed)

- `.gitignore` — added `*.dump` under “Local databases and journals” so `_backup_pre_shiftops.dump` cannot be committed accidentally.

---

## Acceptance criteria

| Criterion | Result |
|-----------|--------|
| Phase 0 git output + trialLegacy.js confirmed | ✓ |
| Phase 1.2 backup file exists with size > 0 | ✗ **blocked** |
| Phase 1.3 current + pending list | ✓ |
| Phase 1.4 one-line verdict per revision | ✓ |
| Phase 2 alembic at head + table counts | ✗ **not run** |
| DATABASE_URL cleared | ✓ |
| Zero modification of existing production data | ✓ (read-only only) |
| No commit / push / deploy | ✓ |

---

## Owner next steps

1. **Install PostgreSQL 18 client tools** (or use a machine/container with `pg_dump` 18+) and create backup:
   ```powershell
   pg_dump --dbname=$env:DATABASE_URL -Fc -f C:\raed_inventory_system\_backup_pre_shiftops.dump
   ```
   Verify file size **> 0**.

2. **Resolve `c1d2e3f4a5b6` collision:** tables already exist from runtime DDL. Likely path:
   ```powershell
   alembic stamp c1d2e3f4a5b6   # after verifying schema matches migration
   alembic upgrade head         # applies only a9b8c7d6e5f4 (8 shift-ops tables)
   ```
   Owner must verify column/index parity before stamp.

3. Re-open gate or issue follow-up gate for Phase 2 only after (1) and (2).

4. **Seed remains out of scope** — tables will be empty after migration until `seed_shift_ops_config.py --production` is approved separately.

---

## Explicit statement

**Nothing was merged, pushed, or deployed.** **No production writes** — only read-only SELECT and Alembic introspection (`current` / `history`). **Zero modification of existing table data — no tables created** in this session.
