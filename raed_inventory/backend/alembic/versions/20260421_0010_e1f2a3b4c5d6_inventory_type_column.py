"""Inventory type (daily / weekly / monthly) — H9

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-04-21 09:00:00

Adds a nullable `inventory_type` VARCHAR(20) column to `daily_inventory`
with a default of 'daily' so existing rows get classified retroactively.
This lets reports and list views show branch users their weekly/monthly
counts separately from the daily ones.
"""
from alembic import op
import sqlalchemy as sa


revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_inventory",
        sa.Column("inventory_type", sa.String(length=20), nullable=True),
    )
    # Backfill: everything that exists right now is a daily count
    op.execute("UPDATE daily_inventory SET inventory_type = 'daily' WHERE inventory_type IS NULL")
    op.create_index(
        "ix_daily_inventory_type",
        "daily_inventory",
        ["inventory_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_daily_inventory_type", table_name="daily_inventory")
    op.drop_column("daily_inventory", "inventory_type")
