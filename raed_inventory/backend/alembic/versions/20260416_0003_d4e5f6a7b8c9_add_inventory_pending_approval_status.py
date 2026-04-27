"""Add pending_approval to InventoryStatus enum and cancelled/adjustment enums

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-16 00:03:00

"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        # Extend enums with new values
        op.execute("ALTER TYPE inventorystatus ADD VALUE IF NOT EXISTS 'pending_approval'")
        op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'adjustment_in'")
        op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'adjustment_out'")
    # SQLite: enum is stored as VARCHAR, no DDL change needed


def downgrade() -> None:
    # PostgreSQL does NOT support removing enum values
    pass
