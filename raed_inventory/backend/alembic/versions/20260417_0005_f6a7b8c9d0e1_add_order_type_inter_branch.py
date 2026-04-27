"""Add inter_branch to OrderType enum

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-17 00:05:00
"""
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        op.execute("ALTER TYPE ordertype ADD VALUE IF NOT EXISTS 'inter_branch'")
    # SQLite: enum stored as VARCHAR — no DDL needed


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
