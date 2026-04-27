"""
Sales Channels Unification & Reconciliation — Service Layer.

Pack C / Phase 1 (SPEC v3). Contains the business logic for:
  * Daily sale creation/edit with conditional orders_count rules
  * Time-based edit escalation (24h / 7 days)
  * Monthly statement ingestion with commission snapshot
  * On-demand reconciliation computation (value + count, two-dimensional)
  * Variance safeguard when app_reported_amount = 0
  * Month closure + snapshot generation
  * Month reopen (requires reason)
  * Compliance metrics (per-branch entry coverage)
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core import sales_permissions as perms
from app.models import Branch, User
from app.models.sales_channels import (
    SalesChannel,
    BranchDailySale,
    AppMonthlyStatement,
    MonthlyClosure,
    ReconciliationSnapshot,
    ChannelType,
    ClosureScopeType,
    ReconciliationStatus,
    ImportSource,
)


# ─────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────
class SalesChannelsError(Exception):
    """Base error for sales_channels domain."""


class MonthLockedError(SalesChannelsError):
    """Attempted to mutate data in a locked month."""


class OrdersCountRuleError(SalesChannelsError):
    """orders_count violates delivery_app/payment_method rule."""


class EditWindowError(SalesChannelsError):
    """Editor doesn't have permission for the elapsed time window."""


class InvalidClosureError(SalesChannelsError):
    """Closure operation failed (duplicate, consistency, etc.)."""


# ─────────────────────────────────────────────
# Variance thresholds (SPEC v3, §8.1)
# ─────────────────────────────────────────────
MINOR_THRESHOLD_PCT = Decimal("5")
MAJOR_THRESHOLD_PCT = Decimal("10")


# ═════════════════════════════════════════════
# Month-lock helpers
# ═════════════════════════════════════════════
def _ym_from_date(d: date) -> str:
    return d.strftime("%Y-%m")


def is_month_locked(db: Session, month: str, branch_id: int) -> bool:
    """Return True if the month is locked for this branch (via 'all' or 'branch' scope)."""
    q = db.query(MonthlyClosure).filter(
        MonthlyClosure.month == month,
        MonthlyClosure.reopened_at.is_(None),  # active closures only
        or_(
            MonthlyClosure.scope_type == ClosureScopeType.all.value,
            and_(
                MonthlyClosure.scope_type == ClosureScopeType.branch.value,
                MonthlyClosure.branch_id == branch_id,
            ),
        ),
    )
    return bool(db.query(q.exists()).scalar())


def _assert_not_locked(db: Session, month: str, branch_id: int) -> None:
    if is_month_locked(db, month, branch_id):
        raise MonthLockedError(
            f"Month {month} is locked for branch {branch_id}; unlock first."
        )


# ═════════════════════════════════════════════
# orders_count rule enforcement
# ═════════════════════════════════════════════
def _validate_orders_count_rule(
    channel: SalesChannel, amount: Decimal, orders_count: Optional[int]
) -> None:
    if channel.type == ChannelType.delivery_app.value:
        if orders_count is None:
            raise OrdersCountRuleError(
                f"orders_count is required for delivery_app '{channel.code}'"
            )
        if Decimal(amount) > 0 and orders_count == 0:
            raise OrdersCountRuleError(
                f"orders_count must be > 0 when amount > 0 for delivery_app '{channel.code}'"
            )
    elif channel.type == ChannelType.payment_method.value:
        if orders_count is not None:
            raise OrdersCountRuleError(
                f"orders_count must be NULL for payment_method '{channel.code}'"
            )


# ═════════════════════════════════════════════
# Daily sales CRUD
# ═════════════════════════════════════════════
def create_daily_sale(
    db: Session,
    *,
    branch_id: int,
    sales_date: date,
    channel_id: int,
    amount: Decimal,
    orders_count: Optional[int],
    submitted_by: int,
    submitter_roles: Iterable[str] = (),
) -> BranchDailySale:
    channel = db.query(SalesChannel).filter(SalesChannel.id == channel_id).first()
    if not channel:
        raise SalesChannelsError(f"Unknown channel_id={channel_id}")
    if not channel.is_active:
        raise SalesChannelsError(f"Channel '{channel.code}' is not active")

    _validate_orders_count_rule(channel, amount, orders_count)
    _assert_not_locked(db, _ym_from_date(sales_date), branch_id)

    # Reject duplicate (branch, date, channel)
    dup = db.query(BranchDailySale).filter(
        BranchDailySale.branch_id == branch_id,
        BranchDailySale.sales_date == sales_date,
        BranchDailySale.channel_id == channel_id,
    ).first()
    if dup:
        raise SalesChannelsError(
            f"Daily sale already exists for branch {branch_id}, "
            f"date {sales_date}, channel {channel.code}"
        )

    entered_by_role = _primary_entry_role(submitter_roles)
    submitter = db.query(User).filter(User.id == submitted_by).first() if submitter_roles else None
    on_behalf_of = bool(
        entered_by_role in ("area_manager", "sales_manager")
        and getattr(submitter, "branch_id", None) != branch_id
    )

    row = BranchDailySale(
        branch_id=branch_id,
        sales_date=sales_date,
        channel_id=channel_id,
        amount=amount,
        orders_count=orders_count,
        submitted_by=submitted_by,
        submitted_at=datetime.utcnow(),
        entered_by_role=entered_by_role,
        on_behalf_of=on_behalf_of,
    )
    db.add(row)
    db.flush()
    return row


def create_daily_sale_batch(
    db: Session,
    *,
    branch_id: int,
    sales_date: date,
    lines: Iterable[dict],  # {channel_id, amount, orders_count}
    submitted_by: int,
    submitter_roles: Iterable[str] = (),
) -> List[BranchDailySale]:
    """One submit for ALL channels of a branch on one date. All-or-nothing."""
    _assert_not_locked(db, _ym_from_date(sales_date), branch_id)
    created = []
    for line in lines:
        row = create_daily_sale(
            db,
            branch_id=branch_id,
            sales_date=sales_date,
            channel_id=line["channel_id"],
            amount=Decimal(line["amount"]),
            orders_count=line.get("orders_count"),
            submitted_by=submitted_by,
            submitter_roles=submitter_roles,
        )
        created.append(row)
    return created


def _primary_entry_role(roles: Iterable[str]) -> Optional[str]:
    """Pick the most relevant human-facing role to stamp on the created row."""
    roles_set = set(roles or ())
    for role in ("branch_manager", "area_manager", "sales_manager", "admin", "super_admin"):
        if role in roles_set:
            return role
    return sorted(roles_set)[0] if roles_set else None


def _edit_window_role(sale: BranchDailySale, now: datetime) -> str:
    """
    Returns the role required to edit this entry given elapsed time.
      ≤ 24h:    'branch_manager'    (submitter can self-edit)
      ≤ 7d:     'area_manager'      (approval needed)
      > 7d:     'sales_manager'
    """
    elapsed = now - sale.submitted_at
    if elapsed <= timedelta(hours=24):
        return "branch_manager"
    if elapsed <= timedelta(days=7):
        return "area_manager"
    return "sales_manager"


def update_daily_sale(
    db: Session,
    *,
    sale_id: int,
    amount: Optional[Decimal],
    orders_count: Optional[int],
    edit_reason: str,
    editor_id: int,
    editor_roles: Iterable[str],
    now: Optional[datetime] = None,
) -> BranchDailySale:
    now = now or datetime.utcnow()
    sale = db.query(BranchDailySale).filter(BranchDailySale.id == sale_id).first()
    if not sale:
        raise SalesChannelsError(f"Daily sale id={sale_id} not found")

    _assert_not_locked(db, _ym_from_date(sale.sales_date), sale.branch_id)

    required_role = _edit_window_role(sale, now)
    roles_set = set(editor_roles)
    # Model C RBAC policy (2026-04-24): each window belongs to ONE operational role.
    # sales_manager is the "Delivery Accounts Manager" — NOT allowed to touch fresh
    # or 24h-7d entries (that's the branch's and area_manager's scope). Only allowed
    # in the stale window (>7d) as the last line before escalating to admin.
    #   * fresh window (<=24h)  : branch_manager only (+ admin / super_admin)
    #   * late window  (24h-7d) : area_manager only  (+ admin / super_admin)
    #   * stale window (>7d)    : sales_manager only (+ admin / super_admin)
    # Platform admins (admin / super_admin) can always edit in any window — this
    # mirrors the central bypass in app.core.auth.require_roles().
    allowed = {"super_admin", "admin"} | perms.edit_window_allowed_role(required_role)

    if not (roles_set & allowed):
        raise EditWindowError(
            f"Edit requires one of {sorted(allowed)}; editor has {sorted(roles_set)}"
        )

    # Late-window edits (outside the fresh <=24h window) require a written reason
    # from any non-admin editor. Branch manager's fresh-window edits do not
    # require a reason — they're quick corrections to own entry.
    is_platform_admin = bool({"admin", "super_admin"} & roles_set)
    if required_role != "branch_manager" and not is_platform_admin:
        if not edit_reason or not edit_reason.strip():
            raise EditWindowError(
                f"Edits in the {required_role} window require a written reason (edit_reason)"
            )

    # Re-validate orders_count rule against the original channel
    new_amount = amount if amount is not None else sale.amount
    new_count = orders_count if orders_count is not None else sale.orders_count
    _validate_orders_count_rule(sale.channel, Decimal(new_amount), new_count)

    if amount is not None:
        sale.amount = amount
    if orders_count is not None or sale.channel.type == ChannelType.delivery_app.value:
        sale.orders_count = new_count
    sale.last_edited_at = now
    sale.last_edited_by = editor_id
    sale.edit_reason = edit_reason
    db.flush()
    return sale


# ═════════════════════════════════════════════
# Monthly statements
# ═════════════════════════════════════════════
def create_monthly_statement(
    db: Session,
    *,
    channel_id: int,
    branch_id: int,
    statement_month: str,
    app_reported_amount: Decimal,
    app_reported_count: Optional[int],
    commission_rate: Decimal,
    import_source: str,
    csv_filename: Optional[str],
    created_by: int,
) -> AppMonthlyStatement:
    channel = db.query(SalesChannel).filter(SalesChannel.id == channel_id).first()
    if not channel:
        raise SalesChannelsError(f"Unknown channel_id={channel_id}")
    if channel.type != ChannelType.delivery_app.value:
        raise SalesChannelsError(
            "App monthly statements only apply to delivery_app channels"
        )
    _assert_not_locked(db, statement_month, branch_id)

    # Check duplicate
    dup = db.query(AppMonthlyStatement).filter(
        AppMonthlyStatement.channel_id == channel_id,
        AppMonthlyStatement.branch_id == branch_id,
        AppMonthlyStatement.statement_month == statement_month,
    ).first()
    if dup:
        raise SalesChannelsError(
            f"Statement already exists for channel={channel.code}, "
            f"branch={branch_id}, month={statement_month}"
        )

    commission_amount = (Decimal(app_reported_amount) * Decimal(commission_rate) / Decimal(100)
                         ).quantize(Decimal("0.01"))
    net_amount = (Decimal(app_reported_amount) - commission_amount).quantize(Decimal("0.01"))

    row = AppMonthlyStatement(
        channel_id=channel_id,
        branch_id=branch_id,
        statement_month=statement_month,
        app_reported_amount=app_reported_amount,
        app_reported_count=app_reported_count,
        commission_rate=commission_rate,
        commission_amount=commission_amount,
        net_amount=net_amount,
        import_source=import_source,
        csv_filename=csv_filename,
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    return row


# ═════════════════════════════════════════════
# Reconciliation computation (on-demand)
# ═════════════════════════════════════════════
def _compute_variance(
    branch_total: Decimal, app_total: Decimal
) -> Tuple[Decimal, Optional[Decimal], str]:
    """
    Returns (variance_amount, variance_percent, status).

    Variance safeguard per SPEC v3 §3.3:
      - app_total = 0 AND branch_total = 0  → percent=0,   status='match'
      - app_total = 0 AND branch_total > 0  → percent=None, status='major'
      - app_total > 0                       → percent = variance / app_total * 100
    """
    variance_amount = (Decimal(branch_total) - Decimal(app_total)).quantize(Decimal("0.01"))
    if Decimal(app_total) == 0:
        if Decimal(branch_total) == 0:
            return variance_amount, Decimal("0"), ReconciliationStatus.match.value
        return variance_amount, None, ReconciliationStatus.major.value

    pct = (variance_amount / Decimal(app_total) * Decimal(100)).quantize(Decimal("0.01"))
    abs_pct = abs(pct)
    if abs_pct < MINOR_THRESHOLD_PCT:
        status = ReconciliationStatus.match.value
    elif abs_pct < MAJOR_THRESHOLD_PCT:
        status = ReconciliationStatus.minor.value
    else:
        status = ReconciliationStatus.major.value
    return variance_amount, pct, status


def compute_reconciliation(
    db: Session,
    *,
    month: str,
    branch_id: Optional[int] = None,
    channel_id: Optional[int] = None,
) -> List[dict]:
    """
    Compute reconciliation on-demand for one month. If a snapshot exists for a
    given (closure, channel, branch), it is returned instead of recomputing
    (to guarantee frozen historical values).
    """
    # Resolve delivery_app channels scope
    ch_q = db.query(SalesChannel).filter(
        SalesChannel.type == ChannelType.delivery_app.value,
        SalesChannel.is_active.is_(True),
    )
    if channel_id is not None:
        ch_q = ch_q.filter(SalesChannel.id == channel_id)
    channels = ch_q.all()

    # Resolve branch scope
    br_q = db.query(Branch).filter(Branch.active.is_(True), Branch.is_deleted.is_(False))
    if branch_id is not None:
        br_q = br_q.filter(Branch.id == branch_id)
    branches = br_q.all()

    lines: List[dict] = []
    if not channels or not branches:
        return lines

    # Check for frozen snapshots upfront
    snapshots = {
        (s.channel_id, s.branch_id): s
        for s in db.query(ReconciliationSnapshot).filter(
            ReconciliationSnapshot.statement_month == month,
            ReconciliationSnapshot.branch_id.in_([b.id for b in branches]),
            ReconciliationSnapshot.channel_id.in_([c.id for c in channels]),
        ).all()
    }

    month_start_date = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    _, last_day = monthrange(month_start_date.year, month_start_date.month)
    month_end_date = date(month_start_date.year, month_start_date.month, last_day)

    for ch in channels:
        for br in branches:
            # If snapshot exists, use it
            snap = snapshots.get((ch.id, br.id))
            if snap:
                lines.append({
                    "channel_id": ch.id,
                    "channel_code": ch.code,
                    "channel_name_ar": ch.name_ar,
                    "branch_id": br.id,
                    "branch_name": br.branch_name,
                    "statement_month": month,
                    "branch_total": Decimal(snap.branch_total),
                    "app_total": Decimal(snap.app_total),
                    "variance_amount": Decimal(snap.variance_amount),
                    "variance_percent": (
                        Decimal(snap.variance_percent) if snap.variance_percent is not None else None
                    ),
                    "branch_count": snap.branch_count,
                    "app_count": snap.app_count,
                    "count_variance": snap.count_variance,
                    "status": snap.status,
                    "commission_rate_used": (
                        Decimal(snap.commission_rate_used)
                        if snap.commission_rate_used is not None else None
                    ),
                })
                continue

            # Compute fresh
            br_total = db.query(func.coalesce(func.sum(BranchDailySale.amount), 0)).filter(
                BranchDailySale.branch_id == br.id,
                BranchDailySale.channel_id == ch.id,
                BranchDailySale.sales_date >= month_start_date,
                BranchDailySale.sales_date <= month_end_date,
            ).scalar()
            br_count = db.query(func.coalesce(func.sum(BranchDailySale.orders_count), 0)).filter(
                BranchDailySale.branch_id == br.id,
                BranchDailySale.channel_id == ch.id,
                BranchDailySale.sales_date >= month_start_date,
                BranchDailySale.sales_date <= month_end_date,
            ).scalar()

            stmt = db.query(AppMonthlyStatement).filter(
                AppMonthlyStatement.branch_id == br.id,
                AppMonthlyStatement.channel_id == ch.id,
                AppMonthlyStatement.statement_month == month,
            ).first()
            app_total = Decimal(stmt.app_reported_amount) if stmt else Decimal("0")
            app_count = stmt.app_reported_count if stmt else None
            commission_used = Decimal(stmt.commission_rate) if stmt else None

            var_amount, var_pct, status = _compute_variance(Decimal(br_total), app_total)
            cnt_variance = None
            if app_count is not None and br_count is not None:
                cnt_variance = int(br_count) - int(app_count)

            lines.append({
                "channel_id": ch.id,
                "channel_code": ch.code,
                "channel_name_ar": ch.name_ar,
                "branch_id": br.id,
                "branch_name": br.branch_name,
                "statement_month": month,
                "branch_total": Decimal(br_total).quantize(Decimal("0.01")),
                "app_total": app_total,
                "variance_amount": var_amount,
                "variance_percent": var_pct,
                "branch_count": int(br_count) if br_count is not None else None,
                "app_count": app_count,
                "count_variance": cnt_variance,
                "status": status,
                "commission_rate_used": commission_used,
            })

    return lines


# ═════════════════════════════════════════════
# Closure + snapshot generation
# ═════════════════════════════════════════════
def close_month(
    db: Session,
    *,
    month: str,
    scope_type: str,          # 'all' or 'branch'
    branch_id: Optional[int],
    closed_by: int,
) -> MonthlyClosure:
    # Pydantic already validated scope consistency, but re-enforce here
    if scope_type == ClosureScopeType.all.value and branch_id is not None:
        raise InvalidClosureError("branch_id must be NULL when scope_type='all'")
    if scope_type == ClosureScopeType.branch.value and branch_id is None:
        raise InvalidClosureError("branch_id is required when scope_type='branch'")

    # Check existing active closure (app-layer check — DB partial unique is the backup)
    existing = db.query(MonthlyClosure).filter(
        MonthlyClosure.month == month,
        MonthlyClosure.scope_type == scope_type,
        MonthlyClosure.branch_id == branch_id,
        MonthlyClosure.reopened_at.is_(None),
    ).first()
    if existing:
        raise InvalidClosureError(
            f"Active closure already exists for month={month}, scope={scope_type}, branch={branch_id}"
        )

    closure = MonthlyClosure(
        month=month,
        scope_type=scope_type,
        branch_id=branch_id,
        closed_by=closed_by,
        closed_at=datetime.utcnow(),
    )
    db.add(closure)
    db.flush()

    # Generate snapshots for every (channel, branch) covered by this closure
    if scope_type == ClosureScopeType.all.value:
        branches = db.query(Branch).filter(
            Branch.active.is_(True), Branch.is_deleted.is_(False)
        ).all()
    else:
        branches = db.query(Branch).filter(Branch.id == branch_id).all()

    channels = db.query(SalesChannel).filter(
        SalesChannel.type == ChannelType.delivery_app.value,
        SalesChannel.is_active.is_(True),
    ).all()

    lines = compute_reconciliation(
        db, month=month, branch_id=(branch_id if scope_type == "branch" else None)
    )
    lines_map = {(ln["channel_id"], ln["branch_id"]): ln for ln in lines}

    for ch in channels:
        for br in branches:
            ln = lines_map.get((ch.id, br.id))
            if not ln:
                continue
            snap = ReconciliationSnapshot(
                closure_id=closure.id,
                channel_id=ch.id,
                branch_id=br.id,
                statement_month=month,
                branch_total=ln["branch_total"],
                app_total=ln["app_total"],
                variance_amount=ln["variance_amount"],
                variance_percent=ln["variance_percent"],
                branch_count=ln["branch_count"],
                app_count=ln["app_count"],
                count_variance=ln["count_variance"],
                status=ln["status"],
                commission_rate_used=ln["commission_rate_used"],
            )
            db.add(snap)

    db.flush()
    return closure


def reopen_month(
    db: Session,
    *,
    closure_id: int,
    reopened_by: int,
    reopen_reason: str,
) -> MonthlyClosure:
    if not reopen_reason or len(reopen_reason.strip()) < 5:
        raise InvalidClosureError("reopen_reason is required (min 5 chars)")
    closure = db.query(MonthlyClosure).filter(MonthlyClosure.id == closure_id).first()
    if not closure:
        raise InvalidClosureError(f"closure id={closure_id} not found")
    if closure.reopened_at is not None:
        raise InvalidClosureError("closure is already reopened")

    closure.reopened_at = datetime.utcnow()
    closure.reopened_by = reopened_by
    closure.reopen_reason = reopen_reason
    db.flush()
    return closure


# ═════════════════════════════════════════════
# Compliance
# ═════════════════════════════════════════════
def compute_compliance(
    db: Session,
    *,
    month: str,
    branch_ids: Optional[List[int]] = None,
    today: Optional[date] = None,
) -> List[dict]:
    """
    For each branch, return:
      - expected_days: calendar days of the month (up to today for current month)
      - submitted_days: days that have AT LEAST ONE sale entry
      - missing_days
      - exceptional_entries: edits where editor != submitter (best-effort proxy for now)
      - compliance_percent
      - last_entry_date
    """
    today = today or date.today()
    month_start = datetime.strptime(month + "-01", "%Y-%m-%d").date()
    _, last_day = monthrange(month_start.year, month_start.month)
    month_end = date(month_start.year, month_start.month, last_day)
    end_bound = min(today, month_end)

    br_q = db.query(Branch).filter(Branch.active.is_(True), Branch.is_deleted.is_(False))
    if branch_ids:
        br_q = br_q.filter(Branch.id.in_(branch_ids))
    branches = br_q.all()

    results: List[dict] = []
    for br in branches:
        # Distinct sales_date set for this branch, this month
        submitted_dates = {
            d[0] for d in db.query(BranchDailySale.sales_date).filter(
                BranchDailySale.branch_id == br.id,
                BranchDailySale.sales_date >= month_start,
                BranchDailySale.sales_date <= end_bound,
            ).distinct().all()
        }
        exceptional_count = db.query(func.count(BranchDailySale.id)).filter(
            BranchDailySale.branch_id == br.id,
            BranchDailySale.sales_date >= month_start,
            BranchDailySale.sales_date <= end_bound,
            BranchDailySale.last_edited_by.isnot(None),
            BranchDailySale.last_edited_by != BranchDailySale.submitted_by,
        ).scalar() or 0

        expected_days = (end_bound - month_start).days + 1
        submitted_days = len(submitted_dates)
        missing = []
        for offset in range(expected_days):
            d = month_start + timedelta(days=offset)
            if d not in submitted_dates:
                missing.append(d)
        compliance_pct = (
            Decimal(submitted_days) / Decimal(expected_days) * Decimal(100)
        ).quantize(Decimal("0.01")) if expected_days > 0 else Decimal("0.00")
        last_entry = max(submitted_dates) if submitted_dates else None

        results.append({
            "branch_id": br.id,
            "branch_name": br.branch_name,
            "month": month,
            "expected_days": expected_days,
            "submitted_days": submitted_days,
            "missing_days": missing,
            "exceptional_entries": int(exceptional_count),
            "compliance_percent": compliance_pct,
            "last_entry_date": last_entry,
        })

    return results


# ═════════════════════════════════════════════
# Helpers exposed to routers
# ═════════════════════════════════════════════
def list_channels(db: Session, active_only: bool = True) -> List[SalesChannel]:
    q = db.query(SalesChannel).order_by(SalesChannel.sort_order, SalesChannel.id)
    if active_only:
        q = q.filter(SalesChannel.is_active.is_(True))
    return q.all()


def update_commission_rate(
    db: Session, *, channel_id: int, commission_rate: Decimal
) -> SalesChannel:
    ch = db.query(SalesChannel).filter(SalesChannel.id == channel_id).first()
    if not ch:
        raise SalesChannelsError(f"channel_id={channel_id} not found")
    if ch.type != ChannelType.delivery_app.value:
        raise SalesChannelsError("commission_rate only applies to delivery_app channels")
    ch.commission_rate = commission_rate
    db.flush()
    return ch
