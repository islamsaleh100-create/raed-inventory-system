# Notifications & Audit Hardening Report — Phase 6

**Date:** 2026-06-14  
**Branch:** `phase6/notifications-audit-hardening-2026-06-14`  
**Alembic head:** `c1d2e3f4a5b6` (no new migration)

---

## 1. Files Reviewed

| File | Purpose |
|------|---------|
| `raed_inventory/backend/app/routers/notifications.py` | In-app notification bell API (poll-from-entity-state) |
| `raed_inventory/backend/app/services/supply_chain_notification_service.py` | **New** — Supply Chain V1 notification sections |
| `raed_inventory/backend/app/services/audit_service.py` | Central audit write/read |
| `raed_inventory/backend/app/routers/branch_requests.py` | Request workflow + audit |
| `raed_inventory/backend/app/routers/production_orders.py` | Kitchen production + audit |
| `raed_inventory/backend/app/routers/warehouse_lines.py` | Warehouse receive/issue + audit |
| `raed_inventory/backend/app/routers/delivery_orders.py` | Delivery workflow + audit |
| `raed_inventory/backend/app/services/branch_request_split_service.py` | Auto/manual split |
| `raed_inventory/backend/app/core/area_manager_scope.py` | Area manager city+brand scoping |
| `WAREHOUSE_DELIVERY_HARDENING_REPORT.md` | Phase 5 deferred items |
| `SUPPLY_CHAIN_E2E_REPORT.md` | Phase 4 workflow baseline |

**Architecture note:** There is no `Notification` database table. In-app notifications are computed at request time by querying workflow entity tables (existing pattern extended for Supply Chain V1).

---

## 2. Notification Events Covered

### Supply Chain V1 (added Phase 6)

| Section key | Role(s) | Workflow signal |
|-------------|---------|-----------------|
| `sc_request_approved` | Branch | Recently approved/split requests |
| `sc_request_rejected` | Branch | Recently rejected requests |
| `sc_production_started` | Branch | Production IN_PROGRESS for branch |
| `sc_production_ready` | Branch | Production READY / PARTIAL_READY |
| `sc_warehouse_delay` | Branch | Warehouse lines with delay_reason |
| `sc_partial_fulfillment` | Branch | PARTIAL / BACKORDER warehouse lines |
| `sc_delivery_created` | Branch | Delivery orders READY |
| `sc_delivered` | Branch | Recent DELIVERED / PARTIAL_DELIVERED |
| `sc_pending_requests` | Area Manager | SUBMITTED branch requests in scope |
| `sc_delayed_requests` | Area Manager | Delayed warehouse lines in scope |
| `sc_partial_orders` | Area Manager | Partial warehouse lines in scope |
| `sc_backorders` | Area Manager | Backorder/partial with pending qty |
| `sc_delivery_delays` | Area Manager | Stale out-for-delivery / partial delivered |
| `sc_production_order_created` | Kitchen | PENDING production orders in section |
| `sc_material_shortage` | Kitchen | WAITING_FOR_MATERIALS |
| `sc_ready_for_warehouse` | Kitchen | READY / PARTIAL_READY for send |
| `sc_kitchen_output_ready` | Warehouse | Kitchen output awaiting issue |
| `sc_warehouse_receive_required` | Warehouse | PENDING branch-request lines |
| `sc_warehouse_partial_fulfillment` | Warehouse | PARTIAL / BACKORDER lines |
| `sc_low_stock` | Warehouse | Available qty below item reorder_point |
| `sc_delivery_ready` | Delivery | READY delivery orders |
| `sc_out_for_delivery` | Delivery | OUT_FOR_DELIVERY orders |
| `sc_delivery_shortage` | Delivery | Recent PARTIAL_DELIVERED |
| `sc_all_pending_requests` | Admin/Ops | Global submitted requests |

### Legacy (pre-existing, unchanged)

Replenishment orders, daily inventory, quality visits, training assessments — still served for roles that had them before Phase 6.

---

## 3. Notification Events Missing

| Event | Status | Notes |
|-------|--------|-------|
| Branch Request Created | **Not a bell item** | Draft requests are visible in list UI; bell focuses on actionable states |
| Branch Request Submitted | **Partial** | Area manager sees `sc_pending_requests`; branch creator has no separate “submitted” ack |
| Area Modification | **Partial** | Covered indirectly via `sc_request_approved` after modify-and-approve |
| Production Started (kitchen bell) | **Partial** | Kitchen sees creation; branch sees `sc_production_started` |
| Production Delayed | **Missing** | No dedicated delay field on production orders |
| Out For Delivery (branch) | **Partial** | Branch sees delivery created/delivered; not in-transit state |
| Push/Email/SMS | **Out of scope** | By design |

---

## 4. Audit Events Covered

| Event | Action(s) | Status |
|-------|-----------|--------|
| Request Created | `request_created` | Fully covered |
| Request Submitted | `request_submitted` | Fully covered |
| Approved | `request_approved` | Fully covered |
| Rejected | `request_rejected` | Fully covered |
| Modified | `request_modified_and_approved` | Fully covered |
| Split Executed | `request_auto_split`, `request_split` | Fully covered (enhanced Phase 6 with child IDs) |
| Production Started | `production_started` | Fully covered |
| Production Ready | `production_ready`, `production_partial_ready` | Fully covered |
| Sent To Warehouse | `production_sent_to_warehouse` | Fully covered |
| Warehouse Receive | `warehouse_receive` | Fully covered |
| Warehouse Issue | `warehouse_issue` | Fully covered |
| Partial Issue | `warehouse_partial_issue` | Fully covered |
| Delay Reason | `warehouse_delay_reason_added`, payload on partial issue | Fully covered |
| Delivery Created | `delivery_order_created` | Fully covered |
| Out For Delivery | `delivery_out_for_delivery` | Fully covered |
| Delivered | `delivery_delivered` | Fully covered |
| Delivery Shortage | `delivery_partial_delivered` + shortages payload | Fully covered |

---

## 5. Audit Events Missing

| Event | Status | Notes |
|-------|--------|-------|
| Production Order Created (standalone) | **Partially covered** | Child IDs now in split audit payload (`production_order_ids`) |
| Backorder Created | **Partially covered** | Via `warehouse_partial_issue` with qty/delay_reason |
| Daily kitchen order paths | **Missing** | Legacy daily-kitchen endpoints not audited (pre-existing gap) |

---

## 6. Notification Scope Validation

| Role | Isolation rule | Test result |
|------|----------------|-------------|
| Branch | `user.branch_id` only | Pass — other branches not in section items |
| Area Manager | `get_area_manager_branch_ids()` city+brand | Pass — Riyadh AM cannot see Dammam pending request |
| Kitchen | `KitchenSectionAssignment` section IDs | Pass — pizza mgr sees no bakery production orders |
| Warehouse | `Branch.warehouse_id == user.warehouse_id` | Pass — Riyadh WH user cannot see Dammam lines |
| Delivery | Delivery orders via branch warehouse | Pass — Riyadh delivery user cannot see Dammam orders |

**Resilience fix:** Legacy sections using `OrderStatus.area_manager_review` are wrapped in `_safe_section()` with session rollback — prevents one bad legacy query from aborting the entire notification response (PostgreSQL enum drift pre-existing issue).

---

## 7. Audit Integrity Validation

Actual `AuditLog` structure:

| Field | Present |
|-------|---------|
| `user_id` | Yes |
| `created_at` | Yes |
| `action` | Yes |
| `entity_type` | Yes |
| `entity_id` | Yes |
| `old_values` / `new_values` | JSON text; state-change actions include status snapshots |
| `module` | Yes |
| `ip_address` | Yes when request available |

**Phase 6 enhancement:** Split audits now include `warehouse_line_ids` and `production_order_ids` in `new_values`.

No schema redesign performed.

---

## 8. Automated Test Results

**Suite:** `tests/test_phase6_notifications_audit.py`  
**Environment:** PostgreSQL, API `http://localhost:8010`, `RATE_LIMIT_ENABLED=false` (local shell only)

```
12 passed
```

**Regression:** `tests/test_phase5_warehouse_delivery_hardening.py`

```
12 passed
```

---

## 9. Remaining Risks

1. **`orderstatus` enum drift** — Python model includes `area_manager_review` but PostgreSQL enum may not; legacy replenishment notification sections return empty until enum migration applied.
2. **No persisted notification rows** — Bell reflects current entity state only; no “read/unread” history per event.
3. **Production delay** — No dedicated delay notification without a delay field on production orders.
4. **Post-split cancellation** — Still no cancel flow (Phase 5 deferred).
5. **Branch submitted ack** — Branch user does not get a dedicated “your request was submitted” bell item.

---

## 10. Bugs Deferred

### H-02 — Ledger source/destination types

**Status:** Carried forward from Phase 5.

**Reason:** Not required for operational stability in Phase 6.

**Decision:** Defer to Phase 7+ architecture hardening.

**Current requirement:** Verify ledger entries are created correctly. Do not refactor ledger type fields during Phase 6.

### Other deferred

- Post-split cancellation + reservation release (Phase 5 → Phase 7)
- Proof-of-delivery module beyond `receiver_name` / `delivery_note`
- `orderstatus` PostgreSQL enum alignment migration (optional; legacy notifications degrade gracefully)

---

## 11. Go / No-Go

| Gate | Verdict | Notes |
|------|---------|-------|
| **Demo** | **Go** | Supply chain bell sections live for all workflow roles |
| **LAN Trial** | **Go** | Scope isolation tested; legacy enum drift handled gracefully |
| **Production** | **Conditional Go** | Recommend `orderstatus` enum migration for full legacy bell parity; supply chain notifications production-ready |

---

*Local only — not deployed to server.*
