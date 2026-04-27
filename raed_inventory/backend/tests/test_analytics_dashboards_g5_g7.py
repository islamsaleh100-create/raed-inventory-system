"""
G5 / G6 / G7 — Analytics dashboards coverage.

Covers:
  G5 /dashboard/branch/{id}/consumption-trend
      - Returns one point per day even with zero data.
      - Aggregates negative inventory_adjustment transactions correctly.
      - Ignores positive adjustments (receipts don't inflate consumption).
      - RBAC: branch user can see own branch only.

  G6 /dashboard/order-delay-analytics
      - KPIs: avg approval / transit / total hours.
      - Top-delayed branches only appear with ≥3 samples.
      - Empty window returns zeroes instead of NaN.

  G7 /dashboard/branches-open-actions
      - Counts only non-resolved `no` responses on non-deleted visits.
      - Overdue = due_date < today.
      - Branches with zero open actions are not in the list.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    Branch,
    Item,
    ItemCategory,
    OrderStatus,
    OrderType,
    QualityResponseStatus,
    QualityVisit,
    QualityVisitItem,
    QualityVisitResponse,
    QualityVisitSection,
    QualityVisitStatus,
    ReplenishmentOrder,
    Role,
    RoleName,
    StockTransaction,
    TransactionType,
    UnitOfMeasure,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)


# ═══════════════════════════════════════════════════════════════════════════
# Seed helpers
# ═══════════════════════════════════════════════════════════════════════════
def _ensure_role(db: Session, name: RoleName) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if role is None:
        role = Role(name=name, display_name=name.value, description="")
        db.add(role)
        db.flush()
    return role


def _seed(db: Session) -> dict:
    wh = Warehouse(warehouse_code="WH-AN", warehouse_name="Analytics WH",
                   location="Riyadh", active=True)
    db.add(wh)
    db.flush()

    # Three branches — two with activity, one empty
    b1 = Branch(branch_code="AN-01", branch_name="Branch 1", city="الرياض",
                area="الرياض", warehouse_id=wh.id, active=True)
    b2 = Branch(branch_code="AN-02", branch_name="Branch 2", city="الرياض",
                area="الرياض", warehouse_id=wh.id, active=True)
    b3 = Branch(branch_code="AN-03", branch_name="Branch 3", city="جدة",
                area="جدة", warehouse_id=wh.id, active=True)
    db.add_all([b1, b2, b3])
    db.flush()

    role_admin = _ensure_role(db, RoleName.admin)
    role_bu = _ensure_role(db, RoleName.branch_user)
    role_ops = _ensure_role(db, RoleName.operations_manager)

    admin = User(username="an_admin", email="an_admin@x.com", full_name="Admin",
                 hashed_password=get_password_hash("Pass@2026"),
                 status=UserStatus.active, is_deleted=False)
    ops = User(username="an_ops", email="an_ops@x.com", full_name="Ops",
               hashed_password=get_password_hash("Pass@2026"),
               status=UserStatus.active, is_deleted=False)
    staff1 = User(username="an_staff1", email="an_staff1@x.com", full_name="Staff1",
                  hashed_password=get_password_hash("Pass@2026"),
                  status=UserStatus.active, branch_id=b1.id, is_deleted=False)
    staff2 = User(username="an_staff2", email="an_staff2@x.com", full_name="Staff2",
                  hashed_password=get_password_hash("Pass@2026"),
                  status=UserStatus.active, branch_id=b2.id, is_deleted=False)
    db.add_all([admin, ops, staff1, staff2])
    db.flush()
    db.add_all([
        UserRole(user_id=admin.id, role_id=role_admin.id),
        UserRole(user_id=ops.id, role_id=role_ops.id),
        UserRole(user_id=staff1.id, role_id=role_bu.id),
        UserRole(user_id=staff2.id, role_id=role_bu.id),
    ])
    db.commit()

    return {
        "branch_1": b1.id, "branch_2": b2.id, "branch_3": b3.id,
        "warehouse_id": wh.id,
        "admin_id": admin.id, "ops_id": ops.id,
        "staff1_id": staff1.id, "staff2_id": staff2.id,
    }


@pytest.fixture
def seeded(client, db: Session):
    return _seed(db)


def _login(client, username: str) -> str:
    r = client.post("/api/v1/auth/login",
                    json={"username": username, "password": "Pass@2026"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ═══════════════════════════════════════════════════════════════════════════
# G5 — Consumption trend
# ═══════════════════════════════════════════════════════════════════════════
def test_consumption_trend_zero_when_no_data(client, seeded):
    tok = _login(client, "an_admin")
    r = client.get(f"/api/v1/dashboard/branch/{seeded['branch_3']}/consumption-trend?days=7",
                   headers=_auth(tok))
    assert r.status_code == 200
    data = r.json()
    assert data["days"] == 7
    assert len(data["trend"]) == 7
    assert data["total_consumed"] == 0
    assert data["avg_daily"] == 0
    assert all(p["consumed_qty"] == 0 for p in data["trend"])


def test_consumption_trend_aggregates_negative_adjustments(client, seeded, db):
    """Three days of consumption, one day positive (should be ignored)."""
    now = datetime.utcnow()
    cat = ItemCategory(code="AN-CAT", name_ar="تصنيف", name_en="Cat")
    db.add(cat)
    db.flush()
    uom = UnitOfMeasure(code="AN-U", name_ar="حبة", name_en="pcs")
    db.add(uom)
    db.flush()
    item = Item(
        item_code="AN-ITEM-1",
        item_name_ar="صنف1",
        item_name_en="Item1",
        category_id=cat.id,
        unit_id=uom.id,
    )
    db.add(item)
    db.flush()

    transactions = [
        # Day 0 (today): -2 consumption
        StockTransaction(transaction_date=now, transaction_type=TransactionType.inventory_adjustment,
                         source_type="branch", source_id=seeded["branch_1"],
                         item_id=item.id, qty=Decimal("-2")),
        # Day 1 (yesterday): -3
        StockTransaction(transaction_date=now - timedelta(days=1),
                         transaction_type=TransactionType.inventory_adjustment,
                         source_type="branch", source_id=seeded["branch_1"],
                         item_id=item.id, qty=Decimal("-3")),
        # Day 1 (yesterday): additional -1.5 (same day aggregates)
        StockTransaction(transaction_date=now - timedelta(days=1, hours=2),
                         transaction_type=TransactionType.inventory_adjustment,
                         source_type="branch", source_id=seeded["branch_1"],
                         item_id=item.id, qty=Decimal("-1.5")),
        # Day 2: POSITIVE 10 (receipt-like — MUST be excluded)
        StockTransaction(transaction_date=now - timedelta(days=2),
                         transaction_type=TransactionType.inventory_adjustment,
                         source_type="branch", source_id=seeded["branch_1"],
                         item_id=item.id, qty=Decimal("10")),
        # Day 3: -5 but for branch_2 — must not leak
        StockTransaction(transaction_date=now - timedelta(days=3),
                         transaction_type=TransactionType.inventory_adjustment,
                         source_type="branch", source_id=seeded["branch_2"],
                         item_id=item.id, qty=Decimal("-5")),
    ]
    db.add_all(transactions)
    db.commit()

    tok = _login(client, "an_admin")
    r = client.get(f"/api/v1/dashboard/branch/{seeded['branch_1']}/consumption-trend?days=7",
                   headers=_auth(tok))
    assert r.status_code == 200
    data = r.json()
    # Total for branch_1 should be |(-2) + (-3) + (-1.5)| = 6.5
    # Positive 10 and branch_2's -5 must be excluded.
    assert data["total_consumed"] == 6.5, data


def test_consumption_trend_rbac_branch_user_can_access_own(client, seeded):
    tok = _login(client, "an_staff1")
    r = client.get(f"/api/v1/dashboard/branch/{seeded['branch_1']}/consumption-trend?days=7",
                   headers=_auth(tok))
    assert r.status_code == 200


def test_consumption_trend_rbac_branch_user_blocked_from_other_branch(client, seeded):
    tok = _login(client, "an_staff1")
    r = client.get(f"/api/v1/dashboard/branch/{seeded['branch_2']}/consumption-trend?days=7",
                   headers=_auth(tok))
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# G6 — Order delay analytics
# ═══════════════════════════════════════════════════════════════════════════
def test_order_delay_empty_returns_zeroes(client, seeded):
    tok = _login(client, "an_admin")
    r = client.get("/api/v1/dashboard/order-delay-analytics?days=30",
                   headers=_auth(tok))
    assert r.status_code == 200
    data = r.json()
    assert data["total_orders_measured"] == 0
    assert data["avg_approval_hours"] == 0.0
    assert data["avg_total_hours"] == 0.0
    assert data["top_delayed_branches"] == []


def _make_received_order(db, branch_id, warehouse_id, submit_at, dispatch_at, receive_at):
    import uuid
    order = ReplenishmentOrder(
        order_no=f"ORD-{uuid.uuid4().hex[:8]}",
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        order_type=OrderType.daily_order,
        status=OrderStatus.received,
        order_date=submit_at.date(),
        submitted_to_warehouse_at=submit_at,
        dispatched_at=dispatch_at,
        received_at=receive_at,
    )
    db.add(order)
    return order


def test_order_delay_computes_averages_and_top_branches(client, seeded, db):
    """Branch_1: 3 fast orders (~24h). Branch_2: 3 slow orders (~72h). Branch_3: 1 order (insufficient samples)."""
    base = datetime.utcnow() - timedelta(days=5)
    # Branch 1 — approx 24h total each
    for i in range(3):
        t0 = base + timedelta(hours=i)
        _make_received_order(db, seeded["branch_1"], seeded["warehouse_id"],
                             t0, t0 + timedelta(hours=4), t0 + timedelta(hours=24))
    # Branch 2 — approx 72h each
    for i in range(3):
        t0 = base + timedelta(hours=i)
        _make_received_order(db, seeded["branch_2"], seeded["warehouse_id"],
                             t0, t0 + timedelta(hours=24), t0 + timedelta(hours=72))
    # Branch 3 — only 1 order, should be omitted from top (needs ≥3)
    _make_received_order(db, seeded["branch_3"], seeded["warehouse_id"],
                         base, base + timedelta(hours=5), base + timedelta(hours=10))
    db.commit()

    tok = _login(client, "an_admin")
    r = client.get("/api/v1/dashboard/order-delay-analytics?days=30",
                   headers=_auth(tok))
    assert r.status_code == 200
    data = r.json()
    assert data["total_orders_measured"] == 7

    top_branch_ids = [b["branch_id"] for b in data["top_delayed_branches"]]
    assert seeded["branch_1"] in top_branch_ids
    assert seeded["branch_2"] in top_branch_ids
    # Branch 3 has only 1 order — must NOT appear
    assert seeded["branch_3"] not in top_branch_ids
    # Branch 2 should be slower than branch 1 → appear first
    assert data["top_delayed_branches"][0]["branch_id"] == seeded["branch_2"]


def test_order_delay_rbac_blocks_branch_user(client, seeded):
    tok = _login(client, "an_staff1")
    r = client.get("/api/v1/dashboard/order-delay-analytics?days=30",
                   headers=_auth(tok))
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# G7 — Branches open actions
# ═══════════════════════════════════════════════════════════════════════════
def _ensure_quality_visit_item(db: Session) -> int:
    sec = QualityVisitSection(name_ar="قسم", name_en="Sec", order=0)
    db.add(sec)
    db.flush()
    it = QualityVisitItem(
        section_id=sec.id,
        text_ar="بند",
        text_en="Item",
        response_type="yes_no",
    )
    db.add(it)
    db.flush()
    return it.id


def _make_visit_with_response(
    db,
    branch_id,
    seeded: dict,
    item_id: int,
    *,
    resolved: bool,
    overdue: bool,
    visit_deleted: bool = False,
    due_date: Optional[date] = None,
):
    """Creates a visit + a single 'no' response. Overdue = due_date in past."""
    visit = QualityVisit(
        branch_id=branch_id,
        visitor_id=seeded["admin_id"],
        visit_date=date.today(),
        status=QualityVisitStatus.closed,
        is_deleted=visit_deleted,
    )
    db.add(visit)
    db.flush()
    if due_date is not None:
        due = due_date
    else:
        due = date.today() - timedelta(days=3) if overdue else date.today() + timedelta(days=3)
    resp = QualityVisitResponse(
        visit_id=visit.id,
        item_id=item_id,
        status=QualityResponseStatus.no,
        is_resolved=resolved,
        corrective_action="Fix it",
        due_date=due,
    )
    db.add(resp)
    return visit, resp


def test_branches_open_actions_counts_correctly(client, seeded, db):
    item_id = _ensure_quality_visit_item(db)
    # Branch 1: 2 open (1 overdue, 1 not), 1 resolved (must be skipped), 1 deleted-visit (must be skipped)
    _make_visit_with_response(db, seeded["branch_1"], seeded, item_id, resolved=False, overdue=True)
    _make_visit_with_response(db, seeded["branch_1"], seeded, item_id, resolved=False, overdue=False)
    _make_visit_with_response(db, seeded["branch_1"], seeded, item_id, resolved=True, overdue=False)
    _make_visit_with_response(
        db, seeded["branch_1"], seeded, item_id, resolved=False, overdue=False, visit_deleted=True
    )
    # Branch 2: 1 open
    _make_visit_with_response(db, seeded["branch_2"], seeded, item_id, resolved=False, overdue=False)
    # Branch 3: only resolved — should NOT appear
    _make_visit_with_response(db, seeded["branch_3"], seeded, item_id, resolved=True, overdue=False)
    db.commit()

    tok = _login(client, "an_admin")
    r = client.get("/api/v1/dashboard/branches-open-actions?limit=10",
                   headers=_auth(tok))
    assert r.status_code == 200
    data = r.json()

    by_branch = {row["branch_id"]: row for row in data["branches"]}
    assert seeded["branch_1"] in by_branch
    assert seeded["branch_2"] in by_branch
    assert seeded["branch_3"] not in by_branch   # no open actions

    assert by_branch[seeded["branch_1"]]["open_actions"] == 2
    assert by_branch[seeded["branch_1"]]["overdue_actions"] == 1
    assert by_branch[seeded["branch_2"]]["open_actions"] == 1
    assert by_branch[seeded["branch_2"]]["overdue_actions"] == 0


def test_branches_open_actions_rbac(client, seeded):
    tok = _login(client, "an_staff1")
    r = client.get("/api/v1/dashboard/branches-open-actions",
                   headers=_auth(tok))
    assert r.status_code == 403


def test_consumption_trend_excludes_future_dated_transactions(client, seeded, db):
    """G9 upper-bound: rows strictly after today must not affect totals."""
    now = datetime.utcnow()
    cat = ItemCategory(code="AN-CAT-FUT", name_ar="ت", name_en="C")
    db.add(cat)
    db.flush()
    uom = UnitOfMeasure(code="AN-U-FUT", name_ar="ح", name_en="u")
    db.add(uom)
    db.flush()
    item = Item(
        item_code="AN-ITEM-FUT",
        item_name_ar="ص",
        item_name_en="I",
        category_id=cat.id,
        unit_id=uom.id,
    )
    db.add(item)
    db.flush()
    future = now + timedelta(days=2)
    db.add_all([
        StockTransaction(
            transaction_date=future,
            transaction_type=TransactionType.inventory_adjustment,
            source_type="branch",
            source_id=seeded["branch_1"],
            item_id=item.id,
            qty=Decimal("-99"),
        ),
        StockTransaction(
            transaction_date=now,
            transaction_type=TransactionType.inventory_adjustment,
            source_type="branch",
            source_id=seeded["branch_1"],
            item_id=item.id,
            qty=Decimal("-4"),
        ),
    ])
    db.commit()

    tok = _login(client, "an_admin")
    r = client.get(
        f"/api/v1/dashboard/branch/{seeded['branch_1']}/consumption-trend?days=7",
        headers=_auth(tok),
    )
    assert r.status_code == 200
    assert r.json()["total_consumed"] == 4.0


def test_consumption_trend_window_lengths_30_and_90(client, seeded):
    tok = _login(client, "an_admin")
    for days in (30, 90):
        r = client.get(
            f"/api/v1/dashboard/branch/{seeded['branch_1']}/consumption-trend?days={days}",
            headers=_auth(tok),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["days"] == days
        assert len(body["trend"]) == days


def test_order_delay_excludes_branches_with_only_two_samples(client, seeded, db):
    base = datetime.utcnow() - timedelta(days=5)
    for i in range(2):
        t0 = base + timedelta(hours=i)
        _make_received_order(
            db, seeded["branch_3"], seeded["warehouse_id"],
            t0, t0 + timedelta(hours=1), t0 + timedelta(hours=10),
        )
    db.commit()

    tok = _login(client, "an_admin")
    r = client.get("/api/v1/dashboard/order-delay-analytics?days=30", headers=_auth(tok))
    assert r.status_code == 200
    top_ids = [b["branch_id"] for b in r.json()["top_delayed_branches"]]
    assert seeded["branch_3"] not in top_ids


def test_order_delay_branch_id_filter(client, seeded, db):
    base = datetime.utcnow() - timedelta(days=5)
    for i in range(3):
        t0 = base + timedelta(hours=i)
        _make_received_order(
            db, seeded["branch_1"], seeded["warehouse_id"],
            t0, t0 + timedelta(hours=2), t0 + timedelta(hours=20),
        )
    for i in range(3):
        t0 = base + timedelta(hours=10 + i)
        _make_received_order(
            db, seeded["branch_2"], seeded["warehouse_id"],
            t0, t0 + timedelta(hours=2), t0 + timedelta(hours=20),
        )
    db.commit()

    tok = _login(client, "an_admin")
    r = client.get(
        f"/api/v1/dashboard/order-delay-analytics?days=30&branch_id={seeded['branch_1']}",
        headers=_auth(tok),
    )
    assert r.status_code == 200
    assert r.json()["total_orders_measured"] == 3


def test_order_delay_warehouse_id_filter(client, seeded, db):
    wh2 = Warehouse(
        warehouse_code="WH-AN-FLT",
        warehouse_name="Filter WH",
        location="Test",
        active=True,
    )
    db.add(wh2)
    db.flush()
    base = datetime.utcnow() - timedelta(days=5)
    for i in range(3):
        t0 = base + timedelta(hours=i)
        _make_received_order(
            db, seeded["branch_1"], wh2.id,
            t0, t0 + timedelta(hours=2), t0 + timedelta(hours=20),
        )
    db.commit()

    tok = _login(client, "an_admin")
    r = client.get(
        f"/api/v1/dashboard/order-delay-analytics?days=30&warehouse_id={wh2.id}",
        headers=_auth(tok),
    )
    assert r.status_code == 200
    assert r.json()["total_orders_measured"] == 3


def test_branches_open_actions_due_today_not_overdue(client, seeded, db):
    """Dashboard counts overdue only when due_date < today (not <=)."""
    item_id = _ensure_quality_visit_item(db)
    _make_visit_with_response(
        db,
        seeded["branch_1"],
        seeded,
        item_id,
        resolved=False,
        overdue=False,
        due_date=date.today(),
    )
    db.commit()

    tok = _login(client, "an_admin")
    r = client.get("/api/v1/dashboard/branches-open-actions", headers=_auth(tok))
    assert r.status_code == 200
    row = next(x for x in r.json()["branches"] if x["branch_id"] == seeded["branch_1"])
    assert row["open_actions"] == 1
    assert row["overdue_actions"] == 0


def test_resolved_open_action_removed_from_branch_counts(client, seeded, db):
    item_id = _ensure_quality_visit_item(db)
    _visit, resp = _make_visit_with_response(
        db, seeded["branch_1"], seeded, item_id, resolved=False, overdue=False,
    )
    db.commit()

    tok = _login(client, "an_admin")
    r1 = client.get("/api/v1/dashboard/branches-open-actions", headers=_auth(tok))
    assert r1.status_code == 200
    row1 = next(x for x in r1.json()["branches"] if x["branch_id"] == seeded["branch_1"])
    assert row1["open_actions"] == 1

    resp.is_resolved = True
    db.commit()

    r2 = client.get("/api/v1/dashboard/branches-open-actions", headers=_auth(tok))
    assert r2.status_code == 200
    ids = {x["branch_id"] for x in r2.json()["branches"]}
    assert seeded["branch_1"] not in ids
