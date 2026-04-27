"""Partial delivery fields and delivery status expansion.

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-04-26 16:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE deliveryorderstatus ADD VALUE IF NOT EXISTS 'PARTIAL_DELIVERED'")

    op.add_column(
        "delivery_order_lines",
        sa.Column("shortage_qty", sa.Numeric(10, 3), nullable=False, server_default="0"),
    )
    op.add_column(
        "delivery_order_lines",
        sa.Column("shortage_reason", sa.Text(), nullable=True),
    )
    op.alter_column("delivery_order_lines", "shortage_qty", server_default=None)


def downgrade() -> None:
    op.drop_column("delivery_order_lines", "shortage_reason")
    op.drop_column("delivery_order_lines", "shortage_qty")
