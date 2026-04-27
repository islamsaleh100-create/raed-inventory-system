"""expand role enum for modern roles

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-04-26 02:10:00.000000
"""

from alembic import op


revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


ROLE_VALUES = (
    "quality_visitor",
    "quality_manager",
    "trainer",
    "area_manager",
    "evaluator",
    "hr_manager",
    "sales_manager",
    "kitchen_manager",
    "kitchen_section_manager",
    "delivery_user",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for value in ROLE_VALUES:
        op.execute(f"ALTER TYPE rolename ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL enums cannot safely drop values in-place without a rebuild.
    # Keep this migration irreversible.
    pass
