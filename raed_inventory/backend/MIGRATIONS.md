# Database Migrations — Raed Inventory System

## Overview

All schema changes are managed with **Alembic**.  
`Base.metadata.create_all()` is **never** used to evolve a production or staging schema.

---

## Environment Setup

Alembic reads the database URL from `app.config.settings.DATABASE_URL`, which is
loaded from the `ENV_FILE` environment variable (default: `.env`).

```bash
# Local development (SQLite)
export ENV_FILE=.env.local

# Staging
export ENV_FILE=.env.staging

# Production
export ENV_FILE=.env.production
```

> Important:
> `staging` and `production` must use PostgreSQL. The application now fails fast
> on startup if `ENVIRONMENT` is `staging` or `production` while `DATABASE_URL`
> still points to SQLite.

---

## First-Time Setup for an Existing Database

If your database tables were already created with `Base.metadata.create_all()`
(before Alembic was introduced), **do not run `upgrade head`**.
Stamp the database to tell Alembic it is already at the baseline:

```bash
export ENV_FILE=.env.local
alembic stamp a1b2c3d4e5f6   # baseline revision ID
```

For a **fresh** database (empty), just run:

```bash
alembic upgrade head
```

For PostgreSQL rollout guidance, see:

- `POSTGRESQL_READINESS.md`

---

## Day-to-Day Workflow

1. Make model changes in `app/models/__init__.py`
2. Generate migration: `alembic revision --autogenerate -m "short description"`
3. Review the generated file in `alembic/versions/`
4. Apply locally: `alembic upgrade head`
5. Test downgrade: `alembic downgrade -1` → `alembic upgrade head`
6. Commit the migration file with your feature branch

> Autogenerate does **not** detect: renamed tables/columns, stored procedures, or enum renames in PostgreSQL.

---

## Common Commands

| Command | What it does |
|---|---|
| `alembic current` | Show which revision the DB is at |
| `alembic history --verbose` | Show full migration history |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic upgrade +1` | Apply exactly one migration forward |
| `alembic downgrade -1` | Roll back one migration |
| `alembic downgrade base` | Roll back all migrations (empty DB) |
| `alembic stamp <rev>` | Mark DB as at revision without running SQL |
| `alembic show <rev>` | Show details of a specific revision |

---

## Naming Convention

```
YYYYMMDD_NNNN_<revid>_<slug>.py
```

Example: `20260416_0002_c3d4e5f6a7b8_multi_tenant_phase2_add_tenant_id.py`

Keep slugs short and descriptive: `add_tenant_id_to_items`, `create_audit_logs_table`, `drop_legacy_flag`.

---

## Migration Chain

```
a1b2c3d4e5f6  ─  baseline: initial schema
                  All core tables: users, roles, warehouses, branches, items,
                  categories, units, branch_stock, warehouse_stock,
                  daily_inventory, replenishment_orders, stock_transactions,
                  audit_logs, idempotency_requests, system_settings, etc.
      │
      ▼
b2c3d4e5f6a7  ─  add order cancellation fields
                  + cancelled_at, cancelled_by, cancellation_reason → replenishment_orders
                  + "cancelled" value → orderstatus enum (PostgreSQL)
      │
      ▼
c3d4e5f6a7b8  ─  multi-tenant phase 2: add tenant_id
                  + nullable tenant_id (server_default=1) → 8 business tables
                    (warehouses, branches, items, branch_stock, warehouse_stock,
                     daily_inventory, replenishment_orders, stock_transactions)
                  + backfill all existing rows: tenant_id = 1
                  + idx_{table}_tenant_id indexes
      │
      ▼
d4e5f6a7b8c9  ─  add new enum values  ← current HEAD
                  + "pending_approval" → inventorystatus
                  + "adjustment_in", "adjustment_out" → transactiontype
```

> **Note:** `audit_logs` was part of the baseline schema (`a1b2c3d4e5f6`) from day one.
> No separate migration is needed for it.

---

## Tenant ID Migration Plan

`tenant_id` was added in migration `c3d4e5f6a7b8` as **nullable with default 1**.
Full 5-phase hardening plan:

| Phase | Status | Description |
|---|---|---|
| 1 — Add nullable `tenant_id` | ✅ Done | Added to 8 tables, indexed |
| 2 — Backfill existing rows | ✅ Done | All rows → tenant_id = 1 |
| 3 — Add indexes | ✅ Done | `idx_{table}_tenant_id` on each table |
| 4 — Add composite unique constraints | ⏳ Pending | e.g. `(tenant_id, branch_code)` UNIQUE |
| 5 — Make `tenant_id` NOT NULL | ⏳ Pending | Only after `MULTI_TENANT_ENABLED=True` |

Full details: `TENANT_ID_MIGRATION_PLAN.md`

---

## Rules

1. **One migration per logical change.** Do not bundle unrelated schema changes.
2. **Always write a working `downgrade()`.**
3. **Never edit a migration applied to staging/production.** Write a new one instead.
4. **Never delete migration files.** They are the audit trail.
5. **Test upgrade + downgrade before merging.**
6. **Coordinate with the team** before running destructive migrations on staging/production.

---

## CI / Deployment

- `alembic upgrade head` runs automatically before the app starts.
- A failed migration aborts the deploy.
- Rollback: `alembic downgrade -1`, then re-deploy the previous image.
