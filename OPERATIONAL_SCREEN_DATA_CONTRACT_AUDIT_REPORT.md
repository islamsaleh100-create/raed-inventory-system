# Operational Screen Data Contract Audit Report

**Date:** 2026-06-15  
**Branch:** `lan-readiness/operational-screen-data-contracts-2026-06-15`  
**Scope:** Root-cause audit of live UI data paths for branch, area, kitchen, warehouse, and delivery operational screens.

---

## 1. Screens Audited

| Role | Screen | Frontend component |
|------|--------|-------------------|
| Branch Manager | Dashboard, Branch Requests, Request Detail | `SupplyChainPages.jsx`, `BranchRequestDetailPage.jsx` |
| Area Manager | Pending Approvals, Scoped Branch Requests | `SupplyChainApprovalsPage` in `SupplyChainPages.jsx` |
| Kitchen Section Manager | Production Queue | `SupplyChainKitchenPage` in `SupplyChainPages.jsx` |
| Warehouse Manager/User | Warehouse Execution | `SupplyChainWarehousePage` in `SupplyChainPages.jsx` |
| Delivery User | Delivery Orders | `SupplyChainDeliveryPage` in `SupplyChainPages.jsx` |

---

## 2. Actual API Endpoints Used

| Screen | HTTP | Endpoint |
|--------|------|----------|
| Branch requests list | GET | `/api/v1/branch-requests` |
| Branch request detail | GET | `/api/v1/branch-requests/{id}/detail` |
| Area approvals | GET | `/api/v1/branch-requests?status=SUBMITTED` |
| Kitchen production queue | GET | `/api/v1/production-orders` |
| Warehouse execution | GET | `/api/v1/warehouse-lines` |
| Warehouse actions | POST | `/api/v1/warehouse-lines/{id}/receive`, `/issue`, `/partial-issue` |
| Delivery orders | GET | `/api/v1/delivery-orders` |
| Supply chain dashboard | GET | `/api/v1/supply-chain/dashboard` |

Frontend API client: `frontend/src/services/api.js` → `supplyChainApi.*`

---

## 3. Payload Fields Before Fix

### Warehouse Execution (primary symptom)

Live UI showed `Branch = —` and `Available Stock = —`.

**Observed on running server (port 8010, pre-restart):**

```json
{
  "id": 5345,
  "branch_id": 9,
  "source_type": "BRANCH_REQUEST",
  "status": "DELIVERED",
  "item": { "...": "..." }
}
```

Missing keys: `branch_name`, `available_stock`, `current_stock`, `reserved_stock`.

**Root cause:** The uvicorn process was serving code from before `supply_chain_serializers.enrich_warehouse_lines` was wired into list responses. List/detail enrichment existed in source but the live process had not been restarted.

Additionally, **mutation endpoints** (`receive`, `issue`, `partial-issue`, `delay-reason`) returned raw ORM rows without passing through `warehouse_line_out`, so any client reading mutation responses directly would also see missing enrichment fields.

### Production orders

- **List** endpoint already used `production_order_out` (branch_name present).
- **GET and mutation** endpoints returned raw `ProductionOrder` ORM → `branch_name` and `destination_warehouse_name` absent in serialized JSON.

### Delivery orders

- **List** endpoint already used `delivery_order_out`.
- **Create / out-for-delivery / deliver** returned raw `_load_delivery_order` → `branch_name` absent on mutation responses.

### Branch / Area / Kitchen list endpoints

Already enriched via `_branch_request_out`, `production_order_out`, `delivery_order_out`. No schema gap found in current source when tested against PostgreSQL seed data.

---

## 4. Root Causes Found

| # | Root cause | Impact |
|---|------------|--------|
| RC-1 | Stale backend process not restarted after serializer enrichment landed in prior sprint | Live UI on `:3000` proxy received un-enriched warehouse line payloads |
| RC-2 | Warehouse line POST mutations returned ORM object, not `_serialize_warehouse_line` | Mutation refresh paths could lose branch/stock fields |
| RC-3 | Production order GET/mutations returned ORM, not `production_order_out` | Detail/action responses missing `branch_name` |
| RC-4 | Delivery order mutations returned ORM, not `delivery_order_out` | Delivery action responses missing `branch_name` |
| RC-5 | Prior tests asserted enrichment on list endpoints only; mutation/get contracts not covered | Regression escaped to live UI when server was stale |

**Not root causes (confirmed expected behaviour):**

- `لا إجراءات متاحة` on warehouse lines in `DELIVERED` / completed statuses — status-gated actions working as designed.
- `available_stock = 0` with `current_stock = 98` — stock fully reserved for pending branch-request lines; numeric zero is correct, not missing data.

---

## 5. Fixes Applied

### Backend

1. **`warehouse_lines.py`**
   - Added `_serialize_warehouse_line()` — always applies `warehouse_line_out` + stock lookup.
   - All GET/POST warehouse line endpoints now return serialized enriched payloads.
   - List query eager-loads `source_request_line` for consistency.

2. **`production_orders.py`**
   - Added `_serialize_production_order()`.
   - GET `/production-orders/{id}` and all production mutations now return `production_order_out`.

3. **`delivery_orders.py`**
   - Added `_serialize_delivery_order()`.
   - Create, out-for-delivery, and deliver endpoints now return `delivery_order_out`.

4. **Restarted backend** on `127.0.0.1:8010` so live UI receives updated serializers.

### Tests

- Added `tests/test_operational_screen_data_contracts.py` — 10 contract tests hitting exact UI endpoints for all five roles, including warehouse mutation enrichment.

---

## 6. Branch Screen Results

| Field | Endpoint | Result |
|-------|----------|--------|
| `request_no` | list | PASS |
| `branch_name` | list | PASS (`Onda Arkan`) |
| `current_owner_ar`, `next_action_ar` | detail | PASS |
| `timeline` | detail | PASS (12 events on sample BR-003912) |
| partial quantities | detail fulfillment_lines | PASS |

---

## 7. Area Manager Screen Results

| Field | Endpoint | Result |
|-------|----------|--------|
| `branch_name` | SUBMITTED list | PASS |
| `request_no`, `status` | SUBMITTED list | PASS |
| Approve/Reject actions | UI + API | PASS (existing RBAC) |

---

## 8. Kitchen Screen Results

| Field | Endpoint | Result |
|-------|----------|--------|
| `branch_name` | production list + get | PASS |
| `item` / `item_id` | production list | PASS |
| `status` | production list | PASS (`PENDING`, etc.) |
| `destination_warehouse_name` | production list | PASS when branch warehouse linked |

---

## 9. Warehouse Screen Results

| Field | Endpoint | Result |
|-------|----------|--------|
| `branch_name` | list / get / receive | PASS (`Onda Arkan`) |
| `available_stock` | list / get / receive | PASS (numeric `0` when fully reserved) |
| `current_stock` | list / get / receive | PASS (`98.000` on sample line) |
| `reserved_stock` | list | PASS |
| Actions on DELIVERED lines | UI | Expected: `لا إجراءات متاحة` |
| Actions on PENDING lines | receive button | PASS (contract test) |

**Live proxy verification (`http://localhost:3000/api/v1/warehouse-lines`):**

```
branch_name=Onda Arkan  available_stock=0
```

---

## 10. Delivery Screen Results

| Field | Endpoint | Result |
|-------|----------|--------|
| `branch_name` | list + get | PASS |
| `qty_dispatched`, `qty_delivered`, `shortage_qty` | line items | PASS |
| `receiver_name` | delivered orders | PASS when delivered |
| `item` on lines | list | PASS |

---

## 11. Automated Test Results

```
tests/test_operational_screen_data_contracts.py     10 passed
tests/test_lan_readiness_ux_sprint_a.py              9 passed
tests/test_role_action_completeness.py              18 passed
tests/test_role_screen_visibility_audit.py          40 passed
────────────────────────────────────────────────────────────
Total                                               77 passed
```

Environment: PostgreSQL, `RATE_LIMIT_ENABLED=false`

---

## 12. Manual Browser Verification

Verified via live API through Vite proxy (`localhost:3000` → backend `8010`) for official users:

| User | Check | Result |
|------|-------|--------|
| `warehouse_dammam_manager` | Warehouse lines JSON has `branch_name`, stock fields | PASS |
| `branch_onda_1_arkan` | Branch requests + detail contract | PASS (automated) |
| `area_dammam_onda` | SUBMITTED list `branch_name` | PASS (automated) |
| `kitchen_dammam_bakery_and_sweets_mgr` | Production list `branch_name` | PASS (automated) |
| `delivery_dammam` | Delivery list `branch_name` + line qty fields | PASS (automated) |

**UI notes:**

- Warehouse table binds `branchDisplay(line)` → `line.branch_name` — now populated.
- Stock column binds `line.available_stock` — now numeric (0) instead of em dash.
- Completed warehouse lines correctly show no action buttons.

---

## 13. Remaining Data Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| Branch request **list** does not include `current_owner` / `next_action` | Low | By design — only on detail endpoint; UI links to detail page |
| Warehouse lines do not expose `request_number` in list payload | Low | UI shows `WL-{id}`; `source_request_id` available if needed later |
| `available_stock = 0` may look like shortage when stock is reserved | Info | Consider UI label "متاح (بعد الحجز)" — out of scope for this sprint |
| Backend restart required after deploy | Ops | Document in runbook: restart uvicorn after serializer changes |

---

## 14. LAN Trial Recommendation

**Verdict: GO WITH CONDITIONS**

**Conditions:**

1. Restart backend (and frontend if needed) on each LAN trial host before user sessions — confirmed fix for missing warehouse fields.
2. Train warehouse users: `available_stock = 0` with pending branch-request reservations is expected, not a data error.
3. Use `run_local.ps1` or `start_backend.bat` + `start_frontend.bat` for consistent startup.

Operational screen data contracts are satisfied on live UI endpoints after backend restart and serializer fixes on mutation paths.
