# LAN Trial Database Reset Procedure

**Purpose:** Prepare a **fresh** PostgreSQL database for LAN Trial.  
**Policy:** Simulation DB ≠ LAN Trial DB. Do **not** reuse the Phase 8 simulation database.

**This document is procedural only.** Phase 9 does not execute these steps.

---

## Prerequisites

- PostgreSQL server reachable from LAN trial host
- `raed_inventory/backend/.env` (or LAN-specific env) with `DATABASE_URL` pointing to the **new** database
- Alembic head: `c1d2e3f4a5b6`
- Workbook: `classified_supply_items.xlsx` at repo root (or documented path)
- Operator has run password rotation per `PASSWORD_ROTATION_CHECKLIST.md`

---

## Procedure (exact order)

### 1. Create fresh PostgreSQL database

```sql
CREATE DATABASE raed_inventory_lan_trial
  WITH ENCODING 'UTF8'
       LC_COLLATE='en_US.UTF-8'
       LC_CTYPE='en_US.UTF-8'
       TEMPLATE template0;
```

Create a dedicated DB user with least privilege on this database only.

Set `DATABASE_URL` in LAN env file, for example:

```text
postgresql+psycopg2://lan_user:STRONG_PASSWORD@lan-host:5432/raed_inventory_lan_trial
```

Verify **not** pointing at:

- SQLite default
- Any database used for Phase 4–8 tests or Phase 8 simulation

---

### 2. Run Alembic upgrade head

From `raed_inventory/backend`:

```powershell
cd raed_inventory\backend
$env:ENV_FILE = ".env.lan"   # or your LAN env file
alembic upgrade head
alembic current
```

**Expected:** `c1d2e3f4a5b6 (head)`

**Do not** rely on `Base.metadata.create_all()` on PostgreSQL. Runtime schema creation is disabled for PostgreSQL (`startup_schema.py`).

---

### 3. Import official branches and base master data

Run prerequisite seeds in order (from `raed_inventory/backend`):

```powershell
python seed_supply_chain_demo.py      # brands, sections, base roles (PostgreSQL-safe)
python seed_official_branches.py      # 23 official branches + warehouses
python backfill_official_kitchens.py  # if used in your environment
```

Confirm warehouses `WH-DM-1` and `WH-RY-1` exist.

---

### 4. Import official users

```powershell
$env:PHASE2_DEMO_PASSWORD = "<operator-chosen-strong-password>"
python seed_phase2_official_users.py
```

**After API startup:** If deployment bootstrap runs, re-run `seed_phase2_official_users.py` post-startup so demo passwords are not overwritten by `Admin@2025` bootstrap (`USER_SCOPE_MATRIX_REPORT.md`).

Official users include: branch users, area managers, kitchen section managers, warehouse users, delivery users (`area_dammam_onda`, `branch_onda_1_arkan`, etc.).

---

### 5. Import official item master

```powershell
python import_classified_supply_items.py
```

Review:

```text
outputs/item_master_rejected_rows.csv
```

Confirm branch request dropdowns show active, requestable, brand-scoped items (no RAW, no NOT_REQUESTABLE).

---

### 6. Validate assignments

Run verification queries or Phase 2 scope checks:

| Check | Expected |
|-------|----------|
| Area managers | Active `AreaManagerAssignment` rows for city + brand |
| Delivery users | `warehouse_id` is NOT NULL (`delivery_dammam` → `WH-DM-1`) |
| Branch users | `branch_id` matches official branch codes |
| Kitchen managers | `KitchenSectionAssignment` matches section + city |
| Branch ↔ brand | `BranchBrand` links for each trial branch |

Optional automated check:

```powershell
$env:RATE_LIMIT_ENABLED = "false"
$env:PHASE2_API_BASE = "http://localhost:8010"
python -m pytest tests/test_phase2_user_scope.py -v --tb=short
```

---

### 7. Verify no simulation data exists

On the **LAN trial database only**, confirm counts are baseline — not Phase 8 volumes:

| Table | Must NOT match simulation DB |
|-------|------------------------------|
| `branch_requests` | ≠ ~3,742 (simulation total) |
| `production_orders` | ≠ ~3,177 |
| `warehouse_lines` | ≠ ~5,228 |
| `delivery_orders` | ≠ ~4,739 |
| `audit_logs` | ≠ ~45,500 |

Fresh DB after seeds only should have **zero** supply-chain workflow rows until operators create trial requests.

```sql
SELECT COUNT(*) FROM branch_requests;
SELECT COUNT(*) FROM production_orders;
SELECT COUNT(*) FROM warehouse_lines;
SELECT COUNT(*) FROM delivery_orders;
```

All should be **0** before trial operations begin.

---

### 8. Verify kitchen hygiene (official kitchens only)

Run on the **LAN trial database** before go-live:

```powershell
cd raed_inventory\backend
python validate_lan_kitchen_hygiene.py --strict-lan-trial --write-report
```

**Required:** only official kitchens:

- Kitchen Dammam (or `Official Kitchen – Dammam`)
- Kitchen Riyadh (or `Official Kitchen – Riyadh`)

**Forbidden on LAN trial DB:** `Flow Kitchen`, `PW Kitchen`, Playwright/test/demo kitchens.

Dev databases may contain extra test kitchens — use `--strict-lan-trial` only when validating the dedicated LAN trial DB. Do **not** auto-delete dev data.

Report: `LAN_KITCHEN_HYGIENE_REPORT.md`

---

### 9. Verify passwords rotated

Complete `PASSWORD_ROTATION_CHECKLIST.md` before proceeding.

Confirm:

- No operator uses `Raed@Demo2026`, `Raed@2025`, or `Admin@2025` in LAN trial
- `PHASE2_DEMO_PASSWORD` set to operator-chosen secret
- Deployment bootstrap passwords overridden post-startup

---

### 10. Smoke test login

Start API (LAN host):

```powershell
$env:RATE_LIMIT_ENABLED = "false"   # local shell only if multi-user demo session
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Verify login for each role class:

| User | Role |
|------|------|
| `branch_onda_1_arkan` | Branch |
| `area_dammam_onda` | Area manager |
| `kitchen_dammam_bakery_and_sweets_mgr` | Kitchen |
| `warehouse_dammam_user` | Warehouse |
| `delivery_dammam` | Delivery |
| `super.admin` | Admin |

```powershell
curl http://localhost:8010/api/v1/ready
```

Expected: HTTP 200.

---

### 10. Start LAN Trial

- Point LAN frontend to LAN API (`VITE_API_BASE_PATH` / proxy)
- Set `ALLOWED_ORIGINS` for LAN frontend IP (`USER_SCOPE_MATRIX_REPORT.md`)
- Load warehouse opening stock for WAREHOUSE-sourced items before warehouse issue tests
- Document Onda bakery vs pizza kitchen item → section mapping for operators
- Accept **C-01** JWT localStorage risk on controlled LAN only

---

## What NOT to run on LAN trial DB

| Script | Reason |
|--------|--------|
| `simulation_data_generator.py` | Simulation data forbidden on LAN trial DB |
| `seed_4months.py` | Idempotency unknown (`ENVIRONMENT_READY_REPORT.md`) |
| Phase 4–8 automated test suites against LAN DB | Would pollute trial data unless isolated |

---

## Rollback

If LAN trial DB is contaminated:

1. Drop database
2. Restart from step 1

Do not attempt to delete simulation rows in place — use fresh database per policy.

---

*Operator procedure — not executed in Phase 9 audit.*
