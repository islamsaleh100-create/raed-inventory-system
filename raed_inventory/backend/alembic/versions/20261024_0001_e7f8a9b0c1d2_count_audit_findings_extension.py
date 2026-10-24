"""Count Audit: extend audit_findings + events + items

Revision ID: e7f8a9b0c1d2
Revises: a9b8c7d6e5f4
Create Date: 2026-10-24 00:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("audit_findings") as batch:
        batch.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("last_event_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("closed_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key("fk_audit_findings_branch_id", "branches", ["branch_id"], ["id"])
        batch.alter_column(
            "status",
            existing_type=sa.String(length=20),
            type_=sa.String(length=30),
            existing_nullable=False,
            existing_server_default="open",
        )
    op.create_index(
        "uq_audit_findings_client_request_id", "audit_findings", ["client_request_id"], unique=True
    )
    op.create_index(
        "idx_audit_findings_type_branch_status",
        "audit_findings",
        ["entity_type", "branch_id", "status"],
    )

    op.create_table(
        "audit_finding_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("finding_id", sa.Integer(), sa.ForeignKey("audit_findings.id"), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_role", sa.String(length=30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_audit_finding_events_finding", "audit_finding_events", ["finding_id", "created_at"])
    op.create_index(
        "uq_audit_finding_events_request",
        "audit_finding_events",
        ["finding_id", "client_request_id"],
        unique=True,
    )

    op.create_table(
        "audit_finding_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("finding_id", sa.Integer(), sa.ForeignKey("audit_findings.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("line_id", sa.Integer(), sa.ForeignKey("branch_shift_count_lines.id"), nullable=True),
        sa.Column("item_name_snapshot", sa.String(length=150), nullable=False),
        sa.Column("closing_balance_snapshot", sa.Numeric(12, 2), nullable=True),
        sa.Column("movement_diff_snapshot", sa.Numeric(12, 2), nullable=True),
        sa.UniqueConstraint("finding_id", "item_id", name="uq_audit_finding_items_finding_item"),
    )
    op.create_index("idx_audit_finding_items_finding", "audit_finding_items", ["finding_id"])
    op.create_index("idx_audit_finding_items_item", "audit_finding_items", ["item_id"])


def downgrade() -> None:
    op.drop_index("idx_audit_finding_items_item", table_name="audit_finding_items")
    op.drop_index("idx_audit_finding_items_finding", table_name="audit_finding_items")
    op.drop_table("audit_finding_items")
    op.drop_index("uq_audit_finding_events_request", table_name="audit_finding_events")
    op.drop_index("idx_audit_finding_events_finding", table_name="audit_finding_events")
    op.drop_table("audit_finding_events")
    op.drop_index("idx_audit_findings_type_branch_status", table_name="audit_findings")
    op.drop_index("uq_audit_findings_client_request_id", table_name="audit_findings")
    bind = op.get_bind()
    too_long = bind.execute(
        sa.text("SELECT COUNT(*) FROM audit_findings WHERE LENGTH(status) > 20")
    ).scalar()
    if too_long:
        raise RuntimeError(
            f"Cannot downgrade: {too_long} audit_findings rows have status longer than 20 chars; "
            "close/migrate them first (refusing to truncate)."
        )
    with op.batch_alter_table("audit_findings") as batch:
        batch.alter_column(
            "status",
            existing_type=sa.String(length=30),
            type_=sa.String(length=20),
            existing_nullable=False,
            existing_server_default="open",
        )
        batch.drop_constraint("fk_audit_findings_branch_id", type_="foreignkey")
        batch.drop_column("closed_at")
        batch.drop_column("last_event_at")
        batch.drop_column("client_request_id")
        batch.drop_column("branch_id")
