"""Quality/Training E8 - attachments, signatures, and action audit."""

from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
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


def _has_index(table: str, index_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        return index_name in {i["name"] for i in insp.get_indexes(table)}
    except Exception:
        return False


def upgrade() -> None:
    if _has_table("quality_visit_responses") and not _has_table("quality_visit_attachments"):
        op.create_table(
            "quality_visit_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "response_id",
                sa.Integer(),
                sa.ForeignKey("quality_visit_responses.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("original_name", sa.String(255), nullable=True),
            sa.Column("mime_type", sa.String(100), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("kind", sa.String(20), nullable=False, server_default="photo"),
            sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if _has_table("quality_visit_attachments") and not _has_index("quality_visit_attachments", "ix_qva_response"):
        op.create_index("ix_qva_response", "quality_visit_attachments", ["response_id"])

    if _has_table("quality_visits"):
        with op.batch_alter_table("quality_visits") as batch_op:
            if not _has_column("quality_visits", "visitor_signature"):
                batch_op.add_column(sa.Column("visitor_signature", sa.String(200), nullable=True))
            if not _has_column("quality_visits", "visitor_signed_at"):
                batch_op.add_column(sa.Column("visitor_signed_at", sa.DateTime(), nullable=True))
            if not _has_column("quality_visits", "branch_mgr_signature"):
                batch_op.add_column(sa.Column("branch_mgr_signature", sa.String(200), nullable=True))
            if not _has_column("quality_visits", "branch_mgr_signed_at"):
                batch_op.add_column(sa.Column("branch_mgr_signed_at", sa.DateTime(), nullable=True))

    if _has_table("quality_visit_responses"):
        with op.batch_alter_table("quality_visit_responses") as batch_op:
            if not _has_column("quality_visit_responses", "resolved_by"):
                batch_op.add_column(sa.Column("resolved_by", sa.Integer(), nullable=True))
            if not _has_column("quality_visit_responses", "resolved_at"):
                batch_op.add_column(sa.Column("resolved_at", sa.DateTime(), nullable=True))

    if _has_table("training_assessments"):
        with op.batch_alter_table("training_assessments") as batch_op:
            if not _has_column("training_assessments", "evaluator_signature"):
                batch_op.add_column(sa.Column("evaluator_signature", sa.String(200), nullable=True))
            if not _has_column("training_assessments", "evaluator_signed_at"):
                batch_op.add_column(sa.Column("evaluator_signed_at", sa.DateTime(), nullable=True))
            if not _has_column("training_assessments", "approver_signature"):
                batch_op.add_column(sa.Column("approver_signature", sa.String(200), nullable=True))
            if not _has_column("training_assessments", "approver_signed_at"):
                batch_op.add_column(sa.Column("approver_signed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    if _has_table("training_assessments"):
        with op.batch_alter_table("training_assessments") as batch_op:
            if _has_column("training_assessments", "approver_signed_at"):
                batch_op.drop_column("approver_signed_at")
            if _has_column("training_assessments", "approver_signature"):
                batch_op.drop_column("approver_signature")
            if _has_column("training_assessments", "evaluator_signed_at"):
                batch_op.drop_column("evaluator_signed_at")
            if _has_column("training_assessments", "evaluator_signature"):
                batch_op.drop_column("evaluator_signature")

    if _has_table("quality_visit_responses"):
        with op.batch_alter_table("quality_visit_responses") as batch_op:
            if _has_column("quality_visit_responses", "resolved_at"):
                batch_op.drop_column("resolved_at")
            if _has_column("quality_visit_responses", "resolved_by"):
                batch_op.drop_column("resolved_by")

    if _has_table("quality_visits"):
        with op.batch_alter_table("quality_visits") as batch_op:
            if _has_column("quality_visits", "branch_mgr_signed_at"):
                batch_op.drop_column("branch_mgr_signed_at")
            if _has_column("quality_visits", "branch_mgr_signature"):
                batch_op.drop_column("branch_mgr_signature")
            if _has_column("quality_visits", "visitor_signed_at"):
                batch_op.drop_column("visitor_signed_at")
            if _has_column("quality_visits", "visitor_signature"):
                batch_op.drop_column("visitor_signature")

    if _has_table("quality_visit_attachments"):
        if _has_index("quality_visit_attachments", "ix_qva_response"):
            op.drop_index("ix_qva_response", table_name="quality_visit_attachments")
        op.drop_table("quality_visit_attachments")
