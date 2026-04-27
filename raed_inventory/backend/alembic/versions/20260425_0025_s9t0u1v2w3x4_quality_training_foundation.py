"""quality and training foundation tables if missing

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-04-25 21:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def _enum(*values, name: str):
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


quality_visit_status = _enum("draft", "submitted", "reviewed", "closed", name="qualityvisitstatus")
quality_response_status = _enum("yes", "no", "na", name="qualityresponsestatus")
training_role_type = _enum("branch_employee", "branch_manager", name="trainingroletype")
assessment_status = _enum("draft", "submitted", "approved", "certified", "needs_reeval", name="assessmentstatus")
assessment_verdict = _enum("passed", "conditional", "failed", name="assessmentverdict")


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table: str) -> bool:
    try:
        return _insp().has_table(table)
    except Exception:
        return False


def _has_index(table: str, index_name: str) -> bool:
    try:
        return index_name in {i["name"] for i in _insp().get_indexes(table)}
    except Exception:
        return False


def _ensure_index(name: str, table: str, columns) -> None:
    if _has_table(table) and not _has_index(table, name):
        op.create_index(name, table, columns)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        quality_visit_status,
        quality_response_status,
        training_role_type,
        assessment_status,
        assessment_verdict,
    ):
        enum_type.create(bind, checkfirst=True)

    if not _has_table("quality_visit_sections"):
        op.create_table(
            "quality_visit_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("brand_key", sa.String(length=32), nullable=True),
            sa.Column("name_ar", sa.String(length=100), nullable=False),
            sa.Column("name_en", sa.String(length=100), nullable=False),
            sa.Column("order", sa.Integer(), nullable=True),
            sa.Column("weight", sa.Numeric(5, 2), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        )
        op.create_index("ix_quality_visit_sections_brand_key", "quality_visit_sections", ["brand_key"])

    if not _has_table("quality_visit_items"):
        op.create_table(
            "quality_visit_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("quality_visit_sections.id"), nullable=False),
            sa.Column("text_ar", sa.Text(), nullable=False),
            sa.Column("text_en", sa.Text(), nullable=True),
            sa.Column("benchmark_ar", sa.Text(), nullable=True),
            sa.Column("benchmark_en", sa.Text(), nullable=True),
            sa.Column("response_type", sa.String(length=10), nullable=False, server_default="yes_no"),
            sa.Column("numeric_unit", sa.String(length=20), nullable=True),
            sa.Column("order", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        )

    if not _has_table("quality_visits"):
        op.create_table(
            "quality_visits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
            sa.Column("brand_key", sa.String(length=32), nullable=True),
            sa.Column("visitor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("branch_in_charge", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("visit_date", sa.Date(), nullable=False),
            sa.Column("shift", sa.String(length=20), nullable=True),
            sa.Column("status", quality_visit_status, nullable=True),
            sa.Column("compliance_pct", sa.Numeric(5, 2), nullable=True),
            sa.Column("summary_notes", sa.Text(), nullable=True),
            sa.Column("follow_up_date", sa.Date(), nullable=True),
            sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("visitor_signature", sa.String(length=200), nullable=True),
            sa.Column("visitor_signed_at", sa.DateTime(), nullable=True),
            sa.Column("branch_mgr_signature", sa.String(length=200), nullable=True),
            sa.Column("branch_mgr_signed_at", sa.DateTime(), nullable=True),
            sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        )
        op.create_index("ix_quality_visits_brand_key", "quality_visits", ["brand_key"])

    if not _has_table("quality_visit_responses"):
        op.create_table(
            "quality_visit_responses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("visit_id", sa.Integer(), sa.ForeignKey("quality_visits.id"), nullable=False),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("quality_visit_items.id"), nullable=False),
            sa.Column("status", quality_response_status, nullable=True),
            sa.Column("numeric_value", sa.Numeric(12, 2), nullable=True),
            sa.Column("text_value", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("corrective_action", sa.Text(), nullable=True),
            sa.Column("action_owner", sa.String(length=100), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("is_resolved", sa.Boolean(), nullable=True, server_default=sa.text("false")),
            sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
        )

    if not _has_table("quality_visit_attachments"):
        op.create_table(
            "quality_visit_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("response_id", sa.Integer(), sa.ForeignKey("quality_visit_responses.id", ondelete="CASCADE"), nullable=True),
            sa.Column("visit_id", sa.Integer(), sa.ForeignKey("quality_visits.id", ondelete="CASCADE"), nullable=True),
            sa.Column("file_path", sa.String(length=500), nullable=False),
            sa.Column("original_name", sa.String(length=255), nullable=True),
            sa.Column("mime_type", sa.String(length=100), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("kind", sa.String(length=20), nullable=True, server_default="photo"),
            sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    _ensure_index("ix_qva_response", "quality_visit_attachments", ["response_id"])
    _ensure_index("ix_qva_visit_id", "quality_visit_attachments", ["visit_id"])

    if not _has_table("training_templates"):
        op.create_table(
            "training_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role_type", training_role_type, nullable=False),
            sa.Column("name_ar", sa.String(length=200), nullable=False),
            sa.Column("name_en", sa.String(length=200), nullable=True),
            sa.Column("version", sa.String(length=10), nullable=True, server_default="v1.0"),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if not _has_table("training_template_sections"):
        op.create_table(
            "training_template_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("template_id", sa.Integer(), sa.ForeignKey("training_templates.id"), nullable=False),
            sa.Column("name_ar", sa.String(length=100), nullable=False),
            sa.Column("name_en", sa.String(length=100), nullable=True),
            sa.Column("order", sa.Integer(), nullable=True),
            sa.Column("weight", sa.Numeric(5, 2), nullable=True),
        )

    if not _has_table("training_template_items"):
        op.create_table(
            "training_template_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("training_template_sections.id"), nullable=False),
            sa.Column("text_ar", sa.Text(), nullable=False),
            sa.Column("text_en", sa.Text(), nullable=True),
            sa.Column("benchmark_ar", sa.Text(), nullable=True),
            sa.Column("benchmark_en", sa.Text(), nullable=True),
            sa.Column("order", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        )

    if not _has_table("training_assessments"):
        op.create_table(
            "training_assessments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("template_id", sa.Integer(), sa.ForeignKey("training_templates.id"), nullable=False),
            sa.Column("trainee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("trainer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
            sa.Column("assessment_date", sa.Date(), nullable=False),
            sa.Column("status", assessment_status, nullable=True),
            sa.Column("overall_score", sa.Numeric(4, 2), nullable=True),
            sa.Column("verdict", assessment_verdict, nullable=True),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("re_eval_date", sa.Date(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("evaluator_signature", sa.String(length=200), nullable=True),
            sa.Column("evaluator_signed_at", sa.DateTime(), nullable=True),
            sa.Column("approver_signature", sa.String(length=200), nullable=True),
            sa.Column("approver_signed_at", sa.DateTime(), nullable=True),
            sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if not _has_table("training_assessment_items"):
        op.create_table(
            "training_assessment_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("training_assessments.id"), nullable=False),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("training_template_items.id"), nullable=False),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )

    if not _has_table("training_development_plans"):
        op.create_table(
            "training_development_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("training_assessments.id"), nullable=False),
            sa.Column("strengths", sa.Text(), nullable=True),
            sa.Column("areas_for_improvement", sa.Text(), nullable=True),
            sa.Column("required_actions", sa.Text(), nullable=True),
            sa.Column("re_evaluation_date", sa.Date(), nullable=True),
            sa.UniqueConstraint("assessment_id", name="uq_training_development_plans_assessment_id"),
        )

    _ensure_index("ix_qv_branch_date", "quality_visits", ["branch_id", "visit_date"])
    _ensure_index("ix_qv_status", "quality_visits", ["status"])
    _ensure_index("ix_qv_responses_visit", "quality_visit_responses", ["visit_id"])
    _ensure_index("ix_train_branch_date", "training_assessments", ["branch_id", "assessment_date"])
    _ensure_index("ix_train_trainee", "training_assessments", ["trainee_id"])


def downgrade() -> None:
    for table, indexes in [
        ("training_assessments", ["ix_train_branch_date", "ix_train_trainee"]),
        ("quality_visit_responses", ["ix_qv_responses_visit"]),
        ("quality_visits", ["ix_qv_branch_date", "ix_qv_status", "ix_quality_visits_brand_key"]),
        ("quality_visit_sections", ["ix_quality_visit_sections_brand_key"]),
        ("quality_visit_attachments", ["ix_qva_response", "ix_qva_visit_id"]),
    ]:
        for idx in indexes:
            if _has_index(table, idx):
                op.drop_index(idx, table_name=table)

    for table in [
        "training_development_plans",
        "training_assessment_items",
        "training_assessments",
        "training_template_items",
        "training_template_sections",
        "training_templates",
        "quality_visit_attachments",
        "quality_visit_responses",
        "quality_visits",
        "quality_visit_items",
        "quality_visit_sections",
    ]:
        if _has_table(table):
            op.drop_table(table)

    bind = op.get_bind()
    for enum_type in (
        assessment_verdict,
        assessment_status,
        training_role_type,
        quality_response_status,
        quality_visit_status,
    ):
        enum_type.drop(bind, checkfirst=True)
