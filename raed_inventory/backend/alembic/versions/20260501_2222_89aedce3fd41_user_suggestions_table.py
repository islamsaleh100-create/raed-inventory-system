"""user_suggestions_table

Revision ID: 89aedce3fd41
Revises: b1c2d3e4f5g6
Create Date: 2026-05-01 22:22:06.344462+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "89aedce3fd41"
down_revision: Union[str, None] = "b1c2d3e4f5g6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(*values, name):
    """Build a dialect-aware ENUM type. Postgres uses native ENUM, SQLite uses VARCHAR."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


def upgrade() -> None:
    bind = op.get_bind()

    # Create enum types (Postgres only — SQLite inlines them)
    if bind.dialect.name == "postgresql":
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE suggestion_category AS ENUM ('ui','workflow','bug','feature','other'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE suggestion_priority AS ENUM ('low','medium','high'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE suggestion_status AS ENUM ('pending','reviewed','approved','rejected','implemented'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )

    suggestion_category = _enum("ui", "workflow", "bug", "feature", "other", name="suggestion_category")
    suggestion_priority = _enum("low", "medium", "high", name="suggestion_priority")
    suggestion_status = _enum("pending", "reviewed", "approved", "rejected", "implemented", name="suggestion_status")

    op.create_table(
        "user_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("role_at_creation", sa.String(length=50), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True, index=True),
        sa.Column("suggestion_text", sa.Text(), nullable=False),
        sa.Column("category", suggestion_category, nullable=False, server_default="other"),
        sa.Column("priority", suggestion_priority, nullable=False, server_default="medium"),
        sa.Column("status", suggestion_status, nullable=False, server_default="pending"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_index(
        "idx_user_suggestions_status_created",
        "user_suggestions",
        ["status", "created_at"],
    )
    op.create_index("idx_user_suggestions_category", "user_suggestions", ["category"])
    op.create_index("idx_user_suggestions_priority", "user_suggestions", ["priority"])


def downgrade() -> None:
    op.drop_index("idx_user_suggestions_priority", table_name="user_suggestions")
    op.drop_index("idx_user_suggestions_category", table_name="user_suggestions")
    op.drop_index("idx_user_suggestions_status_created", table_name="user_suggestions")
    op.drop_table("user_suggestions")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS suggestion_status")
        op.execute("DROP TYPE IF EXISTS suggestion_priority")
        op.execute("DROP TYPE IF EXISTS suggestion_category")
