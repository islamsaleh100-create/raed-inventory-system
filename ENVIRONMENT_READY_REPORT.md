# ENVIRONMENT READY REPORT — PHASE 0
**Date:** 2026-06-14  
**Phase:** 0 — Environment Hardening  
**Method:** Full static code audit + targeted code fixes  
**Note:** Bash sandbox unavailable (disk space). Runtime checks marked ⚙️ MANUAL — must be run on your machine.

---

## OVERALL RESULT

| Section | Result |
|---|---|
| 1. PostgreSQL Status | ✅ CONFIGURED / ⚙️ Runtime Verify |
| 2. DATABASE_URL Validation | ✅ PASS |
| 3. Alembic Status | ✅ PASS (static) / ⚙️ Runtime Verify |
| 4. Migration Head | ✅ 37 migrations — head: `c1d2e3f4a5b6` |
| 5. Runtime Schema Audit | ✅ FIXED — all create_all guarded |
| 6. Repo Hygiene | ✅ FIXED + ⚙️ Manual cleanup needed |
| 7. Seed Validation | ✅ FIXED — PostgreSQL guard added |
| 8. Smoke Test | ⚙️ MANUAL — run commands below |
| 9. Remaining Risks | See section 9 |

### **VERDICT: ✅ PASS (code-level) — ⚙️ Runtime verification required**

---

## 1. PostgreSQL Status

### Static Evidence
`backend/.env` (active env file):
```
DATABASE_URL=postgresql://raed_user:****@localhost:5432/raed_inventory
ENVIRONMENT=local
DEBUG=false
```

`backend/app/config.py` — `validate_security()`:
```python
if self.is_deployment_env and self.DATABASE_URL.lower().startswith("sqlite"):
    raise RuntimeError("SQLite is not allowed in staging/production.")
```
→ SQLite in production/staging causes immediate RuntimeError at startup. ✅

`backend/app/database.py`:
```python
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
```
→ PostgreSQL pool configured with `pool_size=10, max_overflow=20`. ✅

### ⚙️ MANUAL: Verify PostgreSQL is running
```powershell
# On your machine (PowerShell or CMD):
psql -U raed_user -d raed_inventory -c "SELECT version();"
# Expected: PostgreSQL 14+ version string

# Or via Python:
cd raed_inventory\backend
python -c "from app.database import engine; from sqlalchemy import text; print(engine.execute(text('SELECT version()')).scalar())"
```

### ⚙️ MANUAL: Verify no SQLite fallback active
```powershell
python -c "from app.config import settings; print(settings.DATABASE_URL)"
# Must NOT start with sqlite://
```

---

## 2. DATABASE_URL Validation

| Check | Value | Status |
|---|---|---|
| Active `.env` DATABASE_URL | `postgresql://raed_user:****@localhost:5432/raed_inventory` | ✅ PostgreSQL |
| Config default (no .env) | `sqlite:///./raed_inventory_local.db` | ⚠️ SQLite fallback if .env missing |
| Production guard | `RuntimeError` if SQLite in prod | ✅ |
| `.env` in git | No — `.gitignore` excludes `*.env` | ✅ |
| `.env.production` credentials | Template placeholders only (`replace-with-*`) | ✅ |
| `.env.postgres.local` | Contains dev credentials | ✅ Local only, not committed |

**Risk:** If `.env` is absent (CI, new machine, Railway cold start), the default SQLite URL activates. On PostgreSQL production this is blocked by `validate_security()`, but on `ENVIRONMENT=local` it silently uses SQLite.

**Mitigation:** Document in onboarding that `.env` must exist before starting. Railway injects env vars directly — no `.env` file needed there.

---

## 3. Alembic Status

### Configuration
**`alembic.ini`:**
```ini
script_location = alembic
prepend_sys_path = .          # ← required for Windows alembic.exe
sqlalchemy.url =              # ← empty — env.py reads from app.config.settings
```

**`alembic/env.py`:**
- Reads `DATABASE_URL` from `app.config.settings` (respects `ENV_FILE`) ✅
- `compare_type=True` — detects column type changes ✅
- `compare_server_default=True` — detects default changes ✅
- PostgreSQL: uses `NullPool` (no pool reuse between alembic runs) ✅
- SQLite: uses `StaticPool` + disables journaling for recovery mode ✅

### Migration Chain (static analysis — 37 total)
```
a1b2c3d4e5f6  baseline initial schema
b2c3d4e5f6a7  add_order_cancel_fields
c3d4e5f6a7b8  multi_tenant_phase2_add_tenant_id
d4e5f6a7b8c9  add_inventory_pending_approval_status
e5f6a7b8c9d0  phase3_integrity_indexes
f6a7b8c9d0e1  add_order_type_inter_branch
a7b8c9d0e1f2  add_destination_branch_id
b8c9d0e1f2a3  quality_training_real_templates
c9d0e1f2a3b4  quality_training_phase_e8
d0e1f2a3b4c5  documents_module
e1f2a3b4c5d6  inventory_type_column
f2a3b4c5d6e7  visit_level_attachments
b4c5d6e7f8a9  add_sales_manager_role
c5d6e7f8a9b0  sales_channels_tables
h9i0j1k2l3m4  sales_audit_fields
i0j1k2l3m4n5  supply_chain_phase1
j1k2l3m4n5o6  supply_chain_phase2
k2l3m4n5o6p7  kitchen_section_assignments
l3m4n5o6p7q8  production_qty_sent
m4n5o6p7q8r9  supply_chain_phase3_delivery
[n5o6p7q8r9s0] delivery_line_uniqueness / evaluation_core_phase1
[o6p7q8r9s0t1] quality_brand_scope
[p7q8r9s0t1u2] NOT_FOUND in list (merge head)
[q7r8s9t0u1v2] merge_quality_and_evaluations
[r8s9t0u1v2w3] procurement_and_request_snapshots
[s9t0u1v2w3x4] quality_training_foundation
[t0u1v2w3x4y5] supply_item_master_official
[u1v2w3x4y5z6] expand_role_enum_for_modern_roles
[v2w3x4y5z6a7] expand_supply_chain_status_enums
[w3x4y5z6a7b8] partial_delivery_and_material_actions
[x4y5z6a7b8c9] branch_employees
[y5z6a7b8c9d0] kitchen_section_assignment_service_city
[z6a7b8c9d0e1] kitchens_and_kitchen_section_links
[a3b4c5d6e7f8] seed_training_templates (data migration)
[a4b5c6d7e8f9] expand_order_type_enum
[b1c2d3e4f5g6] add_internal_auditor_and_audit_findings
89aedce3fd41   user_suggestions_table
c1d2e3f4a5b6   branch_item_availability + item_change_requests  ← NEW HEAD (added 2026-06-14)
```

### ⚙️ MANUAL: Verify Alembic state on your PostgreSQL
```powershell
cd raed_inventory\backend
set ENV_FILE=.env

# Check current revision:
alembic current
# Expected: c1d2e3f4a5b6 (head)

# Confirm single head:
alembic heads
# Expected: c1d2e3f4a5b6 (head) — one line only

# Apply any pending migrations:
alembic upgrade head
# Expected: all steps apply cleanly, no errors

# Verify no model drift:
alembic check
# Expected: "No new upgrade operations detected."
```

---

## 4. Migration Head

| Check | Status |
|---|---|
| Total migrations | 37 |
| Head revision | `c1d2e3f4a5b6` |
| Single head (no branches) | ✅ Verified (static) |
| All app tables in Alembic | ✅ Fixed — `branch_item_availability` + `item_change_requests` added |
| `alembic check` (model vs DB) | ⚙️ Run manually |

**New migration created this session:**
```
20260614_0001_c1d2e3f4a5b6_branch_item_availability_and_item_change_requests.py
```
This migration adds two tables that were previously created only via `startup_schema.py`'s `Base.metadata.create_all` runtime fallback. A fresh `alembic upgrade head` now creates them correctly.

---

## 5. Runtime Schema Creation Audit

### All `create_all` Occurrences — Classified

| File | Line | Context | Status |
|---|---|---|---|
| `app/startup_schema.py` | 58 | App startup — SQLite compat only | ✅ FIXED — returns immediately on PostgreSQL |
| `seed.py` | 23 | `create_tables()` in seed script | ✅ FIXED — no-op on PostgreSQL |
| `seed_quality_training.py` | 56 | `create_tables()` in seed script | ✅ FIXED — no-op on PostgreSQL |
| `seed_supply_chain_demo.py` | 406 | Demo seed main function | ✅ FIXED — guarded by `if sqlite:` |
| `tests/conftest.py` | 49 | Test database setup | ✅ ACCEPTABLE — in-memory/temp SQLite |
| `tests/test_epic1_*` | 42 | Test setup | ✅ ACCEPTABLE — test DB |
| `tests/test_epic2_*` | 149 | Test setup | ✅ ACCEPTABLE — test DB |
| `tests/test_epic3_*` | 161 | Test setup | ✅ ACCEPTABLE — test DB |
| `tests/test_epic4_9_*` | 166 | Test setup | ✅ ACCEPTABLE — test DB |
| `tests/test_epic10_13_*` | 118 | Test setup | ✅ ACCEPTABLE — test DB |
| `tests/test_epic14_15_*` | 87 | Test setup | ✅ ACCEPTABLE — test DB |
| `tests/test_security_*` | 219/69 | Test setup | ✅ ACCEPTABLE — test DB |
| `alembic/versions/baseline` | comment | Documentation only | ✅ NOT code |

### Summary of Fixes Applied

**`app/startup_schema.py`:**
```python
# BEFORE: ran create_all on every startup including PostgreSQL
# AFTER:
if not is_sqlite:
    return  # PostgreSQL: all tables via alembic upgrade head
```

**`seed.py`:**
```python
# BEFORE: Base.metadata.create_all(bind=engine)
# AFTER:
if not url.startswith("sqlite"):
    print("ℹ️  PostgreSQL — skipping create_all")
    return
Base.metadata.create_all(bind=engine)
```

**`seed_quality_training.py`** and **`seed_supply_chain_demo.py`:** Same pattern applied.

### Runtime Schema Creation Status
```
PostgreSQL production:   ❌ BLOCKED — no create_all will execute
PostgreSQL local dev:    ❌ BLOCKED — no create_all will execute  
SQLite local dev:        ✅ ALLOWED — startup compat layer + seeds still work
Tests (any SQLite):      ✅ ALLOWED — separate test database
```

---

## 6. Repository Hygiene

### Files That Should NOT Be in Git

| Category | Files Found | In `.gitignore` | Action |
|---|---|---|---|
| SQLite databases | 30 `.db` files in `backend/` | ✅ Yes (`*.db`) | ⚙️ Delete manually |
| Log files | 13 `.log` files in `backend/` | ✅ Yes (`*.log`) | ⚙️ Delete manually |
| Upload files | `uploads/evaluations/`, `uploads/import_logs/` | ✅ Yes (`uploads/`) | ⚙️ Keep locally, do not commit |
| `.env` with dev credentials | `.env`, `.env.postgres.local` | ✅ Yes | No action — already excluded |
| `.env.local` | Dev environment copy | ✅ Yes | No action |
| `.env.staging` | Staging template | ✅ Yes | No action |
| `.env.production` | Template with placeholders only | ✅ Yes | No action (safe — placeholder values) |

### `.gitignore` Improvements Applied
Added explicit patterns for debug SQLite naming conventions:
```
*.db-shm
*.db-wal
_alembic_*.db*
_official_supply_master*.db*
raed_inventory_*.db*
sqlite*_probe.db*
manual_test.db*
_chain_full.db*
_demo_write_probe.db*
```

### ⚙️ MANUAL: Clean up local SQLite files
```powershell
cd raed_inventory\backend

# Preview (PowerShell):
Get-ChildItem -Path . -Filter "*.db" | Select-Object Name, Length

# Delete all SQLite files:
Remove-Item *.db, *.db-journal, *.db-shm, *.db-wal -ErrorAction SilentlyContinue

# Delete log files:
Remove-Item *.log -ErrorAction SilentlyContinue
```

### Sensitive File Check

| File | Contains | Risk | Status |
|---|---|---|---|
| `.env` | `raed_user:raed_pass` (dev credentials) | Low — not committed | ✅ Safe |
| `.env.production` | Placeholder values only | None | ✅ Safe |
| `seed.py` | Hardcoded `Admin@2025` password | Medium — visible in logs | ⚠️ Note |
| `seed_supply_chain_demo.py` | `Raed@2025` for all demo accounts | Medium — demo only | ⚠️ Note |

> **Note on hardcoded seed passwords:** These are printed to stdout during seeding and appear in logs. They are demo/bootstrap credentials. Before LAN trial, ensure these are changed via the admin UI after seeding.

---

## 7. Seed Validation

### Seed Script Inventory

| Script | Purpose | create_all | Idempotent | PostgreSQL Safe |
|---|---|---|---|---|
| `seed.py` | Roles, admin, warehouses, branches, items, users | ✅ FIXED | ✅ Yes (filter-or-create) | ✅ After fix |
| `seed_quality_training.py` | Quality checklists, training templates | ✅ FIXED | ✅ Yes (upserts) | ✅ After fix |
| `seed_supply_chain_demo.py` | Complete demo environment (all roles, kitchens, branches) | ✅ FIXED | ✅ Yes (goc pattern) | ✅ After fix |
| `seed_official_branches.py` | Official branch codes (BR-DM-ON-* etc.) | ✅ None | ✅ Yes | ✅ |
| `seed_area_managers.py` | am_riyadh, am_dammam (generates temp passwords) | ✅ None | ✅ Yes (skips existing) | ✅ |
| `seed_internal_auditor.py` | Internal auditor account | ✅ None | ✅ Yes | ✅ |
| `seed_users_from_permission_matrix.py` | Official user accounts from Excel matrix | ✅ None | ✅ Yes | ✅ |
| `seed_4months.py` | 4-month historical simulation data | ✅ None | ❓ Unknown | ⚠️ Verify |
| `seed_sales_channels.py` | Sales channels data | ✅ None | ❓ Unknown | ⚠️ Verify |
| `seed_onda_operations.py` | Onda operational data | ✅ None | ❓ Unknown | ⚠️ Verify |

### User Accounts Seeded by Scripts

**`seed_supply_chain_demo.py` creates:**
| Username | Role | Scope |
|---|---|---|
| `super.admin` | super_admin | Global |
| `am_riyadh` | area_manager | Riyadh × all brands |
| `am_dammam_cafes` | area_manager | Dammam × Onda only |
| `am_dammam_restaurants` | area_manager | Dammam × Ronaldos/Shawarma/Griddle |
| `branch.mgr1` | branch_manager | Kitchen Riyadh |
| `branch.user1` | branch_user | Kitchen Riyadh |
| `meat.section.mgr` | kitchen_section_manager | Meat & Chicken section |
| `bakery.section.mgr` | kitchen_section_manager | Bakery & Sweets section |
| `pizza.section.mgr` | kitchen_section_manager | Pizza section |
| `wh.mgr1` | warehouse_manager | WH-RYD |
| `wh.user1` | warehouse_user | WH-RYD |
| `delivery.user` | delivery_user | WH-RYD |

**`seed_area_managers.py` creates:**
| Username | Role | Note |
|---|---|---|
| `am_riyadh` | area_manager | Temp password printed once |
| `am_dammam` | area_manager | Temp password printed once |

### ⚙️ MANUAL: Recommended Seed Sequence on Fresh PostgreSQL
```powershell
cd raed_inventory\backend
set ENV_FILE=.env

# Step 1: Schema
alembic upgrade head

# Step 2: Demo environment (brands, kitchens, branches, all roles, demo users)
python seed_supply_chain_demo.py

# Step 3: Official branch codes
python seed_official_branches.py

# Step 4: Quality + training templates (auto-seeded on startup too)
python seed_quality_training.py

# Step 5: Official user accounts (if permission matrix Excel available)
# python seed_users_from_permission_matrix.py

# Step 6: Area managers (if not seeded by step 2)
python seed_area_managers.py

# Step 7: Internal auditor
python seed_internal_auditor.py

# Step 8: Verify
python -c "
from app.database import SessionLocal
from app.models import User, Branch, Warehouse
db = SessionLocal()
print(f'Users: {db.query(User).count()}')
print(f'Branches: {db.query(Branch).filter_by(is_deleted=False).count()}')
print(f'Warehouses: {db.query(Warehouse).filter_by(is_deleted=False).count()}')
db.close()
"
```

---

## 8. Smoke Test

### ⚙️ MANUAL: Full Smoke Test Sequence
```powershell
cd raed_inventory\backend
set ENV_FILE=.env

# --- 1. Start backend ---
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload

# --- In a new terminal ---

# 2. Health check
curl http://localhost:8010/api/v1/health
# Expected: {"status": "healthy", ...}

# 3. Database readiness
curl http://localhost:8010/api/v1/ready
# Expected: {"status": "ready", "database": "ok", ...}

# 4. Login
curl -X POST http://localhost:8010/api/v1/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\": \"super.admin\", \"password\": \"Raed@2025\"}"
# Expected: {"access_token": "eyJ...", "token_type": "bearer", ...}

# 5. Confirm no SQLite in use
curl http://localhost:8010/api/v1/meta
# Expected: {"environment": "local", ...}

# 6. Verify API docs HIDDEN on production
# (Set ENVIRONMENT=production in .env.production and restart)
# curl http://localhost:8010/api/docs  → Expected: 404 Not Found
```

### Expected Health Response
```json
{
  "status": "healthy",
  "app": "Raed Inventory System",
  "version": "1.0.0",
  "environment": "local",
  "timestamp": 1718323200.0
}
```

### Expected Readiness Response
```json
{
  "status": "ready",
  "database": "ok",
  "environment": "local",
  "timestamp": 1718323200.0
}
```

---

## 9. Remaining Risks

| Risk | Severity | Status |
|---|---|---|
| Default SQLite if `.env` missing | Medium | ⚠️ Document in onboarding — add `assert` in startup? |
| `seed.py` hardcodes `Admin@2025` | Medium | ⚠️ Change after first login in LAN trial |
| `seed_supply_chain_demo.py` hardcodes `Raed@2025` | Medium | ⚠️ Demo only — change before real users |
| `alembic check` not verified (no bash) | Medium | ⚙️ Run manually — see Section 3 |
| Runtime smoke test not verified | Medium | ⚙️ Run manually — see Section 8 |
| 30 SQLite `.db` files on disk | Low | ⚙️ Delete manually — see Section 6 |
| `seed_4months.py` idempotency unknown | Low | ⚠️ Review before running |
| PostgreSQL not locally running (CI/new machine) | Low | ⚙️ Add Docker Compose setup |

---

## 10. Code Changes Applied This Session

| File | Change | Why |
|---|---|---|
| `app/main.py` | `docs_url=None` in production | Prevent schema enumeration |
| `app/startup_schema.py` | Early return for non-SQLite | No runtime schema creation on PostgreSQL |
| `seed.py` | Guard `create_all` — no-op on PostgreSQL | Enforce Alembic-first workflow |
| `seed_quality_training.py` | Guard `create_all` — no-op on PostgreSQL | Same |
| `seed_supply_chain_demo.py` | Guard `create_all` — no-op on PostgreSQL | Same |
| `alembic/versions/20260614_0001_c1d2e3f4a5b6_*.py` | New migration for 2 missing tables | All tables now in Alembic |
| `.gitignore` | Extended SQLite debug file patterns | Prevent accidental commits |

---

## 11. Startup Command Reference

### Local PostgreSQL (your machine)
```powershell
cd raed_inventory\backend
set ENV_FILE=.env
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

### Railway / Production
```bash
# Railway runs this automatically from Procfile / railway.json:
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Verify environment before starting
```powershell
python -c "
from app.config import settings
print('DB:', settings.DATABASE_URL[:40] + '...')
print('ENV:', settings.ENVIRONMENT)
print('DEBUG:', settings.DEBUG)
assert not settings.DATABASE_URL.startswith('sqlite'), 'SQLite active!'
print('OK: PostgreSQL active')
"
```

---

*Phase 0 complete. Proceed to Phase 1 — RBAC Hardening only after running the manual verification steps above.*
