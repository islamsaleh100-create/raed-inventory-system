# Warehouse & Delivery Hardening Report — Phase 5

**Date:** 2026-06-14  
**Branch:** `phase5/warehouse-delivery-hardening-2026-06-14`  
**Alembic head:** `c1d2e3f4a5b6` (no new migration)

---

## 1. Files Reviewed

| File | Purpose |
|------|---------|
| `raed_inventory/backend/app/routers/warehouse_lines.py` | Receive, full issue, partial issue, stock deduction, ledger |
| `raed_inventory/backend/app/routers/delivery_orders.py` | Delivery creation, dispatch, deliver, shortage handling |
| `raed_inventory/backend/app/services/stock_ledger_service.py` | Ledger posting (H-02 deferred) |
| `raed_inventory/backend/app/services/branch_request_split_service.py` | Split reservations on warehouse lines |
| `raed_inventory/backend/app/routers/production_orders.py` | Kitchen send-to-warehouse stock increase |
| `raed_inventory/backend/tests/test_phase4_supply_chain_e2e.py` | Regression baseline |
| `raed_inventory/backend/tests/test_supply_chain_phase1_branch_requests.py` | Partial issue / delivery reference |

---

## 2. Fixes Applied

### 2.1 Partial issue → delivery dispatch (critical)

**Problem:** `create_delivery_order` only accepted `READY_FOR_DISPATCH`. After partial issue the line stayed `PARTIAL`, blocking delivery of already-issued quantity.

**Fix:** Allow delivery when status is `READY_FOR_DISPATCH` or `PARTIAL` and `issued_qty > 0`. Delivery `qty_dispatched` continues to use `issued_qty` only.

### 2.2 Reservation release scope

**Problem:** Replacing silent `max(0, reserved - qty)` with a strict check broke kitchen-output issue (no reservation on split).

**Fix:** Release `reserved_qty` only for `BRANCH_REQUEST` warehouse lines. Kitchen-output lines deduct `current_qty` only. Branch-request lines reject issue when `reserved_qty < issue_qty` (no silent clamp).

### 2.3 Partial issue status when remainder cleared

When a partial issue consumes all remaining `pending_qty`, status is set to `READY_FOR_DISPATCH` instead of staying `PARTIAL`.

### 2.4 Issue / partial-issue status guards

Full and partial issue reject lines in invalid statuses (e.g. already delivered).

### 2.5 Partial delivery audit

Deliver endpoint records `delivery_partial_delivered` (with shortage details) when `delivered_qty < dispatched_qty`.

---

## 3. Warehouse Issue Results

| Check | Result |
|-------|--------|
| Issue cannot exceed available stock | **Pass** — `warehouse_lines.insufficient_stock` |
| Issue cannot exceed required (pending) qty | **Pass** — full issue must equal pending |
| No negative stock | **Pass** — rejected before deduction |
| No silent clamp on `current_qty` | **Pass** |
| `qty_issued` / `pending_qty` updated | **Pass** |
| Full issue → `READY_FOR_DISPATCH` | **Pass** |
| Partial issue → `PARTIAL` (or `READY_FOR_DISPATCH` if remainder zero) | **Pass** |
| Stock ledger on issue | **Pass** — `TransactionType.warehouse_issue`, ref `WL-{id}` |
| Branch stock before delivery | **Pass** — branch stock updated only at delivery completion |

---

## 4. Partial Issue Results

| Check | Result |
|-------|--------|
| Saves `issued_qty` | **Pass** |
| Saves `pending_qty` (remainder) | **Pass** |
| Saves `delay_reason` when required | **Pass** — required; `warehouse_lines.delay_reason_required` if missing |
| Delivery allowed for issued qty | **Pass** (after fix) |
| Remainder visible as backorder/pending | **Pass** — `PARTIAL` + `pending_qty` + `PARTIAL_WAREHOUSE` on request line |
| Does not block dispatch of issued qty | **Pass** (after fix) |
| Reservation release proportional | **Pass** — only issued portion released from `reserved_qty` |

---

## 5. Backorder Behavior

No separate `BACKORDER` entity. Current representation:

| Field | Location |
|-------|----------|
| `requested_qty` | `warehouse_lines` |
| `issued_qty` | `warehouse_lines` |
| `pending_qty` | `warehouse_lines` (remainder) |
| `status` | `PARTIAL` on warehouse line; `PARTIAL_WAREHOUSE` on branch request line |
| `delay_reason` | `warehouse_lines.delay_reason` |

Duplicate issue of the same quantity is prevented by pending-qty validation and idempotency keys. Remainder is preserved in `pending_qty` until a subsequent partial or full issue.

---

## 6. Warehouse Receive Results

| Flow | Result |
|------|--------|
| Branch request `PENDING` → `AVAILABLE` | **Pass** — no stock movement (reservation unchanged) |
| Duplicate receive | **Pass** — idempotent when already `AVAILABLE` |
| Kitchen send-to-warehouse | **Pass** — stock increases once on `send-to-warehouse` |
| Kitchen receive acknowledge | **Pass** — idempotent; does not double stock |
| Wrong warehouse scope | **Pass** — RBAC from Phase 1/2 |
| Ledger on kitchen receive into stock | **Pass** — `adjustment_in` on send; issue ledger on warehouse issue |

---

## 7. Delivery Creation Results

| Check | Result |
|-------|--------|
| Uses `issued_qty`, not requested | **Pass** |
| Excludes unissued remainder | **Pass** |
| Links `warehouse_line_id` | **Pass** |
| Duplicate delivery line guard | **Pass** — app check + DB unique `uq_delivery_order_line_warehouse_line` |
| Branch / warehouse scope preserved | **Pass** |

---

## 8. Delivery Completion Results

| Check | Result |
|-------|--------|
| `READY` → `OUT_FOR_DELIVERY` → `DELIVERED` | **Pass** |
| Delivery user warehouse scope | **Pass** — Riyadh delivery user blocked on Dammam order |
| `delivered_qty <= dispatched_qty` | **Pass** — `delivery_orders.invalid_received_qty` |
| Branch stock += `delivered_qty` only | **Pass** |
| Full delivery → `DELIVERED` | **Pass** |
| Partial delivery → `PARTIAL_DELIVERED` | **Pass** |
| Receiver / proof fields | **Present** — `receiver_name`, `delivery_note`; no POD module |

---

## 9. Shortage Recovery Results

Minimal recovery implemented (no claims/dispute workflow):

| Behavior | Result |
|----------|--------|
| `shortage_qty = dispatched - delivered` | **Pass** |
| `shortage_reason` stored | **Pass** |
| Order status `PARTIAL_DELIVERED` | **Pass** |
| Line status `PARTIAL_DELIVERED` | **Pass** |
| Branch credited only for delivered qty | **Pass** |
| Missing qty not silently dropped | **Pass** — recorded on delivery line |
| Warehouse line status after shortage | Set to `PARTIAL` when delivery short |

**Note:** No dedicated `DELIVERY_SHORT` or `SHORTAGE_RECORDED` status on warehouse lines; shortage is tracked on delivery order lines.

---

## 10. Reservation Release / Cancel Status

| Check | Result |
|-------|--------|
| Reservation on split | **Yes** — `branch_request_split_service` increments `reserved_qty` |
| Release on issue | **Yes** — branch-request lines only |
| Post-split cancellation API | **Not implemented** |
| Stale reservation risk | **Documented Phase 6** — cancel/abandon after split has no release path |

---

## 11. Audit Trail Status

| Event | Audit action | Status |
|-------|--------------|--------|
| Warehouse receive | `warehouse_receive` | **Present** |
| Full issue | `warehouse_issue` | **Present** |
| Partial issue | `warehouse_partial_issue` | **Present** |
| Delay reason (standalone) | `warehouse_delay_reason_added` | **Present** |
| Delivery created | `delivery_order_created` | **Present** |
| Out for delivery | `delivery_out_for_delivery` | **Present** |
| Delivered (full) | `delivery_delivered` | **Present** |
| Delivered (partial) | `delivery_partial_delivered` | **Present** (added Phase 5) |
| Shortage detail | In audit payload `shortages` | **Present** |
| Backorder | Via partial issue audit + line fields | **Partial** — no separate `backorder_created` action |

---

## 12. Migration Changes If Any

**None.** Existing schema and unique constraint on `delivery_order_lines.warehouse_line_id` are sufficient.

---

## 13. Test Results

**Suite:** `tests/test_phase5_warehouse_delivery_hardening.py`  
**Environment:** PostgreSQL, API `http://localhost:8010`, `RATE_LIMIT_ENABLED=false` (local shell only)

```
12 passed
```

**Regression:** `tests/test_phase4_supply_chain_e2e.py`

```
10 passed, 1 skipped
```

---

## 14. Remaining Risks

1. **Post-split cancellation** — no API to release stale `reserved_qty` if a branch request is abandoned after split.
2. **Shortage follow-up** — shortage is recorded on delivery but there is no automated re-issue or procurement workflow for missing quantity.
3. **Multiple partial issues + multiple deliveries** — one delivery order per warehouse line (unique constraint); remainder requires a second issue cycle before another delivery line can be created for the same request line (by design).
4. **Kitchen vs branch reservation asymmetry** — kitchen-output stock is not reserved on split; only branch-request warehouse stock is reserved.

---

## 15. Bugs Deferred

### H-02 — Ledger source/destination types (Phase 6)

`stock_ledger_service.py` uses free-text `source_type` and `destination_type`. Phase 5 verified ledger entries are created correctly for receive, issue, partial issue, and delivery. **Do not refactor to enums in Phase 5.**

### Phase 6 — Cancellation module

Branch-request cancel after split with reservation release.

### Phase 6 — Proof of delivery

Extended POD (photos, signatures) beyond existing `receiver_name` / `delivery_note`.

---

## 16. Go / No-Go

| Gate | Verdict | Notes |
|------|---------|-------|
| **Demo** | **Go** | Partial issue → delivery path fixed; shortage and scope tests pass |
| **LAN Trial** | **Go** | With monitoring for post-split cancel gaps |
| **Production** | **Conditional Go** | Recommend Phase 6 cancel/reservation cleanup before high-volume production; H-02 enum hardening optional |

---

*Local only — not deployed to server.*
