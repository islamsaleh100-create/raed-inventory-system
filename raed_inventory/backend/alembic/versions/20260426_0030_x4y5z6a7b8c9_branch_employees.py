"""Branch employees and branch-manager scoped management.

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "branch_employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=False),
        sa.Column("work_number", sa.String(length=50), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("work_number", name="uq_branch_employees_work_number"),
    )
    op.create_index("ix_branch_employees_branch_id", "branch_employees", ["branch_id"])
    op.create_index("ix_branch_employees_active", "branch_employees", ["active"])


def downgrade() -> None:
    op.drop_index("ix_branch_employees_active", table_name="branch_employees")
    op.drop_index("ix_branch_employees_branch_id", table_name="branch_employees")
    op.drop_table("branch_employees")
