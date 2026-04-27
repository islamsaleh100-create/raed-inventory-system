"""Pack C / Phase 1 — Sales Channels Unification & Reconciliation tables

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-04-21 12:00:00

Creates the five tables for the Sales Channels module per SPEC v3:
    1. sales_channels               — channel definitions (10 seeded in separate script)
    2. branch_daily_sales           — daily sales per channel per branch (with audit)
    3. app_monthly_statements       — delivery app monthly statements
    4. monthly_closures             — per-branch or global month locks
    5. reconciliation_snapshots     — frozen reconciliation results upon closure

Key constraints:
- CHECK on monthly_closures enforces (scope_type='all' ⇔ branch_id IS NULL)
- Partial unique indexes on monthly_closures prevent duplicate closures
- orders_count rules (required for delivery_app, NULL for payment_method) are
  enforced at Service/Pydantic layer (not DDL) to remain portable.
"""
from alembic import op
import sqlalchemy as sa


revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ────────────────────────────────────────────────
    # 1) sales_channels
    # ────────────────────────────────────────────────
    op.create_table(
        "sales_channels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column(
            "type",
            sa.String(20),
            nullable=False,
        ),
        sa.Column("commission_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            "type IN ('delivery_app','payment_method')",
            name="ck_sales_channels_type",
        ),
    )
    op.create_index("ix_sales_channels_type", "sales_channels", ["type"])

    # ────────────────────────────────────────────────
    # 2) branch_daily_sales
    # ────────────────────────────────────────────────
    op.create_table(
        "branch_daily_sales",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("sales_date", sa.Date, nullable=False),
        sa.Column(
            "channel_id",
            sa.Integer,
            sa.ForeignKey("sales_channels.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("orders_count", sa.Integer, nullable=True),
        # audit
        sa.Column(
            "submitted_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column("submitted_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("last_edited_at", sa.DateTime, nullable=True),
        sa.Column(
            "last_edited_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("edit_reason", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "branch_id",
            "sales_date",
            "channel_id",
            name="uq_branch_daily_sales_branch_date_channel",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_branch_daily_sales_amount_nonneg"),
        sa.CheckConstraint(
            "orders_count IS NULL OR orders_count >= 0",
            name="ck_branch_daily_sales_count_nonneg",
        ),
    )
    op.create_index(
        "ix_branch_daily_sales_branch_date",
        "branch_daily_sales",
        ["branch_id", "sales_date"],
    )
    op.create_index("ix_branch_daily_sales_date", "branch_daily_sales", ["sales_date"])

    # ────────────────────────────────────────────────
    # 3) app_monthly_statements
    # ────────────────────────────────────────────────
    op.create_table(
        "app_monthly_statements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "channel_id",
            sa.Integer,
            sa.ForeignKey("sales_channels.id"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("statement_month", sa.String(7), nullable=False),  # 'YYYY-MM'
        sa.Column("app_reported_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("app_reported_count", sa.Integer, nullable=True),
        sa.Column("commission_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("import_source", sa.String(10), nullable=False),
        sa.Column("csv_filename", sa.String(255), nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint(
            "channel_id",
            "branch_id",
            "statement_month",
            name="uq_app_statements_channel_branch_month",
        ),
        sa.CheckConstraint(
            "import_source IN ('manual','csv')",
            name="ck_app_statements_import_source",
        ),
        sa.CheckConstraint(
            "app_reported_amount >= 0",
            name="ck_app_statements_amount_nonneg",
        ),
    )

    # ────────────────────────────────────────────────
    # 4) monthly_closures
    # ────────────────────────────────────────────────
    op.create_table(
        "monthly_closures",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("scope_type", sa.String(10), nullable=False),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("closed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "closed_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column("reopen_reason", sa.Text, nullable=True),
        sa.Column(
            "reopened_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("reopened_at", sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "scope_type IN ('all','branch')",
            name="ck_monthly_closures_scope_type",
        ),
        sa.CheckConstraint(
            "(scope_type='all' AND branch_id IS NULL) OR (scope_type='branch' AND branch_id IS NOT NULL)",
            name="ck_monthly_closures_scope_consistency",
        ),
    )
    # Partial unique indexes (supported by SQLite 3.8+ and PostgreSQL)
    op.execute(
        "CREATE UNIQUE INDEX ux_closures_all ON monthly_closures (month) "
        "WHERE scope_type = 'all'"
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_closures_branch ON monthly_closures (month, branch_id) "
        "WHERE scope_type = 'branch'"
    )
    op.create_index("ix_monthly_closures_month", "monthly_closures", ["month"])

    # ────────────────────────────────────────────────
    # 5) reconciliation_snapshots
    # ────────────────────────────────────────────────
    op.create_table(
        "reconciliation_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "closure_id",
            sa.Integer,
            sa.ForeignKey("monthly_closures.id"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.Integer,
            sa.ForeignKey("sales_channels.id"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.Integer, sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("statement_month", sa.String(7), nullable=False),
        sa.Column("branch_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("app_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("variance_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("variance_percent", sa.Numeric(7, 2), nullable=True),
        sa.Column("branch_count", sa.Integer, nullable=True),
        sa.Column("app_count", sa.Integer, nullable=True),
        sa.Column("count_variance", sa.Integer, nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("commission_rate_used", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            "status IN ('match','minor','major')",
            name="ck_recon_snapshots_status",
        ),
    )
    op.create_index(
        "ix_recon_snapshots_month",
        "reconciliation_snapshots",
        ["statement_month"],
    )
    op.create_index(
        "ix_recon_snapshots_branch_channel",
        "reconciliation_snapshots",
        ["branch_id", "channel_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recon_snapshots_branch_channel", table_name="reconciliation_snapshots")
    op.drop_index("ix_recon_snapshots_month", table_name="reconciliation_snapshots")
    op.drop_table("reconciliation_snapshots")

    op.drop_index("ix_monthly_closures_month", table_name="monthly_closures")
    op.execute("DROP INDEX IF EXISTS ux_closures_branch")
    op.execute("DROP INDEX IF EXISTS ux_closures_all")
    op.drop_table("monthly_closures")

    op.drop_table("app_monthly_statements")

    op.drop_index("ix_branch_daily_sales_date", table_name="branch_daily_sales")
    op.drop_index("ix_branch_daily_sales_branch_date", table_name="branch_daily_sales")
    op.drop_table("branch_daily_sales")

    op.drop_index("ix_sales_channels_type", table_name="sales_channels")
    op.drop_table("sales_channels")
