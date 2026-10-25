"""Count Audit opening-count baseline (PostgreSQL)."""
from __future__ import annotations

import secrets
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.security import get_password_hash
from app.models import Branch, BranchBrand, Brand, Item, ItemBrand, ItemCategory, Role, RoleName, UnitOfMeasure, User, UserRole, Warehouse
from app.models.branch_shift_ops import (
    BranchShift,
    BranchShiftConfig,
    BranchShiftCount,
    BranchShiftCountLine,
    BranchShiftStatus,
    ShiftCountRowStatus,
    ShiftSectionStatus,
)

CA = "/api/v1/audit/findings/count-audit"
PASSWORD = "Aa1!" + secrets.token_urlsafe(12)


def _role(db, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if not row:
        row = Role(name=name, display_name=name.value, description="")
        db.add(row)
        db.flush()
    return row


def _user(db, username: str, role_name: RoleName, *, branch_id=None) -> User:
    role = _role(db, role_name)
    row = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash(PASSWORD),
        branch_id=branch_id,
        status="active",
        is_deleted=False,
    )
    db.add(row)
    db.flush()
    db.add(UserRole(user_id=row.id, role_id=role.id))
    db.flush()
    return row


def _login(client, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed_branch(db, suffix: str, *, active: bool = True) -> dict:
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-BR",
        branch_name=f"Branch {suffix}",
        city="Riyadh",
        area="Test",
        warehouse_id=wh.id,
        active=active,
        is_deleted=False,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"{suffix}-C", name_ar="c", name_en="c")
    db.add(cat)
    unit = UnitOfMeasure(code=f"{suffix}-U", name_ar="u", name_en="u")
    db.add(unit)
    db.flush()
    item = Item(
        item_code=f"{suffix}-IT",
        item_name_ar="item",
        item_name_en="item",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()
    db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
    db.add(
        BranchShiftConfig(
            branch_id=branch.id,
            shift_number=1,
            shift_name_ar="1",
            is_active=True,
            effective_from=date(2020, 1, 1),
        )
    )
    opener = _user(db, f"{suffix}.opener", RoleName.branch_manager, branch_id=branch.id)
    db.flush()
    return {"branch": branch, "item": item, "opener": opener}


def _add_submitted_shift(
    db,
    ctx: dict,
    *,
    shift_date: date,
    shift_number: int = 1,
    shift_status=BranchShiftStatus.submitted,
    opening_balance=Decimal("0"),
    closing_balance=Decimal("5"),
    movement_diff=Decimal("-5"),
) -> dict:
    shift = BranchShift(
        branch_id=ctx["branch"].id,
        shift_date=shift_date,
        shift_number=shift_number,
        status=shift_status.value,
        opened_by=ctx["opener"].id,
        submitted_at=datetime.utcnow(),
    )
    db.add(shift)
    db.flush()
    count = BranchShiftCount(
        shift_id=shift.id,
        status=ShiftSectionStatus.submitted.value,
        items_frozen_at=datetime.utcnow(),
        created_by=ctx["opener"].id,
        submitted_at=datetime.utcnow(),
    )
    db.add(count)
    db.flush()
    line = BranchShiftCountLine(
        count_id=count.id,
        item_id=ctx["item"].id,
        item_name_snapshot="item",
        unit_snapshot="u",
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        movement_diff=movement_diff,
        row_status=ShiftCountRowStatus.valid.value,
    )
    db.add(line)
    db.flush()
    return {"shift": shift, "count": count, "line": line}


@pytest.fixture(autouse=True)
def _pg_only(db):
    from app.config import settings

    if settings.DATABASE_URL.startswith("sqlite"):
        pytest.skip("PostgreSQL only")


def test_opening_count_zero_variance_in_shifts_and_coverage(client, db):
    ctx = _seed_branch(db, "OB1")
    first = _add_submitted_shift(db, ctx, shift_date=date(2026, 7, 1))
    _user(db, "ob1.auditor", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "ob1.auditor")
    d0, d1 = "2026-07-01", "2026-07-01"
    shifts = client.get(f"{CA}/shifts?date_from={d0}&date_to={d1}", headers=ah)
    assert shifts.status_code == 200
    row = shifts.json()["items"][0]
    assert row["is_opening_count"] is True
    assert row["surplus_lines"] == 0
    assert row["shortage_lines"] == 0
    cov = client.get(f"{CA}/coverage?date_from={d0}&date_to={d1}", headers=ah)
    assert cov.status_code == 200
    cell = cov.json()["branches"][0]["days"][d0]
    assert cell["has_diff"] is False
    var_default = client.get(f"{CA}/variances?date_from={d0}&date_to={d1}&group=line", headers=ah)
    assert var_default.status_code == 200
    assert var_default.json()["total"] == 0
    var_inc = client.get(
        f"{CA}/variances?date_from={d0}&date_to={d1}&group=line&include_opening=true",
        headers=ah,
    )
    assert var_inc.status_code == 200
    assert var_inc.json()["total"] == 1
    assert var_inc.json()["items"][0]["shift_id"] == first["shift"].id


def test_second_count_variances_normal(client, db):
    ctx = _seed_branch(db, "OB2")
    _add_submitted_shift(db, ctx, shift_date=date(2026, 7, 1))
    _add_submitted_shift(
        db,
        ctx,
        shift_date=date(2026, 7, 2),
        opening_balance=Decimal("5"),
        closing_balance=Decimal("3"),
        movement_diff=Decimal("2"),
    )
    _user(db, "ob2.auditor", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "ob2.auditor")
    var = client.get(f"{CA}/variances?date_from=2026-07-02&date_to=2026-07-02&group=line", headers=ah)
    assert var.status_code == 200
    assert var.json()["total"] == 1
    shifts = client.get(f"{CA}/shifts?date_from=2026-07-02&date_to=2026-07-02", headers=ah)
    row = shifts.json()["items"][0]
    assert row["is_opening_count"] is False
    assert row["shortage_lines"] == 1


def test_opening_finding_with_items_rejected_without_items_ok(client, db):
    ctx = _seed_branch(db, "OB3")
    first = _add_submitted_shift(db, ctx, shift_date=date(2026, 7, 1))
    auditor = _user(db, "ob3.auditor", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "ob3.auditor")
    bad = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "ob3-items-001",
            "shift_id": first["shift"].id,
            "severity": "info",
            "title": "Should fail items",
            "description": "Opening count must not attach line items.",
            "item_ids": [ctx["item"].id],
        },
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["error_code"] == "COUNT_AUDIT_OPENING_COUNT_NO_VARIANCE"
    ok = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "ob3-no-items-001",
            "shift_id": first["shift"].id,
            "severity": "info",
            "title": "Remark only",
            "description": "General remark on opening count without line items.",
            "item_ids": [],
        },
    )
    assert ok.status_code == 200, ok.text


def test_exception_locked_prior_does_not_make_next_opening(client, db):
    ctx = _seed_branch(db, "OB4")
    _add_submitted_shift(
        db,
        ctx,
        shift_date=date(2026, 7, 1),
        shift_status=BranchShiftStatus.exception_locked,
    )
    _add_submitted_shift(
        db,
        ctx,
        shift_date=date(2026, 7, 2),
        opening_balance=Decimal("5"),
        closing_balance=Decimal("4"),
        movement_diff=Decimal("1"),
    )
    _user(db, "ob4.auditor", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "ob4.auditor")
    shifts = client.get(f"{CA}/shifts?date_from=2026-07-02&date_to=2026-07-02", headers=ah)
    row = shifts.json()["items"][0]
    assert row["is_opening_count"] is False
    assert row["shortage_lines"] == 1


def test_opening_shift_detail_zero_movement_diff_in_response(client, db):
    ctx = _seed_branch(db, "OB5")
    seeded = _add_submitted_shift(
        db,
        ctx,
        shift_date=date(2026, 7, 1),
        movement_diff=Decimal("-12"),
        closing_balance=Decimal("12"),
    )
    _user(db, "ob5.auditor", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "ob5.auditor")
    detail = client.get(f"{CA}/shifts/{seeded['shift'].id}", headers=ah)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["is_opening_count"] is True
    for line in body["count"]["lines"]:
        assert float(line["movement_diff"]) == 0.0
    db.refresh(seeded["line"])
    assert seeded["line"].movement_diff == Decimal("-12")


def test_inactive_branch_opening_excluded_from_variances(client, db):
    ctx = _seed_branch(db, "OB6", active=False)
    opening = _add_submitted_shift(
        db,
        ctx,
        shift_date=date(2026, 7, 1),
        movement_diff=Decimal("-8"),
    )
    _user(db, "ob6.auditor", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "ob6.auditor")
    params = {
        "date_from": "2026-07-01",
        "date_to": "2026-07-01",
        "group": "line",
        "branch_id": ctx["branch"].id,
    }
    var = client.get(f"{CA}/variances", headers=ah, params=params)
    assert var.status_code == 200
    assert var.json()["total"] == 0
    with_opening = client.get(f"{CA}/variances", headers=ah, params={**params, "include_opening": "true"})
    assert with_opening.status_code == 200
    assert with_opening.json()["total"] == 1
    assert with_opening.json()["items"][0]["shift_id"] == opening["shift"].id
