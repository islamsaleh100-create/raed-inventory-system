# LAN Trial Blockers Sprint Report

**Branch:** `lan-readiness/blockers-sprint-2026-06-15`  
**Date:** 2026-06-15  
**Scope:** Operational clarity blockers only (no new features, AI, deployment)

---

## 1. Files Reviewed

| Area | Files |
|------|-------|
| Branch names | `supply_chain_serializers.py`, `branch_requests.py`, `warehouse_lines.py`, `delivery_orders.py`, `production_orders.py` |
| Owner / next action | `branch_request_detail_service.py`, `BranchRequestDetailPage.jsx` |
| Stock visibility | `supply_chain_serializers.py`, `warehouse_lines.py`, `schemas/__init__.py`, `SupplyChainPages.jsx` |
| Search & filters | `branch_requests.py`, `warehouse_lines.py`, `delivery_orders.py`, `SupplyChainPages.jsx` |
| Confirm dialogs | `SupplyChainPages.jsx`, `ConfirmDialog.jsx` |
| Legacy nav | `AppLayoutV2.jsx` (from Sprint A — verified, no change) |
| Opening stock gate | `validate_lan_opening_stock.py` (from Sprint A — verified) |
| Tests | `tests/test_lan_trial_blockers.py` |

---

## 2. Branch Name Improvements

**Status: Complete**

Human-readable branch names (`branch_name`) are returned on:

- Warehouse line list and detail
- Delivery order list and detail
- Production order list
- Branch request detail (`GET /branch-requests/{id}/detail`)

Examples visible in API payloads: `Onda 1 - ARKAN`, `Ronaldos Al Khobar`, `Shawarma Al Khobar` (exact strings depend on master data).

No unrelated endpoints were refactored.

---

## 3. Current Owner Implementation

**Status: Complete**

`build_branch_request_detail()` now uses `_resolve_workflow_owner_next()` which maps **real workflow state** (production orders, warehouse lines, delivery orders) to Arabic owner labels:

| Owner (AR) | When |
|------------|------|
| الفرع | Draft |
| مدير المنطقة | Submitted, awaiting approval |
| المطبخ | Open production orders |
| المستودع | Pending warehouse issue |
| التسليم | Open delivery orders |
| مكتمل | Delivered or rejected |

Displayed on request detail page as **المالك الحالي**.

---

## 4. Next Action Implementation

**Status: Complete**

Same workflow resolver drives **next_action_ar**, e.g.:

- بانتظار موافقة مدير المنطقة
- بانتظار الإنتاج في المطبخ
- بانتظار الصرف من المستودع
- بانتظار التسليم
- مكتمل

Displayed on request detail page as **الإجراء المطلوب التالي**.

---

## 5. Available Stock Visibility

**Status: Complete**

Warehouse line API responses now include:

- `current_stock`
- `reserved_stock`
- `available_stock`

Warehouse fulfillment UI shows **المخزون المتاح** column before issue actions. Full/partial issue confirm dialogs show available stock alongside requested, issued, and remaining quantities.

Issue logic unchanged — visibility only.

---

## 6. Search & Filter Results

**Status: Complete**

| Screen | Filters |
|--------|---------|
| Branch Requests | Search, status, date range |
| Area Approvals | Search, status, date range |
| Warehouse | Search, branch, item, status, date range |
| Delivery | Search, branch, status, date range |

Backend query params: `search`, `status`, `branch_id`, `item_id`, `date_from`, `date_to`.

Search matches branch name, item name/code, request number.

**Bug fixed:** Area manager + search no longer causes duplicate `branches` SQL alias.

---

## 7. Confirmation Dialog Audit

**Status: Complete**

| Action | Dialog | Context shown |
|--------|--------|---------------|
| Approve | ✅ | Route counts (kitchen/warehouse lines) |
| Reject | ✅ **Added** | Request no, line count, rejection reason |
| Full issue | ✅ | Branch, item, **available stock**, qty |
| Partial issue | ✅ | Branch, item, **available stock**, qty, delay reason |
| Send to warehouse (kitchen) | ✅ | From Sprint A |
| Create delivery | ✅ **Added** | Branch, item, issued/remaining qty |
| Out for delivery | ✅ **Added** | Order id, branch, line count, dispatched qty |
| Delivered | ✅ | Branch, quantities, receiver name |

---

## 8. Legacy Navigation Audit

**Status: Verified (Sprint A)**

Trial roles (`branch_user`, `area_manager`, `kitchen_*`, `warehouse_*`, `delivery_user`) do not see Legacy Orders / Warehouse / Delivery nav items.

`admin` and `super_admin` retain full navigation including legacy modules.

Routes not deleted; navigation hiding only.

---

## 9. Opening Stock Validation Result

**Script:** `raed_inventory/backend/validate_lan_opening_stock.py`  
**Report:** `raed_inventory/LAN_OPENING_STOCK_VALIDATION_REPORT.md`

On dev PostgreSQL database: **GO** (trial warehouses/branches stocked; no blocking zero-stock rows for requestable items).

Re-run on LAN trial DB before go-live.

---

## 10. Automated Test Results

**Command:** `DATABASE_URL=postgresql://... RATE_LIMIT_ENABLED=false pytest tests/test_lan_trial_blockers.py tests/test_lan_readiness_ux_sprint_a.py -v`

| Suite | Result |
|-------|--------|
| `test_lan_trial_blockers.py` | **15 passed** |
| `test_lan_readiness_ux_sprint_a.py` | **9 passed** |
| **Total LAN tests** | **24 passed** |

Coverage includes: branch names, owner/next action, stock fields, filters, confirm dialog titles, legacy nav policy, opening stock script.

---

## 11. Regression Results

**Command:** Phase 4–7 with PostgreSQL + API at `:8010`

| Phase | Passed | Skipped | Failed |
|-------|--------|---------|--------|
| Phase 4 | 10 | 1 (BOTH item doc — pre-existing) | 0 |
| Phase 5 | 12 | 0 | 0 |
| Phase 6 | 12 | 0 | 0 |
| Phase 7 | 23 | 0 | 0 |
| **Total** | **57** | **1** | **0** |

No regressions introduced by this sprint.

---

## 12. Remaining LAN Risks

1. **Opening stock on fresh LAN DB** — validation must pass on production-like seed before trial start.
2. **Kitchen send-to-warehouse** — confirm exists; no quantity preview (lower risk than warehouse issue).
3. **Mobile / offline** — out of scope; trial assumes desktop LAN browsers.
4. **Training** — filters reduce confusion but first-week support should expect questions on partial fulfillment.
5. **Stale uvicorn** — after deploy, restart backend so list/search/stock enrichment is live.

---

## 13. LAN Trial Recommendation

### Verdict: **GO WITH CONDITIONS**

| Gate | Status |
|------|--------|
| Demo | GO |
| **LAN Trial** | **GO WITH CONDITIONS** |
| Production | NO-GO |

**Conditions for LAN Trial start:**

1. Run `validate_lan_opening_stock.py --write-report` on trial database → must be GO or GO WITH WARNINGS (not NO-GO).
2. Restart backend after deploying this branch.
3. Brief warehouse/delivery users on new stock column and filters (5-minute walkthrough).
4. Keep admin accounts for fallback legacy access during trial week 1.

This sprint removes the highest-frequency adoption blockers: *where is my order, who owns it, what happens next, can we issue this, and can I find my queue*.
