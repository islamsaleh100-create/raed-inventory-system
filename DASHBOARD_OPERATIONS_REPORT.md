# Dashboard & Operations UI — Phase 7 Report

**Date:** 2026-06-14  
**Branch:** `phase7/dashboard-operations-ui-2026-06-14`  
**Alembic head:** `c1d2e3f4a5b6` (no new migrations)

---

## 1. Files Reviewed

| Area | Files |
|------|-------|
| Frontend routing | `raed_inventory/frontend/src/App.jsx` |
| Dashboard UI | `raed_inventory/frontend/src/pages/supply_chain/SupplyChainPages.jsx` |
| Legacy dashboards | `raed_inventory/frontend/src/pages/shared/DashboardPages.jsx` |
| API client | `raed_inventory/frontend/src/services/api.js` |
| Route guards | `raed_inventory/frontend/src/components/common/RouteRoleGuard.jsx` |
| Backend dashboard | `raed_inventory/backend/app/routers/dashboard.py` |
| Supply chain dashboard | `raed_inventory/backend/app/routers/supply_chain.py` |
| Schemas | `raed_inventory/backend/app/schemas/__init__.py` |
| Operations routers | `branch_requests.py`, `production_orders.py`, `warehouse_lines.py`, `delivery_orders.py`, `notifications.py` |
| Prior reports | `SUPPLY_CHAIN_E2E_REPORT.md`, `WAREHOUSE_DELIVERY_HARDENING_REPORT.md`, `NOTIFICATIONS_AUDIT_REPORT.md` |

---

## 2. Widgets Verified

Single route `/dashboard` via `SmartDashboard` → `SupplyChainControlDashboard` for all supply-chain roles.

| Role | Widgets (real API) |
|------|-------------------|
| **super_admin** | Super-admin overview (summary KPIs, pipeline, ops tables, audit list) + notifications |
| **admin / operations_manager** | Requests today, pending approvals, in production, warehouse pending, partial/backorders, ready/delivered, ops alerts, notifications |
| **area_manager** | Pending approvals, delayed requests, partial/backorders, delivered today |
| **branch_user / branch_manager** | My requests today, pending approval, in production, warehouse processing, out for delivery, delivered, partial |
| **kitchen_section_manager** | Production pending/in progress (list API), ready, sent to warehouse, waiting/delayed |
| **warehouse_user / warehouse_manager** | Fulfillment queue, ready from kitchen, partial, backorders, delay reasons, available lines |
| **delivery_user** | Ready, out for delivery, delivered today, shortages |

All KPI values come from `GET /api/v1/supply-chain/dashboard` except kitchen pending/in-progress split (production list API) and super-admin executive block (`/super-admin-overview`).

---

## 3. Widget → API Mapping

| Widget | Roles | Endpoint | Scope | Drill-down |
|--------|-------|----------|-------|------------|
| Requests today | admin, branch | `GET /supply-chain/dashboard` | role-scoped | `/supply-chain/branch-requests` |
| Pending approvals | admin, area | `GET /supply-chain/dashboard` | city+brand / all | `/supply-chain/approvals` |
| In production | admin, branch, kitchen | `GET /supply-chain/dashboard` | section / branch / all | `/supply-chain/kitchen` |
| Production pending / in progress | kitchen | `GET /production-orders?status=` | kitchen section | `/supply-chain/kitchen` |
| Warehouse pending | admin, wh, branch | `GET /supply-chain/dashboard` | warehouse / branch | `/supply-chain/warehouse` |
| Partial / backorders | admin, area, wh | `GET /supply-chain/dashboard` | scoped | `/supply-chain/warehouse` |
| Ready for delivery | admin, delivery | `GET /supply-chain/dashboard` | delivery warehouse | `/supply-chain/delivery` |
| Out for delivery | branch, delivery | `GET /supply-chain/dashboard` | scoped | `/supply-chain/delivery` |
| Delivered today | all SC roles | `GET /supply-chain/dashboard` | scoped | `/supply-chain/delivery` |
| Notifications | all | `GET /notifications/summary` | user | `/notifications` |
| Super-admin overview | super_admin | `GET /supply-chain/super-admin-overview` | platform | various ops routes |
| Legacy ops alerts | operations_manager | `GET /dashboard/alerts-summary` | platform | `/operations` |

---

## 4. Operations Screens

Existing Phase 4 screens validated via API tests; no new screens added.

| Screen | Route | Capabilities |
|--------|-------|--------------|
| Branch requests | `/supply-chain/branch-requests` | Create, draft, submit, history, timeline |
| Area approvals | `/supply-chain/approvals` | Pending list, approve/reject/modify |
| Kitchen production | `/supply-chain/kitchen` | Queue, start, partial ready, ready, send to warehouse |
| Warehouse fulfillment | `/supply-chain/warehouse` | Receive, issue, partial, delay, backorders |
| Delivery | `/supply-chain/delivery` | Ready, out for delivery, delivered, shortage |

---

## 5. Drill-down Routes

| Widget / link | Target |
|---------------|--------|
| Pending approvals | `/supply-chain/approvals` |
| Production pending | `/supply-chain/kitchen` |
| Warehouse pending | `/supply-chain/warehouse` |
| Ready for delivery | `/supply-chain/delivery` |
| My requests | `/supply-chain/branch-requests` |
| Notifications | `/notifications` |
| `/supply-chain/control` | Redirects → `/dashboard` |

---

## 6. Route Guards

| Route | Frontend guard | Backend alignment |
|-------|----------------|-------------------|
| `/dashboard` | Auth only; `SmartDashboard` picks widgets | N/A |
| `/supply-chain/branch-requests` | branch, area, auditor, admin | `SCOPED_ROLES` |
| `/supply-chain/approvals` | area, auditor, admin | area_manager actions |
| `/supply-chain/kitchen` | kitchen, auditor, admin | `PRODUCTION_ROLES` |
| `/supply-chain/warehouse` | warehouse, auditor, admin | `WAREHOUSE_ROLES` |
| `/supply-chain/delivery` | delivery, auditor, admin | `DELIVERY_VIEW_ROLES` |
| `/notifications` | authenticated | all users |
| `/audit/*` | auditor, admin (+ findings: area, ops) | read-only auditor scope |

**Note:** `operations_manager` has dashboard API access but is not in supply-chain page guards (matches backend — ops uses legacy `/operations` for execution).

---

## 7. Empty States

`QueuePreviewBlock` now renders explicit messages when queues are empty (e.g. "No pending approvals.", "No deliveries assigned.") instead of hiding the card.

---

## 8. Notification UI

- Existing Phase 6 notification bell and `/notifications` page unchanged.
- Dashboard adds **Notifications** KPI card bound to `GET /notifications/summary` (`total` count).
- No push/email/SMS/WebSocket added.

---

## 9. Audit UI

Existing audit console validated (not rebuilt):

- `/audit/dashboard`, `/audit/trail`, `/audit/findings` for `internal_auditor`, `admin`, `super_admin`.
- Super-admin dashboard includes recent audit events linking to `/audit/logs` → `/audit/trail`.

---

## 10. UI Audit Findings

| Finding | Severity | Status |
|---------|----------|--------|
| `/supply-chain/control` was separate dashboard route | Medium | Fixed — redirects to `/dashboard` |
| Dashboard used 6–8 parallel list calls for KPI counts | Medium | Fixed — primary KPIs from `/supply-chain/dashboard` |
| `QueuePreviewBlock` returned null when empty | Low | Fixed — empty state text |
| `WarehouseDashboard` expected `ready_to_dispatch` | Low | Fixed — backend alias + frontend fallback |
| Super-admin "Delayed" linked to old control route | Low | Fixed → approvals |
| `operations_manager` not on SC operational routes | Info | By design — backend has no SC execute role |
| Some KPI labels hardcoded English on dashboard | Low | Deferred — i18n keys exist for core labels |
| Super-admin block includes analytics section | Info | Pre-existing executive view; not new analytics module |

---

## 11. Automated Tests

**File:** `raed_inventory/backend/tests/test_phase7_dashboard_operations.py`

Coverage:
- Dashboard scope: branch, area, kitchen, warehouse, delivery, admin
- Drill-down endpoint accessibility (5 roles × ops paths)
- Operations screen list APIs
- Security isolation (branch, area, warehouse, delivery)
- H-06 regression: `GET /dashboard/operations` returns 200
- Notifications summary

**Run:**
```powershell
$env:RATE_LIMIT_ENABLED='false'
cd raed_inventory/backend
uvicorn app.main:app --port 8010
python -m pytest tests/test_phase7_dashboard_operations.py -v
```

---

## 12. Regression Results

| Suite | Result |
|-------|--------|
| Phase 4 (`test_phase4_supply_chain_e2e.py`) | 10 passed, 1 skipped |
| Phase 5 (`test_phase5_warehouse_delivery_hardening.py`) | 12 passed |
| Phase 6 (`test_phase6_notifications_audit.py`) | 12 passed |
| Phase 7 (`test_phase7_dashboard_operations.py`) | 23 passed |

---

## 13. Remaining Risks

1. **Server reload:** Backend changes require uvicorn restart; stale process served old dashboard schema during initial test run.
2. **Super-admin dashboard complexity:** Executive overview still heavy; acceptable for demo but may feel slow on large datasets.
3. **Kitchen KPI split:** Pending vs in-progress still requires two list calls (dashboard aggregates `in_production`).
4. **Branch drill-down:** Branch KPIs for warehouse/delivery link to branch-requests (read-only view) rather than dedicated branch delivery view.

---

## 14. Bugs Deferred

| ID | Issue | Status |
|----|-------|--------|
| **C-01** | JWT stored in localStorage | **Deferred** — do not move to httpOnly cookies in this phase |
| **H-02** | `stock_ledger_service.py` uses free-text source/destination types | **Deferred** |

---

## 15. Go / No-Go

| Gate | Demo | LAN Trial | Production |
|------|------|-----------|------------|
| Real workflow data on dashboard | **Go** | **Go** | **Go** (with monitoring) |
| Role-scoped widgets | **Go** | **Go** | **Go** |
| Operational screens wired | **Go** | **Go** | **Go** |
| Automated test coverage | **Go** | **Go** | **Go** |
| Auth token storage (C-01) | **Go** | **Caution** | **No-Go** until C-01 addressed |
| Server deployment | N/A | Local only | **No-Go** — not in scope |

**Overall:** **Go for demo and LAN trial.** Production deployment remains blocked on C-01 and formal server hardening (out of Phase 7 scope).

---

## Backend Changes Summary

### H-06 fix (`dashboard.py`)
- `operations_dashboard()`: batch-load `Item` and `Branch` via `id.in_(...)` instead of per-row queries.
- `branch_dashboard` / stock status: `joinedload` for item relations.

### Supply chain dashboard (`supply_chain.py`)
- Extended `DASHBOARD_ROLES` with `branch_user`, `branch_manager`, `operations_manager`.
- Added scoped KPI fields: `requests_today`, `warehouse_pending`, `backorders`, `ready_for_delivery`, `out_for_delivery`, `delivered_today`, `production_ready`, `sent_to_warehouse`, `my_requests`, `shortages`, `partial_warehouse`.
- Branch-user scoping block added.

### Frontend
- `supplyChainApi.dashboard()` added.
- `SmartDashboard` renders `SupplyChainControlDashboard` at `/dashboard` for all SC roles.
- `/supply-chain/control` redirects to `/dashboard`.
