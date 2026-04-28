"""supply chain phase 2 execution tables

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-04-25 03:58:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def _enum(*values, name: str):
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


def upgrade() -> None:
    production_status_enum = _enum(
        "PENDING", "IN_PROGRESS", "WAITING_FOR_MATERIALS", "PARTIAL_READY", "READY", "SENT_TO_WAREHOUSE",
        name="productionorderstatus",
    )
    material_status_enum = _enum("PENDING", "APPROVED", "ISSUED", "REJECTED", name="kitchenmaterialrequeststatus")
    warehouse_source_enum = _enum(
        "BRANCH_REQUEST", "KITCHEN_OUTPUT", "KITCHEN_MATERIAL_REQUEST", name="warehouselinesourcetype",
    )
    warehouse_status_enum = _enum(
        "PENDING", "AVAILABLE", "PARTIAL", "BACKORDER", "READY_FOR_DISPATCH", name="warehouselinestatus",
    )
    bind = op.get_bind()
    for enum in (production_status_enum, material_status_enum, warehouse_source_enum, warehouse_status_enum):
        enum.create(bind, checkfirst=True)

    op.create_index(
        "uq_area_manager_active_assignment",
        "area_manager_assignments",
        ["user_id", "city", "brand_id"],
        unique=True,
        sqlite_where=sa.text("active = 1"),
        postgresql_where=sa.text("active = true"),
    )

    op.create_table(
        "production_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_request_id", sa.Integer(), sa.ForeignKey("branch_requests.id"), nullable=False),
        sa.Column("source_request_line_id", sa.Integer(), sa.ForeignKey("branch_request_lines.id"), nullable=False),
        sa.Column("destination_branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("kitchen_section_id", sa.Integer(), sa.ForeignKey("kitchen_sections.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty_requested", sa.Numeric(10, 3), nullable=False),
        sa.Column("qty_ready", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("status", production_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("priority", sa.String(length=30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_request_line_id"),
    )
    op.create_index("ix_production_orders_source_request_id", "production_orders", ["source_request_id"])
    op.create_index("ix_production_orders_status", "production_orders", ["status"])

    op.create_table(
        "kitchen_material_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("production_order_id", sa.Integer(), sa.ForeignKey("production_orders.id"), nullable=False),
        sa.Column("kitchen_section_id", sa.Integer(), sa.ForeignKey("kitchen_sections.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(10, 3), nullable=False),
        sa.Column("status", material_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kitchen_material_requests_production_order_id", "kitchen_material_requests", ["production_order_id"])

    op.create_table(
        "warehouse_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_request_id", sa.Integer(), sa.ForeignKey("branch_requests.id"), nullable=True),
        sa.Column("source_request_line_id", sa.Integer(), sa.ForeignKey("branch_request_lines.id"), nullable=True),
        sa.Column("source_type", warehouse_source_enum, nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("kitchen_section_id", sa.Integer(), sa.ForeignKey("kitchen_sections.id"), nullable=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("requested_qty", sa.Numeric(10, 3), nullable=False),
        sa.Column("issued_qty", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("pending_qty", sa.Numeric(10, 3), nullable=False),
        sa.Column("status", warehouse_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("delay_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_request_line_id", "source_type", name="uq_warehouse_line_request_line_source"),
    )
    op.create_index("ix_warehouse_lines_source_request_id", "warehouse_lines", ["source_request_id"])
    op.create_index("ix_warehouse_lines_source_request_line_id", "warehouse_lines", ["source_request_line_id"])
    op.create_index("ix_warehouse_lines_status", "warehouse_lines", ["status"])


def downgrade() -> None:
    production_status_enum = _enum(
        "PENDING", "IN_PROGRESS", "WAITING_FOR_MATERIALS", "PARTIAL_READY", "READY", "SENT_TO_WAREHOUSE",
        name="productionorderstatus",
    )
    material_status_enum = _enum("PENDING", "APPROVED", "ISSUED", "REJECTED", name="kitchenmaterialrequeststatus")
    warehouse_source_enum = _enum(
        "BRANCH_REQUEST", "KITCHEN_OUTPUT", "KITCHEN_MATERIAL_REQUEST", name="warehouselinesourcetype",
    )
    warehouse_status_enum = _enum(
        "PENDING", "AVAILABLE", "PARTIAL", "BACKORDER", "READY_FOR_DISPATCH", name="warehouselinestatus",
    )
    op.drop_index("ix_warehouse_lines_status", table_name="warehouse_lines")
    op.drop_index("ix_warehouse_lines_source_request_line_id", table_name="warehouse_lines")
    op.drop_index("ix_warehouse_lines_source_request_id", table_name="warehouse_lines")
    op.drop_table("warehouse_lines")
    op.drop_index("ix_kitchen_material_requests_production_order_id", table_name="kitchen_material_requests")
    op.drop_table("kitchen_material_requests")
    op.drop_index("ix_production_orders_status", table_name="production_orders")
    op.drop_index("ix_production_orders_source_request_id", table_name="production_orders")
    op.drop_table("production_orders")
    op.drop_index("uq_area_manager_active_assignment", table_name="area_manager_assignments")

    bind = op.get_bind()
    for enum in (warehouse_status_enum, warehouse_source_enum, material_status_enum, production_status_enum):
        enum.drop(bind, checkfirst=True)
