"""Expand supply-chain status enums for PostgreSQL runtime.

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-04-26 11:42:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "v2w3x4y5z6a7"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def _add_enum_values(enum_name: str, values: list[str]) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    ctx = op.get_context()
    with ctx.autocommit_block():
        for value in values:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def upgrade() -> None:
    _add_enum_values(
        "branchrequeststatus",
        ["SPLIT", "IN_EXECUTION", "DELIVERED"],
    )
    _add_enum_values(
        "branchrequestlinestatus",
        [
            "SPLIT_TO_WAREHOUSE",
            "SPLIT_TO_PRODUCTION",
            "IN_PRODUCTION",
            "READY_IN_WAREHOUSE",
            "PARTIAL_WAREHOUSE",
            "DELIVERED",
        ],
    )
    _add_enum_values(
        "warehouselinestatus",
        ["DELIVERED"],
    )


def downgrade() -> None:
    # PostgreSQL enum values are intentionally left in place on downgrade.
    pass
