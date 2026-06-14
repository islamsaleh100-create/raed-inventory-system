# RBAC & Security Fix Report — Phase 1

**Date:** 2026-05-03  
**Scope:** RBAC, authorization scopes, security hardening only (no workflow/dashboard/analytics changes)

---

## Pre-flight: Migration Status

| Check | Result |
|-------|--------|
| `alembic current` | `89aedce3fd41` |
| `alembic heads` | `c1d2e3f4a5b6` |
| **At head?** | **NO** — DB is 1 revision behind head |

**Action required before production deploy:** run `alembic upgrade head` on the target PostgreSQL database. No schema changes were made in this phase; existing `area_manager_assignments` table already has `city` + `brand_id`.

---

## 1. Fixes Applied

### Task 1 — `delivery_user` warehouse bypass (CRITICAL)

**File:** `raed_inventory/backend/app/routers/delivery_orders.py`

**Before:** If `delivery_user` had `warehouse_id = NULL`, `_require_order_access()` returned early without error → global access to all delivery orders.

**After:**
- `warehouse_id = NULL` → `403` with `delivery_orders.warehouse_required`
- List endpoints (`GET /`, `GET /ready`) call `_require_delivery_user_warehouse()` before querying
- Warehouse roles with null `warehouse_id` also get `403` on list endpoints

**Test:** `tests/test_rbac_phase1.py::test_delivery_user_without_warehouse_gets_403` — **PASS**

---

### Task 2 — Area Manager scope hardening (CRITICAL)

**Verification:** `AreaManagerAssignment` contains `city` (String) and `brand_id` (FK) — no migration required.

**New central module:** `raed_inventory/backend/app/core/area_manager_scope.py`
- `get_active_area_manager_assignments()`
- `get_area_manager_branch_ids()` — branches via `Branch.city == assignment.city` + `BranchBrand.brand_id`
- `branch_in_area_manager_scope()` — exact city match, no `lower()`/`strip()` text hacks
- `apply_area_manager_branch_filter()` — query helper

**Updated:** `raed_inventory/backend/app/core/auth.py`
- Removed `_same_region()` and home-branch city/area string matching
- `can_access_branch()` now uses `AreaManagerAssignment` for `area_manager`
- Added `is_platform_admin()`, `is_read_only_auditor()`, `is_super_admin()`

**Router updates:**
| File | Change |
|------|--------|
| `orders.py` | Area manager list filter; scope check on `POST /{id}/area-review`; read access via assignment |
| `notifications.py` | `_area_branch_ids()` uses `get_area_manager_branch_ids()` |
| `branch_requests.py` | Exact city match in `_area_scope_filter` (removed `func.lower`) |
| `supply_chain.py` | Dashboard KPI counts scoped by role (area manager / warehouse / kitchen / delivery) |
| `export.py` | Object-level branch/warehouse scope on all export endpoints |

---

### Task 3 — Stock visibility controls

Reviewed and verified/enforced:

| Endpoint | Scope enforcement |
|----------|-------------------|
| `GET /api/v1/dashboard/stock/branch/{branch_id}` | `can_access_branch()` — already present |
| `GET /api/v1/export/stock/branches/{branch_id}` | Added `_require_branch_export_access()` |
| `GET /api/v1/export/stock/warehouses/{warehouse_id}` | Added `_require_warehouse_export_access()` |
| `GET /api/v1/export/ledger/branches/{branch_id}` | Added branch scope check |
| `POST /api/v1/stock/transfer/branch-to-branch` | Uses `can_access_branch()` via inter_branch_service |
| Warehouse lines list/detail | Warehouse scoping via `_require_warehouse_access()` |
| Delivery list | Warehouse-scoped for delivery/warehouse roles |

**Delivery users:** No stock export or branch stock endpoints in their role set.

---

### Task 4 — Export security

**File:** `raed_inventory/backend/app/routers/export.py`

All endpoints now enforce object-level scope:

| Endpoint | Scope rule |
|----------|------------|
| `GET /export/inventory-compliance` | Branches filtered via `_scoped_branch_ids()` |
| `GET /export/variance-report` | `branch_id` required for non-admin; scope check when provided |
| `GET /export/order-summary` | Role filter (branch / warehouse / area manager) + param checks |
| `GET /export/stock/branches/{branch_id}` | `_require_branch_export_access()` |
| `GET /export/stock/warehouses/{warehouse_id}` | `_require_warehouse_export_access()` |
| `GET /export/ledger/branches/{branch_id}` | `_require_branch_export_access()` |

---

### Task 5 — Demo credentials removal

**Verified — already safe:**
- `frontend/src/pages/auth/LoginPage.jsx` — demo usernames/passwords wrapped in `import.meta.env.DEV` block (lines 159–190)
- Production builds do not expose demo login shortcuts or passwords
- No changes required; documented for audit trail

---

### Task 6 — Admin bypass review

| Location | Before | After |
|----------|--------|-------|
| `require_roles()` in `auth.py` | Only `super_admin` bypasses | Unchanged — correct |
| `delivery_orders._is_admin()` | Included `internal_auditor` | `is_platform_admin()` only |
| `branch_requests._is_admin()` | Included `internal_auditor` | `is_platform_admin()` only; auditor read via explicit `_can_view` path |
| `warehouse_lines._has_global_access()` | Included `internal_auditor` as admin | Split: platform admin OR read-only auditor (read paths only) |
| `orders._ensure_order_read_access()` | `internal_auditor` global read | Retained intentionally (audit read-only) |
| `can_access_warehouse()` | `internal_auditor` global read | Retained intentionally (audit read-only) |

**Intentionally retained:**
- `super_admin` — unrestricted via `require_roles()` and route guards
- `internal_auditor` — global **read** for audit modules; writes blocked by middleware except allowlist
- `admin` — must appear explicitly in each route's `require_roles()` tuple

---

### Task 7 — Frontend route guards

**File:** `frontend/src/App.jsx`

| Route | Guard added |
|-------|-------------|
| `/inventory`, `/inventory/new`, `/inventory/:id` | `branch_user`, `branch_manager`, `admin`, `super_admin` |
| `/orders` | + `area_manager`, `operations_manager`, `internal_auditor` |
| `/orders/exceptional` | Branch roles + admin |
| `/orders/:id` | Branch + warehouse + area + audit + admin |
| `/receiving`, `/receiving/:id` | Branch roles + admin |
| `/branch-stock` | Branch + area + ops + auditor + admin |
| `/warehouse/*` (6 routes) | Warehouse roles + auditor (read) + admin |
| `SmartDashboard` | Redirects `area_manager`, `kitchen_section_manager`, `delivery_user` → `/supply-chain/control` |

`/notifications` — left open (all authenticated users; backend filters by role).

---

### Task 8 — Internal auditor review

**Fixed:** `delivery_orders._is_admin()` no longer treats `internal_auditor` as admin.

**Auditor write paths (middleware allowlist in `main.py`):**
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/change-password`
- `POST/PATCH /api/v1/audit/findings/*`
- `POST /api/v1/assistant/ask`
- `POST/PATCH /api/v1/item-change-requests/*` (review actions)

**All other POST/PATCH/PUT/DELETE → 403** `"Internal auditor is read-only"`

**Read access:** Global read retained for orders, warehouse lines, delivery orders, supply chain pages, audit modules.

---

### Task 9 — Security review (documentation)

| Item | Status |
|------|--------|
| Swagger/OpenAPI disabled in production | **Verified** — `main.py` lines 45–47: `docs_url=None`, `redoc_url=None`, `openapi_url=None` when `settings.is_production` |
| JWT in `localStorage` | Documented risk — `frontend/src/store/index.js`, `services/api.js` use `localStorage.access_token` (no change per scope) |
| URL token usage | Not found in codebase |
| File download authorization | Export endpoints now scope-checked; import endpoints admin-only |

---

### Task 10 — Migration safety

**No schema migrations created in this phase.**

`AreaManagerAssignment` already has required columns. RBAC fixes are code-only.

---

## 2. Endpoints Reviewed

### Orders (`orders.py`)
- `GET /` — area manager scope filter added
- `GET /{id}` — read access includes area manager via assignment
- `POST /{id}/area-review` — scope check added
- All other order actions — existing `can_access_branch` / warehouse checks

### Notifications (`notifications.py`)
- `GET /summary`, `GET /list` — area manager branch IDs via assignment

### Inventory (`inventory.py`)
- Role-gated via `_BRANCH_ROLES` / `_APPROVAL_ROLES` — no area manager access (correct)

### Dashboard (`dashboard.py`)
- `GET /stock/branch/{branch_id}` — `can_access_branch()` verified

### Supply chain (`supply_chain.py`)
- `GET /dashboard` — role-scoped KPI counts
- Super-admin overview — unchanged (super_admin only)

### Branch requests (`branch_requests.py`)
- Scope filter uses exact city + brand assignment
- `_is_admin` excludes auditor from write bypass

### Delivery (`delivery_orders.py`)
- All list/detail/deliver endpoints reviewed and hardened

### Warehouse lines (`warehouse_lines.py`)
- Global access split: admin vs auditor read

### Export (`export.py`)
- All 6 export endpoints scope-hardened

### Stock (`stock.py`)
- Inter-branch transfer uses updated `can_access_branch()`

### Evaluations, quality, training
- Existing role tuples reviewed; no changes (already role-gated)

---

## 3. Scope Rules Verified

| Role | Scope rule | Source |
|------|------------|--------|
| `branch_user` / `branch_manager` | Own `user.branch_id` only | `can_access_branch()` |
| `area_manager` | `AreaManagerAssignment.city` + `brand_id` → matching branches | `area_manager_scope.py` |
| `warehouse_user` / `warehouse_manager` | Own `user.warehouse_id` | `can_access_warehouse()` |
| `delivery_user` | Own `user.warehouse_id` (required); null → deny | `delivery_orders.py` |
| `internal_auditor` | Global read; writes on allowlist only | middleware + explicit read paths |
| `admin` | Explicit per-route; no global bypass in `require_roles()` | `auth.py` |
| `super_admin` | Unrestricted | `require_roles()` |

---

## 4. Route Guards Reviewed

See Task 7 table above. Backend remains source of truth; frontend guards are UX-only.

---

## 5. Auditor Review

- Removed from `_is_admin()` in delivery and branch requests
- Read-only global visibility preserved for audit workflows
- Write allowlist documented in Section 1 Task 8
- Middleware blocks all other mutations

---

## 6. Admin Bypass Review

See Task 6 table. No implicit `admin` bypass in `require_roles()`. `super_admin` only central bypass.

---

## 7. Remaining Security Risks

1. **Alembic not at head** on checked environment — run upgrade before deploy
2. **JWT in localStorage** — XSS could steal tokens (document for Phase 2)
3. **Hardcoded deployment passwords** — `deployment_internal_auditor_service.py` still resets to `Raed@2025` (out of Phase 1 scope)
4. **Notifications query storm** — performance, not RBAC
5. **Legacy replenishment enum drift** (`area_manager_review` in PostgreSQL) — separate migration needed
6. **`/notifications` frontend route** — unguarded but backend filters; low risk

---

## 8. Critical Risks Remaining

1. PostgreSQL enum `orderstatus` missing `area_manager_review` — causes 500 on notification polling
2. Deployment credential reset on every boot
3. Supply chain stuck states (partial fulfillment) — workflow, not RBAC
4. Test suite largely broken outside new RBAC tests — CI gap

---

## 9. Migration Changes

**None in this phase.**

---

## 10. Recommendations for Phase 2

1. Run `alembic upgrade head` and add CI check `alembic current == head`
2. Add Alembic migration for missing `orderstatus` enum values
3. Wire `INTERNAL_AUDITOR_PASSWORD` env in deployment bootstrap
4. Consider httpOnly cookie for JWT instead of localStorage
5. Add supply-chain sections to notifications with scoped queries
6. Repair broader test suite / add RBAC regression to CI
7. Paginate unbounded list endpoints

---

## Test Results

```
tests/test_rbac_phase1.py ........................ 3 passed
tests/test_area_manager_inter_branch_transfer.py .. 2 passed
```

---

## FINAL DECISION

### Demo Readiness: **GO**

RBAC holes for delivery bypass and area manager string-matching are fixed. Demo personas should have valid `AreaManagerAssignment` rows and `warehouse_id` on delivery users.

### LAN Trial Readiness: **GO with conditions**

Conditions:
1. Run `alembic upgrade head` on LAN PostgreSQL
2. Verify all area managers have active `AreaManagerAssignment` rows (city + brand)
3. Verify delivery users have non-null `warehouse_id`
4. Fix `orderstatus` enum migration before heavy notification use

### Production Readiness: **NO-GO**

Justification: Alembic drift, enum 500s, hardcoded credential rotation, and incomplete CI coverage remain. RBAC layer is materially stronger but not sufficient alone for production sign-off.
