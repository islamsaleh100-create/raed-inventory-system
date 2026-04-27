"""Optional service city on kitchen section assignments (city-scoped kitchen visibility).

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


revision = "y5z6a7b8c9d0"
down_revision = "x4y5z6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kitchen_section_assignments",
        sa.Column("service_city", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("kitchen_section_assignments", "service_city")
