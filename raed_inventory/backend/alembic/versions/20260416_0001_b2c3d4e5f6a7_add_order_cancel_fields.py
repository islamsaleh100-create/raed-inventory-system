"""Add cancellation fields to replenishment_orders and cancelled status to OrderStatus enum

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-16 00:01:00

"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # ── PostgreSQL: add 'cancelled' to the enum type ──────────────────────
    if _is_postgresql():
        op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'cancelled'")

    # ── Add cancellation columns to replenishment_orders ──────────────────
    # SQLite batch mode requires a named FK — inline ForeignKey() yields unnamed
    # constraints and raises ValueError: Constraint must have a name.
    with op.batch_alter_table("replenishment_orders") as batch_op:
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("cancelled_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("cancellation_reason", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_replenishment_orders_cancelled_by_users",
            "users",
            ["cancelled_by"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("replenishment_orders") as batch_op:
        batch_op.drop_constraint(
            "fk_replenishment_orders_cancelled_by_users",
            type_="foreignkey",
        )
        batch_op.drop_column("cancellation_reason")
        batch_op.drop_column("cancelled_by")
        batch_op.drop_column("cancelled_at")

    # Note: PostgreSQL does NOT support removing enum values — skip downgrade for enum
