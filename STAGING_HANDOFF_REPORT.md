# Staging handoff report

**Date:** 2026-04-26  
**Last updated:** 2026-04-26 (readiness endpoint + matrix env hardening)  
**Purpose:** Single source for bringing **Raed Inventory** to staging after Step 1 + Step 2 closeout. This is **not** a Railway/PaaS deploy runbook; it covers **env**, **schema/data scripts**, and **verification** from the repo baseline.

**Start here for operators:** then `raed_inventory/backend/.env.example` (numbered commands) and `raed_inventory/docs/STEP1_OPERATIONAL_SURFACE_MAP.md` (URLs and APIs).

**Related:** `FINAL_PHASE_CLOSEOUT_HANDOFF.md`, `PRODUCTION_HARDENING_PLAN.md`, `PHASE_PROGRAM_FINAL_CLOSEOUT.md`, `CURRENT_VERSION_CLOSEOUT_REPORT.md`, `STEP1_STEP2_EXECUTION_CLOSEOUT.md`, `PERMISSION_MATRIX_IMPLEMENTATION_REPORT.md`

---

## 1. Environment expectations

All commands assume **working directory:** `raed_inventory/backend` unless noted.

| Variable | Staging expectation |
|----------|---------------------|
| `ENV_FILE` | `.env.staging` (or inline `export` of the same keys) so `uvicorn` and one-off scripts load staging config. |
| `ENVIRONMENT` | `staging` |
| `DEBUG` | `false` (**required** — `app.config.Settings.validate_security()` raises if `DEBUG=true` in staging.) |
| `DATABASE_URL` | PostgreSQL only (**SQLite rejected** in staging/production at startup.) |
| `SECRET_KEY` | Strong, non-default secret (**set explicitly** for stable JWTs across restarts; the known default triggers a local-only randomization path, not suitable for operated staging.) |
| `ALLOWED_ORIGINS` | Comma-separated staging frontend origin(s), e.g. `https://staging.example.com`. |
| `ADMIN_PASSWORD` | Must **not** be the codebase default `Admin@2025` when `ENVIRONMENT=staging` (validation raises). |
| `PERMISSION_MATRIX_WORKBOOK` | **Required on staging runners:** absolute path to `raed_user_matrix_permissions.xlsx`. The seed script **exits with code 1** if the file is missing. |
| `PERMISSION_MATRIX_PASSWORD` | Optional; default **`Raed@2025`** if unset. Must match **`VERIFY_API_PASSWORD`** when running `verify_matrix_roles_api.py` after seed. |
| `RATE_LIMIT_*` | Defaults `200/minute` (global) and `20/minute` (`/auth/login`). Bulk matrix smoke raises delay (`VERIFY_LOGIN_DELAY_S`) to avoid **429**. |
| `SENTRY_DSN` | Optional; see `PRODUCTION_HARDENING_PLAN.md`. |

### Local vs staging vs production (quick)

| | `ENVIRONMENT` | `DATABASE_URL` | `DEBUG` | Default `ADMIN_PASSWORD` |
|--|---------------|----------------|---------|---------------------------|
| **Local** | `local` | SQLite or Postgres | often `true` | allowed |
| **Staging** | `staging` | Postgres | **`false`** | **blocked** |
| **Production** | `production` | Postgres | **`false`** | **blocked** |

---

## 2. Ordered database and data steps

Run **after** Postgres is reachable and `.env.staging` is in place.

### 2.1 Why this order

1. **Alembic first** — schema is source of truth (do not use `seed.py`’s `create_tables()` for operated environments).  
2. **`seed_supply_chain_demo.py` (optional)** — only when **Brand** rows (and related demo baseline) are missing; `seed_official_branches.py` **fails** if brands from `OFFICIAL_BRANCHES` are not in DB (`get_brand()`).  
3. **`seed_official_branches.py`** — official branches + city warehouses `WH-RY-1` / `WH-DM-1`; **must run before** `finalize_demo_branch_transition.py` (finalize needs active official targets for remap).  
4. **`finalize_demo_branch_transition.py`** — idempotent; deactivates demo branch codes and remaps users still on those branches. **Safe when no demo branches exist** (prints zero actions). Run after official branches exist.  
5. **`seed_users_from_permission_matrix.py`** — upserts matrix users; sets passwords from `PERMISSION_MATRIX_PASSWORD` (default `Raed@2025`).  
6. **`backfill_kitchen_assignment_service_city.py`** — sets `service_city` on kitchen section assignments from `kitchen_dammam_*` / `kitchen_riyadh_*` usernames.  
7. **`backfill_official_kitchens.py`** — official **Kitchen** rows + links active **kitchen sections** (after migrations that add `Kitchen` / M2M).

### 2.2 Command table

| Step | Command | Required? |
|------|---------|-----------|
| 1 | `alembic upgrade head` | **Required** |
| 2 | `python seed_supply_chain_demo.py` | **If** brands/sections baseline missing |
| 3 | `python seed_official_branches.py` | **Required** (for official program) |
| 4 | `python finalize_demo_branch_transition.py` | **Recommended** on any DB that ever had demo supply-chain branches; harmless otherwise |
| 5 | `python seed_users_from_permission_matrix.py` (with `PERMISSION_MATRIX_WORKBOOK` set) | **Required** for matrix QA users |
| 6 | `python backfill_kitchen_assignment_service_city.py` | **Required** after matrix seed for city-scoped kitchen managers |
| 7 | `python backfill_official_kitchens.py` | **Required** after relevant Alembic revisions (kitchen backfill) |

### 2.3 Optional after data

- `python scripts/verify_matrix_roles_api.py` — API probes + negative probe (running API required).  
- `POST /api/v1/master/kitchens` or UI `/admin/kitchens` — extra kitchen sites beyond backfill script.

---

## 3. If a seed or backfill step fails

| Situation | Action |
|-----------|--------|
| **Alembic fails** | Fix migration or DB permissions; do **not** commit partial schema without DBA sign-off. Roll forward after fix; document downgrade only if your runbook allows it. |
| **`seed_official_branches` — brand not found** | Run step 2 (`seed_supply_chain_demo.py`) or insert missing **Brand** rows to match `OFFICIAL_BRANCHES`, then retry step 3. |
| **`finalize_demo` — warnings about users on demo branch** | No active official branch with same city + brand overlap; fix master data or assign users manually, then re-run finalize or matrix seed. |
| **`seed_users_from_permission_matrix` — file not found** | Set `PERMISSION_MATRIX_WORKBOOK` to a path readable on the host; script exits **1** before DB writes. |
| **Matrix seed partial failure (Python exception)** | Transaction rolls back; fix workbook/schema mismatch and re-run (idempotent upsert behavior for users). |
| **Backfill scripts** | Idempotent; safe to re-run after fixing underlying data. |

---

## 4. Health and readiness

| Endpoint | DB | Typical use |
|----------|-----|-------------|
| `GET /health` | No | Liveness |
| `GET /api/v1/health` | No | Version / environment |
| `GET /api/v1/ready` | **Yes** (`SELECT 1`) | **Readiness** after deploy/migrate; **503** if database unreachable |

---

## 5. Application bring-up (staging-shaped)

1. `ENV_FILE=.env.staging uvicorn app.main:app --host 0.0.0.0 --port 8010` (or platform equivalent).  
2. Confirm `GET /api/v1/health` and `GET /api/v1/ready`.  
3. Frontend: `npm run build` from `raed_inventory/frontend`; deploy `dist/`; point API base URL at staging backend.  
4. **Browser smoke (on real staging — not substituted by this doc):** matrix warehouse user → `/supply-chain/control` and `/supply-chain/warehouse` (receive on `PENDING` branch-request line); admin → `/admin/kitchens`; area manager → approvals per operational map.

---

## 6. Verification (automated, this repo)

**Honest scope:** API + pytest + build; **not** a manual pass on a deployed staging URL unless your team runs section 5 step 4.

| Check | Result (last run 2026-04-26) |
|-------|-------------------------------|
| `pytest` `test_supply_chain_phase1_branch_requests.py` + `test_branch_employees.py` | **73 passed** (includes `/api/v1/ready`) |
| `npm run build` | Success |
| `python scripts/verify_matrix_roles_api.py` | Exit 0 when API up; probes include `ready_http` |
| `GET /health`, `GET /api/v1/health` | 200 (local) |

---

## 7. Staging checklist (copy for runbooks)

- [ ] `DATABASE_URL` Postgres live; `alembic upgrade head` applied.  
- [ ] `DEBUG=false`, `SECRET_KEY` set, `ADMIN_PASSWORD` not default, `ALLOWED_ORIGINS` correct.  
- [ ] Brands baseline present **or** `seed_supply_chain_demo.py` executed once.  
- [ ] Steps 3–7 completed in order (per §2.1).  
- [ ] `PERMISSION_MATRIX_WORKBOOK` set for step 5; optional `PERMISSION_MATRIX_PASSWORD` documented for QA.  
- [ ] `/api/v1/ready` **200** before traffic switch.  
- [ ] Optional: `verify_matrix_roles_api.py` with `VERIFY_API_BASE` pointing at staging.  
- [ ] Manual browser smoke (§5 step 4).

---

## 8. Known doc alignment

- `DEMO_LAUNCH_CHECKLIST.md` — legacy demo user names; header points here and to the operational map for the official baseline.
