"""Add branch_item_availability and item_change_requests tables

These two tables were previously created at runtime via startup_schema.py
(Base.metadata.create_all). This migration brings them under Alembic control
so that a fresh `alembic upgrade head` on PostgreSQL creates them correctly
without relying on the runtime fallback.

Revision ID: c1d2e3f4a5b6
Revises: 89aedce3fd41
Create Date: 2026-06-14 00:01:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "89aedce3fd41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── branch_item_availability ─────────────────────────────────────────────
    op.create_table(
        "branch_item_availability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("added_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("removed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "item_id", name="uq_branch_item_availability"),
    )
    op.create_index("ix_bia_branch_id", "branch_item_availability", ["branch_id"])
    op.create_index("ix_bia_item_id", "branch_item_availability", ["item_id"])

    # ── item_change_requests ─────────────────────────────────────────────────
    op.create_table(
        "item_change_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_no", sa.String(40), nullable=False),
        sa.Column("request_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=True),
        sa.Column("proposed_item_name_ar", sa.String(200), nullable=True),
        sa.Column("proposed_item_name_en", sa.String(200), nullable=True),
        sa.Column("proposed_item_code", sa.String(50), nullable=True),
        sa.Column("proposed_unit", sa.String(80), nullable=True),
        sa.Column("proposed_source_type", sa.String(30), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_no"),
    )
    op.create_index("ix_icr_request_no", "item_change_requests", ["request_no"])
    op.create_index("ix_icr_request_type", "item_change_requests", ["request_type"])
    op.create_index("ix_icr_status", "item_change_requests", ["status"])
    op.create_index("ix_icr_target_type", "item_change_requests", ["target_type"])
    op.create_index("ix_icr_warehouse_id", "item_change_requests", ["warehouse_id"])
    op.create_index("ix_icr_branch_id", "item_change_requests", ["branch_id"])
    op.create_index("ix_icr_item_id", "item_change_requests", ["item_id"])
    op.create_index("ix_icr_requested_by", "item_change_requests", ["requested_by"])


def downgrade() -> None:
    op.drop_table("item_change_requests")
    op.drop_table("branch_item_availability")
