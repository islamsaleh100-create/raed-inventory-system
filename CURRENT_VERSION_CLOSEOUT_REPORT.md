# Current Version Closeout Report

**Date:** 2026-04-26  
**Environment:** Local PostgreSQL runtime  
**App URL:** `http://127.0.0.1:8010/login`

---

## Final program closeout (staging handoff)

### 1. Overall verdict

The **current program** is **closed for staging handoff**: official branches and matrix users are coherent, operational UIs prefer **active-only** branches (demo rows stay manageable from admin), kitchen city scoping is **implemented and backfillable**, and automated checks (pytest + API smoke script) pass against the expected local stack. This remains **staging-appropriate**, not a full **production** certification (delivery territory model, legacy `DEMO-WH-1`, and global kitchen section names are still simplifications).

### 2. What is now fully closed

- PostgreSQL baseline with official branches active and legacy demo branches inactive (not deleted).
- Permission-matrix users seeded; duplicate demo users deactivated.
- Warehouse-by-city and delivery-by-warehouse scoping tightened and verified in prior passes; this pass did not regress them.
- Branch employees (model/API/UI) and supply-chain flow through partial delivery / kitchen material requests.
- **Staging prep (this pass):** branch pickers in branch employees, documents, admin stock context, and analytics dashboards use **`active_only: true`** so inactive demo branches do not appear in normal operations; full branch list remains available where admins manage branches.
- **`backend/.env.example`:** short staging handoff notes (migrations, seeds, backfill, optional `RATE_LIMIT_AUTH` for bulk QA).
- **`backend/scripts/verify_matrix_roles_api.py`:** httpx smoke for all listed matrix roles + negative probe (delivery → production orders **403**), with spacing and token reuse so **`RATE_LIMIT_AUTH` (20/min)** does not false-fail the script.
- **Handoff docs (repo root):** `STAGING_HANDOFF_REPORT.md` (ordered staging steps), `PRODUCTION_HARDENING_PLAN.md` (next phase backlog), `FINAL_PHASE_CLOSEOUT_HANDOFF.md` (index).

### 3. Role-by-role verification summary

**Method:** `python scripts/verify_matrix_roles_api.py` against `http://127.0.0.1:8010` (full run: all **OK**, **NEG** `403`). **Not** a manual browser click-through for every screen.

| User (sample) | Login + probe | Forbidden check |
|---------------|---------------|-----------------|
| super.admin, admin | `/master/branches?active_only=true` **200** | — |
| area_dammam_onda, area_dammam_restaurants, area_riyadh_all | `/branch-requests` **200** | — |
| branch_onda_13_al_malqa, branch_pizza_4_riyadh_takhasosy, branch_shawarma_olaya, branch_griddle | `/branch-requests` **200** | — |
| All six `kitchen_*_mgr` (Dammam + Riyadh × sections) | `/production-orders` **200** | — |
| warehouse_dammam_manager/user, warehouse_riyadh_manager/user | `/warehouse-lines` **200** | — |
| delivery_dammam, delivery_riyadh | `/delivery-orders/ready` **200** | delivery_dammam → `/production-orders` **403** |

**Pytest:** `tests/test_supply_chain_phase1_branch_requests.py` + `tests/test_branch_employees.py` — **73 passed** (2026-04-26; includes warehouse `receive`, master kitchens, `POST /master/kitchens`, and **`GET /api/v1/ready`**). Staging DB: **`alembic upgrade head`** through **`z6a7b8c9d0e1`**, then **`python backfill_official_kitchens.py`**. UI: **`/supply-chain/control`** (auto-refresh, queue previews, alerts breakdown); **`/admin/kitchens`** for kitchen CRUD; login default for supply-chain roles → control center (admins stay on `/dashboard`). See **`PHASE_PROGRAM_FINAL_CLOSEOUT.md`** and **`STAGING_HANDOFF_REPORT.md`** for readiness vs liveness.

### 4. Issues found in this pass

- **Auth rate limit vs bulk verification:** sequential logins for 20+ users hit **`RATE_LIMIT_AUTH`** (default **20/minute**) causing **429** and a skipped **`delivery_riyadh`** until spacing and duplicate login removal were fixed.
- **Inactive demo branches** could still appear in some operational branch dropdowns (addressed via `active_only: true` on those loaders).

### 5. Fixes applied

- Frontend: `active_only: true` on branch lists for **BranchEmployeesPage**, **DocumentsPages**, admin **branch stock** picker in **App.jsx**, **AnalyticsDashboards** (admin branch CRUD / master branch management unchanged where full list is intended).
- Verify script: default **`VERIFY_LOGIN_DELAY_S=3.2`**, **429** retry on login, **reuse `delivery_dammam` token** for the negative probe (no second login).
- **`backend/.env.example`:** staging handoff comment block.

### 6. Files changed (this pass)

- `raed_inventory/frontend/src/pages/branch/BranchEmployeesPage.jsx`
- `raed_inventory/frontend/src/pages/documents/DocumentsPages.jsx`
- `raed_inventory/frontend/src/App.jsx`
- `raed_inventory/frontend/src/pages/admin/AnalyticsDashboards.jsx`
- `raed_inventory/backend/.env.example`
- `raed_inventory/backend/scripts/verify_matrix_roles_api.py`
- `CURRENT_VERSION_CLOSEOUT_REPORT.md` (this document)

### 7. Remaining limitations

- **Kitchen:** Section **names** are global; **city** is enforced via **`KitchenSectionAssignment.service_city`** and production-order filters tied to **destination branch city**. Rows with **`service_city = NULL`** remain **legacy-wide** for that section until backfill — run `backfill_kitchen_assignment_service_city.py` after matrix seed/migration as already documented.
- **Delivery:** Scoping is **warehouse-based**, not a full territory/routing engine.
- **Data:** **`DEMO-WH-1`** and other legacy rows may remain for history/compatibility.
- **QA script runtime:** ~80s default due to auth spacing; for faster runs, raise **`RATE_LIMIT_AUTH`** in a disposable env or export a smaller user list (not required for staging).

### 8. Staging handoff recommendation

1. **`alembic upgrade head`** on staging DB.  
2. **`seed_official_branches` / matrix user seed / `finalize_demo_branch_transition`** as applicable; **`python backfill_kitchen_assignment_service_city.py`** so kitchen managers are not left on NULL city assignments.  
3. Set **`ENVIRONMENT=staging`**, secrets and **`DATABASE_URL`** via platform config (not in repo).  
4. Run **`pytest`** on the same paths above; run **`python scripts/verify_matrix_roles_api.py`** (or temporarily relax **`RATE_LIMIT_AUTH`** only for QA).  
5. Optional: one **manual** UI pass per role on staging URLs for layout/regressions (not substituted by the API script).

---

## 1. Overall status

The current version is now in a strong **stabilized demo / official-baseline** state.

It is no longer just a demo seeded on SQLite. It now runs on PostgreSQL with:
- official branches active
- demo branches inactive
- permission-matrix users seeded
- duplicate legacy demo accounts deactivated
- branch scope materially cleaned up
- warehouse-by-city materially improved
- delivery scope materially improved

This is still **not production-ready in the strict sense**, but it is now much closer to an official operational baseline than the earlier demo build.

## 2. What is completed

### PostgreSQL runtime
- PostgreSQL is the active runtime database.
- Backend is live and responding on `8010`.
- `health` returns `200`.

### Branches
- Official branches seeded: `23`
- Old demo branches retained but operationally hidden:
  - `8` inactive demo branches
- Operational selectors now use official active branches.

### Users and permissions
- Users from `raed_user_matrix_permissions.xlsx` were seeded into the system.
- Duplicate legacy demo users were deactivated safely instead of deleted.
- Current user totals:
  - `total_users = 63`
  - `active_users = 50`
  - `inactive_users = 13`

### Branch employees
- Branch employee model/API/UI is implemented.
- Branch manager can manage employees only for own branch.
- Admin/super_admin can manage globally.

### Supply chain
- Branch Request -> Area Approval -> Auto Split -> Kitchen -> Warehouse -> Delivery was already verified previously to `DELIVERED`.
- Current persisted counts:
  - `branch_requests = 1`
  - `production_orders = 1`
  - `warehouse_lines = 2`
  - `delivery_orders = 1`

### Partial delivery / kitchen materials
- Partial delivery backend support exists.
- Kitchen material request approve / issue / reject exists.

## 3. Officialization work completed

### Official branch transition
- Old demo branches were not deleted.
- They were set to `active = False`.
- `is_deleted` remained `False`.

This preserves:
- history
- FKs
- auditability

### branch_griddle normalization
- `branch_griddle` is now attached to:
  - `BR-RY-SH-OLAYA`
  - `Shawarma Olaya`
- That branch now carries both:
  - `Shawarma`
  - `Griddle`

Verified:
- `Griddle_requestable_items = 41`
- `Shawarma_requestable_items = 42`

## 4. Warehouse / delivery improvements

### Warehouses
Current runtime now has:
- `DEMO-WH-1`
- `WH-RY-1`
- `WH-DM-1`

Operationally important warehouses:
- `WH-RY-1` = Riyadh Central Warehouse
- `WH-DM-1` = Dammam Central Warehouse

### Branch to warehouse mapping
- Official Riyadh branches now map to `WH-RY-1`
- Official Dammam branches now map to `WH-DM-1`

Verified branch distribution:
- `warehouse_id = 2` -> `6` active branches
- `warehouse_id = 3` -> `17` active branches

### Warehouse users
- `warehouse_dammam_user` -> `warehouse_id = 3`
- `warehouse_riyadh_user` -> `warehouse_id = 2`
- `warehouse_user` -> `warehouse_id = 2`

### Delivery users
- `delivery_dammam` -> `warehouse_id = 3`
- `delivery_riyadh` -> `warehouse_id = 2`
- `delivery_user` -> `warehouse_id = 2`

### Delivery scope enforcement
- Delivery backend was tightened to respect `warehouse_id` when present.
- After backend restart, the previous leak from the old delivery order disappeared from scoped delivery users.

Verified live after restart:
- `delivery_dammam` sees `warehouse_id = 3`
- `delivery_riyadh` sees `warehouse_id = 2`
- `/delivery-orders` for both scoped users returned `0`, which is correct for the current live data after scoping

## 5. Branch request improvements

### Active branch enforcement
- Inactive branches now cannot be used for new branch requests / allowed-items flow.

### allowed-items UX improvement
- For a branch with exactly one brand:
  - `brand_id` is inferred automatically
- For a multi-brand branch:
  - `brand_id` is required explicitly

Verified:
- `branch_onda_13_al_malqa`
  - `/branch-requests/allowed-items?branch_id=10`
  - `200`
  - `count = 47`
- `branch_griddle` on shared branch:
  - without `brand_id` -> `400 branch_requests.brand_id_required`
  - with correct Griddle `brand_id = 7` -> `200`, `count = 41`

## 6. Role-by-role verification summary

This pass was practical, not purely theoretical.

### super.admin
- login OK
- sees active branch list
- sees supply chain resources

### area_riyadh_all
- login OK
- branch requests access OK
- blocked correctly from kitchen and warehouse execution APIs

### branch_onda_13_al_malqa
- login OK
- linked to official branch
- branch requests access OK
- branch employees access OK
- single-brand allowed-items works without `brand_id`

### kitchen_dammam_meat_and_chicken_mgr
- login OK
- production orders access OK
- blocked correctly from branch request / warehouse / delivery routes

### warehouse_dammam_user
- login OK
- warehouse lines access OK
- delivery ready list access OK
- blocked correctly from branch employee management and kitchen routes

### delivery_dammam
- login OK
- delivery routes access OK
- blocked correctly from warehouse and kitchen routes

## 7. Files added/changed in the latest stabilization wave

Important files in this wave:
- [seed_official_branches.py](C:/raed_inventory_system/raed_inventory/backend/seed_official_branches.py)
- [finalize_demo_branch_transition.py](C:/raed_inventory_system/raed_inventory/backend/finalize_demo_branch_transition.py)
- [activate_demo_readiness.py](C:/raed_inventory_system/raed_inventory/backend/activate_demo_readiness.py)
- [seed_users_from_permission_matrix.py](C:/raed_inventory_system/raed_inventory/backend/seed_users_from_permission_matrix.py)
- [cleanup_duplicate_demo_users.py](C:/raed_inventory_system/raed_inventory/backend/cleanup_duplicate_demo_users.py)
- [normalize_city_runtime_scopes.py](C:/raed_inventory_system/raed_inventory/backend/normalize_city_runtime_scopes.py)
- [branch_requests.py](C:/raed_inventory_system/raed_inventory/backend/app/routers/branch_requests.py)
- [delivery_orders.py](C:/raed_inventory_system/raed_inventory/backend/app/routers/delivery_orders.py)
- [test_supply_chain_phase1_branch_requests.py](C:/raed_inventory_system/raed_inventory/backend/tests/test_supply_chain_phase1_branch_requests.py)
- [PERMISSION_MATRIX_IMPLEMENTATION_REPORT.md](C:/raed_inventory_system/PERMISSION_MATRIX_IMPLEMENTATION_REPORT.md)

## 8. What is still partial

These are the remaining known limitations. They are no longer core setup failures.

### Kitchen-by-city modeling
- `KitchenSectionAssignment.service_city` (optional) scopes production orders by `destination_branch.city` for section managers.
- Re-seed matrix users or run `backfill_kitchen_assignment_service_city.py` after migration. Assignments with `service_city = NULL` keep legacy global visibility for that section.
- Kitchen **sections** remain global names (Meat & Chicken, etc.); only assignments are city-scoped.

### Delivery model
- Delivery scoping is now much better because it uses `warehouse_id`.
- But this is still a practical proxy, not a full delivery territory / assignment engine.

### Legacy compatibility rows
- `DEMO-WH-1` still exists in data for compatibility/history.
- This is acceptable for now, but not the cleanest final production model.

### Admin/legacy tooling visibility
- User management still lists all branches (`active_only` off). Quality/training branch pickers use `active_only=true`.

## 9. Final judgment

The current version is:

- **Demo Ready:** Yes
- **Official baseline ready for continued stabilization:** Yes
- **Production Ready:** No

This is now the right point to stop doing foundational cleanup and move into:
- final role-by-role UI validation
- kitchen-by-city clarification
- then staging hardening

## 10. Recommended next step

1. `alembic upgrade head` (includes `service_city` on `kitchen_section_assignments`).
2. `python seed_users_from_permission_matrix.py` and/or `python backfill_kitchen_assignment_service_city.py`.
3. Set `ENVIRONMENT=staging` in `.env` when deploying to staging; keep `SECRET_KEY` / `DATABASE_URL` out of repo.

## 11. Staging-hardening wave (2026-04-26)

- Kitchen city scope via `service_city` + production order filters.
- Quality & training branch loaders: `active_only=true`.
- Backfill script for `kitchen_dammam_*` / `kitchen_riyadh_*` usernames.
