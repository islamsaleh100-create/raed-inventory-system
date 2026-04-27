"""Add destination_branch_id to replenishment_orders (inter-branch transfers)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-18 00:00:00

Adds a nullable FK column on replenishment_orders pointing to branches.
Used only by OrderType.inter_branch — for normal orders this column stays NULL.

Idempotent against SQLite (column/index existence check) to be safe in local dev
where migrations may be re-applied. PostgreSQL uses standard ALTER TABLE.
"""
from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def _dialect() -> str:
    return op.get_bind().dialect.name


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def _has_index(table: str, index_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return index_name in {i["name"] for i in insp.get_indexes(table)}


def _has_fk(table: str, fk_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return fk_name in {fk["name"] for fk in insp.get_foreign_keys(table)}


def upgrade() -> None:
    if not _has_column("replenishment_orders", "destination_branch_id"):
        with op.batch_alter_table("replenishment_orders") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "destination_branch_id",
                    sa.Integer(),
                    nullable=True,
                )
            )
    if not _has_fk("replenishment_orders", "fk_repl_orders_destination_branch"):
        with op.batch_alter_table("replenishment_orders") as batch_op:
            batch_op.create_foreign_key(
                "fk_repl_orders_destination_branch",
                "branches",
                ["destination_branch_id"],
                ["id"],
            )

    if not _has_index("replenishment_orders", "ix_repl_orders_destination_branch"):
        op.create_index(
            "ix_repl_orders_destination_branch",
            "replenishment_orders",
            ["destination_branch_id"],
        )


def downgrade() -> None:
    if _has_index("replenishment_orders", "ix_repl_orders_destination_branch"):
        op.drop_index(
            "ix_repl_orders_destination_branch",
            table_name="replenishment_orders",
        )
    if _has_fk("replenishment_orders", "fk_repl_orders_destination_branch"):
        with op.batch_alter_table("replenishment_orders") as batch_op:
            batch_op.drop_constraint("fk_repl_orders_destination_branch", type_="foreignkey")
    if _has_column("replenishment_orders", "destination_branch_id"):
        with op.batch_alter_table("replenishment_orders") as batch_op:
            batch_op.drop_column("destination_branch_id")
