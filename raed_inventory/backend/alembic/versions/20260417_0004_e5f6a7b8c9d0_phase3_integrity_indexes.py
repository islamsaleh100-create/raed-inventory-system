"""Phase 3: Integrity constraints + performance indexes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-17 00:04:00

Additions:
1. CHECK constraints: stock quantities must be >= 0
2. Performance indexes on hot FK columns (users, orders, inventory, transactions, audit)
3. Helpful composite indexes for common queries
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def _dialect() -> str:
    return op.get_bind().dialect.name


def _is_sqlite() -> bool:
    return _dialect() == "sqlite"


def _is_postgresql() -> bool:
    return _dialect() == "postgresql"


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return any(ix["name"] == name for ix in insp.get_indexes(table))
    except Exception:
        return False


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return insp.has_table(table)
    except Exception:
        return False


def _safe_create_index(name: str, table: str, cols, unique: bool = False) -> None:
    if not _table_exists(table):
        return
    if _index_exists(table, name):
        return
    op.create_index(name, table, cols, unique=unique)


def _safe_drop_index(name: str, table: str) -> None:
    if not _table_exists(table):
        return
    if not _index_exists(table, name):
        return
    op.drop_index(name, table_name=table)


def upgrade() -> None:
    # ─────────────────────────────────────────────
    # 1. CHECK CONSTRAINTS on stock quantities
    # ─────────────────────────────────────────────
    # PostgreSQL: add CHECK constraints on branch_stock & warehouse_stock.
    # SQLite: batch_alter required. We only enforce >=0 sanity at DB level.
    if _is_postgresql():
        op.execute(
            "ALTER TABLE branch_stock "
            "ADD CONSTRAINT ck_branch_stock_current_nonneg "
            "CHECK (current_qty >= 0)"
        )
        op.execute(
            "ALTER TABLE branch_stock "
            "ADD CONSTRAINT ck_branch_stock_reserved_nonneg "
            "CHECK (reserved_qty >= 0)"
        )
        op.execute(
            "ALTER TABLE branch_stock "
            "ADD CONSTRAINT ck_branch_stock_transit_nonneg "
            "CHECK (in_transit_qty >= 0)"
        )
        op.execute(
            "ALTER TABLE warehouse_stock "
            "ADD CONSTRAINT ck_warehouse_stock_current_nonneg "
            "CHECK (current_qty >= 0)"
        )
        op.execute(
            "ALTER TABLE warehouse_stock "
            "ADD CONSTRAINT ck_warehouse_stock_reserved_nonneg "
            "CHECK (reserved_qty >= 0)"
        )
    elif _is_sqlite():
        # SQLite needs batch_alter_table to add constraints on existing tables.
        with op.batch_alter_table("branch_stock") as batch:
            batch.create_check_constraint(
                "ck_branch_stock_current_nonneg", "current_qty >= 0"
            )
            batch.create_check_constraint(
                "ck_branch_stock_reserved_nonneg", "reserved_qty >= 0"
            )
            batch.create_check_constraint(
                "ck_branch_stock_transit_nonneg", "in_transit_qty >= 0"
            )
        with op.batch_alter_table("warehouse_stock") as batch:
            batch.create_check_constraint(
                "ck_warehouse_stock_current_nonneg", "current_qty >= 0"
            )
            batch.create_check_constraint(
                "ck_warehouse_stock_reserved_nonneg", "reserved_qty >= 0"
            )

    # ─────────────────────────────────────────────
    # 2. INDEXES on hot FK / filter columns
    # ─────────────────────────────────────────────
    # users: branch_id / warehouse_id are used on every permission check.
    _safe_create_index("ix_users_branch_id", "users", ["branch_id"])
    _safe_create_index("ix_users_warehouse_id", "users", ["warehouse_id"])
    _safe_create_index("ix_users_is_deleted", "users", ["is_deleted"])

    # branches / warehouses active filters
    _safe_create_index("ix_branches_warehouse_id", "branches", ["warehouse_id"])
    _safe_create_index("ix_branches_active", "branches", ["active", "is_deleted"])
    _safe_create_index("ix_warehouses_active", "warehouses", ["active", "is_deleted"])

    # items
    _safe_create_index("ix_items_category_id", "items", ["category_id"])
    _safe_create_index(
        "ix_items_active_not_deleted", "items", ["active", "is_deleted"]
    )

    # stock tables already have UNIQUE on (branch_id, item_id) / (warehouse_id, item_id)
    # but many queries scan by branch_id alone — add idx for list/dashboard reads.
    _safe_create_index("ix_branch_stock_branch_id", "branch_stock", ["branch_id"])
    _safe_create_index("ix_branch_stock_item_id", "branch_stock", ["item_id"])
    _safe_create_index(
        "ix_warehouse_stock_warehouse_id", "warehouse_stock", ["warehouse_id"]
    )
    _safe_create_index(
        "ix_warehouse_stock_item_id", "warehouse_stock", ["item_id"]
    )

    # daily inventory
    _safe_create_index(
        "ix_daily_inventory_branch_date",
        "daily_inventory",
        ["branch_id", "inventory_date"],
    )
    _safe_create_index("ix_daily_inventory_status", "daily_inventory", ["status"])
    _safe_create_index(
        "ix_daily_inventory_lines_inv_item",
        "daily_inventory_lines",
        ["inventory_id", "item_id"],
    )

    # replenishment orders — big performance win on listing & dashboard
    _safe_create_index(
        "ix_orders_branch_status_created",
        "replenishment_orders",
        ["branch_id", "status", "created_at"],
    )
    _safe_create_index(
        "ix_orders_warehouse_status",
        "replenishment_orders",
        ["warehouse_id", "status"],
    )
    _safe_create_index(
        "ix_orders_status_created",
        "replenishment_orders",
        ["status", "created_at"],
    )
    _safe_create_index(
        "ix_order_lines_order_item",
        "replenishment_order_lines",
        ["order_id", "item_id"],
    )

    # stock transactions — ledger scans by item & date
    _safe_create_index(
        "ix_stock_tx_item_date",
        "stock_transactions",
        ["item_id", "transaction_date"],
    )
    _safe_create_index(
        "ix_stock_tx_type_date",
        "stock_transactions",
        ["transaction_type", "transaction_date"],
    )
    _safe_create_index(
        "ix_stock_tx_source",
        "stock_transactions",
        ["source_type", "source_id"],
    )
    _safe_create_index(
        "ix_stock_tx_destination",
        "stock_transactions",
        ["destination_type", "destination_id"],
    )

    # audit logs — queried by user and entity
    _safe_create_index("ix_audit_user_id", "audit_logs", ["user_id"])
    _safe_create_index(
        "ix_audit_entity", "audit_logs", ["entity_type", "entity_id"]
    )
    _safe_create_index("ix_audit_created_at", "audit_logs", ["created_at"])

    # idempotency cleanup by expires_at
    _safe_create_index(
        "ix_idempotency_expires_at", "idempotency_requests", ["expires_at"]
    )

    # quality visits
    _safe_create_index(
        "ix_qv_branch_date", "quality_visits", ["branch_id", "visit_date"]
    )
    _safe_create_index("ix_qv_status", "quality_visits", ["status"])
    _safe_create_index(
        "ix_qv_responses_visit", "quality_visit_responses", ["visit_id"]
    )

    # training
    _safe_create_index(
        "ix_train_branch_date",
        "training_assessments",
        ["branch_id", "assessment_date"],
    )
    _safe_create_index(
        "ix_train_trainee", "training_assessments", ["trainee_id"]
    )

    # delivery analytics
    _safe_create_index(
        "ix_delivery_records_brand_period",
        "delivery_records",
        ["brand_id", "year", "month"],
    )
    _safe_create_index(
        "ix_delivery_records_branch", "delivery_records", ["branch_id"]
    )


def downgrade() -> None:
    # drop indexes (safe)
    for name, table in [
        ("ix_users_branch_id", "users"),
        ("ix_users_warehouse_id", "users"),
        ("ix_users_is_deleted", "users"),
        ("ix_branches_warehouse_id", "branches"),
        ("ix_branches_active", "branches"),
        ("ix_warehouses_active", "warehouses"),
        ("ix_items_category_id", "items"),
        ("ix_items_active_not_deleted", "items"),
        ("ix_branch_stock_branch_id", "branch_stock"),
        ("ix_branch_stock_item_id", "branch_stock"),
        ("ix_warehouse_stock_warehouse_id", "warehouse_stock"),
        ("ix_warehouse_stock_item_id", "warehouse_stock"),
        ("ix_daily_inventory_branch_date", "daily_inventory"),
        ("ix_daily_inventory_status", "daily_inventory"),
        ("ix_daily_inventory_lines_inv_item", "daily_inventory_lines"),
        ("ix_orders_branch_status_created", "replenishment_orders"),
        ("ix_orders_warehouse_status", "replenishment_orders"),
        ("ix_orders_status_created", "replenishment_orders"),
        ("ix_order_lines_order_item", "replenishment_order_lines"),
        ("ix_stock_tx_item_date", "stock_transactions"),
        ("ix_stock_tx_type_date", "stock_transactions"),
        ("ix_stock_tx_source", "stock_transactions"),
        ("ix_stock_tx_destination", "stock_transactions"),
        ("ix_audit_user_id", "audit_logs"),
        ("ix_audit_entity", "audit_logs"),
        ("ix_audit_created_at", "audit_logs"),
        ("ix_idempotency_expires_at", "idempotency_requests"),
        ("ix_qv_branch_date", "quality_visits"),
        ("ix_qv_status", "quality_visits"),
        ("ix_qv_responses_visit", "quality_visit_responses"),
        ("ix_train_branch_date", "training_assessments"),
        ("ix_train_trainee", "training_assessments"),
        ("ix_delivery_records_brand_period", "delivery_records"),
        ("ix_delivery_records_branch", "delivery_records"),
    ]:
        _safe_drop_index(name, table)

    # drop CHECK constraints
    if _is_postgresql():
        op.execute(
            "ALTER TABLE branch_stock "
            "DROP CONSTRAINT IF EXISTS ck_branch_stock_current_nonneg"
        )
        op.execute(
            "ALTER TABLE branch_stock "
            "DROP CONSTRAINT IF EXISTS ck_branch_stock_reserved_nonneg"
        )
        op.execute(
            "ALTER TABLE branch_stock "
            "DROP CONSTRAINT IF EXISTS ck_branch_stock_transit_nonneg"
        )
        op.execute(
            "ALTER TABLE warehouse_stock "
            "DROP CONSTRAINT IF EXISTS ck_warehouse_stock_current_nonneg"
        )
        op.execute(
            "ALTER TABLE warehouse_stock "
            "DROP CONSTRAINT IF EXISTS ck_warehouse_stock_reserved_nonneg"
        )
    elif _is_sqlite():
        with op.batch_alter_table("branch_stock") as batch:
            try:
                batch.drop_constraint("ck_branch_stock_current_nonneg")
            except Exception:
                pass
            try:
                batch.drop_constraint("ck_branch_stock_reserved_nonneg")
            except Exception:
                pass
            try:
                batch.drop_constraint("ck_branch_stock_transit_nonneg")
            except Exception:
                pass
        with op.batch_alter_table("warehouse_stock") as batch:
            try:
                batch.drop_constraint("ck_warehouse_stock_current_nonneg")
            except Exception:
                pass
            try:
                batch.drop_constraint("ck_warehouse_stock_reserved_nonneg")
            except Exception:
                pass
