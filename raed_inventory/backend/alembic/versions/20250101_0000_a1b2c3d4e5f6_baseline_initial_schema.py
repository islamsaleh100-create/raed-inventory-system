"""Baseline: initial schema for Raed Inventory System v0.1.0

This migration represents the full schema as it existed before Alembic was
introduced.  It is the single source of truth for fresh database creation.

IMPORTANT — existing databases
-------------------------------
If you already have a database whose tables were created via
``Base.metadata.create_all()``, do NOT run ``alembic upgrade head``.
Instead, stamp the revision so Alembic knows the DB is already at this
baseline:

    alembic stamp a1b2c3d4e5f6

After that, all future migrations will run normally.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Helper: detect dialect
# ---------------------------------------------------------------------------

def _is_postgresql() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


# ---------------------------------------------------------------------------
# Enum type names (PostgreSQL creates named ENUM types; SQLite ignores them)
# ---------------------------------------------------------------------------

_ENUMS = {
    "userstatus":          ("active", "inactive", "suspended"),
    "rolename":            (
        "super_admin", "admin", "branch_user", "branch_manager",
        "warehouse_user", "warehouse_manager", "operations_manager",
    ),
    "inventorystatus":     ("draft", "submitted", "approved", "rejected"),
    "orderstatus":         (
        "draft", "system_generated", "branch_reviewed",
        "submitted_to_warehouse", "under_review", "approved",
        "partially_approved", "rejected", "picking",
        "dispatched", "received", "closed",
    ),
    "ordertype":           ("auto_replenishment", "exceptional"),
    "transactiontype":     (
        "opening_balance", "inventory_adjustment", "replenishment_request",
        "warehouse_issue", "warehouse_dispatch", "branch_receipt",
        "transfer", "wastage", "manual_adjustment",
    ),
    "avgconsumptionmode":  ("last_7_days", "last_14_days", "last_30_days"),
    "itemtype":            ("raw_material", "packaging", "consumable", "finished_good"),
    "storagetype":         ("ambient", "chilled", "frozen"),
}


def _enum(name: str) -> sa.Enum:
    if _is_postgresql():
        return postgresql.ENUM(*_ENUMS[name], name=name, create_type=False)
    return sa.Enum(*_ENUMS[name], name=name)


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create PostgreSQL ENUM types first (no-op on SQLite)
    # ------------------------------------------------------------------
    if _is_postgresql():
        for name, values in _ENUMS.items():
            sa.Enum(*values, name=name).create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # roles
    # ------------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id",           sa.Integer(),                   primary_key=True),
        sa.Column("name",         _enum("rolename"),              nullable=False),
        sa.Column("display_name", sa.String(100),                 nullable=False),
        sa.Column("description",  sa.Text(),                      nullable=True),
        sa.Column("created_at",   sa.DateTime(),                  nullable=True),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    # ------------------------------------------------------------------
    # permissions
    # ------------------------------------------------------------------
    op.create_table(
        "permissions",
        sa.Column("id",          sa.Integer(), primary_key=True),
        sa.Column("code",        sa.String(100), nullable=False),
        sa.Column("module",      sa.String(50),  nullable=False),
        sa.Column("action",      sa.String(50),  nullable=False),
        sa.Column("description", sa.Text(),      nullable=True),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )

    # ------------------------------------------------------------------
    # item_categories
    # ------------------------------------------------------------------
    op.create_table(
        "item_categories",
        sa.Column("id",         sa.Integer(),    primary_key=True),
        sa.Column("code",       sa.String(20),   nullable=False),
        sa.Column("name_ar",    sa.String(100),  nullable=False),
        sa.Column("name_en",    sa.String(100),  nullable=False),
        sa.Column("active",     sa.Boolean(),    nullable=True),
        sa.Column("created_at", sa.DateTime(),   nullable=True),
        sa.UniqueConstraint("code", name="uq_item_categories_code"),
    )

    # ------------------------------------------------------------------
    # units
    # ------------------------------------------------------------------
    op.create_table(
        "units",
        sa.Column("id",      sa.Integer(),   primary_key=True),
        sa.Column("code",    sa.String(20),  nullable=False),
        sa.Column("name_ar", sa.String(50),  nullable=False),
        sa.Column("name_en", sa.String(50),  nullable=False),
        sa.Column("active",  sa.Boolean(),   nullable=True),
        sa.UniqueConstraint("code", name="uq_units_code"),
    )

    # ------------------------------------------------------------------
    # inventory_variance_reasons
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_variance_reasons",
        sa.Column("id",        sa.Integer(),    primary_key=True),
        sa.Column("reason_ar", sa.String(200),  nullable=False),
        sa.Column("reason_en", sa.String(200),  nullable=False),
        sa.Column("active",    sa.Boolean(),    nullable=True),
    )

    # ------------------------------------------------------------------
    # receiving_variance_reasons
    # ------------------------------------------------------------------
    op.create_table(
        "receiving_variance_reasons",
        sa.Column("id",        sa.Integer(),    primary_key=True),
        sa.Column("reason_ar", sa.String(200),  nullable=False),
        sa.Column("reason_en", sa.String(200),  nullable=False),
        sa.Column("active",    sa.Boolean(),    nullable=True),
    )

    # ------------------------------------------------------------------
    # warehouses
    # ------------------------------------------------------------------
    op.create_table(
        "warehouses",
        sa.Column("id",             sa.Integer(),    primary_key=True),
        sa.Column("warehouse_code", sa.String(20),   nullable=False),
        sa.Column("warehouse_name", sa.String(150),  nullable=False),
        sa.Column("location",       sa.String(200),  nullable=True),
        sa.Column("active",         sa.Boolean(),    nullable=True),
        sa.Column("created_at",     sa.DateTime(),   nullable=True),
        sa.Column("updated_at",     sa.DateTime(),   nullable=True),
        sa.Column("is_deleted",     sa.Boolean(),    nullable=True),
        sa.UniqueConstraint("warehouse_code", name="uq_warehouses_code"),
    )

    # ------------------------------------------------------------------
    # branches  (FK -> warehouses)
    # ------------------------------------------------------------------
    op.create_table(
        "branches",
        sa.Column("id",           sa.Integer(),    primary_key=True),
        sa.Column("branch_code",  sa.String(20),   nullable=False),
        sa.Column("branch_name",  sa.String(150),  nullable=False),
        sa.Column("city",         sa.String(100),  nullable=True),
        sa.Column("area",         sa.String(100),  nullable=True),
        sa.Column("warehouse_id", sa.Integer(),    sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("active",       sa.Boolean(),    nullable=True),
        sa.Column("created_at",   sa.DateTime(),   nullable=True),
        sa.Column("updated_at",   sa.DateTime(),   nullable=True),
        sa.Column("is_deleted",   sa.Boolean(),    nullable=True),
        sa.UniqueConstraint("branch_code", name="uq_branches_code"),
    )

    # ------------------------------------------------------------------
    # users  (FK -> branches, warehouses, self)
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id",              sa.Integer(),          primary_key=True),
        sa.Column("username",        sa.String(50),         nullable=False),
        sa.Column("email",           sa.String(150),        nullable=False),
        sa.Column("full_name",       sa.String(150),        nullable=False),
        sa.Column("hashed_password", sa.String(255),        nullable=False),
        sa.Column("status",          _enum("userstatus"),   nullable=True),
        sa.Column("branch_id",       sa.Integer(),          sa.ForeignKey("branches.id"),   nullable=True),
        sa.Column("warehouse_id",    sa.Integer(),          sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("phone",           sa.String(20),         nullable=True),
        sa.Column("created_at",      sa.DateTime(),         nullable=True),
        sa.Column("updated_at",      sa.DateTime(),         nullable=True),
        sa.Column("created_by",      sa.Integer(),          sa.ForeignKey("users.id"),      nullable=True),
        sa.Column("is_deleted",      sa.Boolean(),          nullable=True),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email",    name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # ------------------------------------------------------------------
    # role_permissions  (FK -> roles, permissions)
    # ------------------------------------------------------------------
    op.create_table(
        "role_permissions",
        sa.Column("id",            sa.Integer(), primary_key=True),
        sa.Column("role_id",       sa.Integer(), sa.ForeignKey("roles.id"),       nullable=False),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id"), nullable=False),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),
    )

    # ------------------------------------------------------------------
    # user_roles  (FK -> users, roles)
    # ------------------------------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column("id",      sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles"),
    )

    # ------------------------------------------------------------------
    # items  (FK -> item_categories, units x3)
    # ------------------------------------------------------------------
    op.create_table(
        "items",
        sa.Column("id",                       sa.Integer(),              primary_key=True),
        sa.Column("item_code",                sa.String(30),             nullable=False),
        sa.Column("item_name_ar",             sa.String(200),            nullable=False),
        sa.Column("item_name_en",             sa.String(200),            nullable=False),
        sa.Column("category_id",              sa.Integer(),              sa.ForeignKey("item_categories.id"), nullable=False),
        sa.Column("unit_id",                  sa.Integer(),              sa.ForeignKey("units.id"), nullable=False),
        sa.Column("item_type",                _enum("itemtype"),         nullable=False),
        sa.Column("storage_type",             _enum("storagetype"),      nullable=False),
        sa.Column("purchase_unit_id",         sa.Integer(),              sa.ForeignKey("units.id"), nullable=True),
        sa.Column("supply_unit_id",           sa.Integer(),              sa.ForeignKey("units.id"), nullable=True),
        sa.Column("conversion_ratio",         sa.Numeric(12, 4),         nullable=True),
        sa.Column("branch_requestable",       sa.Boolean(),              nullable=True),
        sa.Column("active",                   sa.Boolean(),              nullable=True),
        sa.Column("min_qty",                  sa.Numeric(10, 3),         nullable=True),
        sa.Column("max_qty",                  sa.Numeric(10, 3),         nullable=True),
        sa.Column("reorder_point",            sa.Numeric(10, 3),         nullable=True),
        sa.Column("safety_stock",             sa.Numeric(10, 3),         nullable=True),
        sa.Column("lead_time_days",           sa.Integer(),              nullable=True),
        sa.Column("shelf_life_days",          sa.Integer(),              nullable=True),
        sa.Column("average_consumption_mode", _enum("avgconsumptionmode"), nullable=True),
        sa.Column("critical_item",            sa.Boolean(),              nullable=True),
        sa.Column("created_at",               sa.DateTime(),             nullable=True),
        sa.Column("updated_at",               sa.DateTime(),             nullable=True),
        sa.Column("is_deleted",               sa.Boolean(),              nullable=True),
        sa.UniqueConstraint("item_code", name="uq_items_item_code"),
    )
    op.create_index("ix_items_item_code", "items", ["item_code"])

    # ------------------------------------------------------------------
    # branch_stock  (FK -> branches, items)
    # ------------------------------------------------------------------
    op.create_table(
        "branch_stock",
        sa.Column("id",             sa.Integer(),        primary_key=True),
        sa.Column("branch_id",      sa.Integer(),        sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("item_id",        sa.Integer(),        sa.ForeignKey("items.id"),    nullable=False),
        sa.Column("current_qty",    sa.Numeric(10, 3),   nullable=True),
        sa.Column("reserved_qty",   sa.Numeric(10, 3),   nullable=True),
        sa.Column("in_transit_qty", sa.Numeric(10, 3),   nullable=True),
        sa.Column("last_updated",   sa.DateTime(),       nullable=True),
        sa.UniqueConstraint("branch_id", "item_id", name="uq_branch_stock"),
    )

    # ------------------------------------------------------------------
    # warehouse_stock  (FK -> warehouses, items)
    # ------------------------------------------------------------------
    op.create_table(
        "warehouse_stock",
        sa.Column("id",           sa.Integer(),        primary_key=True),
        sa.Column("warehouse_id", sa.Integer(),        sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("item_id",      sa.Integer(),        sa.ForeignKey("items.id"),      nullable=False),
        sa.Column("current_qty",  sa.Numeric(10, 3),   nullable=True),
        sa.Column("reserved_qty", sa.Numeric(10, 3),   nullable=True),
        sa.Column("last_updated", sa.DateTime(),       nullable=True),
        sa.UniqueConstraint("warehouse_id", "item_id", name="uq_warehouse_stock"),
    )

    # ------------------------------------------------------------------
    # daily_inventory  (FK -> branches, users x3)
    # ------------------------------------------------------------------
    op.create_table(
        "daily_inventory",
        sa.Column("id",               sa.Integer(),              primary_key=True),
        sa.Column("branch_id",        sa.Integer(),              sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("inventory_date",   sa.Date(),                 nullable=False),
        sa.Column("status",           _enum("inventorystatus"),  nullable=True),
        sa.Column("submitted_at",     sa.DateTime(),             nullable=True),
        sa.Column("submitted_by",     sa.Integer(),              sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at",      sa.DateTime(),             nullable=True),
        sa.Column("approved_by",      sa.Integer(),              sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejection_reason", sa.Text(),                 nullable=True),
        sa.Column("notes",            sa.Text(),                 nullable=True),
        sa.Column("created_at",       sa.DateTime(),             nullable=True),
        sa.Column("updated_at",       sa.DateTime(),             nullable=True),
        sa.Column("created_by",       sa.Integer(),              sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("branch_id", "inventory_date", name="uq_daily_inventory"),
    )
    op.create_index("idx_daily_inv_branch_date", "daily_inventory", ["branch_id", "inventory_date"])

    # ------------------------------------------------------------------
    # daily_inventory_lines  (FK -> daily_inventory, items, inventory_variance_reasons)
    # ------------------------------------------------------------------
    op.create_table(
        "daily_inventory_lines",
        sa.Column("id",                  sa.Integer(),       primary_key=True),
        sa.Column("inventory_id",        sa.Integer(),       sa.ForeignKey("daily_inventory.id"),          nullable=False),
        sa.Column("item_id",             sa.Integer(),       sa.ForeignKey("items.id"),                    nullable=False),
        sa.Column("book_qty",            sa.Numeric(10, 3),  nullable=True),
        sa.Column("counted_qty",         sa.Numeric(10, 3),  nullable=False),
        sa.Column("variance_qty",        sa.Numeric(10, 3),  nullable=True),
        sa.Column("variance_pct",        sa.Numeric(6, 2),   nullable=True),
        sa.Column("variance_status",     sa.String(20),      nullable=True),
        sa.Column("below_min_flag",      sa.Boolean(),       nullable=True),
        sa.Column("out_of_stock_flag",   sa.Boolean(),       nullable=True),
        sa.Column("variance_reason_id",  sa.Integer(),       sa.ForeignKey("inventory_variance_reasons.id"), nullable=True),
        sa.Column("notes",               sa.Text(),          nullable=True),
    )

    # ------------------------------------------------------------------
    # replenishment_orders  (FK -> branches, warehouses, daily_inventory, users x5)
    # ------------------------------------------------------------------
    op.create_table(
        "replenishment_orders",
        sa.Column("id",                        sa.Integer(),         primary_key=True),
        sa.Column("order_no",                  sa.String(30),        nullable=False),
        sa.Column("branch_id",                 sa.Integer(),         sa.ForeignKey("branches.id"),    nullable=False),
        sa.Column("warehouse_id",              sa.Integer(),         sa.ForeignKey("warehouses.id"),  nullable=False),
        sa.Column("order_type",                _enum("ordertype"),   nullable=True),
        sa.Column("status",                    _enum("orderstatus"), nullable=True),
        sa.Column("inventory_id",              sa.Integer(),         sa.ForeignKey("daily_inventory.id"), nullable=True),
        sa.Column("order_date",                sa.Date(),            nullable=False),
        sa.Column("branch_reviewed_at",        sa.DateTime(),        nullable=True),
        sa.Column("branch_reviewed_by",        sa.Integer(),         sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_to_warehouse_at", sa.DateTime(),        nullable=True),
        sa.Column("wh_reviewed_at",            sa.DateTime(),        nullable=True),
        sa.Column("wh_reviewed_by",            sa.Integer(),         sa.ForeignKey("users.id"), nullable=True),
        sa.Column("wh_approved_at",            sa.DateTime(),        nullable=True),
        sa.Column("wh_approved_by",            sa.Integer(),         sa.ForeignKey("users.id"), nullable=True),
        sa.Column("picking_started_at",        sa.DateTime(),        nullable=True),
        sa.Column("dispatched_at",             sa.DateTime(),        nullable=True),
        sa.Column("dispatched_by",             sa.Integer(),         sa.ForeignKey("users.id"), nullable=True),
        sa.Column("received_at",               sa.DateTime(),        nullable=True),
        sa.Column("closed_at",                 sa.DateTime(),        nullable=True),
        sa.Column("rejection_reason",          sa.Text(),            nullable=True),
        sa.Column("notes",                     sa.Text(),            nullable=True),
        sa.Column("dispatch_note_no",          sa.String(30),        nullable=True),
        sa.Column("created_at",                sa.DateTime(),        nullable=True),
        sa.Column("updated_at",                sa.DateTime(),        nullable=True),
        sa.Column("created_by",                sa.Integer(),         sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("order_no", name="uq_replenishment_orders_no"),
    )
    op.create_index("idx_order_branch",  "replenishment_orders", ["branch_id"])
    op.create_index("idx_order_status",  "replenishment_orders", ["status"])

    # ------------------------------------------------------------------
    # replenishment_order_lines  (FK -> replenishment_orders, items, receiving_variance_reasons)
    # ------------------------------------------------------------------
    op.create_table(
        "replenishment_order_lines",
        sa.Column("id",                           sa.Integer(),        primary_key=True),
        sa.Column("order_id",                     sa.Integer(),        sa.ForeignKey("replenishment_orders.id"),  nullable=False),
        sa.Column("item_id",                      sa.Integer(),        sa.ForeignKey("items.id"),                  nullable=False),
        sa.Column("suggested_qty",                sa.Numeric(10, 3),   nullable=True),
        sa.Column("branch_requested_qty",         sa.Numeric(10, 3),   nullable=True),
        sa.Column("wh_approved_qty",              sa.Numeric(10, 3),   nullable=True),
        sa.Column("picked_qty",                   sa.Numeric(10, 3),   nullable=True),
        sa.Column("dispatched_qty",               sa.Numeric(10, 3),   nullable=True),
        sa.Column("received_qty",                 sa.Numeric(10, 3),   nullable=True),
        sa.Column("damaged_qty",                  sa.Numeric(10, 3),   nullable=True),
        sa.Column("missing_qty",                  sa.Numeric(10, 3),   nullable=True),
        sa.Column("shortage_flag",                sa.Boolean(),        nullable=True),
        sa.Column("shortage_reason",              sa.Text(),           nullable=True),
        sa.Column("rejection_reason",             sa.Text(),           nullable=True),
        sa.Column("receiving_variance_reason_id", sa.Integer(),        sa.ForeignKey("receiving_variance_reasons.id"), nullable=True),
        sa.Column("line_status",                  sa.String(30),       nullable=True),
        sa.Column("notes",                        sa.Text(),           nullable=True),
    )

    # ------------------------------------------------------------------
    # stock_transactions  (FK -> items, users)
    # ------------------------------------------------------------------
    op.create_table(
        "stock_transactions",
        sa.Column("id",               sa.Integer(),               primary_key=True),
        sa.Column("transaction_date", sa.DateTime(),              nullable=False),
        sa.Column("transaction_type", _enum("transactiontype"),   nullable=False),
        sa.Column("source_type",      sa.String(50),              nullable=True),
        sa.Column("source_id",        sa.Integer(),               nullable=True),
        sa.Column("destination_type", sa.String(50),              nullable=True),
        sa.Column("destination_id",   sa.Integer(),               nullable=True),
        sa.Column("item_id",          sa.Integer(),               sa.ForeignKey("items.id"),  nullable=False),
        sa.Column("qty",              sa.Numeric(10, 3),          nullable=False),
        sa.Column("reference_no",     sa.String(50),              nullable=True),
        sa.Column("notes",            sa.Text(),                  nullable=True),
        sa.Column("created_by",       sa.Integer(),               sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at",       sa.DateTime(),              nullable=True),
    )
    op.create_index("idx_stock_tx_item", "stock_transactions", ["item_id"])
    op.create_index("idx_stock_tx_date", "stock_transactions", ["transaction_date"])

    # ------------------------------------------------------------------
    # system_settings  (FK -> users)
    # ------------------------------------------------------------------
    op.create_table(
        "system_settings",
        sa.Column("id",          sa.Integer(),    primary_key=True),
        sa.Column("key",         sa.String(100),  nullable=False),
        sa.Column("value",       sa.Text(),       nullable=False),
        sa.Column("description", sa.Text(),       nullable=True),
        sa.Column("updated_at",  sa.DateTime(),   nullable=True),
        sa.Column("updated_by",  sa.Integer(),    sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("key", name="uq_system_settings_key"),
    )

    # ------------------------------------------------------------------
    # audit_logs  (FK -> users)
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id",          sa.Integer(),    primary_key=True),
        sa.Column("user_id",     sa.Integer(),    sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action",      sa.String(100),  nullable=False),
        sa.Column("module",      sa.String(50),   nullable=True),
        sa.Column("entity_type", sa.String(50),   nullable=True),
        sa.Column("entity_id",   sa.Integer(),    nullable=True),
        sa.Column("old_values",  sa.Text(),       nullable=True),
        sa.Column("new_values",  sa.Text(),       nullable=True),
        sa.Column("ip_address",  sa.String(45),   nullable=True),
        sa.Column("created_at",  sa.DateTime(),   nullable=True),
    )

    # ------------------------------------------------------------------
    # idempotency_requests  (FK -> users)
    # ------------------------------------------------------------------
    op.create_table(
        "idempotency_requests",
        sa.Column("id",                      sa.Integer(),    primary_key=True),
        sa.Column("tenant_id",               sa.Integer(),    nullable=False),
        sa.Column("client_request_id",       sa.String(100),  nullable=False),
        sa.Column("operation_name",          sa.String(100),  nullable=False),
        sa.Column("user_id",                 sa.Integer(),    sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status",                  sa.String(30),   nullable=False),
        sa.Column("response_reference_type", sa.String(50),   nullable=True),
        sa.Column("response_reference_id",   sa.String(100),  nullable=True),
        sa.Column("request_hash",            sa.String(128),  nullable=True),
        sa.Column("created_at",              sa.DateTime(),   nullable=False),
        sa.Column("expires_at",              sa.DateTime(),   nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "client_request_id", "operation_name",
            name="uq_idempotency_request",
        ),
    )
    op.create_index("idx_idempotency_expires_at", "idempotency_requests", ["expires_at"])
    op.create_index(
        "idx_idempotency_lookup",
        "idempotency_requests",
        ["tenant_id", "client_request_id", "operation_name"],
    )


# ---------------------------------------------------------------------------
# downgrade  — drops everything in reverse dependency order
# ---------------------------------------------------------------------------

def downgrade() -> None:
    op.drop_index("idx_idempotency_lookup",    table_name="idempotency_requests")
    op.drop_index("idx_idempotency_expires_at", table_name="idempotency_requests")
    op.drop_table("idempotency_requests")

    op.drop_table("audit_logs")
    op.drop_table("system_settings")

    op.drop_index("idx_stock_tx_date", table_name="stock_transactions")
    op.drop_index("idx_stock_tx_item", table_name="stock_transactions")
    op.drop_table("stock_transactions")

    op.drop_table("replenishment_order_lines")

    op.drop_index("idx_order_status",  table_name="replenishment_orders")
    op.drop_index("idx_order_branch",  table_name="replenishment_orders")
    op.drop_table("replenishment_orders")

    op.drop_table("daily_inventory_lines")

    op.drop_index("idx_daily_inv_branch_date", table_name="daily_inventory")
    op.drop_table("daily_inventory")

    op.drop_table("warehouse_stock")
    op.drop_table("branch_stock")

    op.drop_index("ix_items_item_code", table_name="items")
    op.drop_table("items")

    op.drop_table("user_roles")
    op.drop_table("role_permissions")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    op.drop_table("branches")
    op.drop_table("warehouses")
    op.drop_table("receiving_variance_reasons")
    op.drop_table("inventory_variance_reasons")
    op.drop_table("units")
    op.drop_table("item_categories")
    op.drop_table("permissions")
    op.drop_table("roles")

    # Drop PostgreSQL ENUM types after all tables are gone
    if _is_postgresql():
        for name in reversed(list(_ENUMS.keys())):
            sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
