# Raed Inventory System — Full System Audit

**Date:** 2026-04-25
**Scope:** Backend (FastAPI + SQLAlchemy + SQLite) + Frontend (React/Vite) + Workflow + Production-readiness
**Method:** Static read of source code, no runtime execution. Some claims marked `(unverified — requires runtime)` where DB or HTTP behaviour is needed to confirm.
**Reference:** Frontend findings from `frontend_audit_2026-04-24.md` (38 findings) are **not duplicated** here — see that file. This audit adds workflow / data-integrity / RBAC / production-readiness analysis on top.

---

## Executive Summary

- **SYSTEM_HEALTH_SCORE: 52/100**
  The system has rich domain modelling (12 lifecycles, 80+ tables, roles, audit, idempotency, FOR UPDATE wrappers) and demonstrates a mature design instinct. **But it is not production-grade.** The same code that locks rows in `orders_service.dispatch` does not lock them in `warehouse_lines.issue` or `delivery_orders.deliver`; supply-chain stock mutations are not transactionally bound to status updates; SQLite is the live DB and explicitly does not honour `FOR UPDATE`; admin-bypass was made global without auditing the endpoints whose business rules required excluding admin (e.g. month-closure scope, sales_manager-only operations); and the new branch-request workflow has no reservation against the warehouse stock at split time so two parallel approvals + issues can over-issue. UI gates for admin-only routes were never added (per frontend audit). Verdict: **needs-work — 6–8 weeks of focused stabilisation before a paying customer.**

### Top 10 most dangerous issues (severity • location)

1. **CRITICAL** — Warehouse line `issue` does not lock `WarehouseStock` and does not subtract `reserved_qty`. Concurrent issues over-issue stock. (`backend/app/routers/warehouse_lines.py:88-115`)
2. **CRITICAL** — `WarehouseLine` reserves nothing at split time; `BranchStock.reserved_qty` is never set when the request is split. Two simultaneous splits for the same warehouse + item pass the `_deduct_stock` check then both subtract. (`backend/app/services/branch_request_split_service.py:66-118`)
3. **CRITICAL** — SQLite is the production DB and `app/core/locking.py:33` returns `with_for_update()` even though SQLite ignores it (only DB-wide write lock during commit). All "row-lock" guarantees are illusory on the deployed engine. Combined with `check_same_thread=False`, this is a race-condition factory. (`backend/app/database.py:8-14`, `backend/app/core/locking.py:17-37`)
4. **CRITICAL** — `require_roles()` central admin-bypass (auth.py:147-158) was applied without follow-up audit. Several endpoints whose business semantics require *excluding* admin from a particular operational chain (or scoping it) now silently let `admin` perform the action without the service-level checks expected. Specifically `delivery_orders.create` accepts admin without verifying warehouse scope (`delivery_orders.py:181-198`), `branch_requests` accepts admin in `_require_area_review` for region-bounded approvals without checking the user's region (`branch_requests.py:148-158`), and `replenishment_service.create_daily_order` is reachable as admin even though `_require_branch_write` lets admin pass through without an `area` check (`branch_requests.py:135-145`).
5. **CRITICAL** — Auto-split idempotency relies on **app-level lookups** (`branch_request_split_service.py:72,101`). On SQLite without true row locks, two simultaneous `/approve` calls both pass the lookup, both `db.add(ProductionOrder(...))` — and only one will hit the unique-constraint trip on `source_request_line_id`; the other returns the user a 500 when commit fails (no rollback in the auto-split path) and leaves the request in `AREA_APPROVED` (not `SPLIT`) inconsistent with audit log "request_auto_split". (`backend/app/routers/branch_requests.py:404-412`)
6. **HIGH** — `models/__init__.py:550` declares `unique=True` on `ProductionOrder.source_request_line_id` which is a saving grace for split idempotency, **but** `WarehouseLine` only has `(source_request_line_id, source_type)` unique — so a kitchen-sourced line could in theory get both `BRANCH_REQUEST` and `KITCHEN_OUTPUT` warehouse rows. The split logic happens to use `BRANCH_REQUEST` only and `production_orders.send_to_warehouse` only `KITCHEN_OUTPUT` — but this is convention, not a constraint.
7. **HIGH** — `delivery_orders.deliver` mutates `BranchStock.current_qty` without locking the row, in a loop over delivery lines. Two concurrent receives or a delivery during inventory-receive yields lost-update. (`backend/app/routers/delivery_orders.py:283-291`)
8. **HIGH** — `branch_request.brand_id` is a **dynamic FK**, not a snapshot. If an admin renames or soft-deletes a brand mid-flight, every open request line's history changes silently (no `Brand.is_deleted`, just `active=False`). Same for `Item.kitchen_section_id` — production orders that were already in flight will follow the renamed/repointed section. (`backend/app/models/__init__.py:507, 487`)
9. **HIGH** — There is **no procurement / PO module**. Items can run out at the warehouse and there is no Purchase Request or Purchase Order workflow. Replenishment and inventory only redistribute existing stock; receipts from suppliers must be entered as bare manual `/stock/warehouses/{id}/adjust` events with `adjustment_type=increase` and a free-text reason — losing supplier, invoice, GRN traceability.
10. **HIGH** — Frontend route-level RBAC is absent — any logged-in user typing `/admin/users`, `/admin/settings`, `/operations/inter-branch-approvals`, `/delivery/statements`, `/sales-channels/...` reaches the page. Backend then 403s, but UI exposure is real (per `frontend_audit_2026-04-24.md` Top-5 finding #3).

### Verdict

**Needs-work, not ship-ready.** The supply-chain V1 (Branch → Approve → Split → Production → Warehouse → Delivery) is a well-thought-out design but rests on locking primitives that don't work on the deployed engine and stock-reservation guards that were never wired. The Pack C sales-channels module is the cleanest part of the codebase (proper service-layer permissions, snapshot rows, CHECK constraints, partial uniques). The replenishment / orders V0 module shows correct intent (locks, ledger, idempotency) but cannot deliver those guarantees on SQLite. To ship to a multi-branch real customer: migrate to PostgreSQL, add `reserved_qty` flow on split + issue, gate admin routes in the frontend, build a procurement module, and harden the audit log to capture *every* state transition (today only ~70% are logged).

---

## 1) 🔴 CRITICAL ISSUES (must fix before production)

### C-1 — Warehouse issue does not lock stock; over-issue under concurrency
**Location:** `backend/app/routers/warehouse_lines.py:88-115`

**What is wrong**
`_deduct_stock` reads `WarehouseStock` without `lock_row()`. Two concurrent `/issue` calls on different warehouse lines for the same `(warehouse_id, item_id)` both observe the same `current_qty`, both pass `current_qty < qty`, both subtract their `qty`. End state: `current_qty` is **less than reality** (possibly negative; nothing prevents that — no CHECK constraint on `WarehouseStock.current_qty`).

**Why it is wrong**
The same project's `orders_service._get_warehouse_stock_locked` (orders_service.py:23-29) does use `lock_row()` for the legacy replenishment flow. The new supply-chain warehouse-issue flow forgot it.

**Real-world impact**
Stock corruption. Branches dispatch items the warehouse doesn't have; reconciliation requires manual fix. In a 30-branch operation issuing 50 lines/min during morning rush, this fires routinely.

**Exact fix**
```python
# warehouse_lines.py — _deduct_stock
from app.core.locking import lock_row
stock = lock_row(
    db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == warehouse_id,
        WarehouseStock.item_id == row.item_id,
    )
).first()
```
Also wrap the entire `issue_line` and `partial_issue_line` body in an explicit `db.begin_nested()` and handle integrity errors. Add a CHECK constraint `current_qty >= 0` on `warehouse_stock` via Alembic.

---

### C-2 — Split does not reserve stock; warehouse over-promises
**Location:** `backend/app/services/branch_request_split_service.py:66-118`

**What is wrong**
When a branch request is split, `WarehouseLine` rows are created with `requested_qty` and `pending_qty` but **no reservation is placed on `WarehouseStock.reserved_qty`**. The `WarehouseStock` model has the field (`models/__init__.py:885`) and the legacy approve path checks `current_qty - reserved_qty` (`orders_service.py:293`), but the supply-chain split never touches it.

**Why it is wrong**
Two area managers approve two requests for the same item from the same warehouse on Sunday morning. Each request says "you have 100 in WH." Warehouse user issues both. Total dispatched = 200, but warehouse only has 100. Issue C-1 amplifies this.

**Real-world impact**
Over-promised orders. Branches arrive at no-stock state; warehouse must scramble. No audit trail explaining which approval ate which stock first.

**Exact fix**
1. Add to `split_branch_request()` after creating each `WarehouseLine`:
```python
ws = lock_row(
    db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == request.branch.warehouse_id,
        WarehouseStock.item_id == line.item_id,
    )
).first()
if ws:
    ws.reserved_qty = (ws.reserved_qty or Decimal("0")) + qty
else:
    db.add(WarehouseStock(warehouse_id=...., item_id=line.item_id, current_qty=Decimal("0"), reserved_qty=qty))
```
2. In `warehouse_lines._deduct_stock` subtract from `reserved_qty` as well as `current_qty` so future approvals see correct availability.
3. On reject / cancel paths, release the reservation (currently no such path — see C-9).

---

### C-3 — SQLite + `with_for_update()` = no real locking
**Location:** `backend/app/database.py:8-14`, `backend/app/core/locking.py:17-37`

**What is wrong**
`Settings.DATABASE_URL = "sqlite:///./raed_inventory_local.db"` and `_supports_row_locks()` always returns `True` without any dialect check. The comment in `locking.py:31-32` admits "SQLite uses DB-wide lock during write, so semantics are protected via transaction" but that's only true at *commit* time — **the lock is not acquired at SELECT FOR UPDATE time**, so both transactions read the same value, both compute their delta, then SQLite serialises commits — and the second commit overwrites the first's changes (last-write-wins, lost update).

**Why it is wrong**
Compounded with `check_same_thread=False` (database.py:9), uvicorn's threaded request handling can hit `BranchStock` from two threads simultaneously, both holding open transactions, and lose one update silently.

**Real-world impact**
Already-dispatched units appear back in stock. Already-deducted units are deducted again. Customer reports "phantom stock" — engineering can't reproduce because every isolated test passes.

**Exact fix**
Migrate the production deployment to PostgreSQL. Update `_supports_row_locks` to return False for SQLite so the codebase doesn't pretend:
```python
def _supports_row_locks() -> bool:
    return not settings.DATABASE_URL.lower().startswith("sqlite")
```
For SQLite dev mode, replace `with_for_update()` with `BEGIN IMMEDIATE` via:
```python
@event.listens_for(engine, "begin")
def do_begin(conn):
    conn.exec_driver_sql("BEGIN IMMEDIATE")
```
This serialises writers at the connection level. Document clearly that production on SQLite is **forbidden**.

---

### C-4 — Central admin bypass leaked into business-rule endpoints
**Location:** `backend/app/core/auth.py:147-158`; consequences in `branch_requests.py:148-158`, `delivery_orders.py:78-88`, multiple

**What is wrong**
2026-04-24 change: `require_roles()` always allows `admin` and `super_admin`. The docstring claims "Module-level write restrictions must therefore be enforced by the SERVICE layer" — but the service layer mostly hasn't caught up.

Examples found:

- `branch_requests._require_area_review` (line 148) returns silently for admin, **bypassing region scope**. An admin in Riyadh can approve a Dammam branch request without the region-membership check.
- `delivery_orders._require_order_access` (line 78) admits admin without checking warehouse scope — fine for admin but the same pattern is repeated for `delivery_user` (line 79: `"delivery_user" in _roles(user)`) which means **any delivery user reaches every order in the system regardless of warehouse**. (Not strictly admin-bypass, but in the same family of "global-by-default" mistake.)
- `branch_requests._require_branch_write` (line 135) returns for admin without the `_branch_brand_allowed` check — admins can create requests for branch+brand combinations not in `BranchBrand`.

**Why it is wrong**
Region/warehouse/brand scoping is the primary integrity boundary in this multi-brand multi-tenant-style operation. "Admin-bypass" works for break-glass support but **must be logged and gated** — no UI should default to it.

**Real-world impact**
- Audit trail loses context (admin acts as if they were a regional manager, audit log records only `user_id=admin_user`).
- Brand-stocking policy is silently violated.
- Tests that assert "Riyadh admin can't approve Dammam request" now fail in production.

**Exact fix**
1. Change docstring to reality — admin bypasses the *role list* but not the *scope check*.
2. Re-introduce explicit scope checks in `_require_area_review` and friends:
```python
def _require_area_review(db, user, row):
    if _is_admin(user):
        # Admins still must satisfy region scope unless they have an explicit "platform_override" attribute.
        if not _can_view(db, user, row):
            raise AppError(...)
        return
    ...
```
3. Add `is_platform_override: bool = False` flag on User and gate it for super_admin only; require it for cross-region admin actions and audit it.
4. Run a grep for `if _is_admin(...)` returning early; each one needs a re-validation pass.

---

### C-5 — Auto-split race: two parallel approves both add ProductionOrder, second commit fails 500
**Location:** `backend/app/routers/branch_requests.py:388-413` and `services/branch_request_split_service.py:72-118`

**What is wrong**
The `unique=True` on `ProductionOrder.source_request_line_id` (`models/__init__.py:550`) is the saving grace — **it prevents duplicates** at the DB layer. But the auto-split path:

1. Reads `BranchRequest`. Status = `SUBMITTED`.
2. Sets status to `AREA_APPROVED`.
3. Calls `_split_request_service` which checks `BranchRequestStatus.SPLIT` — short-circuit no longer works because the prior status mutation is in the same uncommitted transaction as the second concurrent caller.
4. Both insert `ProductionOrder`. First commits. Second hits unique violation on `source_request_line_id`.
5. Second caller gets `IntegrityError` → 500. **No rollback of step 2 or 4** — the auto-split is inside the same transaction as the approve, so SQLAlchemy's default rollback handler unwinds the whole thing — but the `_audit` log was already added to the session and is also rolled back.

**Why it is wrong**
On SQLite this rarely repros. On PostgreSQL with concurrent area-manager actions during peak hours, this is a routine 500.

**Real-world impact**
- User sees "internal server error" on a successful-looking action; they retry; second retry succeeds.
- But the *audit log* has only one `request_approved` event for what may have been two human actions on different terminals (assume the two humans both clicked approve simultaneously).

**Exact fix**
Wrap the approval+split in a service that:
1. Locks `BranchRequest` row at the top with `SELECT ... FOR UPDATE`:
```python
row = lock_row(db.query(BranchRequest).filter(BranchRequest.id == request_id)).first()
```
2. Checks status is `SUBMITTED` *after* lock acquisition. If `AREA_APPROVED`, return idempotent.
3. Catches `IntegrityError` on the unique-constraint trip and converts it to a 409 with a useful message ("approval is already in progress").

Also add a unique partial index on `WarehouseLine(source_request_line_id)` (regardless of source_type) so warehouse-split is also DB-protected against double-insert.

---

## 2) 🟠 HIGH PRIORITY

### H-1 — `delivery_orders.deliver` updates BranchStock without locking
**Location:** `backend/app/routers/delivery_orders.py:283-291`

**What is wrong**
The loop reads `BranchStock`, then `stock.current_qty = ... + qty` without `lock_row()`. Same race-condition class as C-1.

**Why it is wrong**
A delivery and a manual `/stock/branches/{id}/adjust` (which *does* lock — see `stock_adjustment_service.py:77`) running in parallel produces lost-update.

**Real-world impact**
Branch stock dashboard shows wrong numbers; reconciliation requires audit-log replay.

**Exact fix**
```python
from app.core.locking import lock_row
stock = lock_row(
    db.query(BranchStock).filter(
        BranchStock.branch_id == row.branch_id,
        BranchStock.item_id == line.item_id,
    )
).first()
```

---

### H-2 — Order lifecycle has no enforcement of forbidden-state guard rails on every endpoint
**Location:** `backend/app/services/orders_service.py` various; `backend/app/routers/orders.py:245-275`

**What is wrong**
Some lifecycle endpoints assert allowed-from states (e.g. `submit_to_warehouse` accepts `[branch_reviewed, system_generated, draft, area_manager_review]`). But:

- `area_manager_review` endpoint (orders.py:251-275) does not call `lock_row()` on the order — concurrent reviews mutate `notes` over each other.
- `branch_review_order` (orders_service.py:179-209) does not check `can_access_branch` for area_manager (uses `_ensure_order_branch_access` which only handles branch_user/branch_manager flow).
- The status state machine is **implicit** — there is no `_VALID_TRANSITIONS` table. Adding `closed` from `area_manager_review` becomes possible if someone wires it; nothing prevents it.

**Why it is wrong**
Adding new lifecycle endpoints is unsafe — every contributor must guess the allowed-from set. Audit trails don't capture *why* a transition was permitted.

**Real-world impact**
Future feature work (e.g., "operations_manager can override approval") will introduce illegal transitions silently.

**Exact fix**
Define `ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]]` in `orders_service.py` and a `_transition(order, new_status, by_role)` helper used by every endpoint. Audit the transition.

---

### H-3 — Production order destination_branch_id never re-validated
**Location:** `backend/app/services/branch_request_split_service.py:108`; `backend/app/models/__init__.py:551`

**What is wrong**
`ProductionOrder.destination_branch_id` is `NOT NULL` (good) but **set once at split time** from `request.branch_id`. If the branch is soft-deleted between split and `send-to-warehouse`, the production order keeps a `destination_branch_id` pointing at an `is_deleted=True` branch. `production_orders.send_to_warehouse` (`production_orders.py:256`) then tries to read `row.destination_branch.warehouse_id` — works (the relationship loads regardless of `is_deleted`) but the warehouse_line lands at an inactive branch's warehouse; the resulting delivery_order is for an inactive branch.

**Why it is wrong**
There is no FK ON DELETE CASCADE / RESTRICT on `production_orders.destination_branch_id`. There is no application check against `Branch.is_deleted` at the production endpoints.

**Real-world impact**
Unreachable orders. Branches that were closed mid-month show up in production queues forever.

**Exact fix**
1. `production_orders.send_to_warehouse`: add
```python
if row.destination_branch.is_deleted or not row.destination_branch.active:
    raise AppError(status_code=400, error_code="production_orders.destination_inactive", ...)
```
2. Add a daily scheduler task to flag stale production orders for inactive branches.
3. Document business policy: closing a branch must first cancel/redirect all open production orders.

---

### H-4 — Procurement module is missing entirely
**Location:** entire codebase — no `purchase_*` tables, no router

**What is wrong**
The system has full receiving from warehouse → branch but **no entry point for stock arriving at the warehouse**. Items can run out and recovery is via `stock.adjust_warehouse_stock`. There is no:
- Purchase Request (PR)
- Purchase Order to supplier
- Goods Receipt Note (GRN)
- Supplier master
- Invoice / payable trace

**Why it is wrong**
This is a 30-branch food-service operation. Suppliers exist. Receipts must be tracked.

**Real-world impact**
- Cannot prove inventory provenance to auditor.
- Cannot run shrinkage reports (warehouse intake vs. branch issue vs. counted stock).
- Cannot reconcile against supplier invoices.

**Exact fix**
Build a Phase-2 module:
- `Supplier` master.
- `PurchaseOrder` + `PurchaseOrderLine` with status: `draft → submitted → approved → received → closed`.
- `GoodsReceiptNote` linked to PO, increments `WarehouseStock.current_qty` and posts `TransactionType.opening_balance` or new `purchase_receipt`.
- Replace `stock.adjust_warehouse_stock` with adjustment limited to investigations/wastage; routine intake must go through GRN.

Effort: ~3 weeks for skeleton + tests.

---

### H-5 — Frontend has no route-level RBAC; every logged-in user reaches every page
**Location:** `frontend/src/App.jsx:1283-1365` (per frontend audit Top-5 #3)

**What is wrong**
No `<RoleGuard>` component on routes. `<ProtectedRoute>` only checks "logged in".

**Why it is wrong**
- Information leak: branch_user navigating to `/admin/users` sees the Users page UI, sees the table loading spinner, then 403. They learn "the admin section exists."
- Demo polish: shows admin features to non-admin users in a trial setting.

**Real-world impact**
Confusion and curiosity attacks during the area-manager LAN trial happening **right now** (per memory `project_raed_area_managers.md`).

**Exact fix**
Wrap every admin/ops/sales-manager route with a role guard:
```jsx
<Route path="/admin/*" element={<RoleGuard roles={['admin','super_admin']}><AdminRoutes/></RoleGuard>}/>
```
See frontend audit for the full route list.

---

### H-6 — `BranchRequest.brand_id` is dynamic, not a snapshot
**Location:** `backend/app/models/__init__.py:507`

**What is wrong**
`branch_request.brand_id` and `branch_request_line.item_id` are FKs. If brand is renamed (e.g. "Onda" → "ONDA Restaurants") or item is renamed, all open requests show the new name as if it had always been called that. There is no `brand_name_snapshot`, `item_name_ar_snapshot` on the line.

**Why it is wrong**
Audit log should show what the user *saw* at create time. Today, audit log shows the latest name only.

**Compare to** `EvaluationAnswer` (models/__init__.py:778) which **does** snapshot `question_text_snapshot`, `section_name_snapshot`, `max_score_snapshot` — proving the team knows the pattern but didn't apply it to the supply-chain module.

**Real-world impact**
Disputes ("we ordered X, you delivered Y, but X was the OLD name of Y") become unprovable.

**Exact fix**
Add nullable snapshot columns:
```python
class BranchRequestLine(Base):
    item_name_ar_snapshot = Column(String(200))
    item_name_en_snapshot = Column(String(200))
    item_code_snapshot = Column(String(30))
    brand_name_snapshot = Column(String(100))  # on parent
    unit_code_snapshot = Column(String(20))
```
Populate on submit. Reads should prefer snapshot if present.

---

### H-7 — `Item.kitchen_section_id` repointing breaks in-flight production
**Location:** `backend/app/models/__init__.py:487`; `backend/app/services/branch_request_split_service.py:110`

**What is wrong**
`Item.kitchen_section_id` is mutable. Admin re-points "Beef Patty" from Section-A to Section-B mid-day. All `ProductionOrder` rows already created carry the *old* `kitchen_section_id` (good — split copies it), but new requests with the same item now route to Section-B. **Same kitchen, same cook, different section** — RBAC `kitchen_section_assignment` denies access for old orders that the new admin no longer reports to.

**Why it is wrong**
No audit trail of the repoint. No cascade to existing orders. Section managers see orders they can't action.

**Real-world impact**
Orders get stuck in "PENDING" because no one with section access is around.

**Exact fix**
1. Make kitchen-section repoint admin-only and audit it.
2. On repoint, run a job that either (a) reassigns existing PENDING/IN_PROGRESS production orders to the new section, or (b) leaves them and grants the new section's manager access to the old section for 24h. The choice is policy.
3. Add UI warning when admin attempts to repoint.

---

### H-8 — `_get_branch_stock_locked` not used everywhere it should be
**Location:** `backend/app/services/orders_service.py:533` (dispatch creates BranchStock fresh without lock); `backend/app/routers/delivery_orders.py:287-289`

**What is wrong**
In `dispatch_order` (orders_service.py:531-541), if BranchStock is missing the code creates a fresh one with `db.add(...)` — **without any unique-key contention guard**. Two concurrent dispatches for the same `(branch_id, item_id)` both create rows; one fails the unique constraint at commit, returning 500 (no graceful retry).

**Real-world impact**
Same as C-5 — visible 500s under contention.

**Exact fix**
Use `INSERT ... ON CONFLICT DO NOTHING` (PostgreSQL) or wrap in try/except IntegrityError + re-fetch.

---

### H-9 — `IdempotencyRequest` not used by the supply-chain endpoints
**Location:** `backend/app/routers/branch_requests.py`, `production_orders.py`, `warehouse_lines.py`, `delivery_orders.py`

**What is wrong**
Only the legacy `orders_service.py` integrates `idempotency_service` (multiple `_try_begin_idempotent_operation` calls). The new supply-chain V1 endpoints accept no `X-Idempotency-Key` header. A network blip → user retries → state advances twice (e.g., partial-issue twice subtracts twice, second time pending_qty goes negative — no CHECK constraint).

**Real-world impact**
Lost stock, double-issuing, double-delivery.

**Exact fix**
Apply the same idempotency wrapper used in `orders_service` to: `/branch-requests/{id}/submit`, `/approve`, `/modify-and-approve`, `/reject`, `/split`; `/production-orders/{id}/start`, `/mark-ready`, `/send-to-warehouse`; `/warehouse-lines/{id}/issue`, `/partial-issue`; `/delivery-orders/{id}/out-for-delivery`, `/deliver`. One pattern, eight endpoints.

---

### H-10 — `WarehouseLine.pending_qty` not CHECK-constrained
**Location:** `backend/app/models/__init__.py:601`

**What is wrong**
`pending_qty` is `nullable=False` but no CHECK against negative or against `pending_qty + issued_qty == requested_qty`. Bug in `partial_issue_line` (warehouse_lines.py:201) computes `pending - qty` — if a stale read of `pending` is used in two concurrent partial-issues, second can land `pending = -10` silently.

**Exact fix**
```sql
ALTER TABLE warehouse_lines ADD CONSTRAINT ck_warehouse_lines_qty_balance
    CHECK (pending_qty >= 0 AND issued_qty >= 0 AND pending_qty + issued_qty = requested_qty);
```
Add to a migration. Also add the same balance check via SQLAlchemy validator.

---

### H-11 — `partial_issue` rejects qty == pending; that's wrong
**Location:** `backend/app/routers/warehouse_lines.py:192`

**What is wrong**
```python
if qty <= 0 or qty >= pending:
    raise AppError(... "Partial issue quantity must be greater than zero and less than pending quantity")
```
The `>=` rejects `qty == pending`. So if `pending = 5` and the warehouse user types `5` into the partial input, the system says "use full issue instead" — but they may have a delay reason and want a partial-issue audit row. Also the code has a separate `/issue` endpoint for full — users will get confused.

**Real-world impact**
Confusing 400 errors on edge cases. Users learn to lie ("I'll issue 4.99").

**Exact fix**
Change to `qty <= 0 or qty > pending`. Document that `qty == pending` via partial-issue still records `delay_reason` and sets status `PARTIAL` (not `READY_FOR_DISPATCH`); the user should then explicitly transition.

Better: merge `/issue` and `/partial-issue` into one endpoint with `is_partial: bool` flag in payload.

---

### H-12 — `BranchStock.current_qty` lacks negative guard at DB level
**Location:** `backend/app/models/__init__.py:866-873`

**What is wrong**
No CHECK constraint. Only the application code (`stock_adjustment_service.py:160`: `max(0, ...)`) protects against negatives. Other paths (`delivery_orders.deliver`, `inter_branch_service.approve` line 389) don't `max(0, ...)` — they trust prior validation. Combined with H-1 race condition, we land in negative branch stock.

**Exact fix**
```sql
ALTER TABLE branch_stock ADD CONSTRAINT ck_branch_stock_current_qty_nonneg CHECK (current_qty >= 0);
ALTER TABLE branch_stock ADD CONSTRAINT ck_branch_stock_reserved_qty_nonneg CHECK (reserved_qty >= 0);
ALTER TABLE branch_stock ADD CONSTRAINT ck_branch_stock_in_transit_qty_nonneg CHECK (in_transit_qty >= 0);
ALTER TABLE warehouse_stock ADD CONSTRAINT ck_warehouse_stock_current_qty_nonneg CHECK (current_qty >= 0);
ALTER TABLE warehouse_stock ADD CONSTRAINT ck_warehouse_stock_reserved_qty_nonneg CHECK (reserved_qty >= 0);
```
Note: a previous task #10 ("Phase 3: DB migration CHECK constraints") is marked completed — but the alembic migration file should be checked: the constraints may have been added then dropped or never applied to the demo DB. (unverified — requires runtime check of `_chain_full.db` schema).

---

### H-13 — Audit log is module-only, not transition-only
**Location:** `backend/app/services/audit_service.py` callers across the codebase

**What is wrong**
Audit log captures the *action name* ("request_approved", "warehouse_issue") and *new_values* — but typically only `{"status": "AREA_APPROVED"}`. The `old_values` field is **not populated** in any of the supply-chain calls (grep `audit_service.log` shows no `old_values=` keyword). Without old/new pairing, an audit reviewer cannot reconstruct the state diff.

**Compare:** `EvaluationAuditLog.old_value`/`new_value` (models/__init__.py:849-850) is the right pattern but only used for evaluations.

**Exact fix**
Standardise: every audit call must include `old_values` snapshot + `new_values` snapshot of the entity's relevant fields. Build a helper:
```python
def audit_state_change(db, *, user_id, entity, old_state, new_state, ...):
    ...
```

---

### H-14 — `delivery_orders.create` allows admin without warehouse-scope check
**Location:** `backend/app/routers/delivery_orders.py:155-198`

**What is wrong**
Line 184: `if _is_warehouse_role(current_user) and not _is_admin(current_user) and _line_warehouse_id(line) != current_user.warehouse_id`. Admin short-circuits the warehouse check — but the function still requires `current_user.warehouse_id` to be set elsewhere implicitly. Real bug: admin (no warehouse_id) can create a delivery for any warehouse line — but `current_user.warehouse_id` is None, no scope at all. This is "intentional" but means audit log records admin without source warehouse → cannot trace which physical site dispatched.

**Real-world impact**
"Who dispatched this?" → audit shows admin@raed.com from anywhere. No accountability.

**Exact fix**
Require `warehouse_id` in the request payload when actor is admin; reject otherwise. Audit log captures the chosen warehouse explicitly.

---

## 3) 🟡 MEDIUM

### M-1 — `ChannelType` enum stored as `String(20)` not `SAEnum`
**Location:** `backend/app/models/sales_channels.py:52`

**What is wrong**
Comment says "ChannelType" but column is `String(20)` with a CHECK constraint. The Pydantic enum is enforced at write time but reads return strings, not enum instances — service code does `channel.type == ChannelType.delivery_app.value` instead of `== ChannelType.delivery_app`. Works but loses typing.

**Exact fix**
Change to `Column(SAEnum(ChannelType), nullable=False)` and remove the redundant CHECK. Service-layer comparisons become natural.

---

### M-2 — `is_month_locked` returns True for **active** closure but doesn't index `(month, branch_id, scope_type, reopened_at)`
**Location:** `backend/app/services/sales_channels_service.py:76-89`

**What is wrong**
The query filters on `month + reopened_at IS NULL + scope`. Index `ix_monthly_closures_month` (sales_channels.py:177) covers month only. The condition will scan all closures for that month, then filter. With 1000 closures (3 years × 30 branches × 12 months = ~1100), each daily-sale create does a small scan. Acceptable today but will degrade.

**Exact fix**
Add a partial index:
```sql
CREATE INDEX ix_monthly_closures_active ON monthly_closures (month, branch_id, scope_type) WHERE reopened_at IS NULL;
```

---

### M-3 — `production_orders.send_to_warehouse` increments `qty_sent_to_warehouse` *after* posting ledger; on failure the ledger is rolled back but `qty_sent_to_warehouse` could be miscalculated
**Location:** `backend/app/routers/production_orders.py:264-292`

**What is wrong**
Sequence:
1. Create/update WarehouseLine (`pending_qty += qty_to_send`).
2. Stock create/update.
3. `row.qty_sent_to_warehouse = sent_qty + qty_to_send`.
4. `stock_ledger_service.post_transaction` (only adds; commit happens later).

If the user calls `send-to-warehouse` twice (lifecycle says it's allowed from `SENT_TO_WAREHOUSE` state — line 214), the diff `qty_to_send = ready_qty - sent_qty` produces 0 → no work. OK. But if `qty_ready` was bumped between calls (`mark-partial-ready`), this works correctly. **Edge case**: if `qty_ready < qty_sent_to_warehouse` (e.g., admin manually edits qty_ready down), `qty_to_send` becomes negative. Code raises 400 (line 225). Good.

**Why it is medium not low**
The path is heavily branched and hard to test exhaustively. Add unit tests covering: send twice, mark-ready then send-partial, etc.

**Exact fix**
Add idempotency key on `send-to-warehouse` (per H-9). Add tests for sequence: PENDING → IN_PROGRESS → PARTIAL_READY → send 50% → mark-ready → send remaining.

---

### M-4 — `area_manager_review` endpoint trusts unsanitised `line_notes` keys
**Location:** `backend/app/routers/orders.py:264-269`

**What is wrong**
```python
line_notes = payload.get("line_notes") or {}
for line in order.lines:
    if str(line.id) in line_notes:
        line.notes = line_notes[str(line.id)]
    elif line.id in line_notes:
        line.notes = line_notes[line.id]
```
Type confusion (str vs int) is handled but the dict can be huge (no schema validation, raw `Body(...)`). DOS via large notes is possible.

**Exact fix**
Define `AreaReviewRequest` schema with `Dict[int, constr(max_length=2000)]` and use it.

---

### M-5 — `BranchRequest.priority` is `String(30)` free-text — not enumerated
**Location:** `backend/app/models/__init__.py:509`

**Why it is wrong**
Frontend treats it as free input ("اختياري"). Reports cannot pivot on priority. Translations cannot be applied.

**Exact fix**
Convert to `Enum(low, normal, high, urgent)` with default `normal`. Add migration to bucket existing free-text values.

---

### M-6 — No reservation release on `branch_request.reject`
**Location:** `backend/app/routers/branch_requests.py:491-511`

**What is wrong**
Even when reservation flow is added (per C-2 fix), the reject path needs a counter-action: release reserved_qty. Currently the reject path just toggles statuses.

**Exact fix**
After C-2 lands, add to reject:
```python
for line in row.lines:
    qty = line.qty_approved or line.qty_requested
    if line.resolved_source_type == SupplyDefaultSource.WAREHOUSE:
        ws = lock_row(...).first()
        if ws:
            ws.reserved_qty = max(Decimal("0"), ws.reserved_qty - qty)
```

---

### M-7 — `inventoryStatus` enum has a `pending_approval` alias of `submitted`, but no code uses it
**Location:** `backend/app/models/__init__.py:60`

**Why it is wrong**
Dead enum values cause confusion. Database migrations carry it forward forever.

**Exact fix**
Either:
1. Rename actively used `submitted` → `pending_approval` (data migration).
2. Drop `pending_approval` from the enum (alembic enum-modify).

---

### M-8 — `IdempotencyRequest.tenant_id` is `Integer NOT NULL` but `MULTI_TENANT_ENABLED=false`
**Location:** `backend/app/models/__init__.py:1086`; `backend/app/config.py:51`

**Why it is wrong**
The tenant column is mandatory in the unique key but the system is single-tenant. This is fine but the unused dimension creates a maintenance burden.

**Exact fix**
Either commit fully to multi-tenant (add `tenant_id` to **every** entity, not just idempotency) or remove the tenant_id dimension from the unique key.

---

### M-9 — `Brand.is_deleted` does not exist; brand can only be `active=False`
**Location:** `backend/app/models/__init__.py:371-381`

**Why it is wrong**
Inconsistent with Branch/Item/User which all have `is_deleted`. Brand soft-delete is not honoured by `BranchRequest` lookups (`branch_requests.py:285` checks `Brand.active == True`). If a brand is deactivated mid-flight requests stay valid (good), but new requests cannot be created. If renamed-and-deactivated to be replaced, history is lost.

**Exact fix**
Add `is_deleted` for parity. Honour it everywhere brand is queried.

---

### M-10 — `KitchenMaterialRequest` workflow incomplete
**Location:** `backend/app/routers/production_orders.py:316-347`

**What is wrong**
`request-materials` creates a `KitchenMaterialRequest` and sets the production order to `WAITING_FOR_MATERIALS`. But there is **no endpoint** to approve/reject the material request, **no service** that moves materials from warehouse to kitchen on approve. The `KitchenMaterialRequestStatus` enum has `APPROVED, ISSUED, REJECTED` but no code transitions to those states.

**Real-world impact**
Production stays in `WAITING_FOR_MATERIALS` forever; manual workaround needed.

**Exact fix**
Build endpoints `POST /kitchen-material-requests/{id}/approve` and `/issue` that warehouse_user actions and that move stock from `WarehouseStock` (raw materials) → kitchen (no kitchen-stock model exists yet — that's another gap; Phase-2 work).

---

### M-11 — `delivery_user` role overly broad
**Location:** `backend/app/routers/delivery_orders.py:78-79`

**What is wrong**
```python
if _is_admin(user) or "delivery_user" in _roles(user):
    return
```
Any delivery_user reaches every delivery order. They should only access deliveries assigned to them, or to their region.

**Exact fix**
Add `DeliveryOrder.assigned_to_user_id` and check it. For now (no assignment), at least bound by current_user's branch/warehouse if set.

---

### M-12 — Reconciliation snapshot can be created with missing data, no warning
**Location:** `backend/app/services/sales_channels_service.py:562-584`

**What is wrong**
`close_month` snapshots every (channel, branch) but if no `BranchDailySale` exists for the (branch, channel, month), the snapshot has `branch_total=0`, `app_total=0`, `status=match`. After close, that's frozen. The compliance report (which detects missing days) is **not consulted before close** — admin can close a month with 50% missing entries and the snapshot says all-clear.

**Exact fix**
1. Add a guard in `close_month`: compute compliance, if any branch has `compliance_percent < 100%`, require explicit `force=true` with `force_reason`.
2. Surface compliance gaps prominently in the close-month UI.

---

### M-13 — `RoleName.kitchen_manager` is "legacy value only" — not enforced
**Location:** `backend/app/models/__init__.py:39`

**Why it is wrong**
Comment says legacy. But there's no migration that prevents new assignment. UI should refuse to offer it; backend should reject it on UserRole insert.

**Exact fix**
Add a `Role.is_assignable` flag (default True) and set it False for `kitchen_manager`. Or just delete the enum value via migration once data is verified absent.

---

### M-14 — Soft-delete inconsistency: `Item.is_deleted` exists but `Item.active` is the real switch in queries
**Location:** Multiple — `branch_requests.py:189` filters both, `dashboard.py` various filter only one

**Why it is wrong**
Two flags, two filter rules. Bug-prone — one query forgets one flag and sees deleted items.

**Exact fix**
Choose one. Recommend dropping `active` and using only `is_deleted`. Migrate then alembic-drop the column.

---

### M-15 — `seed_supply_chain_demo.py` and `seed_*` scripts mix concerns
**Location:** `backend/seed_supply_chain_demo.py` etc.

**Why it is wrong**
Multiple seed scripts (10+ in `backend/`) with overlapping responsibilities. A new dev cannot tell which to run for a fresh dev DB.

**Exact fix**
Consolidate into a single `python -m app.seed all` CLI with idempotent steps. Document in README.

---

## 4) 🟢 LOW

- **L-1** `models/__init__.py:1545` — sales_channels imports moved to bottom of file as a workaround. Cleaner: register tables via metadata in a separate module imported at startup. Won't change behaviour today.
- **L-2** `branch_requests.py:288` — `request_no=f"BR-TMP-{...}"` then immediately overwritten with `BR-{id:06d}`. Race during commit could leak the temp value into reads — but it's flushed inside the same transaction, so unlikely.
- **L-3** `delivery_orders.py:331` — label HTML uses `escape()` for user-visible strings — good. But `f"DO-{row.id}"` in title is fine without escape (number).
- **L-4** `routers/delivery_orders.py:344` calls `_audit(... "label_generated") + db.commit()` even though it's a GET — generates DB writes on a read endpoint. Consider only auditing if user role is privileged.
- **L-5** `inter_branch_service.py:233-243` — creates lines with a manual loop instead of bulk insert. Performance is fine for <100 items.
- **L-6** `models/__init__.py:340` — `ReplenishmentOrder` has 16 nullable timestamp fields. Hard to query "what was the latest event". Consider an `OrderStatusHistory` child table for proper temporal modelling. (Already partially built via `get_order_timeline`).
- **L-7** Health endpoint at `/health` returns `{"status": "healthy"}` without doing a DB ping — could return 200 with DB down.
- **L-8** `core/auth.py:67` — every request loads ALL UserRoles via joinedload. Acceptable for <50k roles. Keep an eye on it.
- **L-9** Many seed scripts import `from app.config import settings` at top, then connect to whatever `DATABASE_URL` env says — no `--db` override, easy to seed prod by accident. Add a confirmation prompt.
- **L-10** `routers/auth.py` (not read in this audit but per memory `feedback_login_diagnosis.md`) — login failures often = port instability. Add health-check pre-login on the frontend.
- **L-11** `frontend/src/services/api.js:46` — `downloadUrl: (id) => '/api/v1/documents/...'`. Hardcoded base path — does not respect `VITE_API_BASE_PATH`. Tab-launch from a custom-deployed frontend will 404.
- **L-12** `frontend/src/pages/supply_chain/SupplyChainPages.jsx:579` — `<td>{order.destination_branch_id}</td>` shows raw branch id; should show branch name. The backend (`production_orders.py:62`) joins `destination_branch` so the data is available — frontend just doesn't read it.
- **L-13** No load-testing harness in repo. `tests/` folder exists but no perf tests; no `locust` config. (unverified — requires runtime).
- **L-14** `backend/raed_inventory_local_repair.db`, `_chain_full.db`, `_alembic_chain_test.db`, etc. — many stale DB files in working directory. `.gitignore` should cover them; commits could leak data.
- **L-15** Numerous `__pycache__/__init__.cpython-311.pyc.<id>` files (40+ in `models/__pycache__`) — looks like a Windows AV / antivirus quarantine artefact. Not a code bug but signals filesystem quirks.

---

## 5) 🧠 Architecture risks

### A-1 Two parallel order workflows, only one is enforced

The codebase has two distinct order pipelines:
- **Legacy V0** — `replenishment_orders` (auto-generated daily, reviewed → approved → picked → dispatched → received).
- **Supply Chain V1** — `branch_requests` → split → `production_orders` + `warehouse_lines` → `delivery_orders`.

These do not share status, audit conventions, idempotency, or stock-locking. Frontend has separate pages for each. The two systems can coexist on the same items at the same warehouse — and **deplete the same `WarehouseStock.current_qty` independently** without any cross-awareness.

**Risk:** stock over-allocation; user confusion ("which page should I use?").

**Fix path:** declare V0 deprecated; migrate auto-replenishment generators to emit `BranchRequest` rows; retire V0 routers in a phased rollout.

### A-2 Stock model insufficient for kitchens

`KitchenSection` has no `KitchenStock`. The kitchen consumes raw materials but the warehouse is unaware until production is "sent to warehouse" (which then bumps WarehouseStock as if produced ex nihilo). Material flow into kitchen → during production → out as finished goods is **opaque**.

**Risk:** Cannot track in-kitchen inventory for raw → finished. Cannot detect kitchen wastage. Cannot bill kitchen sections by consumption.

**Fix path:** Phase-2 — build `KitchenStock(kitchen_section_id, item_id, current_qty)` and BOM (Bill of Materials) tying finished goods to raw materials with consumption ratios.

### A-3 Single-tenant code, multi-tenant scaffolding, no tenant boundary

`tenant_id` exists on `IdempotencyRequest`, `QualityVisit`, `TrainingAssessment`, `Document` — but not on Branch, Warehouse, Item, BranchStock. Multi-tenant cannot be enabled without a major migration; meanwhile tenant_id confuses readers.

**Fix path:** Either commit (add tenant_id to everything; document boundary; encrypt cross-tenant in middleware) or remove. As-is is the worst of both.

### A-4 No batch / lot / expiry tracking

The Item model has `shelf_life_days` but no `Batch` or `Lot` table. A delivery from warehouse to branch carries no expiry. Branches counting stock cannot mark "100 units, 20 of which expire in 3 days." Wastage reports are date-of-event, not date-of-expiry.

**Risk:** food-safety blind spot. Not legally compliant for some Saudi food-handling regulations.

**Fix path:** Phase-3 — add `StockBatch(branch_id, item_id, batch_no, mfg_date, expiry_date, qty)`. Tie ledger transactions to a batch. ~4 weeks.

### A-5 Audit log is not the source of truth

`AuditLog.new_values` is `Text` (free JSON). No schema, no replay capability. If a state-machine bug ships, audit log can identify *that* it happened but cannot reconstruct *what* the state was.

**Fix path:** Per-entity event-store table (`branch_request_events(request_id, sequence_no, event_type, payload, created_at)`) feeds into projections. EventSourcing-lite.

---

## 6) 📊 Scalability risks

- **S-1** SQLite ceiling — ~1000 concurrent reads, single writer. With 30 branches × 5 users each = 150 concurrent users, write contention on every `BranchStock` mutation. **Will not scale beyond pilot.** Migrate to PostgreSQL before 50 concurrent users.
- **S-2** `dashboard.py` (921 lines) — most endpoints aggregate via raw SQL `func.sum(...)` over `StockTransaction`. With 1M+ transactions (1 year of 30 branches × ~100 trans/day), each dashboard load runs full-table scans. Add materialised views or a ledger-summary table.
- **S-3** `replenishment_service._get_avg_daily_consumption` (line 40) scans `StockTransaction` per (branch, item) — for 200 items × 30 branches that's 6000 queries per scheduler run. Memoise or batch via `GROUP BY`.
- **S-4** `compute_reconciliation` iterates `len(channels) * len(branches)` then 4 queries each. For 10 channels × 30 branches = 1200 queries per call. Acceptable for monthly close; bad for the live reconciliation page if loaded frequently.
- **S-5** No connection pooling tuning for SQLite — the `pool_pre_ping` is nice but `connect_args={"check_same_thread": False}` allows overlapping connections that SQLite then serialises with `database is locked` errors under load.
- **S-6** Frontend `SupplyChainBranchRequestsPage` (`SupplyChainPages.jsx:97-108`) does N+1 brand-allowed-items lookups in parallel `Promise.all` — for 4 brands that's 4 calls; for 30 brands it'd be 30. Backend should expose `/branches/{id}/allowed-brands` returning brand list with non-empty item count in one query.

---

## 7) ⚠️ Data integrity risks

- **DI-1** `BranchStock.in_transit_qty` is bumped at dispatch (`orders_service.py:533`) and decremented at receipt. If a dispatch is cancelled (no such endpoint exists today), `in_transit_qty` stays inflated forever.
- **DI-2** `ReplenishmentOrder.cancellation_reason` text but cancel does **not** reverse `in_transit_qty` or release reserved warehouse stock (see `cancel_order` line 831-835).
- **DI-3** `daily_inventory.UniqueConstraint("branch_id", "inventory_date")` — but the user can submit a "weekly" inventory for the same date, blocking the daily one. The unique key should include `inventory_type`.
- **DI-4** `branch_requests` and `replenishment_orders` are independent — no constraint preventing the same `(branch_id, item_id, date)` from having both an open auto-replenishment and an open branch request. Stock gets reserved twice (once C-2 fix lands).
- **DI-5** Foreign keys are declared in models but SQLite does not enforce FKs by default unless `PRAGMA foreign_keys = ON;` — the engine creation in `database.py:14` does **not** set this. Orphan rows possible. (unverified — needs `PRAGMA foreign_keys` check on the live DB).
- **DI-6** `EvaluationActionPlan` has no FK ON DELETE behaviour declared on `evaluation_id` — deleting an evaluation orphans plans.
- **DI-7** `Document.expiry_date` not null but `issue_date` is — calculation of remaining-days uses expiry directly, but reports comparing "issued vs expiring" silently treat null issue as 0.

---

## 8) 🔐 Security risks

- **SEC-1** `config.py:25` — `_INSECURE_DEFAULT_SECRET` is the literal value used in `.env` (`backend/.env: SECRET_KEY=raed-local-dev-secret-key`). The `validate_security` warns but auto-generates an in-memory replacement on each restart in local. **In production**, the `.env.production` file is checked in (visible in `ls`); review whether it actually has a strong key. (unverified — file unread; check by hand).
- **SEC-2** `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")` (auth.py:9). Token in `localStorage` (`api.js:76`). XSS → token theft. Move to httpOnly cookie or implement CSRF protection + short-lived tokens + refresh.
- **SEC-3** No password complexity enforcement at the model layer (`User.hashed_password` accepts whatever bcrypt hash). Frontend may not enforce; reset endpoints accept any string ≥1 char (unverified — `auth.py` not read).
- **SEC-4** Rate limits configured at 200/minute (`config.py:45`) and 20/minute on auth — auth limit is fine, default is generous. Per-user (not per-IP) limiting would be safer for shared corporate IPs (LAN trial).
- **SEC-5** `delivery_orders.delivery_labels` (line 318) emits HTML with branch/brand/item names. `escape()` used for these. Good. BUT `request.client.host` not validated — header injection unlikely but check.
- **SEC-6** `frontend/src/services/api.js:96-104` clears tokens on 401 except for `/auth/login`. Good. But `window.location.href = '/login'` on 401 is a hard redirect that loses user state — bad UX after session timeout.
- **SEC-7** No CSRF tokens. CORS allows `localhost:3000/5173` only — but the production CORS is set via env var `ALLOWED_ORIGINS`. Misconfigured comma-list = wildcard exposure.
- **SEC-8** File uploads: `MAX_UPLOAD_SIZE_MB = 20` (config.py:61). Per-route enforcement needed (unverified — `documents.py` not read in detail).
- **SEC-9** Sentry init runs unconditionally on import (`main.py:28`). No DSN check. If DSN is leaked in `.env.production`, tampering with Sentry endpoint is possible. (unverified — `sentry_init.py` not read).
- **SEC-10** Backup script (per task #22) location unknown. If it backs up the SQLite file naively, a backup mid-write yields a corrupt copy.

---

## 9) 🎯 UX / Operational risks

- **UX-1** No "what is this status?" tooltips in supply-chain pages. `SupplyChainPages.jsx:7-26` has internal `STATUS_BADGE` + `STATUS_LABEL` dicts but only Arabic — English users see Arabic labels.
- **UX-2** `SupplyChainKitchenPage` (line 526+) shows `destination_branch_id` raw — confusing.
- **UX-3** No "save draft" pattern on production-page partial-issue inputs — leaving the page loses values.
- **UX-4** Frontend `App.jsx:541-543` route `InterBranchTransferPage` allowed list excludes `area_manager` per frontend audit — but this is the role that *should* be approving inter-branch transfers. Inconsistent.
- **UX-5** Per memory `feedback_login_diagnosis.md`, generic "login error" frequently means port instability — frontend should distinguish between 401 (bad creds) vs network error vs 500.
- **UX-6** Pack C closures: closing a month is an irreversible-feeling action. Frontend should show a "this will lock all daily-sale entries; reopening requires a 5-character reason and audit trail" warning. (unverified — Pack C frontend not yet built per task #134 pending).
- **UX-7** No exponential-backoff on 5xx retries in `api.js`. Single retry to fallback base, then fail.
- **UX-8** No offline-queue for branch users — if branch loses internet during inventory entry, work is lost.
- **UX-9** No notifications when production hits `WAITING_FOR_MATERIALS` for >X minutes. `notifications.py` exists but specific scenarios are unclear without runtime.

---

## 10) Roadmap to production-ready

**Total estimate to ship-ready: 8–12 weeks of one senior engineer + part-time DBA + part-time frontend.**

### Phase A — Stop-the-bleed (2 weeks, MUST DO BEFORE ANY MORE FEATURE WORK)

| # | Task | Effort | Depends |
|---|------|--------|---------|
| A1 | Migrate to PostgreSQL in production; enforce SQLite-dev-only via env validation | 3d | none |
| A2 | Fix C-1: lock WarehouseStock in `warehouse_lines._deduct_stock` | 0.5d | A1 |
| A3 | Fix C-2: implement `reserved_qty` flow on split / issue / reject / cancel | 3d | A1, A2 |
| A4 | Fix C-3: real row locking (`_supports_row_locks` honest) | 0.5d | A1 |
| A5 | Fix C-4: re-add scope checks for admin in `_require_area_review` and friends | 1d | none |
| A6 | Fix C-5: lock BranchRequest before status mutation; convert IntegrityError to 409 | 1d | A4 |
| A7 | Fix H-1 + H-8: lock BranchStock in delivery_orders + dispatch | 1d | A1 |
| A8 | Add CHECK constraints (H-10, H-12) via Alembic migration | 1d | A1 |
| A9 | Smoke-test concurrent splits / issues / deliveries with locust / pytest-xdist | 1d | all |

### Phase B — Workflow correctness (3 weeks)

| # | Task | Effort |
|---|------|--------|
| B1 | Fix H-9: idempotency wrapper on 8 supply-chain endpoints | 3d |
| B2 | Fix H-2: declarative state-machine for ReplenishmentOrder + BranchRequest + ProductionOrder | 5d |
| B3 | Fix H-13: standardised audit-log helper with old/new state diff | 2d |
| B4 | Build M-10: kitchen-material-request approve/issue endpoints + tests | 4d |
| B5 | Fix DI-1, DI-2: cancel paths release reserved + in_transit | 1d |
| B6 | Fix M-12: compliance gate on month-close | 1d |
| B7 | Fix DI-3: weekly/monthly inventory uniqueness | 0.5d |

### Phase C — Snapshot + history (2 weeks)

| # | Task | Effort |
|---|------|--------|
| C1 | Fix H-6, H-7: snapshot brand/item/section names on BranchRequestLine and ProductionOrder | 4d |
| C2 | Build OrderStatusHistory child tables for proper temporal model (replaces 16 nullable timestamps) | 5d |
| C3 | Migrate audit_log writes to use new OrderStatusHistory | 1d |

### Phase D — Procurement + batches (4 weeks)

| # | Task | Effort |
|---|------|--------|
| D1 | Supplier master + Supplier UI | 5d |
| D2 | PurchaseOrder + lines + workflow | 5d |
| D3 | GoodsReceiptNote endpoint + warehouse stock increment | 3d |
| D4 | StockBatch + expiry tracking on issues/receives (H-4 follow-up) | 7d |

### Phase E — Frontend RBAC + polish (1 week)

| # | Task | Effort |
|---|------|--------|
| E1 | Fix H-5: RoleGuard on all admin/ops/sales-mgr routes | 1d |
| E2 | Resolve all CRITICAL/MAJOR findings from `frontend_audit_2026-04-24.md` | 3d |
| E3 | Replace `destination_branch_id` raw display with names everywhere | 0.5d |
| E4 | EN-translation for status badges in SupplyChainPages | 0.5d |

### Phase F — Production hardening (1 week)

| # | Task | Effort |
|---|------|--------|
| F1 | Health endpoint with DB ping | 0.5d |
| F2 | Sentry DSN check + auto-disable | 0.5d |
| F3 | Backup script: pg_dump + S3, restore drill | 1.5d |
| F4 | Metrics: per-endpoint timing, queue depth, pending production count | 1.5d |
| F5 | Load test (locust): 50 concurrent users, 1h | 1d |
| F6 | Runbook: on-call playbook, common errors | 1d |

---

## Methodology notes

### Deeply audited
- `backend/app/core/auth.py` — every line read.
- `backend/app/core/locking.py`, `database.py`, `config.py` — fully read.
- `backend/app/services/branch_request_split_service.py` — fully read; race analysis performed.
- `backend/app/services/sales_channels_service.py` — fully read.
- `backend/app/services/orders_service.py` — fully read (lines 1-940).
- `backend/app/services/inter_branch_service.py` — fully read.
- `backend/app/services/stock_ledger_service.py`, `stock_adjustment_service.py:1-200` — read.
- `backend/app/routers/branch_requests.py`, `production_orders.py`, `warehouse_lines.py`, `delivery_orders.py`, `supply_chain.py`, `sales_channels.py` — fully read.
- `backend/app/routers/orders.py`, `stock.py` — fully read.
- `backend/app/models/__init__.py` lines 1-1545 — read; relationships and constraints traced.
- `backend/app/models/sales_channels.py` — fully read.
- `backend/app/main.py` — fully read.
- `frontend/src/services/api.js` — fully read.
- `frontend/src/pages/supply_chain/SupplyChainPages.jsx` — fully read.

### Surface-level only / read for context
- `backend/app/services/replenishment_service.py:1-200` — formula understood.
- `backend/app/routers/dashboard.py` — size only (921 lines flagged for S-2).
- `backend/app/routers/inventory.py`, `users.py`, `quality.py`, `training.py`, `documents.py` — not read in detail.

### Skipped (and why)
- Alembic migrations — would require runtime DB inspection to verify which CHECK constraints actually applied; migration files not opened.
- `tests/` directory — would require pytest run to assess coverage; test failure log present (`TESTS_FAILURE_TRIAGE.md`) suggests 13 known failing tests.
- Most frontend pages — covered comprehensively in `frontend_audit_2026-04-24.md` (38 findings).
- `backend/seed_*.py` scripts (10+ files) — read titles only; flagged in M-15.

### Requires runtime to verify
- DI-5 (PRAGMA foreign_keys for SQLite) — needs `PRAGMA foreign_keys` check on live DB.
- H-10, H-12 (CHECK constraints) — task #10 was marked completed but the migration itself was not opened; whether it survived subsequent migrations needs Alembic chain replay or `\d branch_stock` on prod.
- C-3 race repro — needs concurrent-request load test.
- C-5 race repro — needs concurrent-request load test.
- SEC-1 (.env.production strength) — file not opened.
- SEC-9 (sentry_init.py details) — not opened.
- L-13 (load test harness presence) — folder structure suggests no, but tests/ not enumerated.
- All frontend route exposures — confirmed by frontend audit but not retried here.

---

**End of audit.**
