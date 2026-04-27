"""Multi-tenant Phase 2: add tenant_id columns to core tables (backfill with 1)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-16 00:02:00

NOTE: This migration adds tenant_id columns but does NOT enforce them as
NOT NULL yet (nullable=True + default=1). Enforcement happens in a
future migration after all rows are confirmed backfilled.
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

# Tables to add tenant_id to, in dependency order
_TABLES = [
    "warehouses",
    "branches",
    "items",
    "branch_stock",
    "warehouse_stock",
    "daily_inventory",
    "replenishment_orders",
    "stock_transactions",
]


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "tenant_id",
                    sa.Integer(),
                    nullable=True,
                    server_default="1",
                )
            )

    # Backfill existing rows
    bind = op.get_bind()
    for table in _TABLES:
        bind.execute(sa.text(f"UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL"))

    # Add indexes for future tenant-scoped queries
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_index(
                f"idx_{table}_tenant_id",
                ["tenant_id"],
                unique=False,
            )


def downgrade() -> None:
    for table in reversed(_TABLES):
        with op.batch_alter_table(table) as batch_op:
            try:
                batch_op.drop_index(f"idx_{table}_tenant_id")
            except Exception:
                pass
            batch_op.drop_column("tenant_id")
