"""Expand ordertype enum for daily and inter-branch orders.

Revision ID: a4b5c6d7e8f9
Revises: z6a7b8c9d0e1
Create Date: 2026-04-26 23:25:00.000000
"""

from alembic import op


revision = "a4b5c6d7e8f9"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    ctx = op.get_context()
    with ctx.autocommit_block():
        op.execute("ALTER TYPE ordertype ADD VALUE IF NOT EXISTS 'daily_order'")
        op.execute("ALTER TYPE ordertype ADD VALUE IF NOT EXISTS 'inter_branch'")


def downgrade() -> None:
    # PostgreSQL enum values are intentionally left in place on downgrade.
    pass
