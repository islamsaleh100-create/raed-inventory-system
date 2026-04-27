"""Documents module — Phase F3.1

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-04-20 09:00:00

Changes:
  + documents (new table)
      id, owner_type (branch|employee),
      branch_id → branches, user_id → users (one of the two must be set),
      doc_type (enum), title, issuer, doc_number,
      issue_date, expiry_date (indexed, NOT NULL), reminder_days (default 30),
      file_path, file_name, mime_type, size_bytes,
      notes,
      is_archived, renewed_from_id → documents, last_reminder_at,
      uploaded_by → users, created_at, updated_at, is_deleted, tenant_id
      Indexes:
        ix_documents_expiry_active (expiry_date, is_archived, is_deleted)
        ix_documents_owner_branch  (owner_type, branch_id)
        ix_documents_owner_user    (owner_type, user_id)
"""
from alembic import op
import sqlalchemy as sa


revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


DOC_OWNER_TYPES = ("branch", "employee")
DOC_TYPES = (
    "municipality_license",
    "civil_defense_license",
    "commercial_registration",
    "food_safety_permit",
    "branch_other",
    "health_certificate",
    "national_id",
    "work_permit",
    "work_contract",
    "employee_other",
)


def upgrade():
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_type",
            sa.Enum(*DOC_OWNER_TYPES, name="documentownertype"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.Integer(),
                  sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "doc_type",
            sa.Enum(*DOC_TYPES, name="documenttype"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("issuer", sa.String(150), nullable=True),
        sa.Column("doc_number", sa.String(100), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("reminder_days", sa.Integer(), nullable=False,
                  server_default="30"),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("renewed_from_id", sa.Integer(),
                  sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("last_reminder_at", sa.DateTime(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("tenant_id", sa.Integer(), nullable=False,
                  server_default="1"),
        # Integrity guard: one of branch_id / user_id must be set based on owner_type
        sa.CheckConstraint(
            "(owner_type = 'branch'   AND branch_id IS NOT NULL AND user_id   IS NULL) OR "
            "(owner_type = 'employee' AND user_id   IS NOT NULL AND branch_id IS NULL)",
            name="ck_documents_owner_ref",
        ),
    )

    op.create_index("ix_documents_expiry_active", "documents",
                    ["expiry_date", "is_archived", "is_deleted"])
    op.create_index("ix_documents_owner_branch",  "documents",
                    ["owner_type", "branch_id"])
    op.create_index("ix_documents_owner_user",    "documents",
                    ["owner_type", "user_id"])
    op.create_index("ix_documents_doc_type",      "documents",
                    ["doc_type"])
    op.create_index("ix_documents_tenant",        "documents",
                    ["tenant_id"])


def downgrade():
    op.drop_index("ix_documents_tenant",        table_name="documents")
    op.drop_index("ix_documents_doc_type",      table_name="documents")
    op.drop_index("ix_documents_owner_user",    table_name="documents")
    op.drop_index("ix_documents_owner_branch",  table_name="documents")
    op.drop_index("ix_documents_expiry_active", table_name="documents")
    op.drop_table("documents")
    # Drop enum types (PostgreSQL). On SQLite this is a no-op.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="documenttype").drop(bind, checkfirst=True)
        sa.Enum(name="documentownertype").drop(bind, checkfirst=True)
