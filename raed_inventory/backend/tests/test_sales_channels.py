"""
Pack C / Phase 1 — Unit tests for the Sales Channels service layer.

Coverage (matches SPEC v3):
  1. orders_count rules (required for delivery_app, NULL for payment_method)
  2. amount >= 0 and orders_count > 0 when amount > 0 (delivery_app)
  3. Duplicate (branch, date, channel) rejected
  4. Variance safeguard when app_total = 0
  5. Variance thresholds: match / minor / major
  6. Month-lock prevents mutations on locked (branch, month)
  7. Edit-window role escalation (24h -> 7d -> > 7d)
  8. close_month generates snapshots for all (channel, branch) pairs
  9. reopen_month requires a reason (>= 5 chars)
 10. compute_compliance counts submitted vs expected days
 11. Monthly statement only allowed for delivery_app channels
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    Branch,
    User,
    UserStatus,
    Warehouse,
)
from app.models.sales_channels import (
    AppMonthlyStatement,
    BranchDailySale,
    ChannelType,
    ClosureScopeType,
    MonthlyClosure,
    ReconciliationSnapshot,
    SalesChannel,
)
from app.services import sales_channels_service as svc


# ═════════════════════════════════════════════════════════════
# Helpers — minimal seed data
# ═════════════════════════════════════════════════════════════
def _seed_basic(db: Session) -> dict:
    """Create 1 warehouse, 1 branch, 1 user, 2 channels (jahez + cash)."""
    wh = Warehouse(
        warehouse_code="SC-WH", warehouse_name="SC WH",
        location="Riyadh", active=True, is_deleted=False,
    )
    db.add(wh)
    db.flush()

    br = Branch(
        branch_code="SC-BR1", branch_name="Branch One",
        city="Riyadh", area="", warehouse_id=wh.id,
        active=True, is_deleted=False,
    )
    db.add(br)
    db.flush()

    user = User(
        username="sc_tester", email="sc_tester@example.com",
        full_name="Tester", hashed_password=get_password_hash("TestPass@2026"),
        status=UserStatus.active, branch_id=br.id, is_deleted=False,
    )
    db.add(user)
    db.flush()

    jahez = SalesChannel(
        code="jahez", name_ar="جاهز", name_en="Jahez",
        type=ChannelType.delivery_app.value,
        commission_rate=Decimal("15.00"), is_active=True, sort_order=10,
    )
    cash = SalesChannel(
        code="cash", name_ar="كاش", name_en="Cash",
        type=ChannelType.payment_method.value,
        commission_rate=None, is_active=True, sort_order=100,
    )
    db.add_all([jahez, cash])
    db.flush()

    return {
        "warehouse_id": wh.id,
        "branch_id": br.id,
        "user_id": user.id,
        "jahez_id": jahez.id,
        "cash_id": cash.id,
    }


def _seed_two_branches(db: Session) -> dict:
    base = _seed_basic(db)
    br2 = Branch(
        branch_code="SC-BR2", branch_name="Branch Two",
        city="Dammam", area="الشرقية",
        warehouse_id=base["warehouse_id"],
        active=True, is_deleted=False,
    )
    db.add(br2)
    db.flush()
    base["branch2_id"] = br2.id
    return base


# ═════════════════════════════════════════════════════════════
# 1. orders_count rules
# ═════════════════════════════════════════════════════════════
def test_orders_count_required_for_delivery_app(db: Session):
    seed = _seed_basic(db)
    with pytest.raises(svc.OrdersCountRuleError):
        svc.create_daily_sale(
            db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 1),
            channel_id=seed["jahez_id"], amount=Decimal("500"),
            orders_count=None, submitted_by=seed["user_id"],
        )


def test_orders_count_must_be_null_for_payment_method(db: Session):
    seed = _seed_basic(db)
    with pytest.raises(svc.OrdersCountRuleError):
        svc.create_daily_sale(
            db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 1),
            channel_id=seed["cash_id"], amount=Decimal("300"),
            orders_count=12, submitted_by=seed["user_id"],
        )


def test_orders_count_zero_with_positive_amount_rejected(db: Session):
    seed = _seed_basic(db)
    with pytest.raises(svc.OrdersCountRuleError):
        svc.create_daily_sale(
            db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 1),
            channel_id=seed["jahez_id"], amount=Decimal("500"),
            orders_count=0, submitted_by=seed["user_id"],
        )


def test_zero_amount_zero_orders_allowed_day_off(db: Session):
    """Branch closed / no orders day — zeros accepted for delivery_app."""
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 2),
        channel_id=seed["jahez_id"], amount=Decimal("0"),
        orders_count=0, submitted_by=seed["user_id"],
    )
    assert row.amount == Decimal("0")
    assert row.orders_count == 0


def test_create_daily_sale_happy_path(db: Session):
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 3),
        channel_id=seed["jahez_id"], amount=Decimal("1250.50"),
        orders_count=18, submitted_by=seed["user_id"],
    )
    assert row.id is not None
    assert row.amount == Decimal("1250.50")
    assert row.orders_count == 18
    assert row.submitted_by == seed["user_id"]


def test_duplicate_daily_sale_rejected(db: Session):
    seed = _seed_basic(db)
    svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 4),
        channel_id=seed["jahez_id"], amount=Decimal("100"),
        orders_count=3, submitted_by=seed["user_id"],
    )
    with pytest.raises(svc.SalesChannelsError):
        svc.create_daily_sale(
            db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 4),
            channel_id=seed["jahez_id"], amount=Decimal("200"),
            orders_count=5, submitted_by=seed["user_id"],
        )


def test_batch_create_all_channels(db: Session):
    seed = _seed_basic(db)
    lines = [
        {"channel_id": seed["jahez_id"], "amount": "900", "orders_count": 12},
        {"channel_id": seed["cash_id"],  "amount": "450", "orders_count": None},
    ]
    rows = svc.create_daily_sale_batch(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 5),
        lines=lines, submitted_by=seed["user_id"],
    )
    assert len(rows) == 2
    assert {r.channel_id for r in rows} == {seed["jahez_id"], seed["cash_id"]}


def test_daily_sale_audit_fields_capture_entry_role_and_on_behalf(db: Session):
    seed = _seed_two_branches(db)

    own_row = svc.create_daily_sale(
        db,
        branch_id=seed["branch_id"],
        sales_date=date(2026, 4, 5),
        channel_id=seed["jahez_id"],
        amount=Decimal("300"),
        orders_count=4,
        submitted_by=seed["user_id"],
        submitter_roles=["branch_manager"],
    )
    assert own_row.entered_by_role == "branch_manager"
    assert own_row.on_behalf_of is False

    substitute_rows = svc.create_daily_sale_batch(
        db,
        branch_id=seed["branch2_id"],
        sales_date=date(2026, 4, 6),
        lines=[{"channel_id": seed["jahez_id"], "amount": "420", "orders_count": 7}],
        submitted_by=seed["user_id"],
        submitter_roles=["area_manager"],
    )
    assert len(substitute_rows) == 1
    assert substitute_rows[0].entered_by_role == "area_manager"
    assert substitute_rows[0].on_behalf_of is True


# ═════════════════════════════════════════════════════════════
# 2. Variance safeguard + thresholds
# ═════════════════════════════════════════════════════════════
def test_variance_both_zero_is_match(db: Session):
    amt, pct, status = svc._compute_variance(Decimal("0"), Decimal("0"))
    assert amt == Decimal("0.00")
    assert pct == Decimal("0")
    assert status == "match"


def test_variance_app_zero_branch_positive_is_major(db: Session):
    amt, pct, status = svc._compute_variance(Decimal("500"), Decimal("0"))
    assert amt == Decimal("500.00")
    assert pct is None  # safeguard: cannot divide by 0
    assert status == "major"


def test_variance_minor_under_5_percent(db: Session):
    # variance = 40 on app_total = 1000 → 4% → minor-floor (match, since < 5%)
    amt, pct, status = svc._compute_variance(Decimal("1040"), Decimal("1000"))
    assert amt == Decimal("40.00")
    assert pct == Decimal("4.00")
    assert status == "match"


def test_variance_minor_band(db: Session):
    # 7% → minor
    amt, pct, status = svc._compute_variance(Decimal("1070"), Decimal("1000"))
    assert pct == Decimal("7.00")
    assert status == "minor"


def test_variance_major_over_10_percent(db: Session):
    amt, pct, status = svc._compute_variance(Decimal("1200"), Decimal("1000"))
    assert pct == Decimal("20.00")
    assert status == "major"


# ═════════════════════════════════════════════════════════════
# 3. Month-lock enforcement
# ═════════════════════════════════════════════════════════════
def test_month_lock_blocks_daily_sale(db: Session):
    seed = _seed_basic(db)
    # Close April 2026 for this branch
    svc.close_month(
        db, month="2026-04", scope_type=ClosureScopeType.branch.value,
        branch_id=seed["branch_id"], closed_by=seed["user_id"],
    )
    db.flush()
    with pytest.raises(svc.MonthLockedError):
        svc.create_daily_sale(
            db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 10),
            channel_id=seed["jahez_id"], amount=Decimal("100"),
            orders_count=2, submitted_by=seed["user_id"],
        )


def test_month_lock_all_scope_blocks_all_branches(db: Session):
    seed = _seed_two_branches(db)
    svc.close_month(
        db, month="2026-04", scope_type=ClosureScopeType.all.value,
        branch_id=None, closed_by=seed["user_id"],
    )
    db.flush()
    # Both branches blocked
    assert svc.is_month_locked(db, "2026-04", seed["branch_id"]) is True
    assert svc.is_month_locked(db, "2026-04", seed["branch2_id"]) is True


def test_month_unlock_after_reopen(db: Session):
    seed = _seed_basic(db)
    closure = svc.close_month(
        db, month="2026-04", scope_type=ClosureScopeType.branch.value,
        branch_id=seed["branch_id"], closed_by=seed["user_id"],
    )
    svc.reopen_month(
        db, closure_id=closure.id, reopened_by=seed["user_id"],
        reopen_reason="found mistake in statement",
    )
    assert svc.is_month_locked(db, "2026-04", seed["branch_id"]) is False


# ═════════════════════════════════════════════════════════════
# 4. Edit-window role escalation
# ═════════════════════════════════════════════════════════════
def test_edit_window_within_24h_branch_manager_ok(db: Session):
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 6),
        channel_id=seed["jahez_id"], amount=Decimal("500"),
        orders_count=10, submitted_by=seed["user_id"],
    )
    # Ten hours later — branch_manager is enough
    updated = svc.update_daily_sale(
        db, sale_id=row.id, amount=Decimal("550"), orders_count=11,
        edit_reason="counted wrong", editor_id=seed["user_id"],
        editor_roles=["branch_manager"],
        now=row.submitted_at + timedelta(hours=10),
    )
    assert updated.amount == Decimal("550")
    assert updated.edit_reason == "counted wrong"


def test_edit_window_over_24h_requires_area_manager(db: Session):
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 7),
        channel_id=seed["jahez_id"], amount=Decimal("500"),
        orders_count=10, submitted_by=seed["user_id"],
    )
    later = row.submitted_at + timedelta(days=2)
    # branch_manager alone: rejected
    with pytest.raises(svc.EditWindowError):
        svc.update_daily_sale(
            db, sale_id=row.id, amount=Decimal("550"), orders_count=11,
            edit_reason="late fix", editor_id=seed["user_id"],
            editor_roles=["branch_manager"], now=later,
        )
    # area_manager: accepted
    updated = svc.update_daily_sale(
        db, sale_id=row.id, amount=Decimal("550"), orders_count=11,
        edit_reason="late fix", editor_id=seed["user_id"],
        editor_roles=["area_manager"], now=later,
    )
    assert updated.amount == Decimal("550")


def test_edit_window_over_7d_requires_sales_manager(db: Session):
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 8),
        channel_id=seed["jahez_id"], amount=Decimal("500"),
        orders_count=10, submitted_by=seed["user_id"],
    )
    later = row.submitted_at + timedelta(days=10)
    with pytest.raises(svc.EditWindowError):
        svc.update_daily_sale(
            db, sale_id=row.id, amount=Decimal("600"), orders_count=12,
            edit_reason="very late fix", editor_id=seed["user_id"],
            editor_roles=["area_manager"], now=later,
        )
    updated = svc.update_daily_sale(
        db, sale_id=row.id, amount=Decimal("600"), orders_count=12,
        edit_reason="very late fix", editor_id=seed["user_id"],
        editor_roles=["sales_manager"], now=later,
    )
    assert updated.amount == Decimal("600")


def test_edit_window_fresh_rejects_area_manager_alone(db: Session):
    """Model C (2026-04-24): fresh window (<=24h) is branch_manager's
    exclusive scope. area_manager, sales_manager cannot edit fresh entries."""
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 9),
        channel_id=seed["jahez_id"], amount=Decimal("500"),
        orders_count=10, submitted_by=seed["user_id"],
    )
    with pytest.raises(svc.EditWindowError):
        svc.update_daily_sale(
            db, sale_id=row.id, amount=Decimal("550"), orders_count=11,
            edit_reason="trying to correct", editor_id=seed["user_id"],
            editor_roles=["area_manager"],
            now=row.submitted_at + timedelta(hours=6),
        )


def test_edit_window_fresh_rejects_sales_manager(db: Session):
    """Model C: sales_manager is the Delivery Accounts Manager — NOT
    an operational entry editor. Cannot touch fresh-window entries."""
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 12),
        channel_id=seed["jahez_id"], amount=Decimal("500"),
        orders_count=10, submitted_by=seed["user_id"],
    )
    with pytest.raises(svc.EditWindowError):
        svc.update_daily_sale(
            db, sale_id=row.id, amount=Decimal("550"), orders_count=11,
            edit_reason="sales_manager trying to edit fresh",
            editor_id=seed["user_id"],
            editor_roles=["sales_manager"],
            now=row.submitted_at + timedelta(hours=6),
        )


def test_edit_window_late_rejects_sales_manager(db: Session):
    """Model C: sales_manager cannot edit in the 24h-7d late window
    either — that belongs to area_manager exclusively."""
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 13),
        channel_id=seed["jahez_id"], amount=Decimal("500"),
        orders_count=10, submitted_by=seed["user_id"],
    )
    later = row.submitted_at + timedelta(days=3)
    with pytest.raises(svc.EditWindowError):
        svc.update_daily_sale(
            db, sale_id=row.id, amount=Decimal("550"), orders_count=11,
            edit_reason="sales_manager trying to edit in late window",
            editor_id=seed["user_id"],
            editor_roles=["sales_manager"], now=later,
        )


def test_edit_window_stale_sales_manager_requires_edit_reason(db: Session):
    """Model C: stale window (>7d) is sales_manager's exclusive scope,
    and must carry a written reason."""
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 14),
        channel_id=seed["jahez_id"], amount=Decimal("500"),
        orders_count=10, submitted_by=seed["user_id"],
    )
    later = row.submitted_at + timedelta(days=10)
    # Empty reason → rejected
    with pytest.raises(svc.EditWindowError):
        svc.update_daily_sale(
            db, sale_id=row.id, amount=Decimal("600"), orders_count=12,
            edit_reason="", editor_id=seed["user_id"],
            editor_roles=["sales_manager"], now=later,
        )
    # Valid reason → accepted
    updated = svc.update_daily_sale(
        db, sale_id=row.id, amount=Decimal("600"), orders_count=12,
        edit_reason="app statement correction after 10 days",
        editor_id=seed["user_id"],
        editor_roles=["sales_manager"], now=later,
    )
    assert updated.amount == Decimal("600")


def test_edit_window_late_area_manager_requires_edit_reason(db: Session):
    """area_manager late-window edit must carry a written reason."""
    seed = _seed_basic(db)
    row = svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 11),
        channel_id=seed["jahez_id"], amount=Decimal("500"),
        orders_count=10, submitted_by=seed["user_id"],
    )
    later = row.submitted_at + timedelta(days=3)
    # Empty reason → rejected
    with pytest.raises(svc.EditWindowError):
        svc.update_daily_sale(
            db, sale_id=row.id, amount=Decimal("520"), orders_count=11,
            edit_reason="", editor_id=seed["user_id"],
            editor_roles=["area_manager"], now=later,
        )
    # Whitespace-only reason → rejected
    with pytest.raises(svc.EditWindowError):
        svc.update_daily_sale(
            db, sale_id=row.id, amount=Decimal("520"), orders_count=11,
            edit_reason="   ", editor_id=seed["user_id"],
            editor_roles=["area_manager"], now=later,
        )
    # Valid reason → succeeds
    updated = svc.update_daily_sale(
        db, sale_id=row.id, amount=Decimal("520"), orders_count=11,
        edit_reason="statement showed 520 not 500", editor_id=seed["user_id"],
        editor_roles=["area_manager"], now=later,
    )
    assert updated.amount == Decimal("520")
    assert updated.edit_reason == "statement showed 520 not 500"


# ═════════════════════════════════════════════════════════════
# 5. Monthly statement + reconciliation
# ═════════════════════════════════════════════════════════════
def test_monthly_statement_only_for_delivery_app(db: Session):
    seed = _seed_basic(db)
    with pytest.raises(svc.SalesChannelsError):
        svc.create_monthly_statement(
            db, channel_id=seed["cash_id"], branch_id=seed["branch_id"],
            statement_month="2026-04", app_reported_amount=Decimal("1000"),
            app_reported_count=None, commission_rate=Decimal("0"),
            import_source="manual", csv_filename=None,
            created_by=seed["user_id"],
        )


def test_monthly_statement_computes_commission_and_net(db: Session):
    seed = _seed_basic(db)
    stmt = svc.create_monthly_statement(
        db, channel_id=seed["jahez_id"], branch_id=seed["branch_id"],
        statement_month="2026-04", app_reported_amount=Decimal("10000"),
        app_reported_count=200, commission_rate=Decimal("15"),
        import_source="manual", csv_filename=None,
        created_by=seed["user_id"],
    )
    assert stmt.commission_amount == Decimal("1500.00")
    assert stmt.net_amount == Decimal("8500.00")


def test_compute_reconciliation_matches_branch_vs_app(db: Session):
    seed = _seed_basic(db)
    # Branch recorded 3 days totalling 900
    for i, amt in enumerate([Decimal("300"), Decimal("300"), Decimal("300")]):
        svc.create_daily_sale(
            db, branch_id=seed["branch_id"],
            sales_date=date(2026, 4, 1 + i),
            channel_id=seed["jahez_id"], amount=amt,
            orders_count=5, submitted_by=seed["user_id"],
        )
    # App reported 920 → variance ~2.17% (match)
    svc.create_monthly_statement(
        db, channel_id=seed["jahez_id"], branch_id=seed["branch_id"],
        statement_month="2026-04", app_reported_amount=Decimal("920"),
        app_reported_count=14, commission_rate=Decimal("15"),
        import_source="manual", csv_filename=None,
        created_by=seed["user_id"],
    )

    lines = svc.compute_reconciliation(db, month="2026-04", branch_id=seed["branch_id"])
    assert len(lines) == 1
    ln = lines[0]
    assert ln["branch_total"] == Decimal("900.00")
    assert ln["app_total"] == Decimal("920")
    assert ln["variance_amount"] == Decimal("-20.00")
    # -2.17% absolute < 5% → match
    assert ln["status"] == "match"
    assert ln["branch_count"] == 15
    assert ln["app_count"] == 14
    assert ln["count_variance"] == 1


# ═════════════════════════════════════════════════════════════
# 6. Close / reopen / snapshots
# ═════════════════════════════════════════════════════════════
def test_close_month_generates_snapshots(db: Session):
    seed = _seed_basic(db)
    svc.create_daily_sale(
        db, branch_id=seed["branch_id"], sales_date=date(2026, 4, 1),
        channel_id=seed["jahez_id"], amount=Decimal("500"),
        orders_count=10, submitted_by=seed["user_id"],
    )
    svc.create_monthly_statement(
        db, channel_id=seed["jahez_id"], branch_id=seed["branch_id"],
        statement_month="2026-04", app_reported_amount=Decimal("510"),
        app_reported_count=10, commission_rate=Decimal("15"),
        import_source="manual", csv_filename=None,
        created_by=seed["user_id"],
    )
    closure = svc.close_month(
        db, month="2026-04", scope_type=ClosureScopeType.branch.value,
        branch_id=seed["branch_id"], closed_by=seed["user_id"],
    )
    db.flush()

    snaps = db.query(ReconciliationSnapshot).filter(
        ReconciliationSnapshot.closure_id == closure.id
    ).all()
    assert len(snaps) == 1
    s = snaps[0]
    assert s.branch_total == Decimal("500.00")
    assert s.app_total == Decimal("510.00") or s.app_total == Decimal("510")
    assert s.status == "match"


def test_reopen_month_requires_reason(db: Session):
    seed = _seed_basic(db)
    closure = svc.close_month(
        db, month="2026-04", scope_type=ClosureScopeType.branch.value,
        branch_id=seed["branch_id"], closed_by=seed["user_id"],
    )
    with pytest.raises(svc.InvalidClosureError):
        svc.reopen_month(
            db, closure_id=closure.id, reopened_by=seed["user_id"],
            reopen_reason="oops",  # too short
        )
    # Valid reason works
    reopened = svc.reopen_month(
        db, closure_id=closure.id, reopened_by=seed["user_id"],
        reopen_reason="CSV import had a typo",
    )
    assert reopened.reopened_at is not None


def test_close_month_scope_consistency(db: Session):
    seed = _seed_basic(db)
    # scope_type=all with branch_id → rejected
    with pytest.raises(svc.InvalidClosureError):
        svc.close_month(
            db, month="2026-04", scope_type=ClosureScopeType.all.value,
            branch_id=seed["branch_id"], closed_by=seed["user_id"],
        )
    # scope_type=branch with branch_id=None → rejected
    with pytest.raises(svc.InvalidClosureError):
        svc.close_month(
            db, month="2026-04", scope_type=ClosureScopeType.branch.value,
            branch_id=None, closed_by=seed["user_id"],
        )


def test_duplicate_active_closure_rejected(db: Session):
    seed = _seed_basic(db)
    svc.close_month(
        db, month="2026-04", scope_type=ClosureScopeType.branch.value,
        branch_id=seed["branch_id"], closed_by=seed["user_id"],
    )
    with pytest.raises(svc.InvalidClosureError):
        svc.close_month(
            db, month="2026-04", scope_type=ClosureScopeType.branch.value,
            branch_id=seed["branch_id"], closed_by=seed["user_id"],
        )


# ═════════════════════════════════════════════════════════════
# 7. Compliance
# ═════════════════════════════════════════════════════════════
def test_compute_compliance_basic(db: Session):
    seed = _seed_basic(db)
    # Submit on 3 of the first 10 days
    for d in (1, 3, 5):
        svc.create_daily_sale(
            db, branch_id=seed["branch_id"],
            sales_date=date(2026, 4, d),
            channel_id=seed["jahez_id"], amount=Decimal("100"),
            orders_count=2, submitted_by=seed["user_id"],
        )

    rows = svc.compute_compliance(
        db, month="2026-04",
        branch_ids=[seed["branch_id"]],
        today=date(2026, 4, 10),
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["expected_days"] == 10
    assert r["submitted_days"] == 3
    assert len(r["missing_days"]) == 7
    assert r["last_entry_date"] == date(2026, 4, 5)
    # 30% compliance
    assert r["compliance_percent"] == Decimal("30.00")


# ═════════════════════════════════════════════════════════════
# 8. Commission rate admin helper
# ═════════════════════════════════════════════════════════════
def test_update_commission_rate_only_for_delivery_app(db: Session):
    seed = _seed_basic(db)
    ok = svc.update_commission_rate(
        db, channel_id=seed["jahez_id"], commission_rate=Decimal("18.50")
    )
    assert ok.commission_rate == Decimal("18.50")
    with pytest.raises(svc.SalesChannelsError):
        svc.update_commission_rate(
            db, channel_id=seed["cash_id"], commission_rate=Decimal("5")
        )
