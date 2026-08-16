"""Branch shift operations — inventory count + cash settlement (isolated module)."""
import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class BranchShiftStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    exception_locked = "exception_locked"


class BranchShiftExceptionType(str, enum.Enum):
    stuck_previous = "stuck_previous"
    branch_closed = "branch_closed"
    manual_gap = "manual_gap"


class ShiftSectionStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"


class ShiftCountRowStatus(str, enum.Enum):
    incomplete = "incomplete"
    valid = "valid"
    invalid = "invalid"


class ShiftReopenTarget(str, enum.Enum):
    count = "count"
    cash = "cash"
    both = "both"


class ShiftExpenseType(str, enum.Enum):
    INVOICES = "INVOICES"
    ADVANCE = "ADVANCE"
    HANDED_TO_PERSON = "HANDED_TO_PERSON"
    OPERATIONAL = "OPERATIONAL"
    OTHER = "OTHER"


class BranchShiftConfig(Base):
    __tablename__ = "branch_shift_configs"

    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    shift_number = Column(Integer, nullable=False)
    shift_name_ar = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    branch = relationship("Branch")

    __table_args__ = (
        UniqueConstraint("branch_id", "shift_number", "effective_from", name="uq_branch_shift_config_from"),
        Index("ix_branch_shift_configs_branch_shift", "branch_id", "shift_number"),
    )


class BranchShift(Base):
    __tablename__ = "branch_shifts"

    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    shift_date = Column(Date, nullable=False)
    shift_number = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default=BranchShiftStatus.draft.value)
    opened_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    opened_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    submitted_at = Column(DateTime, nullable=True)
    exception_type = Column(String(30), nullable=True)
    exception_reason = Column(String(300), nullable=True)
    exception_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    exception_at = Column(DateTime, nullable=True)

    branch = relationship("Branch", foreign_keys=[branch_id])
    opener = relationship("User", foreign_keys=[opened_by])
    count = relationship("BranchShiftCount", back_populates="shift", uselist=False)
    cash = relationship("BranchShiftCash", back_populates="shift", uselist=False)
    reopen_events = relationship("BranchShiftReopenEvent", back_populates="shift")

    __table_args__ = (
        UniqueConstraint("branch_id", "shift_date", "shift_number", name="uq_branch_shift_day"),
        Index("ix_branch_shifts_branch_date", "branch_id", "shift_date"),
    )


class BrandShiftCountItem(Base):
    __tablename__ = "brand_shift_count_items"

    id = Column(Integer, primary_key=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    brand = relationship("Brand")
    item = relationship("Item")

    __table_args__ = (
        UniqueConstraint("brand_id", "item_id", name="uq_brand_shift_count_item"),
    )


class BranchShiftCountExclusion(Base):
    __tablename__ = "branch_shift_count_exclusions"

    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    reason = Column(String(300), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    branch = relationship("Branch")
    item = relationship("Item")

    __table_args__ = (
        UniqueConstraint("branch_id", "item_id", name="uq_branch_shift_count_exclusion"),
    )


class BranchShiftCount(Base):
    __tablename__ = "branch_shift_counts"

    id = Column(Integer, primary_key=True)
    shift_id = Column(Integer, ForeignKey("branch_shifts.id"), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default=ShiftSectionStatus.draft.value)
    items_frozen_at = Column(DateTime, nullable=False)
    general_notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    submitted_at = Column(DateTime, nullable=True)

    shift = relationship("BranchShift", back_populates="count")
    lines = relationship("BranchShiftCountLine", back_populates="count", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_branch_shift_counts_shift", "shift_id"),
    )


class BranchShiftCountLine(Base):
    __tablename__ = "branch_shift_count_lines"

    id = Column(Integer, primary_key=True)
    count_id = Column(Integer, ForeignKey("branch_shift_counts.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    item_name_snapshot = Column(String(150), nullable=False)
    unit_snapshot = Column(String(30), nullable=False)
    opening_balance = Column(Numeric(12, 2), nullable=False, default=0)
    received_qty = Column(Numeric(12, 2), nullable=True)
    returned_qty = Column(Numeric(12, 2), nullable=True)
    damaged_qty = Column(Numeric(12, 2), nullable=True)
    closing_balance = Column(Numeric(12, 2), nullable=True)
    movement_diff = Column(Numeric(12, 2), nullable=True)
    movement_exception_reason = Column(String(300), nullable=True)
    item_notes = Column(Text, nullable=True)
    row_status = Column(String(20), nullable=False, default=ShiftCountRowStatus.incomplete.value)

    count = relationship("BranchShiftCount", back_populates="lines")
    item = relationship("Item")

    __table_args__ = (
        UniqueConstraint("count_id", "item_id", name="uq_branch_shift_count_line_item"),
        CheckConstraint("opening_balance >= 0", name="ck_shift_count_line_opening_nonneg"),
        CheckConstraint("received_qty IS NULL OR received_qty >= 0", name="ck_shift_count_line_received_nonneg"),
        CheckConstraint("returned_qty IS NULL OR returned_qty >= 0", name="ck_shift_count_line_returned_nonneg"),
        CheckConstraint("damaged_qty IS NULL OR damaged_qty >= 0", name="ck_shift_count_line_damaged_nonneg"),
        CheckConstraint("closing_balance IS NULL OR closing_balance >= 0", name="ck_shift_count_line_closing_nonneg"),
    )


class BranchShiftCash(Base):
    __tablename__ = "branch_shift_cash"

    id = Column(Integer, primary_key=True)
    shift_id = Column(Integer, ForeignKey("branch_shifts.id"), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default=ShiftSectionStatus.draft.value)
    total_sale = Column(Numeric(12, 2), nullable=True)
    bill_count = Column(Integer, nullable=True)
    mada_sales = Column(Numeric(12, 2), nullable=True)
    cash_sales = Column(Numeric(12, 2), nullable=True)
    app_sales = Column(Numeric(12, 2), nullable=True)
    refund_bill = Column(Numeric(12, 2), nullable=True)
    exchange_amount = Column(Numeric(12, 2), nullable=True)
    expiry_amount = Column(Numeric(12, 2), nullable=True)
    cash_expense = Column(Numeric(12, 2), nullable=True)
    cash_float_carried_forward = Column(Numeric(12, 2), nullable=True)
    cash_deposited = Column(Numeric(12, 2), nullable=True)
    expense_type = Column(String(30), nullable=True)
    expense_details = Column(String(300), nullable=True)
    shift_notes = Column(Text, nullable=True)
    cash_variance = Column(Numeric(12, 2), nullable=True)
    cash_variance_reason = Column(String(300), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    submitted_at = Column(DateTime, nullable=True)

    shift = relationship("BranchShift", back_populates="cash")

    __table_args__ = (
        Index("ix_branch_shift_cash_shift", "shift_id"),
        CheckConstraint("total_sale IS NULL OR total_sale >= 0", name="ck_shift_cash_total_sale_nonneg"),
        CheckConstraint("mada_sales IS NULL OR mada_sales >= 0", name="ck_shift_cash_mada_nonneg"),
        CheckConstraint("cash_sales IS NULL OR cash_sales >= 0", name="ck_shift_cash_cash_sales_nonneg"),
        CheckConstraint("app_sales IS NULL OR app_sales >= 0", name="ck_shift_cash_app_nonneg"),
        CheckConstraint("refund_bill IS NULL OR refund_bill >= 0", name="ck_shift_cash_refund_nonneg"),
        CheckConstraint("exchange_amount IS NULL OR exchange_amount >= 0", name="ck_shift_cash_exchange_nonneg"),
        CheckConstraint("expiry_amount IS NULL OR expiry_amount >= 0", name="ck_shift_cash_expiry_nonneg"),
        CheckConstraint("cash_expense IS NULL OR cash_expense >= 0", name="ck_shift_cash_expense_nonneg"),
        CheckConstraint("cash_float_carried_forward IS NULL OR cash_float_carried_forward >= 0", name="ck_shift_cash_float_nonneg"),
        CheckConstraint("cash_deposited IS NULL OR cash_deposited >= 0", name="ck_shift_cash_deposited_nonneg"),
    )


class BranchShiftReopenEvent(Base):
    __tablename__ = "branch_shift_reopen_events"

    id = Column(Integer, primary_key=True)
    shift_id = Column(Integer, ForeignKey("branch_shifts.id"), nullable=False, index=True)
    target = Column(String(10), nullable=False)
    reason = Column(String(300), nullable=False)
    reopened_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    reopened_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    shift = relationship("BranchShift", back_populates="reopen_events")
    user = relationship("User", foreign_keys=[reopened_by])

    __table_args__ = (
        Index("ix_branch_shift_reopen_shift_at", "shift_id", "reopened_at"),
    )
