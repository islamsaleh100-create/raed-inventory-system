"""POS terminals registry for audit

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-10-25 00:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pos_terminals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("terminal_number", sa.String(length=64), nullable=False),
        sa.Column("serial_number", sa.String(length=128), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], name="fk_pos_terminals_branch_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "terminal_number", name="uq_pos_terminals_provider_terminal_number"),
    )
    op.create_index("ix_pos_terminals_provider", "pos_terminals", ["provider"])
    op.create_index("ix_pos_terminals_branch_id", "pos_terminals", ["branch_id"])
    op.create_index("ix_pos_terminals_status", "pos_terminals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pos_terminals_status", table_name="pos_terminals")
    op.drop_index("ix_pos_terminals_branch_id", table_name="pos_terminals")
    op.drop_index("ix_pos_terminals_provider", table_name="pos_terminals")
    op.drop_table("pos_terminals")
