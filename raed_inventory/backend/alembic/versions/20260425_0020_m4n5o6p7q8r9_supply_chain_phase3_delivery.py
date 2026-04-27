"""supply chain phase 3 delivery

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-04-25 04:34:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "m4n5o6p7q8r9"
down_revision = "l3m4n5o6p7q8"
branch_labels = None
depends_on = None


def _enum(*values, name: str):
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


delivery_order_status = _enum("READY", "OUT_FOR_DELIVERY", "DELIVERED", name="deliveryorderstatus")
delivery_order_line_status = _enum(
    "READY", "OUT_FOR_DELIVERY", "DELIVERED", "PARTIAL_DELIVERED", name="deliveryorderlinestatus"
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        delivery_order_status.create(bind, checkfirst=True)
        delivery_order_line_status.create(bind, checkfirst=True)

    op.create_table(
        "delivery_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_request_id", sa.Integer(), sa.ForeignKey("branch_requests.id"), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("status", delivery_order_status, nullable=False),
        sa.Column("ready_at", sa.DateTime(), nullable=True),
        sa.Column("out_for_delivery_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("delivered_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("receiver_name", sa.String(length=150), nullable=True),
        sa.Column("delivery_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_delivery_orders_source_request_id", "delivery_orders", ["source_request_id"])
    op.create_index("ix_delivery_orders_branch_id", "delivery_orders", ["branch_id"])
    op.create_index("ix_delivery_orders_brand_id", "delivery_orders", ["brand_id"])
    op.create_index("ix_delivery_orders_status", "delivery_orders", ["status"])

    op.create_table(
        "delivery_order_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("delivery_order_id", sa.Integer(), sa.ForeignKey("delivery_orders.id"), nullable=False),
        sa.Column("warehouse_line_id", sa.Integer(), sa.ForeignKey("warehouse_lines.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty_dispatched", sa.Numeric(10, 3), nullable=False),
        sa.Column("qty_delivered", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("status", delivery_order_line_status, nullable=False),
        sa.Column("delivery_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_delivery_order_lines_delivery_order_id", "delivery_order_lines", ["delivery_order_id"])
    op.create_index("ix_delivery_order_lines_warehouse_line_id", "delivery_order_lines", ["warehouse_line_id"])
    op.create_index("ix_delivery_order_lines_status", "delivery_order_lines", ["status"])


def downgrade() -> None:
    op.drop_index("ix_delivery_order_lines_status", table_name="delivery_order_lines")
    op.drop_index("ix_delivery_order_lines_warehouse_line_id", table_name="delivery_order_lines")
    op.drop_index("ix_delivery_order_lines_delivery_order_id", table_name="delivery_order_lines")
    op.drop_table("delivery_order_lines")

    op.drop_index("ix_delivery_orders_status", table_name="delivery_orders")
    op.drop_index("ix_delivery_orders_brand_id", table_name="delivery_orders")
    op.drop_index("ix_delivery_orders_branch_id", table_name="delivery_orders")
    op.drop_index("ix_delivery_orders_source_request_id", table_name="delivery_orders")
    op.drop_table("delivery_orders")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        delivery_order_line_status.drop(bind, checkfirst=True)
        delivery_order_status.drop(bind, checkfirst=True)
