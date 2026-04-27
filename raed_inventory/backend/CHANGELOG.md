# Changelog — Raed Inventory System

All notable changes are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [1.0.0] — 2026-04-16

### Epic 1 — Foundation
- FastAPI application scaffold with SQLAlchemy + Alembic
- JWT authentication (`/api/v1/auth/login`, `/me`, `/change-password`)
- Role-based access control: super_admin, admin, branch_manager, branch_user, warehouse_manager, warehouse_user
- Idempotency service: `(tenant_id, client_request_id, operation_name)` unique contract
- AppError standard error model: `{error_code, message, detail}`
- Structured logging via `logging_config.py`
- Baseline Alembic migration (`a1b2c3d4e5f6`)

### Epic 2 — Master Data
- Items CRUD with categories, units, storage types
- Branches and warehouses management (soft-delete pattern)
- Branch stock and warehouse stock initialization
- Inventory variance reasons and receiving variance reasons
- `GET /api/v1/master/*` endpoints

### Epic 3 — Daily Inventory Workflow
- `DailyInventory` lifecycle: draft → submitted → approved/rejected
- Per-line counted_qty updates with variance calculation
- Inventory approval triggers stock ledger `inventory_adjustment` transactions
- Idempotent submit (`X-Client-Request-Id`)
- `InventoryStatus` enum: draft, submitted, pending_approval, approved, rejected
- Migration: `a1b2c3d4e5f6` (baseline)

### Epic 4 — Order Management Enhancements
- `cancel_order`: role-based cancellable statuses, requires reason, idempotent
- `close_order`: manually close received/dispatched orders
- `get_order_timeline`: chronological event list from timestamp columns
- `OrderStatus.cancelled` added
- `cancelled_at`, `cancelled_by`, `cancellation_reason` columns added
- Migration: `b2c3d4e5f6a7`

### Epic 5 — Stock Adjustments & Transfers
- `POST /api/v1/stock/branches/{bid}/adjust` — increase/decrease/set with ledger post
- `POST /api/v1/stock/warehouses/{wid}/adjust` — same for warehouse
- `POST /api/v1/stock/transfer/warehouse-to-branch` — checks sufficient stock
- `POST /api/v1/stock/transfer/branch-to-warehouse` — return to warehouse
- `TransactionType.adjustment_in` and `adjustment_out` added
- Migration: `d4e5f6a7b8c9`

### Epic 6 — Ledger & Reports
- `GET /api/v1/ledger/branches/{bid}` — full stock transaction history
- `GET /api/v1/ledger/warehouses/{wid}` — warehouse ledger
- `GET /api/v1/ledger/variance-report` — approved inventory variance lines
- `GET /api/v1/ledger/low-stock` — items at/below reorder point

### Epic 7 — User Management
- `GET /api/v1/users/me` — current user profile
- `POST /api/v1/users/me/change-password` — self-service password change
- `GET /api/v1/users/roles` — list all system roles

### Epic 8 — Reports
- `GET /api/v1/reports/inventory-compliance` — per-branch per-day grid (max 90 days)
- `GET /api/v1/reports/order-summary` — counts grouped by status
- `GET /api/v1/reports/variance-trend` — avg variance % per branch over time

### Epic 9 — Alerts
- `GET /api/v1/alerts/low-stock` — branch-scoped for branch users
- `GET /api/v1/alerts/overdue-orders` — stalled orders > N hours
- `GET /api/v1/alerts/pending-inventories` — awaiting approval
- `GET /api/v1/alerts/missing-inventory-today` — branches with no inventory today

### Epic 10 — Replenishment Enhancements
- `POST /api/v1/inventory/{id}/trigger-replenishment` — idempotent auto-order generation
- `GET /api/v1/inventory/branches/{bid}/replenishment-preview` — dry-run calculation
- `preview_replenishment_order` service function

### Epic 11 — Dashboard
- `GET /api/v1/dashboard/global` — platform-wide KPIs
- `GET /api/v1/dashboard/branch/{bid}/trend` — per-day trend (N days)
- `GET /api/v1/dashboard/alerts-summary` — combined badge counts

### Epic 12 — Data Export
- `GET /api/v1/export/*` — 6 endpoints supporting `?format=csv|xlsx`
- openpyxl integration with bold headers and auto-width columns
- Graceful CSV fallback if openpyxl not installed

### Epic 13 — Multi-Tenant Foundation
- `TenantMiddleware` — reads `X-Tenant-ID` header, pass-through in single-tenant mode
- `get_current_tenant_id()` context variable
- `MULTI_TENANT_ENABLED` config flag (default: False)
- `tenant_id` column added to 8 business tables (nullable, server_default=1)
- Migration: `c3d4e5f6a7b8`

### Epic 14 — Audit Log
- `GET /api/v1/audit/logs` — paginated audit trail with filters
- `GET /api/v1/audit/entity/{type}/{id}` — full history of one entity
- `GET /api/v1/audit/modules` and `/actions` — for filter UI
- Audit writes wired into: inventory approve/reject, order approve/reject/cancel, stock import
- Savepoint pattern ensures audit failure never rolls back caller's transaction

### Epic 15 — Data Import
- `GET /api/v1/import/templates/{name}` — download blank CSV template
- `POST /api/v1/import/items` — bulk create/update items from CSV or XLSX
- `POST /api/v1/import/branch-stock` — set branch stock quantities
- `POST /api/v1/import/warehouse-stock` — set warehouse stock quantities
- Per-row error reporting: `{created, updated, total_errors, errors[{row, error}]}`

### Infrastructure
- `docker-compose.yml` — PostgreSQL + FastAPI + pgAdmin (dev profile)
- `docker-compose.prod.yml` — production overrides (4 workers, no volumes, tighter rate limits)
- `Dockerfile` — HEALTHCHECK + `alembic upgrade head` before startup
- `slowapi` rate limiting (200/min default, 10-20/min on login)
- `tests/conftest.py` + `pytest.ini` — shared test fixtures and configuration
- `.gitignore` — excludes secrets, databases, pycache, IDEs
- `API_REFERENCE.md` — full endpoint documentation (75+ endpoints)

---

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| 1.0.0 | 2026-04-16 | All 15 Epics complete |
