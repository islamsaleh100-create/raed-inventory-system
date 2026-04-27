"""
Sales Channels Unification & Reconciliation — SQLAlchemy models.

Pack C / Phase 1 (SPEC v3). These are imported at the bottom of
app/models/__init__.py to ensure SQLAlchemy picks up the tables via Base.metadata.
"""
import enum

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Numeric,
    UniqueConstraint, Index, CheckConstraint, func
)
from sqlalchemy.orm import relationship

from app.database import Base


# ─────────────────────────────────────────────
# ENUMS (string-valued for portability; stored as VARCHAR)
# ─────────────────────────────────────────────
class ChannelType(str, enum.Enum):
    delivery_app = "delivery_app"
    payment_method = "payment_method"


class ClosureScopeType(str, enum.Enum):
    all = "all"
    branch = "branch"


class ReconciliationStatus(str, enum.Enum):
    match = "match"
    minor = "minor"
    major = "major"


class ImportSource(str, enum.Enum):
    manual = "manual"
    csv = "csv"


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────
class SalesChannel(Base):
    __tablename__ = "sales_channels"

    id = Column(Integer, primary_key=True)
    code = Column(String(30), nullable=False, unique=True)
    name_ar = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # ChannelType
    commission_rate = Column(Numeric(5, 2), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=func.current_timestamp())

    __table_args__ = (
        CheckConstraint(
            "type IN ('delivery_app','payment_method')",
            name="ck_sales_channels_type",
        ),
        Index("ix_sales_channels_type", "type"),
    )

    def __repr__(self):
        return f"<SalesChannel {self.code} ({self.type})>"


class BranchDailySale(Base):
    __tablename__ = "branch_daily_sales"

    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    sales_date = Column(Date, nullable=False)
    channel_id = Column(Integer, ForeignKey("sales_channels.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    orders_count = Column(Integer, nullable=True)

    # Audit fields
    submitted_at = Column(DateTime, nullable=False, default=func.current_timestamp())
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    entered_by_role = Column(String(32), nullable=True)
    on_behalf_of = Column(Boolean, nullable=False, default=False, server_default="0")
    last_edited_at = Column(DateTime, nullable=True)
    last_edited_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    edit_reason = Column(Text, nullable=True)

    channel = relationship("SalesChannel", lazy="joined")
    branch = relationship("Branch", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "branch_id", "sales_date", "channel_id",
            name="uq_branch_daily_sales_branch_date_channel",
        ),
        CheckConstraint("amount >= 0", name="ck_branch_daily_sales_amount_nonneg"),
        CheckConstraint(
            "orders_count IS NULL OR orders_count >= 0",
            name="ck_branch_daily_sales_count_nonneg",
        ),
        Index(
            "ix_branch_daily_sales_branch_date",
            "branch_id", "sales_date",
        ),
        Index("ix_branch_daily_sales_date", "sales_date"),
    )


class AppMonthlyStatement(Base):
    __tablename__ = "app_monthly_statements"

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("sales_channels.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    statement_month = Column(String(7), nullable=False)  # 'YYYY-MM'
    app_reported_amount = Column(Numeric(12, 2), nullable=False)
    app_reported_count = Column(Integer, nullable=True)
    commission_rate = Column(Numeric(5, 2), nullable=False)
    commission_amount = Column(Numeric(12, 2), nullable=False)
    net_amount = Column(Numeric(12, 2), nullable=False)
    import_source = Column(String(10), nullable=False)
    csv_filename = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.current_timestamp())
    updated_at = Column(
        DateTime, nullable=False,
        default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    channel = relationship("SalesChannel", lazy="joined")
    branch = relationship("Branch", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "branch_id", "statement_month",
            name="uq_app_statements_channel_branch_month",
        ),
        CheckConstraint(
            "import_source IN ('manual','csv')",
            name="ck_app_statements_import_source",
        ),
        CheckConstraint(
            "app_reported_amount >= 0",
            name="ck_app_statements_amount_nonneg",
        ),
    )


class MonthlyClosure(Base):
    __tablename__ = "monthly_closures"

    id = Column(Integer, primary_key=True)
    month = Column(String(7), nullable=False)
    scope_type = Column(String(10), nullable=False)  # 'all' or 'branch'
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    closed_at = Column(DateTime, nullable=False, default=func.current_timestamp())
    reopen_reason = Column(Text, nullable=True)
    reopened_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reopened_at = Column(DateTime, nullable=True)

    branch = relationship("Branch", lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('all','branch')",
            name="ck_monthly_closures_scope_type",
        ),
        CheckConstraint(
            "(scope_type='all' AND branch_id IS NULL) "
            "OR (scope_type='branch' AND branch_id IS NOT NULL)",
            name="ck_monthly_closures_scope_consistency",
        ),
        # Partial unique indexes are created in Alembic migration (not declaratively here).
        Index("ix_monthly_closures_month", "month"),
    )

    @property
    def is_active(self) -> bool:
        """True = currently locked (not reopened)."""
        return self.reopened_at is None


class ReconciliationSnapshot(Base):
    __tablename__ = "reconciliation_snapshots"

    id = Column(Integer, primary_key=True)
    closure_id = Column(Integer, ForeignKey("monthly_closures.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("sales_channels.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    statement_month = Column(String(7), nullable=False)

    branch_total = Column(Numeric(12, 2), nullable=False)
    app_total = Column(Numeric(12, 2), nullable=False)
    variance_amount = Column(Numeric(12, 2), nullable=False)
    variance_percent = Column(Numeric(7, 2), nullable=True)

    branch_count = Column(Integer, nullable=True)
    app_count = Column(Integer, nullable=True)
    count_variance = Column(Integer, nullable=True)

    status = Column(String(10), nullable=False)  # match/minor/major
    commission_rate_used = Column(Numeric(5, 2), nullable=True)
    generated_at = Column(DateTime, nullable=False, default=func.current_timestamp())

    __table_args__ = (
        CheckConstraint(
            "status IN ('match','minor','major')",
            name="ck_recon_snapshots_status",
        ),
        Index("ix_recon_snapshots_month", "statement_month"),
        Index("ix_recon_snapshots_branch_channel", "branch_id", "channel_id"),
    )


__all__ = [
    "ChannelType",
    "ClosureScopeType",
    "ReconciliationStatus",
    "ImportSource",
    "SalesChannel",
    "BranchDailySale",
    "AppMonthlyStatement",
    "MonthlyClosure",
    "ReconciliationSnapshot",
]
