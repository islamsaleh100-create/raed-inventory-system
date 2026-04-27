"""delivery line uniqueness

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-04-25 05:02:00.000000
"""

from alembic import op


revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("delivery_order_lines") as batch_op:
        batch_op.create_unique_constraint(
            "uq_delivery_order_line_warehouse_line",
            ["warehouse_line_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("delivery_order_lines") as batch_op:
        batch_op.drop_constraint(
            "uq_delivery_order_line_warehouse_line",
            type_="unique",
        )
