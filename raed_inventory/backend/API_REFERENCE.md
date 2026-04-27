# Raed Inventory System — API Reference
**Version:** 1.0.0 | **Base URL:** `/api/v1` | **Auth:** Bearer JWT

---

## Authentication — `/api/v1/auth`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| POST | `/token` | Login → returns `access_token` | Public |
| POST | `/logout` | Invalidate token | Any |

---

## Users — `/api/v1/users`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/me` | Current user profile | Any |
| POST | `/me/change-password` | Self-service password change | Any |
| GET | `/roles` | List all system roles | Any |
| GET | `/` | List users (paginated) | admin, super_admin |
| POST | `/` | Create user | admin, super_admin |
| GET | `/{user_id}` | Get user by ID | admin, super_admin |
| PUT | `/{user_id}` | Update user | admin, super_admin |
| DELETE | `/{user_id}` | Soft-delete user | super_admin |
| POST | `/{user_id}/reset-password` | Admin reset password | admin, super_admin |

---

## Master Data — `/api/v1/master`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/items` | List items (filter: item_type, storage_type, search) | Any |
| POST | `/items` | Create item | admin+ |
| GET | `/items/{id}` | Get item | Any |
| PUT | `/items/{id}` | Update item | admin+ |
| POST | `/items/{id}/stock/branch/{bid}` | Initialize branch stock | admin+ |
| POST | `/items/{id}/stock/warehouse/{wid}` | Initialize warehouse stock | admin+ |
| GET | `/categories` | List categories | Any |
| POST | `/categories` | Create category | admin+ |
| GET | `/categories/{id}` | Get category | Any |
| PUT | `/categories/{id}` | Update category | admin+ |
| DELETE | `/categories/{id}` | Delete category (guard: no active items) | admin+ |
| GET | `/units` | List units | Any |
| POST | `/units` | Create unit | admin+ |
| PUT | `/units/{id}` | Update unit | admin+ |
| DELETE | `/units/{id}` | Delete unit (guard) | admin+ |
| GET | `/branches` | List branches | Any |
| GET | `/branches/{id}` | Get branch | Any |
| GET | `/branches/{id}/stock` | Branch stock list | Any |
| GET | `/warehouses` | List warehouses | Any |
| GET | `/warehouses/{id}` | Get warehouse | Any |
| GET | `/warehouses/{id}/stock` | Warehouse stock list | Any |
| GET | `/variance-reasons` | List inventory variance reasons | Any |
| POST | `/variance-reasons` | Create reason | admin+ |
| PUT | `/variance-reasons/{id}` | Update | admin+ |
| DELETE | `/variance-reasons/{id}` | Delete | admin+ |
| GET | `/receiving-variance-reasons` | List receiving variance reasons | Any |
| POST | `/receiving-variance-reasons` | Create | admin+ |
| PUT | `/receiving-variance-reasons/{id}` | Update | admin+ |
| DELETE | `/receiving-variance-reasons/{id}` | Delete | admin+ |

---

## Daily Inventory — `/api/v1/inventory`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/today` | Today's status per branch | Any |
| GET | `/` | List inventories (paginated) | Any |
| POST | `/` (**201**) | Create inventory | branch+ |
| GET | `/{id}` | Get inventory detail | Any |
| PATCH | `/{id}/lines/{line_id}` | Update single line (counted_qty, reason) | branch+ |
| POST | `/{id}/submit` | Submit (idempotent via X-Client-Request-Id) | branch+ |
| POST | `/{id}/approve` | Approve inventory | manager+ |
| POST | `/{id}/reject` | Reject with reason | manager+ |
| POST | `/{id}/reopen` | Reopen rejected → draft | branch+ |
| DELETE | `/{id}` | Delete DRAFT inventory | branch+ |
| POST | `/{id}/trigger-replenishment` (**201**) | Generate auto-replenishment order | manager+ |
| GET | `/branches/{bid}/replenishment-preview` | Dry-run replenishment calculation | manager+ |

---

## Replenishment Orders — `/api/v1/orders`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/` | List orders (filter: branch, warehouse, status, date) | Role-scoped |
| GET | `/{id}` | Get order detail | Role-scoped |
| POST | `/exceptional` (**201**) | Create exceptional order | branch+ |
| GET | `/{id}/timeline` | Status transition history | Any |
| POST | `/{id}/branch-review` | Branch adjusts quantities | branch+ |
| POST | `/{id}/submit-to-warehouse` | Submit to warehouse | branch_manager+ |
| POST | `/{id}/warehouse-review` | Warehouse reviews quantities | warehouse+ |
| POST | `/{id}/approve` | Warehouse approves (idempotent) | warehouse_manager+ |
| POST | `/{id}/reject` | Warehouse rejects (idempotent) | warehouse_manager+ |
| POST | `/{id}/start-picking` | Begin warehouse picking (idempotent) | warehouse+ |
| POST | `/{id}/dispatch` | Dispatch items (idempotent) | warehouse+ |
| POST | `/{id}/receive` | Branch confirms receipt (idempotent) | branch+ |
| POST | `/{id}/cancel` | Cancel order with reason (idempotent) | branch/warehouse/admin |
| POST | `/{id}/close` | Manually close order | manager+ |
| GET | `/{id}/pick-list` | Warehouse pick list | warehouse+ |

---

## Stock Adjustments & Transfers — `/api/v1/stock`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| POST | `/branches/{bid}/adjust` | Manual branch stock adjustment (increase/decrease/set) | branch+ |
| POST | `/warehouses/{wid}/adjust` | Manual warehouse stock adjustment | warehouse+ |
| POST | `/transfer/warehouse-to-branch` | Transfer WH→Branch (no order) | manager+ |
| POST | `/transfer/branch-to-warehouse` | Return Branch→WH | manager+ |

**Adjustment types:** `increase` \| `decrease` \| `set`

---

## Ledger & Reports — `/api/v1/ledger`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/branches/{bid}` | Stock transaction ledger for branch | Any |
| GET | `/warehouses/{wid}` | Stock transaction ledger for warehouse | Any |
| GET | `/variance-report` | Approved inventory lines with variance | Any |
| GET | `/low-stock` | Items at or below reorder point | Any |

---

## Reports — `/api/v1/reports`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/inventory-compliance` | Per-branch per-day compliance grid (max 90 days) | manager+ |
| GET | `/order-summary` | Orders grouped by status | manager+ |
| GET | `/variance-trend` | Avg variance % per branch over time | manager+ |

---

## Alerts — `/api/v1/alerts`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/low-stock` | Stock below reorder point (branch-scoped for branch users) | Any |
| GET | `/overdue-orders` | Orders stalled > N hours (default 48h) | manager+ |
| GET | `/pending-inventories` | Inventories waiting approval | manager+ |
| GET | `/missing-inventory-today` | Branches that haven't started today's inventory | manager+ |

---

## Data Export — `/api/v1/export`

All export endpoints support `?format=csv` (default) or `?format=xlsx`.

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/inventory-compliance` | Export compliance grid | manager+ |
| GET | `/variance-report` | Export variance data | manager+ |
| GET | `/order-summary` | Export orders | manager+ |
| GET | `/stock/branches/{bid}` | Export branch stock snapshot | manager+ |
| GET | `/stock/warehouses/{wid}` | Export warehouse stock snapshot | manager+ |
| GET | `/ledger/branches/{bid}` | Export branch ledger | manager+ |

---

## Dashboard — `/api/v1/dashboard`

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/global` | Platform-wide KPIs | admin+ |
| GET | `/alerts-summary` | Combined alert counts (for badges) | admin+ |
| GET | `/branch/{bid}` | Branch dashboard | branch+ |
| GET | `/branch/{bid}/trend` | Branch trend (N days) | branch+ |
| GET | `/warehouse/{wid}` | Warehouse dashboard | warehouse+ |
| GET | `/operations` | Operations manager dashboard | ops_manager+ |
| GET | `/stock/branch/{bid}` | Branch stock status | branch+ |
| GET | `/stock/warehouse/{wid}` | Warehouse stock status | warehouse+ |

---

## System — `/api/v1`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/meta` | App name/version/environment |

---

## Common Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | int ≥ 1 | Page number (default: 1) |
| `page_size` | int 1–100 | Items per page (default: 20) |
| `date_from` | date (YYYY-MM-DD) | Start of date range |
| `date_to` | date (YYYY-MM-DD) | End of date range |
| `branch_id` | int | Filter by branch |
| `warehouse_id` | int | Filter by warehouse |

## Headers

| Header | Description |
|--------|-------------|
| `Authorization: Bearer <token>` | JWT auth (required on all endpoints except login) |
| `X-Client-Request-Id` | Idempotency key for submit/approve/dispatch/receive/cancel/close |
| `X-Tenant-ID` | Tenant identifier (reserved; single-tenant mode: ignored) |

## Standard Error Format

```json
{
  "error_code": "orders.not_found",
  "message": "Order not found",
  "detail": {"order_id": 42}
}
```

## Idempotency
Send `X-Client-Request-Id: <uuid>` on state-changing endpoints.
- First call: processes the operation.
- Duplicate call (same ID): replays the original response without re-processing.
- Supported on: `submit`, `approve`, `reject`, `start-picking`, `dispatch`, `receive`, `cancel`, `close`, `submit-inventory`.

---

*Generated: 2026-04-16 | Epics 1-13 complete*

## Audit Log — `/api/v1/audit`

Admin / super_admin only.

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/logs` | Paginated audit log with filters | admin+ |
| GET | `/entity/{entity_type}/{entity_id}` | Full history of a single entity | admin+ |
| GET | `/modules` | Distinct module names (for filter UI) | admin+ |
| GET | `/actions` | Distinct action names, optionally filtered by module | admin+ |

**Query params for `/logs`:** `entity_type`, `entity_id`, `module`, `action`, `user_id`, `date_from`, `date_to`, `page`, `page_size`

**Audited actions:** `approve`, `reject`, `cancel` on orders and inventory; `import` on items/stock.

---

## Data Import — `/api/v1/import`

Upload CSV or XLSX to bulk-create or update records.

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/templates/{name}` | Download blank CSV template | admin+ |
| POST | `/items` | Create / update items from file | admin+ |
| POST | `/branch-stock` | Set branch stock quantities from file | admin+ |
| POST | `/warehouse-stock` | Set warehouse stock quantities from file | admin+ |

**Template names:** `items` \| `branch-stock` \| `warehouse-stock`

**Accepted formats:** `.csv` (UTF-8) or `.xlsx`

**Response format:**
```json
{
  "created": 12,
  "updated": 3,
  "total_errors": 1,
  "errors": [
    { "row": 5, "item_code": "ITM-009", "error": "category_code 'UNKNOWN' not found" }
  ]
}
```

**Items template columns:**
`item_code`, `item_name_ar`, `item_name_en`, `category_code`, `unit_code`,
`min_qty`, `max_qty`, `reorder_point`, `active` (optional)

**Branch/Warehouse stock template columns:**
`branch_code` / `warehouse_code`, `item_code`, `qty`

---
