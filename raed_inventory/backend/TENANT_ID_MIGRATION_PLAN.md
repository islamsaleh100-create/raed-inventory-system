# Tenant ID Migration Plan

## Goal
Introduce `tenant_id` early enough to avoid painful schema drift when `Epic 2` and later modules add new tables.

## Guiding Rule
- Any new business table created from this point forward must decide on `tenant_id` explicitly.
- Default decision: add `tenant_id` unless the table is purely static reference data shared by all tenants.

## Phase 1: Foundation Now
- Keep `DEFAULT_TENANT_ID=1` in configuration for single-tenant runtime compatibility.
- Use tenant-aware idempotency keys now:
  - `(tenant_id, client_request_id, operation_name)`
- Document tenant policy before adding new tables in `Epic 2`.

## Phase 2: Existing Table Classification
Before the first `Epic 2` migration, classify existing tables into three groups:

### A. Business Tables: add `tenant_id`
- `users`
- `branches`
- `warehouses`
- `items`
- `branch_stock`
- `warehouse_stock`
- `daily_inventory`
- `daily_inventory_lines`
- `replenishment_orders`
- `replenishment_order_lines`
- `stock_transactions`
- `audit_logs`
- `idempotency_requests`

### B. Shared Reference Tables: evaluate carefully
- `roles`
- `item_categories`
- `units`
- `inventory_variance_reasons`
- `receiving_variance_reasons`

Default for this group:
- keep shared only if business rules truly allow cross-tenant reuse
- otherwise clone into tenant-scoped reference data later

### C. System Tables: no `tenant_id` unless needed
- migration metadata
- internal scheduler/process tables

## Phase 3: Migration Order
Apply tenant support in this order:
1. Add nullable `tenant_id` columns to core business tables
2. Backfill all existing rows with `tenant_id = 1`
3. Add indexes involving `tenant_id`
4. Add composite uniqueness where needed
5. Switch application queries/services to tenant-aware filters
6. Make `tenant_id` non-nullable after backfill and query rollout

## Phase 4: Query Rules
- Any lookup for business entities must become tenant-scoped before multi-tenant rollout.
- Do not rely on `id` alone once tenant rollout starts.
- Favor patterns such as:
  - `tenant_id + id`
  - `tenant_id + business_key`

## Phase 5: Uniqueness Strategy
When a table has unique business identifiers, convert uniqueness to tenant-scoped uniqueness.

Examples:
- item code:
  - from `UNIQUE(item_code)`
  - to `UNIQUE(tenant_id, item_code)`
- branch code:
  - from `UNIQUE(branch_code)`
  - to `UNIQUE(tenant_id, branch_code)`

## Phase 6: Application Rollout Rules
- `Epic 2` migrations must not introduce new business tables without deciding tenant scope.
- New services should accept tenant context indirectly through current runtime configuration now, and explicit tenant context later.
- Avoid hard-coding single-tenant assumptions into new APIs or uniqueness constraints.

## Definition of Done Before Opening Full SaaS Work
- all core business tables have `tenant_id`
- all business uniqueness rules are tenant-scoped
- all business queries enforce tenant filtering
- seeds support tenant bootstrap
- tests include tenant isolation coverage
