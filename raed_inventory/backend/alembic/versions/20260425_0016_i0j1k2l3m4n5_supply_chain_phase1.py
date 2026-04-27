"""supply chain phase 1 branch requests

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-04-25 03:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "i0j1k2l3m4n5"
down_revision = "h9i0j1k2l3m4"
branch_labels = None
depends_on = None


def _enum(*values, name: str):
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


source_type_enum = _enum("WAREHOUSE", "KITCHEN", "BOTH", name="supplysourcetype")
default_source_enum = _enum("WAREHOUSE", "KITCHEN", name="supplydefaultsource")
request_status_enum = _enum("DRAFT", "SUBMITTED", "AREA_APPROVED", "AREA_REJECTED", name="branchrequeststatus")
line_status_enum = _enum("DRAFT", "SUBMITTED", "APPROVED", "REJECTED", name="branchrequestlinestatus")


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (source_type_enum, default_source_enum, request_status_enum, line_status_enum):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "kitchen_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "branch_brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("branch_id", "brand_id", name="uq_branch_brand"),
    )
    op.create_table(
        "area_manager_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "item_brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.UniqueConstraint("item_id", "brand_id", name="uq_item_brand"),
    )

    with op.batch_alter_table("items") as batch:
        batch.add_column(sa.Column("source_type", source_type_enum, nullable=False, server_default="WAREHOUSE"))
        batch.add_column(sa.Column("default_source", default_source_enum, nullable=False, server_default="WAREHOUSE"))
        batch.add_column(sa.Column("kitchen_section_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_items_kitchen_section_id",
            "kitchen_sections",
            ["kitchen_section_id"],
            ["id"],
        )

    op.create_table(
        "branch_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_no", sa.String(length=40), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("status", request_status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("priority", sa.String(length=30), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejection_note", sa.Text(), nullable=True),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_no"),
    )
    op.create_index("ix_branch_requests_request_no", "branch_requests", ["request_no"])
    op.create_index("ix_branch_requests_branch_id", "branch_requests", ["branch_id"])
    op.create_index("ix_branch_requests_brand_id", "branch_requests", ["brand_id"])
    op.create_index("ix_branch_requests_status", "branch_requests", ["status"])

    op.create_table(
        "branch_request_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("branch_requests.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty_requested", sa.Numeric(10, 3), nullable=False),
        sa.Column("qty_approved", sa.Numeric(10, 3), nullable=True),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column("resolved_source_type", default_source_enum, nullable=True),
        sa.Column("status", line_status_enum, nullable=False, server_default="DRAFT"),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_branch_request_lines_request_id", "branch_request_lines", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_branch_request_lines_request_id", table_name="branch_request_lines")
    op.drop_table("branch_request_lines")
    op.drop_index("ix_branch_requests_status", table_name="branch_requests")
    op.drop_index("ix_branch_requests_brand_id", table_name="branch_requests")
    op.drop_index("ix_branch_requests_branch_id", table_name="branch_requests")
    op.drop_index("ix_branch_requests_request_no", table_name="branch_requests")
    op.drop_table("branch_requests")

    with op.batch_alter_table("items") as batch:
        batch.drop_constraint("fk_items_kitchen_section_id", type_="foreignkey")
        batch.drop_column("kitchen_section_id")
        batch.drop_column("default_source")
        batch.drop_column("source_type")

    op.drop_table("item_brands")
    op.drop_table("area_manager_assignments")
    op.drop_table("branch_brands")
    op.drop_table("kitchen_sections")
    op.drop_table("brands")

    bind = op.get_bind()
    for enum in (line_status_enum, request_status_enum, default_source_enum, source_type_enum):
        enum.drop(bind, checkfirst=True)
