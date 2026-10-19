"""Shift-ops integrity: reopen audit snapshot + close-no-activity guard (TG reopen audit fix)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.security import get_password_hash
from app.models import (
    AuditLog,
    Branch,
    BranchBrand,
    Brand,
    BrandShiftCountItem,
    Item,
    ItemBrand,
    ItemCategory,
    Role,
    RoleName,
    UnitOfMeasure,
    User,
    UserRole,
    Warehouse,
)
from app.models.branch_shift_ops import BranchShiftConfig, BranchShiftReopenEvent, BranchShiftStatus

API = "/api/v1/shift-ops"
PASSWORD = "Pass@2026"


@pytest.fixture(autouse=True)
def _shift_ops_audit_fix_env(monkeypatch):
    monkeypatch.setattr("app.config.settings.SHIFT_CASH_ENABLED", True)
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")


def _role(db, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if not row:
        row = Role(name=name, display_name=name.value, description="")
        db.add(row)
        db.flush()
    return row


def _user(db, username: str, role_name: RoleName, branch_id=None) -> User:
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


def _seed(db, *, items: int = 2, suffix: str = "AF") -> dict:
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-B1",
        branch_name="Audit Fix Branch",
        city="Riyadh",
        area="Olaya",
        warehouse_id=wh.id,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"{suffix}-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    unit = UnitOfMeasure(code=f"{suffix}-PCS", name_ar="pcs", name_en="pcs")
    db.add(unit)
    db.flush()

    item_ids = []
    for i in range(items):
        item = Item(
            item_code=f"{suffix}-ITEM-{i}",
            item_name_ar=f"صنف {i}",
            item_name_en=f"Item {i}",
            category_id=cat.id,
            unit_id=unit.id,
            active=True,
            is_deleted=False,
        )
        db.add(item)
        db.flush()
        db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
        db.add(BrandShiftCountItem(brand_id=brand.id, item_id=item.id, display_order=i + 1, is_active=True))
        item_ids.append(item.id)

    db.add(
        BranchShiftConfig(
            branch_id=branch.id,
            shift_number=1,
            shift_name_ar="الشفت 1",
            is_active=True,
            effective_from=date(2020, 1, 1),
            effective_to=None,
        )
    )
    users = {
        "branch": _user(db, f"{suffix}_bm", RoleName.branch_manager, branch.id),
        "branch_user": _user(db, f"{suffix}_bu", RoleName.branch_user, branch.id),
        "admin": _user(db, f"{suffix}_admin", RoleName.admin),
        "ops": _user(db, f"{suffix}_ops", RoleName.operations_manager),
    }
    db.commit()
    return {"branch_id": branch.id, "item_ids": item_ids, "usernames": {k: v.username for k, v in users.items()}}


def _open_shift(client, hdr, day="2026-09-01"):
    resp = client.post(f"{API}/shifts", json={"shift_date": day, "shift_number": 1}, headers=hdr)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _submit_count_with_closings(client, hdr, shift_id, closings: list[float]):
    created = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    assert created.status_code in (200, 201), created.text
    lines = created.json()["lines"]
    assert len(lines) == len(closings)
    payload = {
        "lines": [
            {
                "item_id": ln["item_id"],
                "received_qty": 0,
                "returned_qty": 0,
                "damaged_qty": 0,
                "closing_balance": closing,
            }
            for ln, closing in zip(lines, closings)
        ]
    }
    assert client.patch(f"{API}/shifts/{shift_id}/count/lines", json=payload, headers=hdr).status_code == 200
    submit = client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr)
    assert submit.status_code == 200, submit.text
    return submit.json()


def _fill_and_submit_cash(client, hdr, shift_id):
    body = {
        "total_sale": 100,
        "bill_count": 2,
        "mada_sales": 60,
        "cash_sales": 40,
        "app_sales": 0,
        "refund_bill": 0,
        "exchange_amount": 0,
        "expiry_amount": 0,
        "cash_expense": 0,
        "cash_float_carried_forward": 0,
        "cash_deposited": 40,
    }
    assert client.put(f"{API}/shifts/{shift_id}/cash", json=body, headers=hdr).status_code == 200
    assert client.post(f"{API}/shifts/{shift_id}/cash/submit", headers=hdr).status_code == 200


def _reopen(client, hdr, shift_id, *, target="count", reason="تصحيح بعد المراجعة", admin_override=False):
    body = {"target": target, "reason": reason, "admin_override": admin_override}
    return client.post(f"{API}/shifts/{shift_id}/reopen", json=body, headers=hdr)


def _latest_reopen_audit(db) -> AuditLog:
    row = (
        db.query(AuditLog)
        .filter(AuditLog.module == "shift_ops", AuditLog.action == "shift_reopened")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row is not None
    return row


def test_reopen_audit_old_values_capture_all_lines(db, client):
    """a) After submit, reopen stores original quantities and submitted_by/at in old_values."""
    seed = _seed(db, items=3, suffix="A1")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr)
    submitted = _submit_count_with_closings(client, bhdr, shift_id, [1.0, 2.0, 3.0])
    _fill_and_submit_cash(client, bhdr, shift_id)

    bm = db.query(User).filter(User.username == seed["usernames"]["branch"]).one()
    before_audit = db.query(AuditLog).count()

    assert _reopen(client, ahdr, shift_id, target="count").status_code == 200

    entry = _latest_reopen_audit(db)
    assert entry.user_id is not None
    new_values = json.loads(entry.new_values)
    assert set(new_values.keys()) == {"target", "reason"}
    assert new_values["target"] == "count"

    old_values = json.loads(entry.old_values)
    assert old_values["count_id"] == submitted["id"]
    assert old_values["count_status"] == "submitted"
    assert old_values["shift_status"] == "submitted"
    assert old_values["submitted_by"] == bm.id
    assert old_values["submitted_at"] is not None
    assert len(old_values["lines"]) == 3
    closings = {ln["item_id"]: Decimal(ln["closing_balance"]) for ln in old_values["lines"]}
    expected = [Decimal("1"), Decimal("2"), Decimal("3")]
    for ln, exp in zip(submitted["lines"], expected):
        assert closings[ln["item_id"]] == exp
    assert db.query(AuditLog).count() == before_audit + 1


def test_reopen_audit_old_values_unchanged_after_resubmit(db, client):
    """b) Patch after reopen + re-submit: old_values frozen; live lines updated."""
    seed = _seed(db, items=2, suffix="B2")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr)
    submitted = _submit_count_with_closings(client, bhdr, shift_id, [5.0, 6.0])
    _fill_and_submit_cash(client, bhdr, shift_id)

    assert _reopen(client, ahdr, shift_id, target="count").status_code == 200
    entry = _latest_reopen_audit(db)
    old_values = json.loads(entry.old_values)
    original_closings = {ln["item_id"]: ln["closing_balance"] for ln in old_values["lines"]}  # strings

    lines = client.get(f"{API}/shifts/{shift_id}/count", headers=bhdr).json()["lines"]
    patch = {
        "lines": [
            {
                "item_id": ln["item_id"],
                "received_qty": 0,
                "returned_qty": 0,
                "damaged_qty": 0,
                "closing_balance": 50.0 + idx,
            }
            for idx, ln in enumerate(lines)
        ]
    }
    assert client.patch(f"{API}/shifts/{shift_id}/count/lines", json=patch, headers=bhdr).status_code == 200
    resubmit = client.post(f"{API}/shifts/{shift_id}/count/submit", headers=bhdr)
    assert resubmit.status_code == 200
    live = {ln["item_id"]: Decimal(ln["closing_balance"]) for ln in resubmit.json()["lines"]}

    db.refresh(entry)
    old_after = json.loads(entry.old_values)
    assert {
        ln["item_id"]: Decimal(ln["closing_balance"]) for ln in old_after["lines"]
    } == {k: Decimal(v) for k, v in original_closings.items()}
    assert live == {lines[0]["item_id"]: Decimal("50"), lines[1]["item_id"]: Decimal("51")}


def test_close_no_activity_rejects_submitted_count(db, client):
    """c) close-no-activity refused when count submitted; no exception/audit side effects."""
    seed = _seed(db, suffix="C3")
    bhdr = _login(client, seed["usernames"]["branch"])
    ops_hdr = _login(client, seed["usernames"]["ops"])
    shift_id = _open_shift(client, bhdr)
    _submit_count_with_closings(client, bhdr, shift_id, [1.0, 2.0])

    audit_before = db.query(AuditLog).filter(AuditLog.module == "shift_ops").count()
    reopen_before = db.query(BranchShiftReopenEvent).count()

    resp = client.post(
        f"{API}/shifts/{shift_id}/close-no-activity",
        json={"exception_type": "branch_closed", "reason": "Branch closed for holiday"},
        headers=ops_hdr,
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "shift_ops.count_already_submitted"

    body = client.get(f"{API}/shifts/{shift_id}", headers=bhdr).json()
    assert body["count_status"] == "submitted"
    assert body["status"] != BranchShiftStatus.exception_locked.value
    assert body["exception_type"] is None
    assert db.query(AuditLog).filter(AuditLog.module == "shift_ops").count() == audit_before
    assert db.query(BranchShiftReopenEvent).count() == reopen_before


def test_close_no_activity_still_works_without_submitted_count(db, client):
    """d) Regression: draft shift without count can still be exception-locked."""
    seed = _seed(db, suffix="D4")
    bhdr = _login(client, seed["usernames"]["branch"])
    ops_hdr = _login(client, seed["usernames"]["ops"])
    shift_id = _open_shift(client, bhdr)

    resp = client.post(
        f"{API}/shifts/{shift_id}/close-no-activity",
        json={"exception_type": "manual_gap", "reason": "No activity this day"},
        headers=ops_hdr,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == BranchShiftStatus.exception_locked.value


def test_reopen_disallowed_role_still_refused(db, client):
    """e) branch_user still cannot reopen."""
    seed = _seed(db, suffix="E5")
    bhdr = _login(client, seed["usernames"]["branch"])
    buhdr = _login(client, seed["usernames"]["branch_user"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr)
    _submit_count_with_closings(client, bhdr, shift_id, [1.0, 2.0])
    _fill_and_submit_cash(client, bhdr, shift_id)

    assert _reopen(client, buhdr, shift_id).status_code == 403
    assert _reopen(client, ahdr, shift_id).status_code == 200


def test_reopen_limit_still_enforced(db, client):
    """e) Max-2 reopen cap still enforced (admin override for third)."""
    seed = _seed(db, suffix="E6")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr, day="2026-09-10")
    _submit_count_with_closings(client, bhdr, shift_id, [1.0, 2.0])
    _fill_and_submit_cash(client, bhdr, shift_id)

    for _ in range(2):
        assert _reopen(client, ahdr, shift_id, target="both").status_code == 200
        _submit_count_with_closings(client, bhdr, shift_id, [1.0, 2.0])
        _fill_and_submit_cash(client, bhdr, shift_id)

    blocked = _reopen(client, ahdr, shift_id)
    assert blocked.status_code == 409
    assert blocked.json()["error_code"] == "REOPEN_LIMIT_REACHED"

    bypass = _reopen(client, ahdr, shift_id, admin_override=True)
    assert bypass.status_code == 200


def test_reopen_window_still_enforced(db, client):
    """e) 48h reopen window still enforced from submission time."""
    from datetime import datetime

    from app.models.branch_shift_ops import BranchShift, BranchShiftCash, BranchShiftCount

    seed = _seed(db, suffix="E7")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr, day="2026-09-11")
    _submit_count_with_closings(client, bhdr, shift_id, [1.0, 2.0])
    _fill_and_submit_cash(client, bhdr, shift_id)

    shift = db.query(BranchShift).filter(BranchShift.id == shift_id).one()
    count = db.query(BranchShiftCount).filter(BranchShiftCount.shift_id == shift_id).one()
    cash = db.query(BranchShiftCash).filter(BranchShiftCash.shift_id == shift_id).one()
    stale = datetime.utcnow() - timedelta(hours=49)
    shift.submitted_at = stale
    count.submitted_at = stale
    cash.submitted_at = stale
    db.commit()

    expired = _reopen(client, ahdr, shift_id, target="count")
    assert expired.status_code == 409
    assert expired.json()["error_code"] == "REOPEN_WINDOW_EXPIRED"
