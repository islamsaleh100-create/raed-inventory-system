# Phase 9 Pre-Check — Go-Live Readiness Audit Preparation

**Date:** 2026-06-15  
**Scope:** Audit-only synthesis from Phases 0–8 reports. No code changes.  
**Sources reviewed:**

- `PROJECT_STATUS_REPORT.md`
- `SIMULATED_DATA_ANALYTICS_REPORT.md`
- `DASHBOARD_OPERATIONS_REPORT.md`
- `NOTIFICATIONS_AUDIT_REPORT.md`
- `WAREHOUSE_DELIVERY_HARDENING_REPORT.md`
- `SUPPLY_CHAIN_E2E_REPORT.md`
- `RBAC_SECURITY_FIX_REPORT.md`
- `ENVIRONMENT_READY_REPORT.md`

Alembic head (documented): `c1d2e3f4a5b6`  
Latest phase branch (documented): `phase8/simulated-operations-data-2026-06-14`

---

## Open Risks

Consolidated from all **Open Risks**, **Remaining Risks**, **Known Issues**, and **UI Audit Findings** sections. Grouped by domain.

### Security

| ID / Item | Source | Status in reports |
|-----------|--------|-------------------|
| **C-01** — JWT stored in `localStorage` (XSS token theft) | PROJECT_STATUS, DASHBOARD_OPERATIONS, SIMULATED_DATA, RBAC_SECURITY | **Open** — deferred Phases 7–8 |
| Hardcoded deployment credential reset on boot (`deployment_internal_auditor_service`, `Admin@2025`) | RBAC_SECURITY | **Open** — out of Phase 1 scope |
| Deployment `admin` password may differ from Phase 2 demo password after deployment refresh | PROJECT_STATUS | **Open** — operational confusion |
| Default SQLite URL if `.env` missing on local/CI | ENVIRONMENT_READY | **Open** — documented onboarding risk |
| Hardcoded seed passwords (`Admin@2025`, `Raed@2025` in demo seeds) | ENVIRONMENT_READY | **Open** — change before real users |
| `/notifications` frontend route unguarded (backend filters) | RBAC_SECURITY | **Open** — low severity |
| Test suite largely broken outside RBAC tests at Phase 1 time | RBAC_SECURITY | **Partially mitigated** — Phases 2–8 added phase-specific suites; full CI breadth not re-documented |

### Operations

| Item | Source | Notes |
|------|--------|-------|
| Post-split cancellation — no API to release `reserved_qty` | WAREHOUSE_DELIVERY, NOTIFICATIONS_AUDIT | **Open** — deferred Phase 5 → 6 → 7 |
| Shortage follow-up — no automated re-issue / procurement for missing qty | WAREHOUSE_DELIVERY | **Open** |
| Multiple partial issues require second issue cycle before new delivery line | WAREHOUSE_DELIVERY | **Open** — by design |
| Kitchen vs branch reservation asymmetry (kitchen output not reserved on split) | WAREHOUSE_DELIVERY | **Open** |
| Legacy `AREA_APPROVED` without split possible from pre-auto-split data | SUPPLY_CHAIN_E2E | **Open** — recovery via idempotent `/split` documented |
| `operations_manager` has dashboard API but not supply-chain execute routes | PROJECT_STATUS, DASHBOARD_OPERATIONS | **Open** — documented as by design |
| BOTH items missing from Onda imported catalog | SUPPLY_CHAIN_E2E | **Open** — E2E scenario C still skipped |
| Production delay notification missing (no delay field on production orders) | NOTIFICATIONS_AUDIT | **Open** |
| Branch submitted ack not in bell | NOTIFICATIONS_AUDIT | **Open** — partial coverage |
| Proof-of-delivery beyond `receiver_name` / `delivery_note` | WAREHOUSE_DELIVERY, NOTIFICATIONS_AUDIT | **Open** — deferred |
| Kitchen output paths depend on section manager assignments per city | SIMULATED_DATA | **Open** — config dependency |

### Data Integrity

| Item | Source | Notes |
|------|--------|-------|
| **H-02** — `stock_ledger_service.py` free-text `source_type` / `destination_type` | All phase reports 4–8 | **Open** — deferred; ledger entries verified correct in tested paths |
| Simulation data is additive — DB mixes test + simulated history | PROJECT_STATUS, SIMULATED_DATA | **Open** — not a workflow bug; affects trial DB clarity |
| `seed_4months.py` idempotency unknown | ENVIRONMENT_READY | **Open** — review before running on trial DB |
| Imported item rejections need production data sign-off | SUPPLY_CHAIN_E2E (Production NO-GO) | **Open** — not re-closed in later phases |

### Performance

| Item | Source | Notes |
|------|--------|-------|
| Super-admin dashboard complexity under large datasets | PROJECT_STATUS, DASHBOARD_OPERATIONS | **Open** — acceptable for demo; may slow at scale |
| Kitchen KPI split requires two list API calls | DASHBOARD_OPERATIONS | **Open** |
| Notifications query storm (performance, not RBAC) | RBAC_SECURITY | **Open** |
| Full 90-day simulation runtime scales with volume | SIMULATED_DATA | **Open** — ~10 min local for 3,483 requests |
| Server reload required after backend changes (stale uvicorn) | DASHBOARD_OPERATIONS | **Open** — operational |
| Unbounded list endpoints — pagination recommended | RBAC_SECURITY (Phase 2 rec) | **Open** — not verified closed |

### UI

| Item | Source | Notes |
|------|--------|-------|
| Some dashboard KPI labels hardcoded English | DASHBOARD_OPERATIONS | **Open** — deferred i18n |
| Branch KPI drill-down for warehouse/delivery links to branch-requests only | DASHBOARD_OPERATIONS | **Open** |
| Super-admin block includes heavy executive/analytics section | DASHBOARD_OPERATIONS | **Open** — pre-existing |
| Legacy `AREA_APPROVED` detection UI not implemented | SUPPLY_CHAIN_E2E (deferred Phase 5) | **Open** |
| Consolidated audit timeline view | SUPPLY_CHAIN_E2E (deferred Phase 5) | **Open** |

### Deployment

| Item | Source | Notes |
|------|--------|-------|
| All phase work **local only** — not pushed/deployed | PROJECT_STATUS, all reports | **Open** |
| Runtime smoke test not verified in Phase 0 (manual) | ENVIRONMENT_READY | **Open** — ⚙️ manual |
| `alembic check` not verified in Phase 0 (no bash) | ENVIRONMENT_READY | **Open** — ⚙️ manual |
| 30 SQLite `.db` files on disk | ENVIRONMENT_READY | **Open** — cleanup |
| PostgreSQL not locally running on CI/new machine | ENVIRONMENT_READY | **Open** — Docker Compose suggested |
| Staging E2E replay with production-like stock levels | SUPPLY_CHAIN_E2E (Production NO-GO) | **Open** |
| LAN warehouse opening stock must be ensured for WAREHOUSE items | SUPPLY_CHAIN_E2E (LAN Trial) | **Open** — trial prep |

### Mitigated since earlier reports (not counted as open)

| Item | Resolution |
|------|------------|
| **H-06** N+1 in `operations_dashboard()` | **Fixed** Phase 7 (`DASHBOARD_OPERATIONS_REPORT`) |
| Dashboard fake KPIs / parallel list storm | **Fixed** Phase 7 |
| `/supply-chain/control` duplicate route | **Fixed** Phase 7 |
| Supply chain notification sections | **Implemented** Phase 6 |
| `orderstatus` enum 500 on notification polling | **Partially mitigated** Phase 6 `_safe_section()` — legacy sections empty, supply chain OK |

---

## Deferred Bugs

### C-01 — JWT stored in localStorage

| Check | Result |
|-------|--------|
| Still open? | **Yes** — explicitly deferred Phases 7 and 8 |
| Partially mitigated? | **No** — no httpOnly cookie, no token storage change per phase constraints |
| Fully mitigated? | **No** |
| Production impact | **Blocker** for production (all reports agree) |
| Demo / LAN impact | **Warning** — acceptable with documented caution |

### H-02 — Ledger free-text source/destination types

| Check | Result |
|-------|--------|
| Still open? | **Yes** — deferred Phases 4 → 5 → 6 → 7 → 8 |
| Partially mitigated? | **Yes** — Phases 5–8 verified ledger entries created correctly on receive, issue, partial issue, delivery |
| Fully mitigated? | **No** — still free-text strings in `stock_ledger_service.py` |
| Production impact | **Warning** — reports call enum hardening optional for production; integrity relies on tested paths |

### Other documented deferrals (not C/H numbered)

| Item | First deferred | Still open? | Notes |
|------|----------------|-------------|-------|
| Post-split cancellation + reservation release | Phase 5 → 6 → 7 | **Yes** | NOTIFICATIONS_AUDIT, WAREHOUSE_DELIVERY |
| Proof-of-delivery module (photos, signatures) | Phase 5 → 6 | **Yes** | |
| `orderstatus` PostgreSQL enum alignment | Phase 4 → 6 | **Partial** | Graceful degradation in Phase 6; migration optional |
| BOTH Onda catalog items | Phase 4 | **Yes** | E2E test still skipped |
| Dashboard English KPI labels i18n | Phase 7 | **Yes** | Low severity |
| Legacy replenishment consolidated audit timeline | Phase 4 | **Yes** | |

---

## Production Blockers

Classification for **Demo**, **LAN Trial**, and **Production** using only documented phase verdicts.

### Demo

| Item | Class | Source verdict |
|------|-------|----------------|
| Supply chain workflow E2E | **Ready** | SUPPLY_CHAIN_E2E: **GO** |
| RBAC layer | **Ready** | RBAC_SECURITY: Demo **GO** |
| Dashboard & operations UI | **Ready** | DASHBOARD_OPERATIONS: **Go** |
| Simulated operational volume | **Ready** | SIMULATED_DATA: **Go** |
| C-01 JWT localStorage | **Warning** | Acceptable for controlled demo |
| BOTH item scenario | **Nice To Have** | Scenario C skipped — not required for kitchen/warehouse happy paths |
| Post-split cancellation | **Nice To Have** | Not required for demo path |

**Demo verdict (documented): GO** across Phases 4, 5, 6, 7, 8.

### LAN Trial

| Item | Class | Source verdict |
|------|-------|----------------|
| Workflow stability | **Ready** | Phases 4–8 tests pass |
| Role scope isolation | **Ready** | Phases 2, 4, 6, 7, 8 |
| Alembic at head on trial PostgreSQL | **Blocker** if not run | RBAC_SECURITY LAN condition #1 |
| Area manager assignments (city + brand) | **Blocker** if missing | RBAC_SECURITY LAN condition #2 |
| Delivery users `warehouse_id` set | **Blocker** if missing | RBAC_SECURITY LAN condition #3 |
| Warehouse opening stock for WAREHOUSE items | **Warning** | SUPPLY_CHAIN_E2E LAN condition |
| Onda bakery vs pizza kitchen mapping documented | **Warning** | SUPPLY_CHAIN_E2E LAN condition |
| C-01 JWT localStorage | **Warning** | DASHBOARD_OPERATIONS, SIMULATED_DATA: **Caution** |
| Post-split cancel gaps | **Warning** | WAREHOUSE_DELIVERY: monitor |
| `orderstatus` enum legacy bell parity | **Warning** | NOTIFICATIONS_AUDIT: optional migration |
| Simulation + test data mixed in DB | **Warning** | SIMULATED_DATA, PROJECT_STATUS |
| Demo/seed password rotation | **Warning** | ENVIRONMENT_READY |
| Server deployment / staging replay | **Blocker** for production only | Not performed — local only |

**LAN Trial verdict (documented): GO or CONDITIONAL GO** — Phases 4, 5, 6, 7, 8.

### Production

| Item | Class | Source verdict |
|------|-------|----------------|
| **C-01** JWT localStorage | **Blocker** | All go/no-go tables |
| Formal server hardening / deployment | **Blocker** | Out of scope Phases 0–8; not performed |
| **H-02** ledger typing | **Warning** | Optional per Phase 5; recommended not blocking alone |
| Post-split cancellation | **Warning** | Phase 5 recommends before high-volume production |
| BOTH Onda catalog gap | **Warning** | SUPPLY_CHAIN_E2E production NO-GO list |
| `orderstatus` enum migration | **Warning** | RBAC_SECURITY, NOTIFICATIONS_AUDIT |
| Imported item rejection sign-off | **Warning** | SUPPLY_CHAIN_E2E |
| Staging E2E with production-like stock | **Blocker** | SUPPLY_CHAIN_E2E — not done |
| Hardcoded deployment credentials | **Blocker** | RBAC_SECURITY production NO-GO |
| CI / full test suite coverage | **Warning** | RBAC_SECURITY |
| Alembic drift on target environment | **Blocker** | RBAC_SECURITY |

**Production verdict (documented): NO-GO** — RBAC_SECURITY, SUPPLY_CHAIN_E2E (original), DASHBOARD_OPERATIONS, SIMULATED_DATA, PROJECT_STATUS.

---

## Readiness Matrix

Based on documented phase outcomes only. **READY** = phase report go/no-go or tests pass. **PARTIAL** = conditional go, known gaps, or manual verification pending. **NOT READY** = explicit no-go or unverified blocker.

| Area | Status | Evidence |
|------|--------|----------|
| **Environment** | **PARTIAL** | Phase 0: code-level PASS; runtime smoke, alembic check, SQLite cleanup ⚙️ manual |
| **Database** | **READY** | Phase 0: PostgreSQL + Alembic-only; head `c1d2e3f4a5b6`; Phase 8 integrity tests pass |
| **RBAC** | **READY** | Phase 1: Demo GO, LAN GO with conditions; Phases 2–8 scope tests pass |
| **Users** | **READY** | Phase 2: official user matrix seeded; deployment password drift documented |
| **Items** | **PARTIAL** | Phase 3 import validated; BOTH Onda items missing (Phase 4); RAW/NOT_REQUESTABLE rules enforced |
| **Workflow** | **READY** | Phase 4: 10 passed; Phases 5–8 regression pass; auto-split on approve verified |
| **Kitchen** | **READY** | Phase 4 kitchen E2E; Phase 8 simulation 3,101 POs; delay notifications partial |
| **Warehouse** | **READY** | Phase 5: 12 passed; partial issue, backorder, reservation rules tested |
| **Delivery** | **READY** | Phase 5 shortage/dispatch tests; Phase 8: 4,609 simulated deliveries |
| **Notifications** | **PARTIAL** | Phase 6: supply chain sections live; legacy enum drift; no persisted read/unread |
| **Audit** | **READY** | Phase 6: workflow audit covered; 45,500+ audit rows after simulation |
| **Dashboard** | **READY** | Phase 7: 23 tests; real API KPIs; H-06 fixed |
| **Simulation** | **READY** | Phase 8: 90-day / 3,483 requests; integrity tests 9/9 |

---

## LAN Trial Recommendation

### Answer: **YES WITH CONDITIONS**

Documented phase verdicts consistently support LAN trial **after** environment prep. Production remains **NO-GO**.

### Exact conditions (consolidated from reports)

1. **PostgreSQL target**
   - Run `alembic upgrade head` on LAN PostgreSQL (`c1d2e3f4a5b6`).
   - Confirm `DATABASE_URL` points to PostgreSQL (not default SQLite).

2. **User & scope matrix**
   - Run / verify `seed_phase2_official_users.py` (or equivalent) on trial DB.
   - Confirm all area managers have active `AreaManagerAssignment` (city + brand).
   - Confirm delivery users have non-null `warehouse_id`.
   - Document Onda bakery vs pizza kitchen section → item mapping.

3. **Inventory & catalog**
   - Ensure warehouse opening stock for WAREHOUSE-sourced items on trial branches.
   - Acknowledge BOTH-item routing untested for Onda until catalog gap closed.

4. **Security & credentials**
   - Accept **C-01** risk for LAN (JWT in localStorage) — controlled network only.
   - Rotate demo/seed passwords before real branch users touch the system.
   - Resolve deployment `admin` password drift if using deployment bootstrap.

5. **Data hygiene**
   - Decide whether trial DB is clean or includes Phase 8 simulation + test history.
   - Do not run `seed_4months.py` without idempotency review.

6. **Operational monitoring**
   - Monitor post-split cancellation / stale reservation edge cases.
   - Restart uvicorn after backend updates.
   - Watch notification bell for legacy section gaps (`orderstatus` enum).

7. **Deployment scope**
   - LAN trial is **local/LAN only** — no production server deploy until Phase 9+ addresses C-01, staging E2E, and credential hardening.

---

## Required Work Before Phase 9

Phase 9 is **Go-Live Readiness Audit** — this pre-check completes preparation. Before starting Phase 9 implementation:

### Prerequisites (complete or confirm)

- [x] Phases 0–8 committed locally (documented in `PROJECT_STATUS_REPORT.md`)
- [x] Cross-phase risk synthesis (this document)
- [ ] Manual Phase 0 runtime checks on LAN target machine (smoke test, `alembic current == head`)
- [ ] Decide LAN trial DB strategy (clean vs existing simulated data)
- [ ] Identify LAN trial operator roster aligned to Phase 2 official users

### Phase 9 audit should address (from documented gaps only)

1. **Security:** C-01 disposition plan; deployment credential rotation policy
2. **Operations:** Post-split cancellation design; shortage follow-up workflow
3. **Data:** H-02 enum hardening decision; BOTH Onda catalog; trial DB baseline
4. **Deployment:** Staging E2E replay checklist; production NO-GO criteria sign-off
5. **Notifications:** `orderstatus` enum migration decision; read/unread requirements
6. **Performance:** Super-admin dashboard load test on LAN hardware with Phase 8 dataset
7. **UI:** i18n backlog; branch delivery drill-down UX
8. **Verification:** Consolidated go/no-go gate with sign-off owners for Demo / LAN / Production

### Explicitly out of scope for Phase 9 pre-check (per phase boundaries)

- AI, prediction, forecasting, optimization
- Procurement module
- Push / email / SMS / WhatsApp notifications
- Server deployment execution (audit planning only)

---

*Audit-only document. No code, migrations, tests, or features created.*
