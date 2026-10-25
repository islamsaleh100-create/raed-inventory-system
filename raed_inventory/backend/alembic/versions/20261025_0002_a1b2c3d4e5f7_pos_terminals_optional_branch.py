"""POS terminals optional branch + branch_label

Revision ID: a1b2c3d4e5f7
Revises: f8a9b0c1d2e3
Create Date: 2026-10-25 16:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pos_terminals", sa.Column("branch_label", sa.String(length=128), nullable=True))
    op.alter_column("pos_terminals", "branch_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    null_count = bind.execute(
        sa.text("SELECT count(*) FROM pos_terminals WHERE branch_id IS NULL")
    ).scalar()
    if null_count and int(null_count) > 0:
        raise RuntimeError(
            f"Cannot downgrade a1b2c3d4e5f7: {null_count} pos_terminals row(s) have NULL branch_id. "
            "Assign a branch or delete those rows before downgrade."
        )
    op.alter_column("pos_terminals", "branch_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("pos_terminals", "branch_label")
