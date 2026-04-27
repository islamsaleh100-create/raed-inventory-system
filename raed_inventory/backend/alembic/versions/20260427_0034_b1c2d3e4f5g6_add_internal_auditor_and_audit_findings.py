"""Add internal auditor role and audit findings table.

Revision ID: b1c2d3e4f5g6
Revises: a4b5c6d7e8f9
Create Date: 2026-04-27 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5g6"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        ctx = op.get_context()
        with ctx.autocommit_block():
            op.execute("ALTER TYPE rolename ADD VALUE IF NOT EXISTS 'internal_auditor'")

    op.create_table(
        "audit_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("finding_no", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.UniqueConstraint("finding_no", name="uq_audit_findings_finding_no"),
    )
    op.create_index("idx_audit_findings_entity", "audit_findings", ["entity_type", "entity_id"])
    op.create_index("idx_audit_findings_severity", "audit_findings", ["severity"])
    op.create_index("idx_audit_findings_status", "audit_findings", ["status"])
    op.create_index("idx_audit_findings_created_by", "audit_findings", ["created_by"])

    op.execute(
        sa.text(
            """
            INSERT INTO roles (name, display_name, description, created_at)
            SELECT 'internal_auditor', 'مراجع داخلي', 'Read-only audit oversight with finding creation', CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'internal_auditor')
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_audit_findings_created_by", table_name="audit_findings")
    op.drop_index("idx_audit_findings_status", table_name="audit_findings")
    op.drop_index("idx_audit_findings_severity", table_name="audit_findings")
    op.drop_index("idx_audit_findings_entity", table_name="audit_findings")
    op.drop_table("audit_findings")
    op.execute("DELETE FROM roles WHERE name = 'internal_auditor'")
    # Enum value intentionally remains in PostgreSQL on downgrade.
