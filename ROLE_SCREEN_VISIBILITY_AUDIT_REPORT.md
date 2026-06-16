# Role Screen Visibility Audit Report

**Branch:** `lan-readiness/role-screen-visibility-audit-2026-06-15`  
**Date:** 2026-06-15  
**Purpose:** Final visibility audit before LAN Trial — navigation, screens, action buttons, scope isolation

---

## 1. Roles Tested

| Role | Tested |
|------|--------|
| Super Admin | ✅ |
| Admin | ✅ |
| Area Manager | ✅ (3 users) |
| Branch User | ✅ (3 users) |
| Kitchen Section Manager | ✅ (3 users) |
| Warehouse Manager | ✅ (Dammam + Riyadh) |
| Warehouse User | ✅ (Dammam + Riyadh) |
| Delivery User | ✅ (Dammam + Riyadh) |
| Internal Auditor | ✅ (`audit.officer`) |

---

## 2. Users Tested

All official Phase 2 users verified via `GET /api/v1/auth/me`:

- `super.admin`, `admin`
- `area_dammam_onda`, `area_dammam_restaurants`, `area_riyadh_all`
- `branch_onda_1_arkan`, `branch_pizza_1_al_khobar`, `branch_shawarma_1_khobar`
- `kitchen_dammam_meat_and_chicken_mgr`, `kitchen_dammam_bakery_and_sweets_mgr`, `kitchen_dammam_pizza_mgr`
- `warehouse_dammam_manager`, `warehouse_dammam_user`, `warehouse_riyadh_manager`, `warehouse_riyadh_user`
- `delivery_dammam`, `delivery_riyadh`
- `audit.officer`

---

## 3. Navigation Findings

### Correct (no change needed)

| Role | Visible nav | Hidden legacy (LAN trial) |
|------|-------------|---------------------------|
| Branch User | Dashboard, Supply Chain (control, branch requests), Daily Inventory, Branch Stock | Legacy Orders, Receiving, Legacy Warehouse/Delivery |
| Area Manager | Dashboard, Supply Chain (control, branch requests, approvals), Operations reports, Quality/Training subset | Legacy Orders/Warehouse/Sales Delivery |
| Kitchen | Dashboard, Supply Chain (control, kitchen) | Legacy kitchen/daily orders paths |
| Warehouse | Dashboard, Supply Chain (control, warehouse) | Legacy warehouse modules |
| Delivery | Dashboard, Supply Chain (control, delivery) | Legacy sales delivery module |
| Admin / Super Admin | Full nav including legacy + admin setup | — |
| Internal Auditor | Audit section + **Supply Chain read-only nav (fixed)** | Write actions hidden in UI |

### Issue found & fixed

**Internal Auditor missing Supply Chain nav** — routes allowed read-only access but sidebar had no links. Added `internal_auditor` to all supply-chain nav items.

---

## 4. Dashboard Findings

| Role | Dashboard behavior | Status |
|------|-------------------|--------|
| Branch / Kitchen / Warehouse / Delivery / Area | `SupplyChainControlDashboard` role widgets | ✅ |
| Internal Auditor | Redirect to `/audit/dashboard` | ✅ |
| Admin / Super Admin | Supply chain control + super-admin overview | ✅ |
| Super Admin | Executive pipeline widgets with drill-downs | ✅ |

No cross-scope data leaks detected in Phase 7 dashboard tests.

---

## 5. Screen Findings

| Screen | Branch | Area Mgr | Kitchen | Warehouse | Delivery | Auditor | Admin |
|--------|--------|----------|---------|-----------|----------|---------|-------|
| Branch Requests list | Own branch + create | Scoped list (fixed) | ❌ | ❌ | ❌ | Read-only | All branches |
| Approvals | ❌ | ✅ | ❌ | ❌ | ❌ | Read-only | ✅ |
| Kitchen production | ❌ | ❌ | ✅ section scope | ❌ | ❌ | Read-only | ✅ |
| Warehouse fulfillment | ❌ | ❌ | ❌ | ✅ wh scope | ❌ | Read-only | ✅ |
| Delivery orders | ❌ | ❌ | ❌ | ❌ | ✅ wh scope | Read-only | ✅ |
| Request detail/timeline | ✅ | ✅ scoped | via API | via API | via API | Read-only | ✅ |

### Issue found & fixed

**Area Manager on Branch Requests page** showed empty list (required `branch_id`). Fixed: scoped list loads without branch filter; create form hidden (`canCreateRequest` only for branch roles).

---

## 6. Button Visibility Matrix

| Button | Branch | Area Mgr | Kitchen | Warehouse | Delivery | Auditor |
|--------|--------|----------|---------|-----------|----------|---------|
| Create / Submit Request | ✅ | ❌ hidden | ❌ | ❌ | ❌ | ❌ |
| Approve / Reject | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ read-only banner |
| Start / Ready / Partial Ready | ❌ | ❌ | ✅ status-gated | ❌ | ❌ | ❌ |
| Send To Warehouse | ❌ | ❌ | ✅ when READY/PARTIAL_READY | ❌ | ❌ | ❌ |
| Receive / Issue / Partial Issue | ❌ | ❌ | ❌ | ✅ status-gated | ❌ | ❌ |
| Create Delivery (from WH line) | ❌ | ❌ | ❌ | ✅ when issued | ❌ | ❌ |
| Out For Delivery | ❌ | ❌ | ❌ | ❌ | ✅ when READY | ❌ |
| Mark Delivered | ❌ | ❌ | ❌ | ❌ | ✅ when OUT_FOR_DELIVERY + confirm | ❌ |

Daily kitchen order buttons already status-gated (receive → start → ready → send).

---

## 7. Hidden Required Buttons

| Issue | Resolution |
|-------|------------|
| Area Manager could not see scoped branch request list | **Fixed** — list API called without `branch_id` |
| Internal Auditor had no nav to supply chain screens | **Fixed** — nav items added |
| Send To Warehouse visible on all production statuses | **Fixed** — only READY / PARTIAL_READY |
| Issue buttons visible on completed warehouse lines | **Fixed** — status + pending qty gates |
| Deliver button visible before out-for-delivery | **Fixed** — OUT_FOR_DELIVERY only |

---

## 8. Visible Forbidden Buttons

| Issue | Resolution |
|-------|------------|
| Area Manager saw create-request form (non-functional) | **Fixed** — form hidden |
| All production action buttons always visible | **Fixed** — status helpers |
| Warehouse issue on DELIVERED lines | **Fixed** |
| Delivery "Delivered" on READY orders | **Fixed** |

No forbidden backend writes exposed — API 403 tests pass for branch/kitchen/delivery on warehouse issue and branch approve.

---

## 9. Scope Leaks

| Test | Result |
|------|--------|
| Wrong area manager cannot approve | ✅ Phase 4 |
| Warehouse Riyadh vs Dammam line access | ✅ 403 |
| Delivery scoped to warehouse | ✅ Phase 4/7 |
| Kitchen section isolation | ✅ Phase 6/7 |
| Branch user list own branch only | ✅ Phase 7 |

No new scope leaks found.

---

## 10. Legacy Navigation Findings

Trial operational roles (`branch_user`, `area_manager`, `kitchen_*`, `warehouse_*`, `delivery_user`):

- Legacy Orders, Warehouse, Sales Delivery paths **hidden** in sidebar
- Supply Chain modules **visible**
- Admin / Super Admin **retain full legacy nav**

Branch users still see **Daily Inventory** and **Branch Stock** (intended branch inventory, not legacy supply-chain orders).

---

## 11. Notifications Findings

Phase 6 regression confirms:

- Branch sees own supply-chain notification sections
- Area manager pending approval notifications
- Kitchen / warehouse / delivery scoped notifications
- No cross-scope notification leaks in automated tests

---

## 12. Audit Findings

| Role | Audit access | Write buttons |
|------|-------------|---------------|
| Internal Auditor | Full audit module + read-only SC | Hidden (ReadOnlyBanner + no action buttons) |
| Admin | Audit + admin setup | Allowed where designed |
| Trial roles | No audit admin nav | N/A |

Auditor redirected from `/dashboard` to `/audit/dashboard`.

---

## 13. Fixes Applied

| File | Change |
|------|--------|
| `AppLayoutV2.jsx` | Added `internal_auditor` to supply chain nav items |
| `SupplyChainPages.jsx` | Area manager scoped list without create form |
| `SupplyChainPages.jsx` | Status-gated kitchen production buttons |
| `SupplyChainPages.jsx` | Status-gated warehouse receive/issue/delivery-create |
| `SupplyChainPages.jsx` | Status-gated delivery out-for-delivery / delivered |
| `tests/test_role_screen_visibility_audit.py` | 40 automated visibility tests |

No backend RBAC changes. No new features.

---

## 14. Tests Run

```text
DATABASE_URL=postgresql://... RATE_LIMIT_ENABLED=false pytest \
  tests/test_role_screen_visibility_audit.py \
  tests/test_lan_trial_blockers.py \
  tests/test_lan_readiness_ux_sprint_a.py \
  tests/test_phase4_supply_chain_e2e.py \
  tests/test_phase5_warehouse_delivery_hardening.py \
  tests/test_phase6_notifications_audit.py \
  tests/test_phase7_dashboard_operations.py -v
```

| Suite | Result |
|-------|--------|
| Role visibility audit | **40 passed** |
| LAN blockers | 15 passed |
| LAN UX Sprint A | 9 passed |
| Phase 4 | 10 passed, 1 skipped |
| Phase 5 | 12 passed |
| Phase 6 | 12 passed |
| Phase 7 | 23 passed |
| **Total** | **121 passed, 1 skipped** |

---

## 15. Remaining Risks

1. **Browser-only verification** — Automated tests cover API + nav config; recommend 5-minute walkthrough per role on LAN desktop.
2. **Branch Stock / Daily Inventory** — Still visible to branch users (by design); ensure trial training clarifies vs Supply Chain requests.
3. **Area Manager operations nav** — Reports, inter-branch approvals, branch-items remain visible (pre-existing scope, not LAN supply-chain).
4. **Warehouse manager vs user** — No manager-only SC actions differentiated in UI (same fulfillment screen); legacy `/warehouse/reports` hidden for trial roles.
5. **Assistant widget** — Visible globally; out of audit scope (not AI sprint).

---

## 16. LAN Trial Verdict

### **GO WITH CONDITIONS**

| Gate | Status |
|------|--------|
| Demo | GO |
| **LAN Trial** | **GO WITH CONDITIONS** |
| Production | NO-GO |

**Conditions:**

1. Restart frontend after deploy so nav + button visibility fixes are live.
2. Run opening stock validation on trial DB before day 1.
3. Brief each role using the button matrix above (especially warehouse status-gated actions and delivery two-step flow).
4. Keep `admin` / `super.admin` available for legacy fallback during trial week 1.

The visibility audit found **5 UI issues**, all fixed without expanding permissions or adding features. Backend authorization remains the source of truth; UI now matches it.
