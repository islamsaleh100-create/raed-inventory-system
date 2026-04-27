"""Quality/Training — real ONDA templates support

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-18 01:00:00

Changes:
  quality_visit_items:
    + response_type   VARCHAR(10)  NOT NULL DEFAULT 'yes_no'   -- yes_no | numeric | text
    + numeric_unit    VARCHAR(20)  NULL                        -- optional unit (SAR, °C, ppm, count...)
    + benchmark_ar    TEXT         NULL                        -- expected / standard text
    + benchmark_en    TEXT         NULL

  quality_visit_responses:
    + numeric_value   NUMERIC(12,2) NULL
    + text_value      TEXT          NULL

  training_templates:
    + name_en   VARCHAR(200) NULL

  training_template_sections:
    + name_en   VARCHAR(100) NULL

  training_template_items:
    + text_en       TEXT NULL
    + benchmark_en  TEXT NULL

  training_assessments:
    + rejection_reason TEXT NULL   -- reason when approver rejects (draft round-trip)

All columns nullable or defaulted to preserve existing rows.
Idempotent against SQLite by checking column existence before ALTER.
"""
from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        return column in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def _has_table(table: str) -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        return insp.has_table(table)
    except Exception:
        return False


def _add_col_if_missing(table: str, column: sa.Column):
    if not _has_table(table):
        return
    if _has_column(table, column.name):
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.add_column(column)


def upgrade() -> None:
    # quality_visit_items
    _add_col_if_missing(
        "quality_visit_items",
        sa.Column("response_type", sa.String(10), nullable=False, server_default="yes_no"),
    )
    _add_col_if_missing(
        "quality_visit_items",
        sa.Column("numeric_unit", sa.String(20), nullable=True),
    )
    _add_col_if_missing(
        "quality_visit_items",
        sa.Column("benchmark_ar", sa.Text(), nullable=True),
    )
    _add_col_if_missing(
        "quality_visit_items",
        sa.Column("benchmark_en", sa.Text(), nullable=True),
    )

    # quality_visit_responses
    _add_col_if_missing(
        "quality_visit_responses",
        sa.Column("numeric_value", sa.Numeric(12, 2), nullable=True),
    )
    _add_col_if_missing(
        "quality_visit_responses",
        sa.Column("text_value", sa.Text(), nullable=True),
    )

    # training_templates
    _add_col_if_missing(
        "training_templates",
        sa.Column("name_en", sa.String(200), nullable=True),
    )

    # training_template_sections
    _add_col_if_missing(
        "training_template_sections",
        sa.Column("name_en", sa.String(100), nullable=True),
    )

    # training_template_items
    _add_col_if_missing(
        "training_template_items",
        sa.Column("text_en", sa.Text(), nullable=True),
    )
    _add_col_if_missing(
        "training_template_items",
        sa.Column("benchmark_en", sa.Text(), nullable=True),
    )

    # training_assessments
    _add_col_if_missing(
        "training_assessments",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # Best-effort — SQLite batch mode handles drops
    for table, col in [
        ("training_assessments",       "rejection_reason"),
        ("training_template_items",    "benchmark_en"),
        ("training_template_items",    "text_en"),
        ("training_template_sections", "name_en"),
        ("training_templates",         "name_en"),
        ("quality_visit_responses",    "text_value"),
        ("quality_visit_responses",    "numeric_value"),
        ("quality_visit_items",        "benchmark_en"),
        ("quality_visit_items",        "benchmark_ar"),
        ("quality_visit_items",        "numeric_unit"),
        ("quality_visit_items",        "response_type"),
    ]:
        if _has_table(table) and _has_column(table, col):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column(col)
