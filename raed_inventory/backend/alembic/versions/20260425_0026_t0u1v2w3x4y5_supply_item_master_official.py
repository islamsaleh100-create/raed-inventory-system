"""official supply item master visibility + not-requestable support

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-04-25 23:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        op.execute("ALTER TYPE supplysourcetype ADD VALUE IF NOT EXISTS 'NOT_REQUESTABLE'")

    with op.batch_alter_table("items") as batch_op:
        batch_op.add_column(
            sa.Column(
                "visible_in_branch_ui",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("items") as batch_op:
        batch_op.drop_column("visible_in_branch_ui")
