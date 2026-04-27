# Raed Inventory System — Full Production Audit v2

**Date:** 2026-04-25
**Method:** Static read of source code, no runtime execution.
**Previous audit score:** 52/100

---

## Executive Summary

- **SYSTEM_HEALTH_SCORE: 58/100** (+6 vs v1).
  Justification:
    - Two of v1's top-10 (split lock + reserved_qty write) are genuinely fixed.
    - Two more (item-master idempotent import; AreaManagerAssignment `(user_id, city, brand_id)` partial-unique index) are fixed.
    - The remaining 8 of the v1 top-10 are still in the codebase as written — the SQLite-vs-row-lock no-op, admin bypass in `require_roles`, FK-without-snapshot on Items in `WarehouseLine` / `DeliveryOrderLine`, missing 409 on approve race, no procurement-receive flow, and no global frontend role-route guard for legacy pages still ship.
    - New issues found in v2 that did not exist in v1: in-memory file reads with no streaming (DoS surface), uploads stored on local disk in a Railway container (lost on every redeploy), `WarehouseStock`/`BranchStock` UniqueConstraint on `(warehouse_id, item_id)` is unnamed — index name will collide on Postgres autogen, MIME-only validation (file content not sniffed), `delivery-orders/{id}/labels` writes audit + commits inside a GET, Dockerfile runs uvicorn as root with no `--workers`, no ASGI request size limit anywhere.
    - These regressions hold the score back from breaking 65/100.

- **PRODUCTION_READINESS: NOT_READY**

- **TOP 10 MOST DANGEROUS issues (one line each):**
  1. **CRITICAL** — SQLite + `lock_row()` is a deliberate no-op (`backend/app/core/locking.py:24`); demo DB is SQLite, so `_deduct_stock`, approve-inventory, dispatch, and split all run with **zero** row-lock protection in production-shaped tests and the live demo. Concurrent dispatch can over-issue.
  2. **CRITICAL** — `require_roles()` bypasses ALL role checks for `admin`/`super_admin` regardless of the tuple passed (`backend/app/core/auth.py:147-157`). Any service-layer role gate (e.g. sales_channels closure-owner) is the only thing standing between admin and write paths it was never meant to touch.
  3. **CRITICAL** — `delivery_orders/{order_id}/deliver` blindly sets `qty_delivered = qty_dispatched` and `status = DELIVERED` for every line (`backend/app/routers/delivery_orders.py:297-300`); no support for short-receive, no per-line `received_qty`, no damaged/missing fields, no receiver signature/photo. The `DeliveryOrderLineStatus.PARTIAL_DELIVERED` enum exists but is never written.
  4. **CRITICAL** — Production materials request creates a `KitchenMaterialRequest` row but never lifts the lock or actually consumes any warehouse stock (`backend/app/routers/production_orders.py:344-375`); status flips to WAITING_FOR_MATERIALS but no warehouse fulfillment line is created. The kitchen→warehouse pull is non-functional.
  5. **HIGH** — `production_orders/{id}/send-to-warehouse` increments `WarehouseStock.current_qty` **without a row lock** (`backend/app/routers/production_orders.py:292-305`); concurrent kitchen-output posts can lose updates.
  6. **HIGH** — `delivery_orders/{id}/labels` (a GET) calls `audit_service.log` then `db.commit()` (`backend/app/routers/delivery_orders.py:370-371`); a GET that mutates is both a CSRF anti-pattern and breaks idempotency for any cache/proxy.
  7. **HIGH** — Procurement is shells-only: `PurchaseRequest` has DRAFT/SUBMITTED states, no Purchase Order, no Receipt, no Invoice, no supplier price (`backend/app/routers/procurement.py:1-90`). The system cannot replenish warehouse stock from suppliers; the only way new stock enters is `seed_supply_chain_demo.py` writing 500 units once.
  8. **HIGH** — `WarehouseLine` and `BranchRequestLine` snapshot item `name`/`code`/`unit_code` but `DeliveryOrderLine`, `ProductionOrder`, `KitchenMaterialRequest`, `ReplenishmentOrderLine`, `StockTransaction` all FK live to `items` with no snapshot (`backend/app/models/__init__.py:553-666, 1055-1080, 1087-1101`). Renaming/reclassifying an item retroactively rewrites historical orders and ledger.
  9. **HIGH** — `_ensure_inventory_access` and order branch access checks call `can_access_branch(...)` which falls back to legacy `area_manager` regional comparison by city/area name (`backend/app/core/auth.py:84-118`); city/area are free-text fields with no normalization beyond `.strip().lower()`. A typo or trailing space breaks scope. Supply-chain branch_requests already moved to `AreaManagerAssignment` (correct), but legacy orders still use the fragile path.
  10. **MEDIUM-HIGH** — `frontend/src/components/common/RouteRoleGuard.jsx:13` always elevates `super_admin`/`admin`. Same admin-bypass shape as backend; combined with the backend bypass the admin role can do anything anywhere with no explicit grant.

- **Verdict (one paragraph):**
  The split-and-reserve fix is real and complete; the area_manager scope tightening via `AreaManagerAssignment` is real; the item-master importer is solid. But the system is still **not production-ready**: the entire concurrency story is a no-op on SQLite (which is what the live demo and Railway-without-Postgres path runs on), `require_roles` admin-bypass undermines every per-module write restriction, and the supply-chain V1 phase 3 (delivery) cannot model partial deliveries despite having the enum. Procurement is a stub. The kitchen-material-request workflow is half-wired. Treat this as a strong demo build and a viable LAN trial, not a multi-tenant SaaS.

---

## 🔴 CRITICAL ISSUES (must fix before production)

### C1. SQLite makes every `lock_row()` call a no-op
- **Path:** `backend/app/core/locking.py:13-28`, called from:
  - `backend/app/services/branch_request_split_service.py:70`
  - `backend/app/routers/warehouse_lines.py:96-101`
  - `backend/app/routers/branch_requests.py:497, 554`
  - `backend/app/routers/delivery_orders.py:306-311`
  - `backend/app/services/orders_service.py:24-38, 65`
  - `backend/app/services/inventory_service.py:425-428`
- **What is wrong:**
  `_supports_row_locks()` returns `False` for any `sqlite:` URL; `lock_row()` returns the unmodified query. Every call site was *written* assuming `SELECT ... FOR UPDATE` semantics — pessimistic concurrency control.
- **Why it is wrong:**
  The default `DATABASE_URL` in `app/config.py:19` is `sqlite:///./raed_inventory_local.db`. The Railway deploy plan in `RAILWAY_DEPLOY.md` and `railway.toml` *says* set Postgres, but nothing forces it. Running the LAN trial (per memory: am_riyadh + am_dammam) means two concurrent area-manager approvals on the same submitted request can both pass the "is SUBMITTED?" check, both run the split, both attempt to insert two `WarehouseLine` rows with the same `(source_request_line_id, source_type)` — and the unique constraint will save you, but only by raising `IntegrityError` 500, not 409.
- **Real-world impact:**
  Concurrent dispatch + concurrent inventory approval can over-issue stock to negative *during the same transaction window*. The `CHECK (current_qty >= 0)` constraint added in migration 0004 protects you on Postgres, but on SQLite `WriteBeforeCommit + no row lock` will still allow two transactions to read the same `current_qty=10`, both subtract 7, both write 3, and the check fires on neither because the value lands at 3.
- **Exact fix:**
  1. Hard-fail boot when `DATABASE_URL.startswith("sqlite")` AND `ENVIRONMENT == "production"` — already in `config.py:110`. Keep it.
  2. Add the same hard-fail in `Settings.validate_security` for `ENVIRONMENT == "staging"`.
  3. In `core/locking.py`, when SQLite is detected log a `WARNING` once per process at import time, not silently fall back. Add at top of module:
     ```python
     import logging
     _LOG = logging.getLogger(__name__)
     if settings.DATABASE_URL.lower().startswith("sqlite"):
         _LOG.warning("SQLite in use — lock_row() is a no-op. NOT safe for >1 concurrent writer.")
     ```
  4. The actual production fix is to switch the demo to Postgres in Docker for the LAN trial. SQLite + busy_timeout=5000 (set in `database.py:21`) gives serialization but no row-level granularity, so a long-running approve will block every other write.

### C2. Central `require_roles` admin bypass is too wide
- **Path:** `backend/app/core/auth.py:133-158`
- **What is wrong:**
  Every endpoint dependency `Depends(require_roles("warehouse_user", "warehouse_manager"))` silently allows `admin` and `super_admin` past, regardless of the tuple.
- **Why it is wrong:**
  Module-level write restrictions (e.g. only sales_channel closure owners can reopen) can only be enforced in services, but several services *don't* re-check (e.g. `procurement.create_purchase_request` only checks "warehouse_id matches your warehouse" via `_is_admin or...`). The footgun is: any new endpoint that forgets a service-layer recheck is silently exposed to all admins.
- **Real-world impact:**
  Any user accidentally given the `admin` role for a one-off operations task gains permanent total access — including the closure of monthly sales reconciliations they should never touch. This is a data-integrity time bomb because `admin` is a low-friction grant.
- **Exact fix:**
  Replace the central bypass with explicit opt-in. Change `require_roles` so that admin/super_admin only bypass when `*roles` is empty OR contains the literal `"*"`:
  ```python
  def checker(current_user: User = Depends(get_current_active_user)):
      user_roles = get_user_roles(current_user)
      if "*" in roles and ("super_admin" in user_roles or "admin" in user_roles):
          return current_user
      if not any(r in user_roles for r in roles):
          if "super_admin" in user_roles:  # super_admin always — admin must be listed
              return current_user
          raise HTTPException(...)
      return current_user
  ```
  Then audit every router and add `"admin"` to the tuples that *should* allow admin (most of them — but the audit is the point).

### C3. Delivery cannot model partial deliveries — silent over-credit risk
- **Path:** `backend/app/routers/delivery_orders.py:276-341`
- **What is wrong:**
  `deliver_order` walks every line in the order and unconditionally:
    ```python
    qty = Decimal(str(line.qty_dispatched))
    line.qty_delivered = qty
    line.status = DeliveryOrderLineStatus.DELIVERED
    ```
  No request body lets the delivery user say "received 8 of 10". `DeliveryOrderDeliverPayload` only carries `receiver_name` + `delivery_note`. `BranchStock.current_qty` is then incremented by `qty_dispatched` for every line.
- **Why it is wrong:**
  The `DeliveryOrderLineStatus` enum has `PARTIAL_DELIVERED` and the schema documents per-line delivery — but no code path writes it. The "labels" workflow exists, the OUT_FOR_DELIVERY event is recorded, the receiver name is stored, but the actual count of what was received is fiction. Worse: `qty_delivered` will report what was *dispatched*, which violates the basic invariant of delivery analytics.
- **Real-world impact:**
  If a delivery driver hands the branch 9 boxes when 10 were dispatched, the system records 10. `BranchStock.current_qty` is over-credited by 1. The branch's next inventory will show "missing" 1, the variance will get blamed on the branch, and the warehouse's loss is hidden.
- **Exact fix:**
  1. Extend `DeliveryOrderDeliverPayload`:
     ```python
     class DeliveryLineReceipt(BaseModel):
         line_id: int
         qty_received: Decimal  # 0 ≤ qty_received ≤ qty_dispatched
         damaged_qty: Decimal = Decimal("0")
         shortage_reason: Optional[str] = None
     class DeliveryOrderDeliverPayload(BaseModel):
         receiver_name: str
         delivery_note: Optional[str] = None
         lines: list[DeliveryLineReceipt]
         signature_attachment_id: Optional[int] = None
     ```
  2. In `deliver_order` iterate by `payload.lines`, validate `qty_received + shortage <= qty_dispatched`, and if `qty_received < qty_dispatched` set `line.status = DeliveryOrderLineStatus.PARTIAL_DELIVERED` and the order status to a new `PARTIAL_DELIVERED`.
  3. Lock both `BranchStock` and the `DeliveryOrderLine` (currently only `BranchStock` is locked).
  4. Post a `WarehouseStock` adjustment_in for any `damaged_qty + shortage` so the unaccounted stock returns to the warehouse ledger.

### C4. Kitchen material request creates a row and dies
- **Path:** `backend/app/routers/production_orders.py:344-375`
- **What is wrong:**
  Endpoint creates a `KitchenMaterialRequest` (PENDING) and flips the production order to `WAITING_FOR_MATERIALS`. There is no router/service path that ever advances the material request to APPROVED → ISSUED. No `WarehouseLine` of `source_type=KITCHEN_MATERIAL_REQUEST` is created. The enum `WarehouseLineSourceType.KITCHEN_MATERIAL_REQUEST` exists (`models/__init__.py:166`) but no code writes it.
- **Why it is wrong:**
  Half-wired feature: kitchen says "I need 5kg of flour" → request is logged → nobody and nothing acts on it → kitchen sits in WAITING_FOR_MATERIALS forever.
- **Real-world impact:**
  In demo, the kitchen flow appears to work because the seed warehouse stock is sufficient. The moment a section manager hits "request materials" they're permanently stuck.
- **Exact fix:**
  Add three endpoints in `production_orders.py` (or a new `kitchen_materials.py` router):
  - `POST /api/v1/kitchen-materials/{id}/approve` (warehouse_manager): flips PENDING→APPROVED.
  - `POST /api/v1/kitchen-materials/{id}/issue` (warehouse_user): locks `WarehouseStock`, decrements, posts a ledger row of new `TransactionType.kitchen_issue` (add to enum), creates a `WarehouseLine` of `KITCHEN_MATERIAL_REQUEST` source_type, sets status ISSUED, and flips the production order back to IN_PROGRESS.
  - `POST /api/v1/kitchen-materials/{id}/reject` with reason; flips production order back to IN_PROGRESS too.

---

## 🟠 HIGH PRIORITY ISSUES

### H1. `send-to-warehouse` increments warehouse stock without a lock
- **Path:** `backend/app/routers/production_orders.py:292-305`
- **What is wrong:** `db.query(WarehouseStock).filter(...).first()` then `stock.current_qty = ... + qty_to_send`. No `lock_row()`.
- **Why it is wrong:** Two concurrent kitchen managers calling `send-to-warehouse` for two different production orders that map to the same `(warehouse_id, item_id)` race; one increment is lost.
- **Impact:** Warehouse over- or under-credits silently. Ledger has both transactions but stock has only one.
- **Fix:** Wrap the `WarehouseStock` query in `lock_row(...)` exactly as `_deduct_stock` does. Same in `branch_request_split_service.py:70-87` (already locked) for symmetry.

### H2. GET endpoint mutates state
- **Path:** `backend/app/routers/delivery_orders.py:344-393`
- **What is wrong:** `delivery_labels` is a `@router.get`, but it calls `audit_service.log(...)` and `db.commit()`. RFC 9110 requires GET to be safe & idempotent.
- **Impact:** Any browser/proxy/cache that retries a GET (Chrome, CDN) duplicates the audit row. Page refresh inflates audit logs.
- **Fix:** Drop the audit + commit from `delivery_labels`. If you need an audit, expose `POST /api/v1/delivery-orders/{id}/labels` and have the print page POST first, then redirect to the GET render.

### H3. Procurement workflow is a stub
- **Path:** `backend/app/routers/procurement.py:1-90`
- **What is wrong:** Only `Supplier` and `PurchaseRequest` (DRAFT/SUBMITTED). No PO, no Goods Receipt, no Invoice, no supplier price, no warehouse-stock receive transition.
- **Impact:** No way to replenish warehouse stock outside of seed scripts. Production demo will exhaust seeded 500-unit per-item stock and never recover.
- **Fix:** Either ship full procurement (add `PurchaseOrder`, `PurchaseOrderLine`, `GoodsReceipt`, `GoodsReceiptLine`, `SupplierInvoice` models + state machine), or remove the procurement router and the "Procurement" navigation item until v2. Half-shipped is worse than absent.

### H4. Historical data tied to live FKs (item rename rewrites history)
- **Path:**
  - `backend/app/models/__init__.py:650-666` (`DeliveryOrderLine`)
  - `backend/app/models/__init__.py:553-577` (`ProductionOrder`)
  - `backend/app/models/__init__.py:580-593` (`KitchenMaterialRequest`)
  - `backend/app/models/__init__.py:1055-1080` (`ReplenishmentOrderLine`)
  - `backend/app/models/__init__.py:1087-1101` (`StockTransaction`)
- **What is wrong:** Only `BranchRequest`/`BranchRequestLine` snapshot brand/item names. All downstream entities still join live `items.item_name_*`.
- **Impact:** Renaming an item ("Pizza Dough Ball" → "Pizza Dough Ball v2") changes every historical delivery PDF, every ledger entry, every audit log. Re-classifying an item from KITCHEN to WAREHOUSE corrupts old reports.
- **Fix:** Add to each model: `item_name_ar_snapshot`, `item_name_en_snapshot`, `item_code_snapshot`, `unit_code_snapshot`, `kitchen_section_name_snapshot` (where applicable). Populate in the same place where the row is created. Add an Alembic migration to back-fill from the current join.

### H5. Approve race returns 500 instead of 409
- **Path:** `backend/app/routers/branch_requests.py:483-537` and `inventory_service.approve_inventory_for_user` at `inventory_service.py:175-230`
- **What is wrong:** The branch-request approve endpoint *does* check `if row.status in (AREA_APPROVED, ...): return row` after taking the lock — so on Postgres + lock, a second approve sees the new status and returns 200. But on SQLite (no lock), both can pass the check, both call `_split_request_service`, both flush, and the second hits `IntegrityError` from `uq_warehouse_line_request_line_source` → propagates as 500. Inventory approve raises 409 only via idempotency, not via `inventory.already_approved` race; the same race produces an `IntegrityError` on the BranchStock UNIQUE constraint or stale read.
- **Impact:** A double-click on the approve button in the area manager UI returns 500 to the second click. Demo will show a red error toast.
- **Fix:**
  1. In `main.py` add an `IntegrityError` handler that returns 409 with `error_code="resource.conflict"`.
  2. In `branch_requests.approve_branch_request`, wrap the `_split_request_service(db, row)` call in `try/except IntegrityError as e: db.rollback(); raise AppError(status_code=409, error_code="branch_requests.split_in_progress", ...)`.

### H6. `WarehouseLine` unique constraint relies on `source_type` + nullable `source_request_line_id`
- **Path:** `backend/app/models/__init__.py:613-615`
- **What is wrong:** `UniqueConstraint("source_request_line_id", "source_type")`. But `source_request_line_id` is nullable. SQLite treats `NULL` as distinct (multi-NULL allowed); Postgres also. So if you ever create a WarehouseLine without a `source_request_line_id` (e.g. a manual procurement receipt), the uniqueness gives no protection.
- **Impact:** Future procurement integration will silently allow duplicate inbound lines.
- **Fix:** Either make `source_request_line_id` non-nullable and create separate `source_purchase_order_id`, `source_goods_receipt_id` columns; or replace the constraint with a partial unique index: `WHERE source_request_line_id IS NOT NULL`.

### H7. Quality/Document file upload reads entire file into memory
- **Path:**
  - `backend/app/services/quality_service.py:624` (`data = file.file.read()`)
  - `backend/app/services/document_service.py:288` (same pattern)
- **What is wrong:** Reads whole file into RAM before checking size. The `MAX_UPLOAD_SIZE_MB=20` and `_MAX_ATTACHMENT_BYTES=10MB` checks happen *after* the read.
- **Impact:** A malicious user uploads a 5GB file; uvicorn allocates 5GB before raising 413. Single request can OOM the container.
- **Fix:** Stream the upload:
  ```python
  CHUNK = 1 << 16
  total = 0
  with open(full_path, "wb") as f:
      while chunk := file.file.read(CHUNK):
          total += len(chunk)
          if total > _MAX_ATTACHMENT_BYTES:
              raise HTTPException(413, "...")
          f.write(chunk)
  ```
  Also configure uvicorn with `--limit-max-requests` and the gunicorn worker arg `--limit-request-line` if behind gunicorn.

### H8. Uploads stored on local disk in a Railway container
- **Path:**
  - `backend/app/config.py:64-66` — `UPLOAD_DIR = "./uploads"`
  - `backend/app/services/quality_service.py:630-636`
  - `backend/app/services/document_service.py:294-302`
- **What is wrong:** Files written to relative path inside the container.
- **Impact:** Railway container restarts wipe `/app/uploads`. Every quality photo, every document, every signature lost on next deploy. There is no S3/MinIO integration anywhere in the codebase.
- **Fix:** Either mount a Railway volume on `/app/uploads` (and document this in `RAILWAY_DEPLOY.md`), or — preferred — abstract the storage backend behind a tiny `app/services/object_store.py` with `upload(key, bytes) -> url` / `read(key) -> bytes` and a default disk impl + an S3 impl gated on `STORAGE_BACKEND=s3`. Required env: `S3_BUCKET`, `S3_REGION`, IAM creds.

### H9. MIME-type validated only by `file.content_type` (client header)
- **Path:** `backend/app/services/quality_service.py:617-622`, `backend/app/services/document_service.py:281-286`
- **What is wrong:** Trusts the multipart `Content-Type` field, which the client controls. A malicious upload labels a `.exe` as `image/png` and the server happily writes it.
- **Impact:** Server hosts arbitrary content. If you ever serve `/uploads/...` directly, it's RCE-via-mime.
- **Fix:** Use `python-magic` or `filetype` to sniff the first 4KB of bytes. Reject if sniffed type doesn't match the extension AND the allowed prefix list. Also, never serve uploads directly — always go through `/api/v1/.../download` which forces `Content-Disposition: attachment`.

### H10. Frontend RouteRoleGuard mirrors backend admin bypass
- **Path:** `frontend/src/components/common/RouteRoleGuard.jsx:13`
- **What is wrong:** `const elevated = roles.includes('super_admin') || roles.includes('admin')`. Same as backend.
- **Impact:** UI shows admin every restricted page. Combined with backend, admin can do everything. Fine for super_admin; not fine for `admin`.
- **Fix:** Change `elevated` to only include `super_admin`. Force `admin` to appear in every `allowed` list explicitly.

### H11. Notifications router lacks visible per-role scoping (unverified — requires runtime)
- **Path:** `backend/app/routers/notifications.py` (not read; deferred). Listed in `main.py:267`.
- **What is wrong (unverified):** Notification list endpoints typically need branch/warehouse/role scope so a delivery_user doesn't see warehouse_manager notifications.
- **Fix:** Read `notifications.py` and confirm every list endpoint scopes by current_user.id or current_user.role.

---

## 🟡 MEDIUM ISSUES

### M1. `_refresh_request_statuses` doesn't handle PARTIAL_DELIVERED
- **Path:** `backend/app/routers/delivery_orders.py:110-124`
- **What is wrong:** Only flips `BranchRequestStatus.DELIVERED` when *all* lines are DELIVERED or REJECTED. If we ever ship partial-delivery (we should — see C3), there's no `PARTIAL_DELIVERED` request status.
- **Fix:** Add `BranchRequestStatus.PARTIAL_DELIVERED` and `BranchRequestLineStatus.PARTIAL_DELIVERED`; update `_refresh_request_statuses` to handle the partial case.

### M2. `receive_order` does not write an audit log
- **Path:** `backend/app/services/orders_service.py:578-746`
- **What is wrong:** `audit_service.log` is called for cancel and close but not for receive. Receiving is the most consequential ledger event.
- **Fix:** Add an audit_service.log call after the ledger transactions, before the all_received check.

### M3. `Branch` city/area free text leak into RBAC
- **Path:** `backend/app/core/auth.py:84-118` and `Branch.city`/`Branch.area` (`models/__init__.py:328-329`)
- **What is wrong:** Region check normalizes only with `.strip().lower()`. "Riyadh ", "riyadh", "RIYADH" all match — fine — but "Ar Riyadh", "Riyad", or Arabic "الرياض" don't. A typo locks an area manager out.
- **Fix:** Either link `Branch` to a `Region` table by FK, or always go through `AreaManagerAssignment` (the supply-chain path already does this). Drop the legacy text-match fallback after migrating the legacy orders router.

### M4. `_ensure_inventory_access` calls `can_access_branch` with stale `area_manager` semantics
- **Path:** `backend/app/services/inventory_service.py:42-49`
- **What is wrong:** Inventory access for `area_manager` falls back to the city/area text path. Inventory branch_id has no AreaManagerAssignment join.
- **Fix:** Wire inventory's area_manager scope to `AreaManagerAssignment` like supply-chain does, since branch_brands + assignment is the only authoritative source.

### M5. `can_access_branch` returns True for `operations_manager` globally — but `operations_manager` is also branch-less
- **Path:** `backend/app/core/auth.py:104-105`
- **What is wrong:** Anyone with `operations_manager` sees every branch's data. Probably intentional, but no audit anywhere reflects the global access.
- **Fix:** Document explicitly in code, and add a `tenant_id` filter so multi-tenant rollout isn't broken by it.

### M6. `WarehouseStock` / `BranchStock` UniqueConstraint is unnamed
- **Path:** `backend/app/models/__init__.py:923, 937`
- **What is wrong:** `UniqueConstraint("branch_id", "item_id")` with no `name=`. SQLAlchemy autogen names → on Postgres `branch_stock_branch_id_item_id_key` (autogen) — fine — but Alembic with `compare_type=True` will sometimes regenerate. Not catastrophic, but pinning the name helps migration diffs.
- **Fix:** `UniqueConstraint("branch_id", "item_id", name="uq_branch_stock_branch_item")`. Same for warehouse_stock.

### M7. Demo seed creates `DEMO-WH-1` but admin pages can delete it
- **Path:** `backend/seed_supply_chain_demo.py:438-448`
- **What is wrong:** No protective marker. Admin UI has a delete button per `frontend_audit_2026-04-24.md`.
- **Fix:** Add a `is_seed=True` flag to Warehouse/Branch and refuse delete in the admin router for seed rows.

### M8. `BranchRequest.priority` is free text
- **Path:** `backend/app/models/__init__.py:512`
- **What is wrong:** `priority = Column(String(30), nullable=True)`. No enum. UI free-types.
- **Impact:** Priority filtering is futile; "high", "High", "HIGH" all distinct in DB.
- **Fix:** Convert to `Enum("low", "normal", "high", "urgent")`.

### M9. `_ensure_training_templates_seeded` runs on every cold-start
- **Path:** `backend/app/main.py:100-135`
- **What is wrong:** Runs `seed_quality_training` from inside the request handler thread on startup if any item missing. On a cold container, this can take seconds and block readiness.
- **Fix:** Move auto-seed behind `--auto-seed` CLI flag or an explicit `seed: true` env var, not on every startup. Migrations should own seed data, not the request app.

### M10. Browser `localStorage` for `access_token`
- **Path:** `frontend/src/services/api.js:76-77`
- **What is wrong:** Token stored in `localStorage` is XSS-readable.
- **Impact:** Any compromised npm dependency in the React build gets the token. With `ACCESS_TOKEN_EXPIRE_MINUTES=480` (8 hours), the blast radius is high.
- **Fix:** Move to `httpOnly` cookie set by `/auth/login`. Requires CORS update and CSRF token (the codebase has none).

### M11. No N+1 protection on `list_orders` summary
- **Path:** `backend/app/routers/orders.py:121-168`
- **What is wrong:** `selectinload(ReplenishmentOrder.lines).selectinload(ReplenishmentOrderLine.item)` is good, but no `joinedload` on `item.unit` despite `_line_to_dict` accessing `item.unit.name_ar`.
- **Impact:** N+1 on every order list page for the unit join.
- **Fix:** Add `.selectinload(ReplenishmentOrderLine.item).joinedload(Item.unit)` (chain `joinedload` after selectinload).

### M12. `DeliveryOrder` / `DeliveryOrderLine` indexes missing on `(branch_id, status)` hot path
- **Path:** `backend/app/models/__init__.py:625-666`
- **What is wrong:** `status` and `branch_id` each individually indexed but no composite. `list_ready_delivery_orders` filters on both.
- **Fix:** Add `Index("ix_delivery_orders_branch_status", "branch_id", "status")`.

### M13. `ItemBrand` cascade on `Item` deletion
- **Path:** `models/__init__.py:501` — `cascade="all, delete-orphan"`
- **What is wrong:** Deleting an Item cascades into `ItemBrand`. `Item.is_deleted` is the soft-delete column — cascade will fire only on hard `DELETE`. If admin UI ever does hard delete, the cascade is the second-worst case. Better: refuse hard delete when historical rows reference the item.
- **Fix:** Move from cascade to `passive_deletes=True` and add a `pre_delete` listener that checks for live references in branch_request_lines, warehouse_lines, etc.

### M14. `seed_supply_chain_demo.py` deactivates DEMO-* items on re-run
- **Path:** `backend/seed_supply_chain_demo.py:351-356`
- **What is wrong:** If item starts with `DEMO-`, `goc_item` flips `branch_requestable=False` and `visible_in_branch_ui=False` on re-run. This is intentional but undocumented behaviour: re-running the seed *hides* demo items. The seed report reports `(0 created)` and the user assumes the data is still there — but the UI hides the items.
- **Fix:** Either remove the deactivation block (idempotent should mean idempotent), or print a clear warning after seed: "DEMO-* items hidden from branch UI; seed only on a fresh DB."

---

## 🟢 LOW IMPROVEMENTS

- **L1.** `app/main.py:18` is one massive import line — unreadable. Split into multiple lines.
- **L2.** `app/main.py:181-202` startup wraps every auto-seed in `try/except Exception:` and logs — but if these crash the request thread, the app still starts. Consider a `startup_health` endpoint that surfaces the partial state.
- **L3.** No CI gate for the duplicate revision-id smell: two files in `alembic/versions/` start with `20260425_0021_n5o6p7q8r9s0_*` (one is `delivery_line_uniqueness`, one is `evaluation_core_phase1`). They have *different* revision ids but identical date+slot prefixes — extremely confusing for `alembic history`. Rename one to `20260425_0022_p6q7r8s9t0u1_evaluation_core_phase1.py`.
- **L4.** `BranchStock.in_transit_qty` is computed during dispatch but never decremented when an inter-branch transfer is cancelled (orders_service.cancel_order, line 831). Stale in_transit values accumulate.
- **L5.** `production_orders.py:283` raises `production_orders.destination_warehouse_missing` if `row.destination_branch.warehouse_id` is missing. But in `branch_request_split_service.py:52-58` the same check fires only for WAREHOUSE-source items. Make both paths consistent: a Branch with no warehouse should be flagged at branch-create time.
- **L6.** Idempotency keys in `supply_chain_idempotency_service` (referenced in routers) are not validated for size — a 10MB header could blow the audit table. Add `len(client_request_id) <= 128` validation.
- **L7.** `delivery-orders/.../labels` HTML template uses `escape(...)` correctly, but the inline CSS is a 10-line raw f-string — extract to a template.
- **L8.** `auth.py:12-46` `ROLE_PERMISSIONS` dict appears unused in code (search for `ROLE_PERMISSIONS` returns only this file). Remove or wire up.
- **L9.** Sentry init on every startup but `SENTRY_DSN` is not in `config.py`. Documented in code as "no-op if unset" — fine, but add `SENTRY_DSN` and `SENTRY_ENVIRONMENT` to `Settings`.
- **L10.** `auth.py:106` allows `operations_manager` global branch access; `inventory_service.py` and `orders.py` don't always include this role in their `require_roles` calls. Inconsistency.
- **L11.** `RouteRoleGuard` returns a `<div>` with a generic message — no logout link, no "request access" CTA. UX nit.
- **L12.** `start_scheduler` and `stop_scheduler` are imported from `scheduler_service` but the actual scheduler config (intervals, jobs) isn't visible. Re-verify there isn't a scheduler running document-reminder + replenishment in dev mode flooding the audit log (unverified — requires runtime).

---

## 🧠 Architecture risks

- **No policy/guard layer.** Authorization decisions are scattered across:
  - `core/auth.require_roles` (role gate)
  - `core/auth.can_access_branch` / `can_access_warehouse` (scope gate)
  - Per-router `_require_branch_write` / `_require_area_review` (subset of legalities)
  - Service layer scattered re-checks
  An explicit `policies/` module per resource (BranchRequestPolicy.can_approve, can_view, can_edit) backed by `pytest`-tested fixtures would prevent drift. Right now adding a new role means hitting at least 4 files.
- **Two parallel order workflows ship in production.** Old `replenishment_orders` (28 status transitions, draft → closed) AND new `branch_requests`/`warehouse_lines`/`delivery_orders` chain. They don't share line-status terminology; they don't share a ledger source-tag convention. This is two products inside one codebase.
- **`models/__init__.py` is 1595 lines, 60+ models in one file.** Should be split: `models/auth.py`, `models/master.py`, `models/inventory.py`, `models/orders.py`, `models/quality.py`, `models/sales_channels.py` etc. `sales_channels.py` already split — pattern exists.
- **Dual-purpose admin role.** `admin` is both "platform operator" and "tenant admin". The bypass behaviour is correct for one and dangerous for the other.

## 📊 Scalability risks

- **SQLite is the production DB unless someone manually sets DATABASE_URL.** Under load this is the binding constraint — busy_timeout=5000 means concurrent writes serialize, throughput ≤ ~50 writes/sec at best on the LAN trial.
- **Frontend bundles all pages eagerly.** `App.jsx:13-53` imports every page non-lazy. Bundle size grows linearly with feature count. Use `lazy()` (already imported but unused).
- **Audit log table grows unbounded.** `audit_logs` has no retention. After a year of demo runs the demo DB is bloated.
- **No DB connection pool tuning for Postgres production.** `database.py:11-12` sets pool_size=10, max_overflow=20 — fine for a single uvicorn worker but un-tuned for multi-worker uvicorn.
- **`scheduler_service` runs in-process.** `app/main.py:201` `start_scheduler(app)`. APScheduler in-process means N uvicorn workers = N copies of every scheduled job. Need either a leader-elect mechanism or a separate worker container.

## ⚠️ Data integrity risks

- See C1 (lock no-op), C3 (silent over-credit), C4 (stuck production), H4 (FK-not-snapshot), H5 (race → 500), H6 (nullable unique).
- **Idempotency table cleanup runs every hour** (`config.py:52`, `main.py:78-87`). Default TTL=1 day. If a client retries a request older than 24h, it gets re-executed.
- **`StockTransaction` has no `tenant_id`.** `DEFAULT_TENANT_ID=1` — a multi-tenant rollout cannot scope stock movements.

## 🔐 Security risks

- See C2 (admin bypass), H7 (memory blow), H8 (volatile uploads), H9 (mime spoof), H10 (frontend mirror), M10 (localStorage token).
- **No CSRF protection.** All state-changing endpoints rely on Bearer token in `Authorization` header. Fine if no cookie auth — but `frontend/src/App.jsx` routes `*.html` files via the same FastAPI handler, so any future "login session cookie" introduction will need CSRF.
- **CORS allows credentials.** `main.py:64` `allow_credentials=True` paired with default `localhost` origins. In production with `ALLOWED_ORIGINS` set narrowly, this is OK.
- **Rate limit on login is 20/minute (`config.py:46`).** With 1000 employees that's tight. With brute-force focus that's loose. Add `1000/hour` AND `5/minute` as a layered limit.
- **`reset_password.py`, `reset_admin_password.bat`, `repurpose_demo_accounts.py` ship in repo.** Production should never have these scripts on the server. Move to `scripts/dev/`.
- **No audit on auth failures.** `authenticate_user` returns None silently on bad password. No "5 failed logins, lock account" mechanism.

## 🎯 UX / Operational risks

- **5 supply-chain pages exist in one file.** `frontend/src/pages/supply_chain/SupplyChainPages.jsx` (887 lines) — fine for now but a monolithic risk.
- **Demo PASSWORD = `Raed@2025` baked into seed scripts** (`seed_supply_chain_demo.py:70`). Demo accounts on a publicly-exposed Railway are an instant compromise. Add a banner: "demo mode — change passwords before any real data."
- **No DB backup script ships in `backend/`.** Phase 7D claims to have added one — verify in `backend/scripts/`. (unverified — file not read)
- **`BranchRequest.request_no` is `BR-{id:06d}`** (`branch_requests.py:371`) — fine for sequential IDs, but multi-tenant collisions occur (tenant 1's BR-000001 == tenant 2's BR-000001). Add tenant prefix.
- **No alerting hooks for backorders, partial deliveries, etc.** The "BACKORDER" warehouse-line state exists but nothing notifies anyone.

---

## Demo environment status

- **Seed users working: Y** —
  `backend/seed_supply_chain_demo.py:219-247` `goc_user` is fully idempotent; updates email/full_name and resets password every run. 13 demo accounts (admin, super.admin, am_riyadh, am_dammam_cafes, am_dammam_restaurants, branch.mgr1, branch.user1, meat.section.mgr, bakery.section.mgr, pizza.section.mgr, wh.mgr1, wh.user1, delivery.user) all created with PASSWORD `Raed@2025`.

- **Items loaded: PARTIAL** —
  `classified_supply_items.xlsx` is **NOT in the repo**. `import_classified_supply_items.py:14` hardcodes `C:\Users\islam\Downloads\classified_supply_items.xlsx`. The import service `supply_item_master_import_service.py` is correctly written: validates source/default rules, brand-targets (General → 4 brands, Shared → 3 brands), upserts via deterministic `_item_code` hash, logs invalid rows to `uploads/import_logs/classified_supply_items_invalid_rows.json` (file present in repo: `backend/uploads/import_logs/classified_supply_items_invalid_rows.json`). However ground-truth cross-check vs the workbook itself was not possible because the workbook is not committed. In its place the demo seed creates 12 deterministic DEMO-* items across the 4 brands × 3 source types (WAREHOUSE, KITCHEN, BOTH) — sufficient for a full E2E demo but NOT representative of the official item master.
  **Recommendation:** Commit `classified_supply_items.xlsx` to a `data/` directory or document the expected workbook schema in a sibling `.md` so external auditors can verify item-master correctness without your local Downloads folder.

- **End-to-end runnable: PARTIAL Y** — Verified by static read of router code:
  - `branch.user1` → POST `/api/v1/branch-requests`: ✅ `branch_requests.py:332`
  - submit: ✅ `branch_requests.py:446`
  - `am_riyadh` → POST `/approve`: ✅ `branch_requests.py:483` (auto-splits via `_split_request_service`)
  - kitchen `meat.section.mgr` → start/mark-ready/send-to-warehouse: ✅ `production_orders.py:129-340`
  - `wh.user1` → issue / partial-issue: ✅ `warehouse_lines.py:155-236`
  - warehouse → POST `/api/v1/delivery-orders`: ✅ `delivery_orders.py:161`
  - `delivery.user` → out-for-delivery + deliver: ✅ `delivery_orders.py:246-341`

  **Failure points:**
  - C3: deliver step cannot record partial; whatever the driver actually delivered, the system records full.
  - C4: if kitchen hits "request materials" the flow stops permanently.
  - H7/H8: photos uploaded during the flow lost on next Railway redeploy.

---

## v1 → v2 delta

**Fixed since v1:**
| v1 # | v1 issue | Status now |
| --- | --- | --- |
| 2 | Split doesn't write reserved_qty | ✅ Fixed: `branch_request_split_service.py:77` writes `stock.reserved_qty += qty` and creates the row if missing |
| 9 | Procurement missing | ⚠️ Partially: skeleton router exists (90 LoC), still no PO/Receipt/Invoice |
| 10 | No frontend route-level RBAC | ✅ Fixed: `RouteRoleGuard` ships and is wired across most routes (`App.jsx:1310-1421`) |
| (n/a) | area_manager regional scope by AreaManagerAssignment | ✅ Fixed: supply-chain path uses `_area_scope_filter` joined to `AreaManagerAssignment` (city + brand + active + ended_at) |
| (n/a) | Item master import is idempotent + logs invalid rows | ✅ New: `supply_item_master_import_service.py` with rejected-rows JSON log |
| (n/a) | sales_channels Pack C tables + service | ✅ New: 5 tables + service layer per Pack C migration |
| (n/a) | Auto-split on approve / modify-and-approve | ✅ New: `branch_requests.py:528, 608` calls `_split_request_service` immediately |

**Still broken from v1:**
| v1 # | v1 issue | Reason it still ships |
| --- | --- | --- |
| 1 | `_deduct_stock` no row-lock | Locking added but SQLite makes it a no-op (C1) |
| 3 | SQLite + with_for_update is no-op | Still SQLite default (C1) |
| 4 | Central admin-bypass leaks scope checks | Still in `require_roles` (C2) |
| 5 | Approve race → 500 not 409 | Still 500 on IntegrityError (H5) |
| 6 | WarehouseLine unique key only convention | UniqueConstraint added but on nullable column (H6) |
| 7 | Delivery dispatch no lock on BranchStock | `BranchStock` is now locked in deliver_order (`delivery_orders.py:306-311`) ✅ but `production_orders.send_to_warehouse` still doesn't lock WarehouseStock (H1) |
| 8 | Dynamic FKs not snapshots | Snapshots only on BranchRequest/Line; rest still live FK (H4) |

**Net delta:** Solid progress on the supply-chain V1 phase 1+2+3 plumbing, the area-manager RBAC, the item-master import. The concurrency story is unchanged because the DB choice is unchanged. The admin-bypass is unchanged.

---

## Roadmap to production-ready

### Phase 1 — Block production deploys (1–2 days)
1. **Hard-fail SQLite in production AND staging** (`config.py:110`) — already enforces production; extend.
2. **Switch demo to Postgres in Docker Compose for the LAN trial** — write `docker-compose.lan.yml` with Postgres 15 + the backend.
3. **Replace admin-bypass in `require_roles`** — opt-in via `"*"` (C2 fix).
4. **Frontend: `RouteRoleGuard` only elevates `super_admin`** (H10 fix).
5. **Add IntegrityError handler in `main.py`** that returns 409 (H5 fix).

Effort: ~12 hours.

### Phase 2 — Make the supply chain trustworthy (3–5 days)
1. **Implement partial-delivery in `deliver_order`** (C3 fix). Schema + service + tests.
2. **Wire kitchen-material-request approve/issue/reject flow** (C4 fix). 3 endpoints + WarehouseLine of new source_type + ledger.
3. **Add `lock_row` to `production_orders.send_to_warehouse` WarehouseStock query** (H1 fix).
4. **Add item snapshots to `DeliveryOrderLine`, `ProductionOrder`, `KitchenMaterialRequest`, `ReplenishmentOrderLine`, `StockTransaction`** with a back-fill migration (H4 fix).
5. **Audit-log the `receive_order` and `delivery_labels` paths properly** (M2, H2 fix).

Effort: 4 days.

### Phase 3 — Storage + uploads (2 days)
1. **Streaming uploads with size guard** (H7 fix).
2. **Persistent storage abstraction + Railway volume mount** (H8 fix).
3. **MIME sniffing with `python-magic` or `filetype`** (H9 fix).

Effort: 2 days.

### Phase 4 — Procurement reality (5–8 days)
Either ship full PO/Receipt/Invoice flow OR remove the procurement nav until v2. Decision required.

### Phase 5 — Multi-tenant readiness (2 weeks, deferred)
- Tenant-prefixed `request_no`, `order_no`, etc.
- Row-level tenant filter middleware (the `TenantMiddleware` exists; verify it actually filters).
- Region table replacing free-text city/area.

### Phase 6 — Observability (2 days)
- Wire SENTRY_DSN to Settings.
- Persistent audit-log retention (90-day rolling).
- Liveness + readiness probes that fail when migrations are behind.
- Per-endpoint latency dashboards via `X-Process-Time` header (already emitted; just chart it).

---

## Methodology notes

**Deeply audited (read end-to-end):**
- `backend/app/core/auth.py` (RBAC contract, area_manager regional fallback)
- `backend/app/core/locking.py` (SQLite no-op confirmation)
- `backend/app/database.py` + `backend/app/config.py` (DATABASE_URL default + production guard)
- `backend/app/main.py` (boot order, exception handlers, route registration)
- `backend/app/services/branch_request_split_service.py` (v1 fix verified real)
- `backend/app/routers/branch_requests.py` (request lifecycle, auto-split path, approve race)
- `backend/app/routers/warehouse_lines.py` (issue / partial-issue / delay-reason; lock posture)
- `backend/app/routers/delivery_orders.py` (create, OUT_FOR_DELIVERY, deliver, labels — partial-delivery gap confirmed)
- `backend/app/routers/production_orders.py` (start, mark-ready, send-to-warehouse, request-materials gap confirmed)
- `backend/app/routers/procurement.py` (skeleton confirmed)
- `backend/app/routers/auth.py` (login + me + change_password)
- `backend/app/services/inventory_service.py` (approve flow, lock posture)
- `backend/app/services/orders_service.py` (full lifecycle dispatch + receive)
- `backend/app/services/supply_item_master_import_service.py` (item-master import contract)
- `backend/app/services/document_service.py` upload portion + `quality_service.py` upload portion
- `backend/seed_supply_chain_demo.py` (idempotency confirmed)
- `backend/app/models/__init__.py` (selected sections; 1595 LoC scanned in regions)
- `frontend/src/App.jsx` (route table)
- `frontend/src/services/api.js` (API surface, fallback base, 401 handling)
- `frontend/src/components/common/RouteRoleGuard.jsx` (admin elevation)

**Surface-level (sampled, not exhaustive):**
- Alembic migration sequence (29 files; merge head at 0023 confirmed; no orphaned heads)
- Test directory inventory (24 test files; phase 2/3 supply-chain coverage limited to phase1 file)
- `app/routers/notifications.py`, `dashboard.py`, `evaluations.py`, `quality.py` (only spot-checked for upload patterns)
- Frontend pages other than Supply Chain (only file sizes / route guards verified, content not read)

**Requires runtime to verify:**
- Concurrent approve test on Postgres (would exercise C1, H5)
- Streaming upload of >10MB to confirm H7 actually OOMs vs gets caught
- `notifications.py` per-role scoping (M11 placeholder)
- `scheduler_service` job inventory + per-worker behaviour
- pytest baseline (sandbox here cannot run uvicorn/pytest; the v1 baseline of 13 known failures is the latest known state)
- whether the Vite build under `frontend/dist` actually contains the latest pages (multiple stale logs in repo: `vite.demo.err.log`, `vite.demo.out.log`)
- `classified_supply_items.xlsx` ground-truth comparison (workbook not in repo)

**Not audited (out of scope or v1-detailed already):**
- Quality/evaluation/training detailed business logic — covered in v1 audit, no major changes since
- Sales Channels Pack C — only confirmed migration + service exist; spec verification deferred
- Documents reminder scheduler — out of supply-chain critical path
- Inter-branch transfer router — Phase A complete per task list, not re-verified
