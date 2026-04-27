"""evaluation core phase 1

Revision ID: p6q7r8s9t0u1
Revises: m4n5o6p7q8r9
Create Date: 2026-04-25 05:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "p6q7r8s9t0u1"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


evaluation_type = sa.Enum("BRANCH", "EMPLOYEE", "STORE_VISIT", "MANAGER", "ROLE_SPECIFIC", name="evaluationtype")
target_mode = sa.Enum("BRANCH", "EMPLOYEE", "NONE", name="evaluationtargetmode")
version_status = sa.Enum("DRAFT", "PUBLISHED", "ARCHIVED", name="evaluationtemplateversionstatus")
evaluation_status = sa.Enum("DRAFT", "SUBMITTED", "REVIEWED", "ACTION_REQUIRED", "CLOSED", "CANCELLED", name="evaluationstatus")
action_plan_status = sa.Enum("OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED", name="evaluationactionplanstatus")
final_rating = sa.Enum("POOR", "NEEDS_IMPROVEMENT", "GOOD", "EXCELLENT", name="evaluationfinalrating")


def upgrade() -> None:
    op.create_table(
        "evaluation_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("evaluation_type", evaluation_type, nullable=False),
        sa.Column("target_mode", target_mode, nullable=False),
        sa.Column("target_role", sa.String(length=100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_evaluation_templates_brand_id", "evaluation_templates", ["brand_id"])

    op.create_table(
        "evaluation_template_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("evaluation_templates.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", version_status, nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("template_id", "version_no", name="uq_evaluation_template_version_no"),
    )
    op.create_index("ix_evaluation_template_versions_template_id", "evaluation_template_versions", ["template_id"])
    op.create_index("ix_evaluation_template_versions_status", "evaluation_template_versions", ["status"])

    op.create_table(
        "evaluation_template_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_version_id", sa.Integer(), sa.ForeignKey("evaluation_template_versions.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("weight_percent", sa.Numeric(6, 2), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_evaluation_template_sections_template_version_id", "evaluation_template_sections", ["template_version_id"])

    op.create_table(
        "evaluation_template_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("section_id", sa.Integer(), sa.ForeignKey("evaluation_template_sections.id"), nullable=False),
        sa.Column("question_text_ar", sa.Text(), nullable=False),
        sa.Column("question_text_en", sa.Text(), nullable=True),
        sa.Column("max_score", sa.Numeric(10, 3), nullable=False, server_default="5"),
        sa.Column("allow_na", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_note_if_low_score", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("low_score_threshold", sa.Numeric(10, 3), nullable=False, server_default="2"),
        sa.Column("requires_photo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_evaluation_template_questions_section_id", "evaluation_template_questions", ["section_id"])

    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("evaluation_templates.id"), nullable=False),
        sa.Column("template_version_id", sa.Integer(), sa.ForeignKey("evaluation_template_versions.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("evaluation_type", evaluation_type, nullable=False),
        sa.Column("target_mode", target_mode, nullable=False),
        sa.Column("evaluated_role", sa.String(length=100), nullable=True),
        sa.Column("evaluator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("evaluation_date", sa.Date(), nullable=False),
        sa.Column("status", evaluation_status, nullable=False),
        sa.Column("total_score", sa.Numeric(10, 3), nullable=True),
        sa.Column("total_percentage", sa.Numeric(6, 2), nullable=True),
        sa.Column("final_rating", final_rating, nullable=True),
        sa.Column("general_notes", sa.Text(), nullable=True),
        sa.Column("low_score_count", sa.Integer(), nullable=True),
        sa.Column("action_required_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    for col in ["template_id", "template_version_id", "brand_id", "branch_id", "employee_id", "evaluator_id", "status"]:
        op.create_index(f"ix_evaluations_{col}", "evaluations", [col])

    op.create_table(
        "evaluation_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("evaluations.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("evaluation_template_questions.id"), nullable=False),
        sa.Column("score", sa.Numeric(10, 3), nullable=True),
        sa.Column("is_na", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("question_text_snapshot", sa.Text(), nullable=False),
        sa.Column("section_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("max_score_snapshot", sa.Numeric(10, 3), nullable=False),
        sa.Column("section_weight_snapshot", sa.Numeric(6, 2), nullable=True),
        sa.Column("display_order_snapshot", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("evaluation_id", "question_id", name="uq_evaluation_answer_question"),
    )
    op.create_index("ix_evaluation_answers_evaluation_id", "evaluation_answers", ["evaluation_id"])
    op.create_index("ix_evaluation_answers_question_id", "evaluation_answers", ["question_id"])

    op.create_table(
        "evaluation_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("evaluations.id"), nullable=False),
        sa.Column("answer_id", sa.Integer(), sa.ForeignKey("evaluation_answers.id"), nullable=True),
        sa.Column("storage_disk", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_evaluation_attachments_evaluation_id", "evaluation_attachments", ["evaluation_id"])
    op.create_index("ix_evaluation_attachments_answer_id", "evaluation_attachments", ["answer_id"])

    op.create_table(
        "evaluation_action_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("evaluations.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("issue", sa.Text(), nullable=False),
        sa.Column("corrective_action", sa.Text(), nullable=False),
        sa.Column("responsible_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", action_plan_status, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    for col in ["evaluation_id", "branch_id", "employee_id", "status"]:
        op.create_index(f"ix_evaluation_action_plans_{col}", "evaluation_action_plans", [col])

    op.create_table(
        "evaluation_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("evaluations.id"), nullable=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("evaluation_templates.id"), nullable=True),
        sa.Column("template_version_id", sa.Integer(), sa.ForeignKey("evaluation_template_versions.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ["evaluation_id", "template_id", "template_version_id", "action"]:
        op.create_index(f"ix_evaluation_audit_logs_{col}", "evaluation_audit_logs", [col])


def downgrade() -> None:
    for table, indexes in {
        "evaluation_audit_logs": ["evaluation_id", "template_id", "template_version_id", "action"],
        "evaluation_action_plans": ["evaluation_id", "branch_id", "employee_id", "status"],
    }.items():
        for col in indexes:
            op.drop_index(f"ix_{table}_{col}", table_name=table)
        op.drop_table(table)
    op.drop_index("ix_evaluation_attachments_answer_id", table_name="evaluation_attachments")
    op.drop_index("ix_evaluation_attachments_evaluation_id", table_name="evaluation_attachments")
    op.drop_table("evaluation_attachments")
    op.drop_index("ix_evaluation_answers_question_id", table_name="evaluation_answers")
    op.drop_index("ix_evaluation_answers_evaluation_id", table_name="evaluation_answers")
    op.drop_table("evaluation_answers")
    for col in ["status", "evaluator_id", "employee_id", "branch_id", "brand_id", "template_version_id", "template_id"]:
        op.drop_index(f"ix_evaluations_{col}", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index("ix_evaluation_template_questions_section_id", table_name="evaluation_template_questions")
    op.drop_table("evaluation_template_questions")
    op.drop_index("ix_evaluation_template_sections_template_version_id", table_name="evaluation_template_sections")
    op.drop_table("evaluation_template_sections")
    op.drop_index("ix_evaluation_template_versions_status", table_name="evaluation_template_versions")
    op.drop_index("ix_evaluation_template_versions_template_id", table_name="evaluation_template_versions")
    op.drop_table("evaluation_template_versions")
    op.drop_index("ix_evaluation_templates_brand_id", table_name="evaluation_templates")
    op.drop_table("evaluation_templates")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        final_rating.drop(bind, checkfirst=True)
        action_plan_status.drop(bind, checkfirst=True)
        evaluation_status.drop(bind, checkfirst=True)
        version_status.drop(bind, checkfirst=True)
        target_mode.drop(bind, checkfirst=True)
        evaluation_type.drop(bind, checkfirst=True)
