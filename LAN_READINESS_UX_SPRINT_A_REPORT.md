# LAN Readiness UX Sprint A Report

**Date:** 2026-06-15  
**Branch:** `lan-readiness/ux-sprint-a-2026-06-15`  
**Scope:** UX/readiness only — no workflow/RBAC/schema changes

---

## 1. Files Reviewed

| Area | Files |
|------|-------|
| Branch requests | `app/routers/branch_requests.py`, `SupplyChainPages.jsx`, `BranchRequestDetailPage.jsx` |
| Warehouse / delivery / kitchen | `warehouse_lines.py`, `delivery_orders.py`, `production_orders.py`, `SupplyChainPages.jsx` |
| Navigation | `AppLayoutV2.jsx` |
| Opening stock | `validate_lan_opening_stock.py`, `seed_official_branches.py` |
| Prior reports | `GO_LIVE_READINESS_REPORT.md`, `PHASE9_PRECHECK_REPORT.md` |

---

## 2. Request Timeline Changes

**New endpoint:** `GET /api/v1/branch-requests/{id}/detail`

Returns:
- `timeline` — real events from request timestamps + audit logs (branch request, production, warehouse, delivery)
- `status_summary` — `current_status_ar`, `current_owner_ar`, `next_action_ar`, `last_updated_at`
- `fulfillment_lines` — per-line qty breakdown
- `timeline_gaps` — documented missing data (if any)

**New UI:** `/supply-chain/branch-requests/:id` — Arabic timeline, status cards, fulfillment table.

**List drill-down:** Branch request list rows link to detail page.

**Approvals:** Link to detail from selected request.

---

## 3. Partial Fulfillment Visibility Changes

| Screen | Change |
|--------|--------|
| Request detail | Table: requested / issued / delivered / remaining / delay / route |
| Warehouse | Added **المصروف** column; pending highlighted |
| Delivery | Expandable line detail: dispatched / delivered / shortage |
| Dashboard | Existing `partial_orders` / `partial_warehouse` KPIs unchanged (verified) |

Backend uses existing fields: `requested_qty`, `issued_qty`, `pending_qty`, delivery line `qty_delivered`, `delay_reason`.

---

## 4. Opening Stock Validation Script Result

**Script:** `raed_inventory/backend/validate_lan_opening_stock.py`

**Dev DB run (2026-06-15):**

| Metric | Result |
|--------|--------|
| Verdict | **GO** |
| Trial branches | 3 (Onda Arkan, Ronaldos Al Khobar, Shawarma Al Khobar) |
| Warehouse | Dammam Central Warehouse (`WH-DM-1`) |
| Zero stock | 0 |
| Missing rows | 0 |
| Below reorder | 0 |

Report: `LAN_OPENING_STOCK_VALIDATION_REPORT.md`

**Note:** LAN trial must re-run on **fresh trial DB** after opening stock load.

---

## 5. Confirm Dialogs Added

| Action | Screen | Arabic confirm content |
|--------|--------|------------------------|
| Area approve / modify-approve | Approvals | Kitchen / warehouse line counts |
| Warehouse full issue | Warehouse | Branch, item, qty, remainder |
| Warehouse partial issue | Warehouse | + delay reason |
| Kitchen send to warehouse | Kitchen (production orders) | Item, qty, branch, warehouse |
| Mark delivered | Delivery | Branch, dispatched/delivered qty, receiver name (required before confirm) |

Component: `ConfirmDialog.jsx`

---

## 6. Branch Name Display Changes

Added optional `branch_name` to API responses (targeted endpoints only):

| Endpoint | Field |
|----------|-------|
| `GET /warehouse-lines` | `branch_name` |
| `GET /production-orders` | `branch_name`, `destination_warehouse_name` |
| `GET /delivery-orders` | `branch_name` |
| `GET /branch-requests/{id}` | `branch_name` |

UI updated: delivery list, warehouse list, kitchen production rows, request detail.

---

## 7. Legacy Hiding Changes

**Frontend nav only** — no env flag, no backend toggle.

Hidden for trial roles (`branch_user`, `branch_manager`, `area_manager`, `kitchen_section_manager`, `warehouse_*`, `delivery_user`):

- Legacy orders (`/orders`, `/orders/daily`, `/receiving`)
- Legacy warehouse section (all `/warehouse/*`)
- Sales delivery section (`/delivery/*`)

**Admin / super_admin:** full nav unchanged. Legacy API routes still work.

Added area manager nav link to supply-chain branch requests.

---

## 8. Tests Run

```text
python -m pytest tests/test_lan_readiness_ux_sprint_a.py -v
```

**Result:** 9 passed

---

## 9. Regression Results

```text
python -m pytest \
  tests/test_phase4_supply_chain_e2e.py \
  tests/test_phase5_warehouse_delivery_hardening.py \
  tests/test_phase6_notifications_audit.py \
  tests/test_phase7_dashboard_operations.py \
  -v
```

| Suite | Result |
|-------|--------|
| Phase 4 E2E | 10 passed, 1 skipped |
| Phase 5 Warehouse/Delivery | 12 passed |
| Phase 6 Notifications/Audit | 12 passed |
| Phase 7 Dashboard/Operations | 23 passed |
| **Total regression** | **57 passed, 1 skipped** |

Combined with sprint tests: **66 passed, 1 skipped**

`RATE_LIMIT_ENABLED=false` set in test shell only.

---

## 10. Remaining UX Risks

1. Daily kitchen orders on kitchen page still mixed with production (not split in this sprint)
2. Daily kitchen “send to warehouse” has no confirm dialog (production path covered)
3. Timeline depends on audit log coverage — some production delay events still missing in backend
4. Opening stock script result is environment-specific — must re-run on LAN fresh DB
5. Frontend confirm dialogs are client-side only (backend validation unchanged — by design)
6. Branch user still sees inventory / branch-stock legacy items (intentionally kept)

---

## 11. LAN Trial Recommendation

### **GO WITH CONDITIONS**

Sprint A materially reduces the top LAN confusion risks identified in Phase 9 operational review:

- Request tracking (“where is my order?”)
- Partial qty visibility
- Dangerous action confirms
- Branch names instead of IDs
- Single supply-chain nav path for trial roles

**Conditions before LAN trial (unchanged from Phase 9):**

1. Fresh PostgreSQL DB + `alembic upgrade head`
2. Official seeds + item master + **opening stock**
3. Run `validate_lan_opening_stock.py --write-report` → expect GO or GO WITH WARNINGS
4. Password rotation (`PASSWORD_ROTATION_CHECKLIST.md`)
5. Operator briefing on new request detail page and confirm dialogs
6. Restart backend after deploy so `/detail` endpoint is live

---

*Sprint A complete. No migrations. No workflow redesign.*
