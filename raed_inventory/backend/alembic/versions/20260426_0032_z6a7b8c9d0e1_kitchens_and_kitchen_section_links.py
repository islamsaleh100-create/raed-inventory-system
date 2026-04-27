"""Kitchen sites (per city) + M2M to kitchen_sections for blueprint alignment.

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


revision = "z6a7b8c9d0e1"
down_revision = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kitchens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kitchens_city", "kitchens", ["city"], unique=False)

    op.create_table(
        "kitchen_kitchen_sections",
        sa.Column("kitchen_id", sa.Integer(), nullable=False),
        sa.Column("kitchen_section_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["kitchen_id"], ["kitchens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kitchen_section_id"], ["kitchen_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("kitchen_id", "kitchen_section_id"),
    )


def downgrade() -> None:
    op.drop_table("kitchen_kitchen_sections")
    op.drop_index("ix_kitchens_city", table_name="kitchens")
    op.drop_table("kitchens")
