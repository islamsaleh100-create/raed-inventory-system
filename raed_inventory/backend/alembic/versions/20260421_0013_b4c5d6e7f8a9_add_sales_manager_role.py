"""Add sales_manager to RoleName enum

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-04-21 10:00:00

sales_manager is a NEW operational role introduced 2026-04-21 for
commercial / delivery analytics (import, brand/branch performance,
AOV outliers). It is separate from operations_manager because the
skillset is commercial/BI, not operational oversight.

Pack A migration — pairs with:
- RoleName enum update in app/models/__init__.py
- NEW_ROLES entry in seed_quality_training.py
- seed_sales_manager.py for demo account
"""
from alembic import op


revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        op.execute("ALTER TYPE rolename ADD VALUE IF NOT EXISTS 'sales_manager'")
    # SQLite: enum stored as VARCHAR — no DDL needed


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # SQLite: no DDL was applied upstream, so no-op.
    pass
