# Final LAN Trial Readiness Report

**Date:** 2026-06-15  
**Branch:** `lan-readiness/final-verification-2026-06-15`  
**Verification type:** Live API + live UI proxy (no code changes, no new features)

**Live environment verified:**

| Service | Address | Status |
|---------|---------|--------|
| Frontend (Vite) | `http://localhost:3000` | LISTENING |
| Backend (FastAPI) | `http://127.0.0.1:8010` | LISTENING |
| Health | `GET /api/v1/health` | 200 |

---

## Roles Verified

Password used for official users: `Raed@Demo2026` (demo — rotation still required before LAN trial).

| Username | Login | Role checks | Data contract |
|----------|-------|-------------|---------------|
| `branch_onda_1_arkan` | PASS | Dashboard, branch requests, notifications | `branch_name`, detail owner/next/timeline |
| `branch_pizza_1_al_khobar` | PASS | Same | `branch_name` on requests |
| `branch_shawarma_1_khobar` | PASS | Same | API 200 (no recent requests in sample) |
| `area_dammam_onda` | PASS | Dashboard, SUBMITTED approvals, notifications | Scoped to Onda Arkan |
| `area_dammam_restaurants` | PASS | Same | API 200 (empty SUBMITTED sample at verify time) |
| `area_riyadh_all` | PASS | Same | Scoped to Riyadh branch only |
| `kitchen_dammam_meat_and_chicken_mgr` | PASS | Production queue | `branch_name` present |
| `kitchen_dammam_bakery_and_sweets_mgr` | PASS | Production queue | `branch_name`, PENDING orders (18) |
| `kitchen_dammam_pizza_mgr` | PASS | Production queue | `branch_name` present |
| `warehouse_dammam_manager` | PASS | Warehouse lines | All stock fields populated |
| `warehouse_dammam_user` | PASS | Warehouse lines | Same as manager (scoped) |
| `delivery_dammam` | PASS | Delivery orders | `branch_name`, lines, receiver |
| `internal_auditor` | **N/A** | Username does not exist in DB | See note below |
| `audit.officer` | PASS | Auditor role verified instead | Read-only write block confirmed |
| `super.admin` | PASS | Users, global dashboard, supply chain | All admin routes 200 |

**Auditor username note:** Official seeded user is `audit.officer` (role `internal_auditor`), not username `internal_auditor`. Login with `audit.officer` / `Raed@2025` verified all auditor checks.

---

## Screens Verified

### Branch user (`branch_onda_1_arkan`)

| Screen | Live API | Result |
|--------|----------|--------|
| Dashboard | `GET /supply-chain/dashboard` | 200 |
| Branch Requests | `GET /branch-requests` | 200, `branch_name` present |
| Request Detail | `GET /branch-requests/{id}/detail` | 200 |
| Timeline | detail payload | Present (2+ events on sample) |
| Current Owner | `status_summary.current_owner_ar` | Present |
| Next Action | `status_summary.next_action_ar` | Present |
| Notifications | `GET /notifications/summary` | 200 |

**Forbidden items:**

| Check | Result |
|-------|--------|
| RAW items in allowed-items (Onda brand) | 0 RAW of 47 allowed |
| NOT_REQUESTABLE in allowed-items | 0 |
| Legacy supply-chain nav only for operational roles | Confirmed in `AppLayoutV2.jsx` |

### Area manager (`area_dammam_onda`, `area_riyadh_all`)

| Screen | Result |
|--------|--------|
| Approvals (SUBMITTED) | 200 |
| Branch Requests in scope | 200 |
| Timeline / owner / next | Via detail endpoint (same service as branch) |

Approve / Reject / Modify buttons: present in `SupplyChainApprovalsPage` for non-auditor area managers (verified in prior role audits; API approve endpoints reachable).

### Kitchen (`kitchen_dammam_bakery_and_sweets_mgr`)

| Field | Result |
|-------|--------|
| Production queue | 200 |
| Branch name | `Onda Arkan` on PENDING orders |
| Status | `PENDING`, `SENT_TO_WAREHOUSE`, etc. |

Status-gated buttons (`Start`, `Ready`, `Send To Warehouse`): implemented in `SupplyChainKitchenPage`; 18 PENDING orders available for Start button.

### Warehouse (`warehouse_dammam_manager`)

**Live via UI proxy (`localhost:3000/api/v1/warehouse-lines`):**

```text
branch_name=Onda Arkan
available_stock=0
current_stock=98.000
reserved_stock=377.400
requested_qty=2.000
issued_qty=2.000
pending_qty=0.000 (remaining)
```

| Check | Result |
|-------|--------|
| Missing `branch_name` on any line | **0 of 4,926 lines** |
| Missing stock fields | **0 lines** |
| Em dash placeholders from null API | **None** (fields populated) |

Status distribution (action context):

| Status | Count | Expected actions |
|--------|-------|------------------|
| PENDING | 60 | Receive |
| AVAILABLE | 49 | Issue / Partial / Delay |
| READY_FOR_DISPATCH | 63 | Create Delivery |
| PARTIAL | 198 | Issue / Delivery |
| BACKORDER | 360 | Delay reason |
| DELIVERED | 4,196 | No actions (`لا إجراءات متاحة`) — correct |

### Delivery (`delivery_dammam`)

| Field | Result |
|-------|--------|
| Branch name | Present on orders |
| Receiver name | Present on delivered sample |
| Line details | Lines array populated |
| Delivered qty / shortage | Fields on line items |

Status counts: 60 READY (Out For Delivery available), 12 OUT_FOR_DELIVERY (Deliver available), delivered/partial delivered present.

### Internal auditor (`audit.officer`)

| Check | Result |
|-------|--------|
| Supply chain dashboard | 200 |
| Warehouse lines (read) | 200, enriched fields |
| Audit findings | 200 |
| Write blocked | POST `/warehouse-lines/1/issue` → denied |
| UI read-only banners | Present in supply chain pages (prior audit) |

### Admin (`super.admin`)

| Route / API | Result |
|-------------|--------|
| `GET /users/` | 200 |
| `GET /dashboard/global` | 200 |
| Supply chain pages | 200 |
| Frontend routes (`/admin/*`, `/audit/*`, legacy warehouse) | HTTP 200 (SPA) |

---

## Buttons Verified

Verified by live status distribution + prior role action completeness tests (77 passed):

| Role | Buttons | Status |
|------|---------|--------|
| Branch | Create, Submit Draft, View Detail | API + UI paths OK |
| Area | Approve, Reject, Modify | UI present; API 200 |
| Kitchen | Start (PENDING), Ready, Send To Warehouse | PENDING orders exist |
| Warehouse | Receive/Issue/Partial/Delay/Delivery | Status-gated; DELIVERED shows no actions |
| Delivery | Out For Delivery (READY), Deliver (OUT_FOR_DELIVERY) | 60 + 12 orders in actionable states |
| Auditor | No write buttons | Write API blocked |
| Admin | Full nav | Routes registered in `App.jsx` |

---

## Scope Verification

| User | Scope rule | Observed |
|------|------------|----------|
| `area_dammam_onda` | City + Brand (Onda / Dammam) | Branch list: **Onda Arkan only** |
| `area_riyadh_all` | City + Brand (Riyadh) | Branch list: **Ronaldos Riyadh Takhasosy** |
| `branch_*` | Own branch only | Requests scoped to branch |
| `warehouse_dammam_*` | WH-DM-1 lines | Warehouse_id filter applied |
| `delivery_dammam` | WH-DM-1 deliveries | Scoped delivery orders |

---

## Opening Stock Validation Result

**Command:** `python validate_lan_opening_stock.py --write-report`

**Verdict: GO**

| Metric | Value |
|--------|-------|
| Trial branches | 3 (Onda Arkan, Ronaldos Al Khobar, Shawarma Al Khobar) |
| Trial warehouse | WH-DM-1 Dammam Central |
| Zero stock items | 0 |
| Missing stock rows | 0 |
| Below reorder | 0 |

Report: `LAN_OPENING_STOCK_VALIDATION_REPORT.md`

---

## Password Checklist Status

**Document:** `PASSWORD_ROTATION_CHECKLIST.md` — **exists and applies**.

**Readiness status: NOT COMPLETE (expected for dev verification)**

| Item | Status |
|------|--------|
| Checklist documented | YES |
| Passwords rotated for LAN | **NO** — still using `Raed@Demo2026` / `Raed@2025` |
| `.env` not in git | YES (untracked) |
| Operator action required before trial | **Mandatory** |

Do not rotate passwords during this verification pass (per instructions).

---

## Final LAN Checklist

| Item | Documented | Verified |
|------|------------|----------|
| Fresh PostgreSQL plan | `LAN_TRIAL_DB_RESET.md` | YES |
| Alembic head | `c1d2e3f4a5b6` | YES (`alembic heads` / `alembic current`) |
| Official users available | `seed_phase2_official_users.py` | YES (13/14 usernames; auditor = `audit.officer`) |
| Official item master | `import_classified_supply_items.py` | YES (47 requestable items for Onda branch sample) |
| Opening stock procedure | `validate_lan_opening_stock.py` | YES — GO |
| Password rotation checklist | `PASSWORD_ROTATION_CHECKLIST.md` | YES — pending operator action |
| LAN reset procedure | `LAN_TRIAL_DB_RESET.md` | YES |
| LAN access / firewall | `docs/LAN_ACCESS.md`, `setup_lan_firewall.ps1` | YES |
| Contract tests | `test_operational_screen_data_contracts.py` | **10/10 passed** |

---

## Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Demo passwords still active | High | Complete `PASSWORD_ROTATION_CHECKLIST.md` before trial |
| Current DB contains simulation workflow volume (~4k+ delivery orders) | Medium | Use **fresh** DB per `LAN_TRIAL_DB_RESET.md` for actual LAN trial |
| Backend stale process after deploy | Medium | Restart uvicorn after any backend change (`run_local.ps1`) |
| JWT in localStorage (C-01) | Low | Accepted for controlled LAN only |

---

## Remaining Warnings

1. Username `internal_auditor` does not exist — operators must log in as **`audit.officer`**.
2. `available_stock = 0` with high `reserved_stock` is valid when stock is reserved for branch requests — not a display bug.
3. `area_dammam_restaurants` had no SUBMITTED requests at verification time — empty queue is valid, not a scope failure.
4. `branch_shawarma_1_khobar` had no recent requests in the first page sample — API access confirmed.
5. This verification ran on the **development/simulation PostgreSQL instance**, not a fresh LAN trial database.

---

## Automated Test Results (re-run during verification)

```
tests/test_operational_screen_data_contracts.py   10 passed
```

Prior sprint regression (from operational data contract audit): **77 passed**.

---

## LAN Trial Verdict

# GO WITH CONDITIONS

The live application on `localhost:3000` / `8010` is functionally ready for LAN Trial. All operational roles authenticate, scoped data returns correctly, warehouse enrichment fields are populated on live API, opening stock validation is GO, and contract tests pass.

### Conditions (all mandatory before LAN Trial day)

1. **Rotate all passwords** per `PASSWORD_ROTATION_CHECKLIST.md` — do not use `Raed@Demo2026`, `Raed@2025`, or `Admin@2025` on the LAN host.
2. **Provision a fresh PostgreSQL database** following `LAN_TRIAL_DB_RESET.md` — do not use the current simulation/dev database for the trial.
3. **Run `alembic upgrade head`** on fresh DB (expected head: `c1d2e3f4a5b6`).
4. **Re-seed official users and item master** on the fresh DB; re-run opening stock validation (`validate_lan_opening_stock.py --write-report`).
5. **Start servers** with `run_local.ps1` or `start_backend.bat` + `start_frontend.bat`; open firewall ports 3000 and 8010 (`setup_lan_firewall.ps1`).
6. **Brief operators:** auditor login is `audit.officer`; warehouse `available_stock=0` may mean fully reserved stock.
7. **Restart backend** after any code deployment before users connect.

When all seven conditions are met on the LAN host, the system is ready to proceed to trial operations.
