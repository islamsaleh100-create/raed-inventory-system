"""Add branch shift operations tables

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-08-15 02:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.create_table(
        "branch_shift_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("shift_number", sa.Integer(), nullable=False),
        sa.Column("shift_name_ar", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "shift_number", "effective_from", name="uq_branch_shift_config_from"),
    )
    op.create_index("ix_branch_shift_configs_branch_shift", "branch_shift_configs", ["branch_id", "shift_number"])

    op.create_table(
        "branch_shifts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("shift_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("opened_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("exception_type", sa.String(30), nullable=True),
        sa.Column("exception_reason", sa.String(300), nullable=True),
        sa.Column("exception_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("exception_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "shift_date", "shift_number", name="uq_branch_shift_day"),
    )
    op.create_index("ix_branch_shifts_branch_date", "branch_shifts", ["branch_id", "shift_date"])

    op.create_table(
        "brand_shift_count_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "item_id", name="uq_brand_shift_count_item"),
    )

    op.create_table(
        "branch_shift_count_exclusions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "item_id", name="uq_branch_shift_count_exclusion"),
    )

    op.create_table(
        "branch_shift_counts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("branch_shifts.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("items_frozen_at", sa.DateTime(), nullable=False),
        sa.Column("general_notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shift_id"),
    )

    op.create_table(
        "branch_shift_count_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("count_id", sa.Integer(), sa.ForeignKey("branch_shift_counts.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("item_name_snapshot", sa.String(150), nullable=False),
        sa.Column("unit_snapshot", sa.String(30), nullable=False),
        sa.Column("opening_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("received_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("returned_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("damaged_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("closing_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("movement_diff", sa.Numeric(12, 2), nullable=True),
        sa.Column("movement_exception_reason", sa.String(300), nullable=True),
        sa.Column("item_notes", sa.Text(), nullable=True),
        sa.Column("row_status", sa.String(20), nullable=False, server_default="incomplete"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("count_id", "item_id", name="uq_branch_shift_count_line_item"),
        sa.CheckConstraint("opening_balance >= 0", name="ck_shift_count_line_opening_nonneg"),
        sa.CheckConstraint("received_qty IS NULL OR received_qty >= 0", name="ck_shift_count_line_received_nonneg"),
        sa.CheckConstraint("returned_qty IS NULL OR returned_qty >= 0", name="ck_shift_count_line_returned_nonneg"),
        sa.CheckConstraint("damaged_qty IS NULL OR damaged_qty >= 0", name="ck_shift_count_line_damaged_nonneg"),
        sa.CheckConstraint("closing_balance IS NULL OR closing_balance >= 0", name="ck_shift_count_line_closing_nonneg"),
    )

    op.create_table(
        "branch_shift_cash",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("branch_shifts.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_sale", sa.Numeric(12, 2), nullable=True),
        sa.Column("bill_count", sa.Integer(), nullable=True),
        sa.Column("mada_sales", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_sales", sa.Numeric(12, 2), nullable=True),
        sa.Column("app_sales", sa.Numeric(12, 2), nullable=True),
        sa.Column("refund_bill", sa.Numeric(12, 2), nullable=True),
        sa.Column("exchange_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("expiry_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_expense", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_float_carried_forward", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_deposited", sa.Numeric(12, 2), nullable=True),
        sa.Column("expense_type", sa.String(30), nullable=True),
        sa.Column("expense_details", sa.String(300), nullable=True),
        sa.Column("shift_notes", sa.Text(), nullable=True),
        sa.Column("cash_variance", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_variance_reason", sa.String(300), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shift_id"),
    )

    op.create_table(
        "branch_shift_reopen_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("branch_shifts.id"), nullable=False),
        sa.Column("target", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("reopened_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reopened_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_branch_shift_reopen_shift_at", "branch_shift_reopen_events", ["shift_id", "reopened_at"])

    if is_pg:
        op.execute(
            """
            ALTER TABLE branch_shift_configs
            ADD CONSTRAINT ex_branch_shift_config_no_overlap
            EXCLUDE USING gist (
                branch_id WITH =,
                shift_number WITH =,
                daterange(effective_from, COALESCE(effective_to, 'infinity'::date), '[]') WITH &&
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE branch_shift_configs DROP CONSTRAINT IF EXISTS ex_branch_shift_config_no_overlap"
        )

    op.drop_index("ix_branch_shift_reopen_shift_at", table_name="branch_shift_reopen_events")
    op.drop_table("branch_shift_reopen_events")
    op.drop_table("branch_shift_cash")
    op.drop_table("branch_shift_count_lines")
    op.drop_table("branch_shift_counts")
    op.drop_table("branch_shift_count_exclusions")
    op.drop_table("brand_shift_count_items")
    op.drop_index("ix_branch_shifts_branch_date", table_name="branch_shifts")
    op.drop_table("branch_shifts")
    op.drop_index("ix_branch_shift_configs_branch_shift", table_name="branch_shift_configs")
    op.drop_table("branch_shift_configs")
