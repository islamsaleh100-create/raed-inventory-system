"""
Pydantic schemas for Sales Channels Unification & Reconciliation (Pack C / Phase 1).

Key rules (SPEC v3):
- orders_count is REQUIRED for delivery_app entries, FORBIDDEN for payment_method.
- amount >= 0 always; if amount > 0 and delivery_app then orders_count > 0.

For Pydantic schemas we cannot know the channel.type at validation time unless
it is passed via a factory. Hence the `create` schema accepts an optional
`channel_type` field (used only at validation, not persisted) so that the
service layer can still resolve the type from the channel_id server-side.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.sales_channels import (
    ChannelType, ClosureScopeType, ReconciliationStatus, ImportSource,
)


# ─── SalesChannel ──────────────────────────────
class SalesChannelOut(BaseModel):
    id: int
    code: str
    name_ar: str
    name_en: str
    type: str
    commission_rate: Optional[Decimal] = None
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class CommissionRateUpdate(BaseModel):
    commission_rate: Decimal = Field(ge=0, le=100)


# ─── BranchDailySale ───────────────────────────
class DailySaleCreate(BaseModel):
    """
    Branch manager's daily entry payload for ONE channel.
    If submitted via the per-day-all-channels endpoint, the batch wrapper is used.
    """
    branch_id: int
    sales_date: date
    channel_id: int
    amount: Decimal = Field(ge=0)
    orders_count: Optional[int] = Field(default=None, ge=0)
    # channel_type is only hinted by the client; authoritative check is server-side
    channel_type: Optional[ChannelType] = None

    @model_validator(mode="after")
    def _enforce_orders_count_rules(self):
        """
        Rules (v3):
          - delivery_app: orders_count REQUIRED; if amount > 0 → orders_count > 0
          - payment_method: orders_count MUST be None
        """
        if self.channel_type is None:
            # Client didn't hint; skip here — service layer will re-check after resolving channel.
            return self
        if self.channel_type == ChannelType.delivery_app:
            if self.orders_count is None:
                raise ValueError("orders_count is required for delivery_app channels")
            if Decimal(self.amount) > 0 and self.orders_count == 0:
                raise ValueError(
                    "orders_count must be > 0 when amount > 0 for delivery_app channels"
                )
        elif self.channel_type == ChannelType.payment_method:
            if self.orders_count is not None:
                raise ValueError("orders_count must be NULL for payment_method channels")
        return self


class DailySaleUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, ge=0)
    orders_count: Optional[int] = Field(default=None, ge=0)
    edit_reason: str = Field(min_length=3)


class DailySaleOut(BaseModel):
    id: int
    branch_id: int
    sales_date: date
    channel_id: int
    amount: Decimal
    orders_count: Optional[int] = None
    submitted_at: datetime
    submitted_by: int
    entered_by_role: Optional[str] = None
    on_behalf_of: bool = False
    last_edited_at: Optional[datetime] = None
    last_edited_by: Optional[int] = None
    edit_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class DailySaleChannelLine(BaseModel):
    """One channel's numbers inside a batch daily-entry payload."""
    channel_id: int
    amount: Decimal = Field(ge=0)
    orders_count: Optional[int] = Field(default=None, ge=0)


class DailySaleBatchCreate(BaseModel):
    """The user fills ALL channels for one (branch, date) in one submit."""
    branch_id: int
    sales_date: date
    lines: List[DailySaleChannelLine] = Field(min_length=1)


# ─── AppMonthlyStatement ──────────────────────
class AppStatementCreate(BaseModel):
    channel_id: int
    branch_id: int
    statement_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    app_reported_amount: Decimal = Field(ge=0)
    app_reported_count: Optional[int] = Field(default=None, ge=0)
    commission_rate: Decimal = Field(ge=0, le=100)
    import_source: ImportSource = ImportSource.manual
    csv_filename: Optional[str] = None


class AppStatementOut(BaseModel):
    id: int
    channel_id: int
    branch_id: int
    statement_month: str
    app_reported_amount: Decimal
    app_reported_count: Optional[int] = None
    commission_rate: Decimal
    commission_amount: Decimal
    net_amount: Decimal
    import_source: str
    csv_filename: Optional[str] = None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── MonthlyClosure ───────────────────────────
class MonthlyClosureCreate(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    scope_type: ClosureScopeType
    branch_id: Optional[int] = None

    @model_validator(mode="after")
    def _validate_scope(self):
        if self.scope_type == ClosureScopeType.all and self.branch_id is not None:
            raise ValueError("branch_id must be NULL when scope_type='all'")
        if self.scope_type == ClosureScopeType.branch and self.branch_id is None:
            raise ValueError("branch_id is required when scope_type='branch'")
        return self


class MonthlyClosureReopen(BaseModel):
    reopen_reason: str = Field(min_length=5)


class MonthlyClosureOut(BaseModel):
    id: int
    month: str
    scope_type: str
    branch_id: Optional[int] = None
    closed_by: int
    closed_at: datetime
    reopened_at: Optional[datetime] = None
    reopened_by: Optional[int] = None
    reopen_reason: Optional[str] = None
    is_active: bool = True

    model_config = {"from_attributes": True}


# ─── Reconciliation ───────────────────────────
class ReconciliationLine(BaseModel):
    channel_id: int
    channel_code: str
    channel_name_ar: str
    branch_id: int
    branch_name: Optional[str] = None
    statement_month: str
    branch_total: Decimal
    app_total: Decimal
    variance_amount: Decimal
    variance_percent: Optional[Decimal] = None  # None when app_total = 0 and branch > 0
    branch_count: Optional[int] = None
    app_count: Optional[int] = None
    count_variance: Optional[int] = None
    status: str  # match / minor / major
    commission_rate_used: Optional[Decimal] = None


class ReconciliationReport(BaseModel):
    month: str
    branch_id: Optional[int] = None
    lines: List[ReconciliationLine]
    generated_at: datetime
    is_locked: bool = False


# ─── Compliance ───────────────────────────────
class BranchComplianceRow(BaseModel):
    branch_id: int
    branch_name: Optional[str] = None
    month: str
    expected_days: int
    submitted_days: int
    missing_days: List[date] = []
    exceptional_entries: int = 0
    compliance_percent: Decimal
    last_entry_date: Optional[date] = None


class ComplianceReport(BaseModel):
    month: str
    rows: List[BranchComplianceRow]
    generated_at: datetime


__all__ = [
    "SalesChannelOut", "CommissionRateUpdate",
    "DailySaleCreate", "DailySaleUpdate", "DailySaleOut",
    "DailySaleChannelLine", "DailySaleBatchCreate",
    "AppStatementCreate", "AppStatementOut",
    "MonthlyClosureCreate", "MonthlyClosureReopen", "MonthlyClosureOut",
    "ReconciliationLine", "ReconciliationReport",
    "BranchComplianceRow", "ComplianceReport",
]
