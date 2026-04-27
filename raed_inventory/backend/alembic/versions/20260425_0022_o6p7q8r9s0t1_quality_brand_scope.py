"""quality brand scope for legacy visits

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-04-25 18:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        return insp.has_table(table)
    except Exception:
        return False


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        return column in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def upgrade() -> None:
    if _has_table("quality_visit_sections"):
        with op.batch_alter_table("quality_visit_sections") as batch_op:
            if not _has_column("quality_visit_sections", "brand_key"):
                batch_op.add_column(sa.Column("brand_key", sa.String(length=32), nullable=True))
            batch_op.create_index("ix_quality_visit_sections_brand_key", ["brand_key"], unique=False)

    if _has_table("quality_visits"):
        with op.batch_alter_table("quality_visits") as batch_op:
            if not _has_column("quality_visits", "brand_key"):
                batch_op.add_column(sa.Column("brand_key", sa.String(length=32), nullable=True))
            batch_op.create_index("ix_quality_visits_brand_key", ["brand_key"], unique=False)


def downgrade() -> None:
    if _has_table("quality_visits"):
        with op.batch_alter_table("quality_visits") as batch_op:
            batch_op.drop_index("ix_quality_visits_brand_key")
            if _has_column("quality_visits", "brand_key"):
                batch_op.drop_column("brand_key")

    if _has_table("quality_visit_sections"):
        with op.batch_alter_table("quality_visit_sections") as batch_op:
            batch_op.drop_index("ix_quality_visit_sections_brand_key")
            if _has_column("quality_visit_sections", "brand_key"):
                batch_op.drop_column("brand_key")
