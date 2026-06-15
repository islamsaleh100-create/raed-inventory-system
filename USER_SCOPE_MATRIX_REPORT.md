# Phase 2 — User & Scope Matrix Validation Report

**Date:** 2026-06-14  
**Branch:** `phase2/user-scope-matrix-2026-06-14` (local only)  
**Alembic head:** `c1d2e3f4a5b6`  
**API tested:** `http://localhost:8010`  
**Demo password policy:** local/dev only via `PHASE2_DEMO_PASSWORD` (never logged or exposed in UI)

---

## Summary

Phase 2 validated and stabilized official users, role mappings, branch/area/kitchen/warehouse/delivery assignments, legacy area-manager migration, and automated HTTP scope tests.

| Area | Result |
|------|--------|
| Required roles | 8/8 present |
| Official active users | 40/40 verified in DB |
| Login + `/me` HTTP tests | 40/40 passed |
| Inactive / legacy login denial | 5/5 passed |
| Scope HTTP tests | 6/6 passed |
| **Total automated tests** | **51/51 passed** |

**Artifacts added**

- `raed_inventory/backend/seed_phase2_official_users.py` — idempotent official user seed + legacy AM migration
- `raed_inventory/backend/tests/test_phase2_user_scope.py` — HTTP login and scope tests

**Prerequisite seeds (run once, in order)**

```text
python seed_supply_chain_demo.py
python seed_official_branches.py
python backfill_official_kitchens.py
python seed_phase2_official_users.py   # after API startup if using demo password for admin
```

**Test run (local only — rate limit disabled via shell env for bulk login tests)**

```text
RATE_LIMIT_ENABLED=false uvicorn app.main:app --port 8010
python seed_phase2_official_users.py
PHASE2_LOGIN_DELAY_S=3.2 python -m pytest tests/test_phase2_user_scope.py -v
```

> **Rate limiting note:** The first test run failed (44/51) because bulk login tests hit the default auth rate limit (`RATE_LIMIT_AUTH=20/minute`, HTTP 429). The final **51/51 pass** was executed with `RATE_LIMIT_ENABLED=false` set **only in the local shell** for the test API process. No application defaults, `.env.example`, `docker-compose.prod.yml`, or staging/production settings were changed. Production and staging rate limiting **remains enabled** (`RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_AUTH=20/minute` default; `10/minute` in `docker-compose.prod.yml`).

---

## Users Created / Verified

All 40 official **active** users exist, are active, have correct roles, and pass login + `/me` HTTP tests.

| Group | Count | Usernames |
|-------|------:|-----------|
| Admin | 2 | `super.admin`, `admin` |
| Area managers | 3 | `area_dammam_onda`, `area_dammam_restaurants`, `area_riyadh_all` |
| Branch users | 23 | `branch_onda_*`, `branch_pizza_*`, `branch_ronaldos_*`, `branch_shawarma_*` |
| Kitchen section | 6 | `kitchen_dammam_*_mgr`, `kitchen_riyadh_*_mgr` |
| Warehouse | 4 | `warehouse_dammam_manager/user`, `warehouse_riyadh_manager/user` |
| Delivery | 2 | `delivery_dammam`, `delivery_riyadh` |

**Inactive (verified, login denied)**

| Username | Status | Notes |
|----------|--------|-------|
| `kitchen_dammam_manager_future` | inactive | Placeholder only |
| `kitchen_riyadh_manager_future` | inactive | Placeholder only |
| `am_riyadh` | inactive | Legacy; assignments deactivated |
| `am_dammam_cafes` | inactive | Legacy; assignments deactivated |

**Notes**

- `admin` also carries `super_admin` from deployment bootstrap (startup). Both roles present; login test accepts `admin` role.
- No duplicate active usernames in DB.
- Demo passwords set by seed; **re-run seed after every API restart** if `admin` must use the phase-2 demo password (see Remaining Risks).

---

## Old Area Manager Migration

| Legacy account | Status | Assignments copied | Action |
|----------------|--------|-------------------:|--------|
| `am_riyadh` | inactive | 0 (already migrated or none active) | Deactivated |
| `am_dammam` | **not found** | 0 | N/A — account never existed in this DB |
| `am_dammam_cafes` | inactive | 0 | Deactivated |

**Canonical replacements**

| Username | Scope (city + brand_id rows) |
|----------|------------------------------|
| `area_dammam_onda` | Dammam × Onda |
| `area_dammam_restaurants` | Dammam × Ronaldos, Shawarma, Griddle |
| `area_riyadh_all` | Riyadh × Onda, Ronaldos, Shawarma, Griddle |

Migration logic in `seed_phase2_official_users.py`:

1. Copies active `AreaManagerAssignment` rows from legacy users to canonical targets (one row per city + brand).
2. Deactivates legacy assignments (`active=false`, `ended_at` set).
3. Sets legacy user `status=inactive`.
4. Does **not** leave duplicate active area managers for the same city + brand.

No duplicate active area-manager scopes detected after migration.

---

## Role Mapping

Spec names use SCREAMING_SNAKE; DB `RoleName` enum uses snake_case.

| Spec role | DB `RoleName` | Status |
|-----------|---------------|--------|
| `SUPER_ADMIN` | `super_admin` | OK |
| `ADMIN` | `admin` | OK |
| `AREA_MANAGER` | `area_manager` | OK |
| `BRANCH_USER` | `branch_user` + `branch_manager` | OK — official branch users get both |
| `KITCHEN_SECTION_MANAGER` | `kitchen_section_manager` | OK |
| `WAREHOUSE_MANAGER` | `warehouse_manager` | OK |
| `WAREHOUSE_USER` | `warehouse_user` | OK |
| `DELIVERY_USER` | `delivery_user` | OK |

**Untouched (per phase scope):** `internal_auditor`, `quality_visitor`, `quality_manager`, `trainer`, `evaluator`, `hr_manager`, `sales_manager`, `operations_manager`, `branch_manager` (role retained; not removed).

**Brand naming note:** Spec “Pizza” branches map to brand **`Ronaldos`** in `seed_official_branches.py` (pizza/restaurant brand entity). No separate `Pizza` brand exists.

---

## Branch Mapping

All 23 branch users mapped to official branch codes from `seed_official_branches.py`. **0 issues** (missing branch_id, wrong branch, inactive branch, or duplicate mapping).

| Username | Branch code | City |
|----------|-------------|------|
| `branch_onda_1_arkan` | BR-DM-ON-ARKAN | Dammam |
| `branch_onda_13_al_malqa` | BR-RY-ON-MALQA | Riyadh |
| `branch_onda_14_hassa` | BR-DM-ON-HASSA | Dammam |
| `branch_onda_16_najmah` | BR-DM-ON-NAJMA | Dammam |
| `branch_onda_18_al_midra_gym` | BR-DM-ON-MIDRA | Dammam |
| `branch_onda_2_hoqail` | BR-DM-ON-HOQAI | Dammam |
| `branch_onda_4_sefarat` | BR-RY-ON-SEFAR | Riyadh |
| `branch_onda_5_muowasat` | BR-DM-ON-MUOWA | Dammam |
| `branch_onda_9_ras_tanura` | BR-DM-ON-RASTN | Dammam |
| `branch_onda_dau_university` | BR-DM-ON-DAU | Dammam |
| `branch_pizza_1_al_khobar` | BR-DM-RN-KHOBR | Dammam |
| `branch_pizza_10_mazaar` | BR-DM-RN-MAZAR | Dammam |
| `branch_pizza_15_ras_tanura` | BR-DM-RN-RASTN | Dammam |
| `branch_pizza_3_arkan` | BR-DM-RN-ARKAN | Dammam |
| `branch_pizza_4_riyadh_takhasosy` | BR-RY-RN-TAKHS | Riyadh |
| `branch_pizza_5_al_ulaya` | BR-RY-RN-ULAYA | Riyadh |
| `branch_pizza_6_riyadh_nada` | BR-RY-RN-NADA | Riyadh |
| `branch_pizza_7_aramco` | BR-DM-RN-ARAMC | Dammam |
| `branch_pizza_9_al_azizia` | BR-DM-RN-AZIZI | Dammam |
| `branch_ronaldos_dau_university` | BR-DM-RN-DAU | Dammam |
| `branch_shawarma_1_khobar` | BR-DM-SH-KHOBR | Dammam |
| `branch_shawarma_4_arkan` | BR-DM-SH-ARKAN | Dammam |
| `branch_shawarma_olaya` | BR-RY-SH-OLAYA | Riyadh |

**Spec vs seed discrepancies (documented, not changed in this phase)**

- `Pizza 10 - Mazaar` listed under Riyadh in spec → official branch `BR-DM-RN-MAZAR` is **Dammam**.
- `ONDA DAU University` listed under Riyadh in spec → official branch `BR-DM-ON-DAU` is **Dammam**.

Branch users receive `branch_user` + `branch_manager` roles; scope enforced via `branch_id` on user record.

---

## Area Manager Assignments

All assignments use **`city` + `brand_id` + `active`** — no city-string fallback.

### `area_dammam_onda`

| City | Brand |
|------|-------|
| Dammam | Onda |

### `area_dammam_restaurants`

| City | Brand |
|------|-------|
| Dammam | Ronaldos |
| Dammam | Shawarma |
| Dammam | Griddle |

### `area_riyadh_all`

One row per brand (not a multi-brand single row):

| City | Brand |
|------|-------|
| Riyadh | Onda |
| Riyadh | Ronaldos |
| Riyadh | Shawarma |
| Riyadh | Griddle |

HTTP scope test: `area_dammam_onda` branch-requests list returns only Dammam + Onda; cross-city stock access to Riyadh branch returns **403**.

---

## Kitchen Mapping

**Official kitchen entities** (from `backfill_official_kitchens.py`):

| Kitchen | City |
|---------|------|
| Official Kitchen — Dammam | Dammam |
| Official Kitchen — Riyadh | Riyadh |

**Sections** (shared across kitchens, scoped by `service_city` on assignment):

| Section | Exists |
|---------|--------|
| Meat & Chicken | Yes |
| Bakery & Sweets | Yes |
| Pizza | Yes |

**Kitchens are not branches:** 0 branch rows with “kitchen” in name; kitchens live in `kitchens` table.

---

## Kitchen User Mapping

| Username | Section | Service city |
|----------|---------|--------------|
| `kitchen_dammam_meat_and_chicken_mgr` | Meat & Chicken | Dammam |
| `kitchen_dammam_bakery_and_sweets_mgr` | Bakery & Sweets | Dammam |
| `kitchen_dammam_pizza_mgr` | Pizza | Dammam |
| `kitchen_riyadh_meat_and_chicken_mgr` | Meat & Chicken | Riyadh |
| `kitchen_riyadh_bakery_and_sweets_mgr` | Bakery & Sweets | Riyadh |
| `kitchen_riyadh_pizza_mgr` | Pizza | Riyadh |

HTTP scope test: `kitchen_dammam_pizza_mgr` production orders filtered to **Pizza** section; destination branches limited to Dammam when city present.

---

## Warehouse Mapping

| Username | Role | Warehouse | Location |
|----------|------|-----------|----------|
| `warehouse_dammam_manager` | warehouse_manager | WH-DM-1 (id=3) | Dammam |
| `warehouse_dammam_user` | warehouse_user | WH-DM-1 (id=3) | Dammam |
| `warehouse_riyadh_manager` | warehouse_manager | WH-RY-1 (id=2) | Riyadh |
| `warehouse_riyadh_user` | warehouse_user | WH-RY-1 (id=2) | Riyadh |

All `warehouse_id` values match expected warehouse codes. HTTP test: `warehouse_dammam_user` can access `/warehouse-lines` (200).

---

## Delivery Mapping

| Username | Role | Warehouse scope |
|----------|------|-----------------|
| `delivery_dammam` | delivery_user | WH-DM-1 (id=3) |
| `delivery_riyadh` | delivery_user | WH-RY-1 (id=2) |

Both have non-null `warehouse_id`. HTTP test: `/delivery-orders/ready` returns **200** (scoped access). Missing warehouse scope would deny per Phase 1 hardening.

---

## Failed Users

**None.** All 40 official active users verified in DB and passing HTTP login tests.

---

## Scope Test Results

Executed: `pytest tests/test_phase2_user_scope.py` — **51 passed**, 0 failed.

| Test | User / subject | Assertion |
|------|----------------|-----------|
| Login + roles | All 40 official users | 200 login; expected role(s) on `/me` |
| Inactive denial | 2 future kitchen + 3 legacy AM | 401/403 on login |
| Branch scope | `branch_onda_13_al_malqa` | Requestable items only; no RAW/NOT_REQUESTABLE; foreign branch stock 403 |
| Area manager scope | `area_dammam_onda` | Branch-requests Dammam + Onda only |
| Kitchen scope | `kitchen_dammam_pizza_mgr` | Production orders Pizza section / Dammam |
| Warehouse scope | `warehouse_dammam_user` | `/warehouse-lines` 200 with assigned warehouse |
| Delivery scope | `delivery_dammam` | `warehouse_id` set; `/delivery-orders/ready` 200 |
| Area cross-city deny | `area_dammam_onda` | Riyadh branch stock 403 |

**Test execution history**

| Run | Result | Cause |
|-----|--------|-------|
| Initial | 44 failed / 7 passed | Auth rate limit (429) during 40+ sequential logins; `/me` roles parsed as dicts instead of strings |
| Final | **51 passed** | Tests fixed; API started locally with `RATE_LIMIT_ENABLED=false` (shell env only); post-startup seed applied |

---

## Future Kitchen Manager Status

| Item | Status |
|------|--------|
| `KITCHEN_MANAGER_FUTURE` enum / `RoleName` | **Absent** (not created) |
| `kitchen_dammam_manager_future` | inactive placeholder |
| `kitchen_riyadh_manager_future` | inactive placeholder |
| Workflow dependency | **None** — inactive users cannot login; no workflow gates on these accounts |

Legacy `kitchen_manager` enum value exists for historical rows only; production access remains section-assignment based.

---

## Remaining Risks

1. **Deployment admin bootstrap** — On every API startup, `ensure_deployment_admin_user()` resets `admin` password to `ADMIN_PASSWORD` (default `Admin@2025`). Phase-2 demo password applies only after `seed_phase2_official_users.py` runs post-startup.
2. **Auth rate limiting** — Bulk Phase 2 login tests require temporarily disabling rate limits in the **local test shell** (`RATE_LIMIT_ENABLED=false`) or a delay ≥3.2s per login. Application defaults and production/staging configs are unchanged and remain enabled.
3. **Spec vs branch master data** — Mazaar and Onda DAU city assignments differ between written spec and `seed_official_branches.py` (see Branch Mapping).
4. **`am_dammam` never existed** in this database; migration is a no-op for that account.
5. **PostgreSQL enum drift** — `orderstatus` missing `area_manager_review` can still 500 `/notifications/summary` (pre-existing; out of Phase 2 scope).
6. **Broader test suite** — Legacy tests outside Phase 2 remain largely broken; only Phase 2 + Phase 1 RBAC tests verified green.

---

## Demo Readiness

**Ready for local/demo user matrix trial** when:

1. Prerequisites seeded.
2. `seed_phase2_official_users.py` run after API startup.
3. Demo password configured via `PHASE2_DEMO_PASSWORD` env (local only).

All official personas login and pass scope checks against `localhost:8010`.

---

## LAN Trial Readiness

**Conditionally ready** for LAN trial of user/scope matrix:

- Run API on LAN host with PostgreSQL.
- Set `ALLOWED_ORIGINS` for LAN frontend IP.
- Run phase-2 seed post-startup on trial DB.
- Disable or raise auth rate limits for multi-user demo sessions.
- Do **not** expose demo password in frontend production builds (existing `LoginPage.jsx` dev-only hint is acceptable for local).

---

## Production Readiness

**Not production-ready** for identity matrix alone:

- Demo password policy is local/dev only.
- Deployment admin bootstrap conflicts with phase-2 unified demo password for `admin`.
- Branch master-data spec discrepancies should be resolved with business before production cutover.
- Notification enum drift and broader test debt remain.

**Production identity work still needed:** align `ADMIN_PASSWORD` strategy, confirm official branch cities with business, run migration on production DB with legacy AM accounts if present, and re-run HTTP scope tests against staging.

---

## Phase Boundaries (not started)

Dashboards, workflow redesign, kitchen tracking, warehouse/delivery redesign, analytics, AI, forecasting, and optimization were **not** touched in this phase.
