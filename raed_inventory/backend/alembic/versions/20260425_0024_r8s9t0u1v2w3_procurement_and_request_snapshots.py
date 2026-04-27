"""procurement skeleton and branch request snapshots

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-04-25 20:18:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def _enum(*values, name: str):
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


purchase_request_status_enum = _enum("DRAFT", "SUBMITTED", name="purchaserequeststatus")


def upgrade() -> None:
    bind = op.get_bind()
    purchase_request_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("contact_name", sa.String(length=150), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("supplier_code", name="uq_suppliers_supplier_code"),
    )
    op.create_index("ix_suppliers_supplier_code", "suppliers", ["supplier_code"])

    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", purchase_request_status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_purchase_requests_warehouse_id", "purchase_requests", ["warehouse_id"])
    op.create_index("ix_purchase_requests_status", "purchase_requests", ["status"])

    op.create_table(
        "purchase_request_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_request_id", sa.Integer(), sa.ForeignKey("purchase_requests.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty_requested", sa.Numeric(10, 3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_purchase_request_lines_purchase_request_id", "purchase_request_lines", ["purchase_request_id"])

    with op.batch_alter_table("branch_requests") as batch_op:
        batch_op.add_column(sa.Column("brand_name_snapshot", sa.String(length=100), nullable=True))

    with op.batch_alter_table("branch_request_lines") as batch_op:
        batch_op.add_column(sa.Column("item_name_ar_snapshot", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("item_name_en_snapshot", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("item_code_snapshot", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("unit_code_snapshot", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("branch_request_lines") as batch_op:
        batch_op.drop_column("unit_code_snapshot")
        batch_op.drop_column("item_code_snapshot")
        batch_op.drop_column("item_name_en_snapshot")
        batch_op.drop_column("item_name_ar_snapshot")

    with op.batch_alter_table("branch_requests") as batch_op:
        batch_op.drop_column("brand_name_snapshot")

    op.drop_index("ix_purchase_request_lines_purchase_request_id", table_name="purchase_request_lines")
    op.drop_table("purchase_request_lines")

    op.drop_index("ix_purchase_requests_status", table_name="purchase_requests")
    op.drop_index("ix_purchase_requests_warehouse_id", table_name="purchase_requests")
    op.drop_table("purchase_requests")

    op.drop_index("ix_suppliers_supplier_code", table_name="suppliers")
    op.drop_table("suppliers")

    bind = op.get_bind()
    purchase_request_status_enum.drop(bind, checkfirst=True)
