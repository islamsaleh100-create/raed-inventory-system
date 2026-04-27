"""sales audit fields

Revision ID: h9i0j1k2l3m4
Revises: c5d6e7f8a9b0
Create Date: 2026-04-24 16:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h9i0j1k2l3m4"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # Temporary SQLite recovery mode for local/dev databases that were left
        # with broken journaling after the disk filled up.
        bind.exec_driver_sql("PRAGMA journal_mode=OFF")
    op.add_column("branch_daily_sales", sa.Column("entered_by_role", sa.String(length=32), nullable=True))
    op.add_column(
        "branch_daily_sales",
        sa.Column("on_behalf_of", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("PRAGMA journal_mode=OFF")
    op.drop_column("branch_daily_sales", "on_behalf_of")
    op.drop_column("branch_daily_sales", "entered_by_role")
