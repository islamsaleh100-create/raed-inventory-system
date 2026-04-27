"""track production quantity sent to warehouse

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-04-25 04:24:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "l3m4n5o6p7q8"
down_revision = "k2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.add_column(sa.Column("qty_sent_to_warehouse", sa.Numeric(10, 3), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("production_orders") as batch_op:
        batch_op.drop_column("qty_sent_to_warehouse")
