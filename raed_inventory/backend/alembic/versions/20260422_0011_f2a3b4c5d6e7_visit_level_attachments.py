"""Visit-level attachments on quality visits — I3

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-04-22 09:00:00

Allows attaching photos/files to a quality visit itself (not only to a
specific checklist response). Adds a nullable ``visit_id`` FK to
``quality_visit_attachments`` and relaxes ``response_id`` to nullable so
exactly one of the two can be set.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # Fresh databases may not yet have the quality foundation tables because the
    # historical chain introduced I3 before the later quality foundation merge.
    # In that case, let the foundation migration create the final table shape.
    if not insp.has_table("quality_visits") or not insp.has_table("quality_visit_responses"):
        return

    # Dev DBs sometimes reached e1f2a3b4c5d6 without c9d0e1f2a3b4 having created this
    # table (e.g. failed early migrations then manual stamp). Build I3 shape in one step.
    if not insp.has_table("quality_visit_attachments"):
        op.create_table(
            "quality_visit_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "response_id",
                sa.Integer(),
                sa.ForeignKey("quality_visit_responses.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "visit_id",
                sa.Integer(),
                sa.ForeignKey("quality_visits.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("original_name", sa.String(255), nullable=True),
            sa.Column("mime_type", sa.String(100), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("kind", sa.String(20), nullable=False, server_default="photo"),
            sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column(
                "uploaded_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_qva_response",
            "quality_visit_attachments",
            ["response_id"],
        )
        op.create_index(
            "ix_qva_visit_id",
            "quality_visit_attachments",
            ["visit_id"],
        )
        return

    op.add_column(
        "quality_visit_attachments",
        sa.Column("visit_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_qva_visit_id",
        "quality_visit_attachments",
        "quality_visits",
        ["visit_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_qva_visit_id",
        "quality_visit_attachments",
        ["visit_id"],
    )
    # Relax response_id to nullable so visit-level attachments can skip it
    with op.batch_alter_table("quality_visit_attachments") as batch_op:
        batch_op.alter_column(
            "response_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    # Drop any visit-level attachments before reverting, else rows would be orphaned
    op.execute(
        "DELETE FROM quality_visit_attachments "
        "WHERE visit_id IS NOT NULL AND response_id IS NULL"
    )
    with op.batch_alter_table("quality_visit_attachments") as batch_op:
        batch_op.alter_column(
            "response_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
    op.drop_index("ix_qva_visit_id", table_name="quality_visit_attachments")
    op.drop_constraint("fk_qva_visit_id", "quality_visit_attachments", type_="foreignkey")
    op.drop_column("quality_visit_attachments", "visit_id")
