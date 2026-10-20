"""Shift open date validation (D1–D3) — validation ENABLED; clock patched on validation module."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from zoneinfo import ZoneInfo

from app.config import Settings, settings
from app.core.security import get_password_hash
from app.models import (
    AreaManagerAssignment,
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
from app.models.branch_shift_ops import BranchShift, BranchShiftConfig, BranchShiftStatus
from app.services import shift_ops_date_validation as sdv

API = "/api/v1/shift-ops"
PASSWORD = "Pass@2026"
ANCHOR = date(2026, 8, 15)


@pytest.fixture(autouse=True)
def _validation_enabled(monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_DATE_VALIDATION_ENABLED", True)


@pytest.fixture(autouse=True)
def _anchor_today(monkeypatch):
    monkeypatch.setattr(sdv, "shift_open_today", lambda: ANCHOR)


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


def _seed(db, *, suffix: str = "SDV", shift_configs: tuple[int, ...] = (1,)):
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-B1",
        branch_name="Date Val Branch",
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
    unit = UnitOfMeasure(code=f"{suffix}-PCS", name_ar="قطعة", name_en="pcs")
    db.add(unit)
    db.flush()
    item = Item(
        item_code=f"{suffix}-ITEM-1",
        item_name_ar="صنف",
        item_name_en="Item",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()
    db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
    db.add(BrandShiftCountItem(brand_id=brand.id, item_id=item.id, display_order=1, is_active=True))
    for n in shift_configs:
        db.add(
            BranchShiftConfig(
                branch_id=branch.id,
                shift_number=n,
                shift_name_ar=f"الشفت {n}",
                is_active=True,
                effective_from=date(2020, 1, 1),
                effective_to=None,
            )
        )
    bm = _user(db, f"{suffix}_bm", RoleName.branch_manager, branch.id)
    am = _user(db, f"{suffix}_am", RoleName.area_manager)
    db.add(AreaManagerAssignment(user_id=am.id, city="Riyadh", brand_id=brand.id, active=True))
    admin = _user(db, f"{suffix}_admin", RoleName.admin)
    db.commit()
    return {
        "branch_id": branch.id,
        "item_id": item.id,
        "bm": bm.username,
        "am": am.username,
        "admin": admin.username,
    }


def test_t1_future_date_rejected_all_roles(client, db):
    seed = _seed(db, suffix="T1")
    bm_hdr = _login(client, seed["bm"])
    resp_bm = client.post(
        f"{API}/shifts",
        json={"shift_date": "2026-08-16", "shift_number": 1},
        headers=bm_hdr,
    )
    assert resp_bm.status_code == 422
    assert resp_bm.json()["error_code"] == "shift_ops.date_in_future"
    for user in (seed["am"], seed["admin"]):
        hdr = _login(client, user)
        resp = client.post(
            f"{API}/shifts",
            json={
                "branch_id": seed["branch_id"],
                "shift_date": "2026-08-16",
                "shift_number": 1,
                "override": True,
                "override_reason": "Manager-assisted open",
            },
            headers=hdr,
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["error_code"] == "shift_ops.date_in_future"


def test_t2_branch_manager_today_and_yesterday(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_CASH_ENABLED", False)
    seed = _seed(db, suffix="T2")
    hdr = _login(client, seed["bm"])
    s_y = client.post(f"{API}/shifts", json={"shift_date": "2026-08-14", "shift_number": 1}, headers=hdr)
    assert s_y.status_code == 201, s_y.text
    _submit_count_only(client, hdr, s_y.json()["id"])
    s_t = client.post(f"{API}/shifts", json={"shift_date": "2026-08-15", "shift_number": 1}, headers=hdr)
    assert s_t.status_code == 201, s_t.text
    resp = client.post(
        f"{API}/shifts",
        json={"shift_date": "2026-08-13", "shift_number": 1},
        headers=hdr,
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "shift_ops.date_too_old"


def _submit_count_only(client, hdr, shift_id: int, *, closing: float | None = None) -> None:
    count = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr).json()
    line = count["lines"][0]
    bal = closing if closing is not None else float(line["opening_balance"])
    client.patch(
        f"{API}/shifts/{shift_id}/count/lines",
        json={
            "lines": [
                {
                    "item_id": line["item_id"],
                    "received_qty": 0,
                    "returned_qty": 0,
                    "damaged_qty": 0,
                    "closing_balance": bal,
                }
            ]
        },
        headers=hdr,
    )
    client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr)


def test_t3_area_manager_backdate_audit(client, db, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")
    seed = _seed(db, suffix="T3")
    hdr = _login(client, seed["am"])
    mgr_open = {
        "branch_id": seed["branch_id"],
        "override": True,
        "override_reason": "Area manager opening shift",
    }
    bad = client.post(
        f"{API}/shifts",
        json={**mgr_open, "shift_date": "2026-08-10", "shift_number": 1},
        headers=hdr,
    )
    assert bad.status_code == 422
    assert bad.json()["error_code"] == "shift_ops.backdate_reason_required"
    good = client.post(
        f"{API}/shifts",
        json={
            **mgr_open,
            "shift_date": "2026-08-10",
            "shift_number": 1,
            "backdate_reason": "Late entry approved",
        },
        headers=hdr,
    )
    assert good.status_code == 201, good.text
    shift_id = good.json()["id"]
    row = (
        db.query(AuditLog)
        .filter(AuditLog.action == "shift_open_backdated", AuditLog.entity_id == shift_id)
        .one()
    )
    assert row.module == "shift_ops"
    assert row.new_values is not None
    assert "age_days" in (row.new_values if isinstance(row.new_values, str) else str(row.new_values))
    shift = db.query(BranchShift).filter_by(id=shift_id).one()
    assert shift.status == BranchShiftStatus.draft.value


def test_t4_beyond_max_backdate_even_admin(client, db):
    seed = _seed(db, suffix="T4")
    hdr = _login(client, seed["admin"])
    resp = client.post(
        f"{API}/shifts",
        json={
            "branch_id": seed["branch_id"],
            "shift_date": "2026-08-07",
            "shift_number": 1,
            "override": True,
            "override_reason": "Admin backdate attempt",
            "backdate_reason": "Too far back",
        },
        headers=hdr,
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "shift_ops.date_beyond_max_backdate"


def test_t5_d3_middle_insert_rejected(client, db):
    seed = _seed(db, suffix="T5")
    bm = _login(client, seed["bm"])
    client.post(f"{API}/shifts", json={"shift_date": "2026-08-14", "shift_number": 1}, headers=bm)
    admin = _login(client, seed["admin"])
    resp = client.post(
        f"{API}/shifts",
        json={
            "branch_id": seed["branch_id"],
            "shift_date": "2026-08-13",
            "shift_number": 1,
            "override": True,
            "override_reason": "Attempt middle insert",
            "backdate_reason": "Backfill attempt",
        },
        headers=admin,
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "shift_ops.date_not_after_latest"


def test_t6_gap_open_after_submitted_carry_over(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_CASH_ENABLED", False)
    seed = _seed(db, suffix="T6")
    am = _login(client, seed["am"])
    s1_resp = client.post(
        f"{API}/shifts",
        json={
            "branch_id": seed["branch_id"],
            "shift_date": "2026-08-10",
            "shift_number": 1,
            "override": True,
            "override_reason": "Open gap week start",
            "backdate_reason": "Late count for Aug 10",
        },
        headers=am,
    )
    assert s1_resp.status_code == 201, s1_resp.text
    s1 = s1_resp.json()
    hdr = _login(client, seed["bm"])
    _submit_count_only(client, hdr, s1["id"], closing=12)
    s2 = client.post(f"{API}/shifts", json={"shift_date": "2026-08-15", "shift_number": 1}, headers=hdr)
    assert s2.status_code == 201, s2.text
    count2 = client.post(f"{API}/shifts/{s2.json()['id']}/count", headers=hdr).json()
    assert Decimal(str(count2["lines"][0]["opening_balance"])) == Decimal("12")


def test_t7_shift_number_must_be_configured(client, db):
    seed = _seed(db, suffix="T7", shift_configs=(1,))
    hdr = _login(client, seed["bm"])
    bad = client.post(f"{API}/shifts", json={"shift_date": "2026-08-15", "shift_number": 2}, headers=hdr)
    assert bad.status_code == 422
    assert bad.json()["error_code"] == "shift_ops.shift_number_not_configured"
    ok = client.post(f"{API}/shifts", json={"shift_date": "2026-08-15", "shift_number": 1}, headers=hdr)
    assert ok.status_code == 201


def test_t8_duplicate_before_d3(client, db):
    seed = _seed(db, suffix="T8")
    hdr = _login(client, seed["bm"])
    client.post(f"{API}/shifts", json={"shift_date": "2026-08-15", "shift_number": 1}, headers=hdr)
    dup = client.post(f"{API}/shifts", json={"shift_date": "2026-08-15", "shift_number": 1}, headers=hdr)
    assert dup.status_code == 409
    assert dup.json()["error_code"] == "shift_ops.already_exists"


def test_t9_future_beats_duplicate(client, db):
    seed = _seed(db, suffix="T9")
    hdr = _login(client, seed["bm"])
    client.post(f"{API}/shifts", json={"shift_date": "2026-08-15", "shift_number": 1}, headers=hdr)
    resp = client.post(f"{API}/shifts", json={"shift_date": "2026-08-16", "shift_number": 1}, headers=hdr)
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "shift_ops.date_in_future"


def test_t10_stuck_override_and_backdate_both_audit(client, db, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")
    seed = _seed(db, suffix="T10", shift_configs=(1, 2))
    bm = _login(client, seed["bm"])
    first = client.post(f"{API}/shifts", json={"shift_date": "2026-08-14", "shift_number": 1}, headers=bm).json()
    am = _login(client, seed["am"])
    resp = client.post(
        f"{API}/shifts",
        json={
            "branch_id": seed["branch_id"],
            "shift_date": "2026-08-14",
            "shift_number": 2,
            "override": True,
            "override_reason": "Lock previous shift",
            "backdate_reason": "Backdated entry same day",
        },
        headers=am,
    )
    assert resp.status_code == 201, resp.text
    shift_id = resp.json()["id"]
    back = db.query(AuditLog).filter(AuditLog.action == "shift_open_backdated", AuditLog.entity_id == shift_id).all()
    lock = db.query(AuditLog).filter(
        AuditLog.action == "shift_open_override_lock_previous",
        AuditLog.entity_id == first["id"],
    ).all()
    assert len(back) == 1
    assert len(lock) == 1
    lock_row = lock[0]
    am_user = db.query(User).filter(User.username == seed["am"]).one()
    assert lock_row.user_id == am_user.id
    assert lock_row.created_at is not None
    old_v = json.loads(lock_row.old_values) if isinstance(lock_row.old_values, str) else lock_row.old_values
    new_v = json.loads(lock_row.new_values) if isinstance(lock_row.new_values, str) else lock_row.new_values
    assert old_v == {"status": BranchShiftStatus.draft.value}
    assert new_v["previous_shift_id"] == first["id"]
    assert new_v["previous_status"] == BranchShiftStatus.draft.value
    assert new_v["new_status"] == BranchShiftStatus.exception_locked.value
    assert new_v["branch_id"] == seed["branch_id"]


def test_open_override_lock_rolls_back_when_open_fails_after_audit(client, db, monkeypatch):
    """Open must not complete when flush fails after override lock + audit (no new shift row)."""
    from app.services.shift_ops_service import open_shift

    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")
    seed = _seed(db, suffix="T10RB", shift_configs=(1, 2))
    bm = _login(client, seed["bm"])
    client.post(f"{API}/shifts", json={"shift_date": "2026-08-14", "shift_number": 1}, headers=bm)
    am_user = db.query(User).filter(User.username == seed["am"]).one()

    original_flush = db.flush

    def flush_fail_when_persisting_new_shift():
        for obj in db.new:
            if isinstance(obj, BranchShift):
                raise RuntimeError("forced open failure after override lock")
        original_flush()

    monkeypatch.setattr(db, "flush", flush_fail_when_persisting_new_shift)

    with pytest.raises(RuntimeError, match="forced open failure"):
        open_shift(
            db,
            am_user,
            branch_id=seed["branch_id"],
            shift_date=date(2026, 8, 15),
            shift_number=2,
            override=True,
            override_reason="Lock previous shift",
        )

    second_rows = (
        db.query(BranchShift)
        .filter(
            BranchShift.branch_id == seed["branch_id"],
            BranchShift.shift_date == date(2026, 8, 15),
            BranchShift.shift_number == 2,
        )
        .count()
    )
    assert second_rows == 0


def test_t11_reopen_unaffected(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_CASH_ENABLED", False)
    seed = _seed(db, suffix="T11")
    hdr = _login(client, seed["bm"])
    shift = client.post(f"{API}/shifts", json={"shift_date": "2026-08-14", "shift_number": 1}, headers=hdr).json()
    count = client.post(f"{API}/shifts/{shift['id']}/count", headers=hdr).json()
    line = count["lines"][0]
    client.patch(
        f"{API}/shifts/{shift['id']}/count/lines",
        json={
            "lines": [
                {
                    "item_id": line["item_id"],
                    "received_qty": 0,
                    "returned_qty": 0,
                    "damaged_qty": 0,
                    "closing_balance": float(line["opening_balance"]),
                }
            ]
        },
        headers=hdr,
    )
    client.post(f"{API}/shifts/{shift['id']}/count/submit", headers=hdr)
    am = _login(client, seed["am"])
    reopen = client.post(
        f"{API}/shifts/{shift['id']}/reopen",
        json={"target": "count", "reason": "Fix typo in count"},
        headers=am,
    )
    assert reopen.status_code == 200, reopen.text


def test_t12_riyadh_boundary_today(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_CASH_ENABLED", False)
    seed = _seed(db, suffix="T12A")
    hdr = _login(client, seed["bm"])
    monkeypatch.setattr(sdv, "shift_open_today", lambda: date(2026, 8, 15))
    future = client.post(f"{API}/shifts", json={"shift_date": "2026-08-16", "shift_number": 1}, headers=hdr)
    assert future.status_code == 422
    assert future.json()["error_code"] == "shift_ops.date_in_future"
    ok15 = client.post(f"{API}/shifts", json={"shift_date": "2026-08-15", "shift_number": 1}, headers=hdr)
    assert ok15.status_code == 201
    _submit_count_only(client, hdr, ok15.json()["id"])
    monkeypatch.setattr(sdv, "shift_open_today", lambda: date(2026, 8, 16))
    ok16 = client.post(f"{API}/shifts", json={"shift_date": "2026-08-16", "shift_number": 1}, headers=hdr)
    assert ok16.status_code == 201


def test_t13_validation_disabled_allows_past_date(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_DATE_VALIDATION_ENABLED", False)
    seed = _seed(db, suffix="T13")
    hdr = _login(client, seed["bm"])
    resp = client.post(f"{API}/shifts", json={"shift_date": "2026-01-01", "shift_number": 1}, headers=hdr)
    assert resp.status_code == 201, resp.text


def test_t14_default_setting_is_true():
    field = Settings.model_fields["SHIFT_DATE_VALIDATION_ENABLED"]
    assert field.default is True


def test_t15_zoneinfo_riyadh_resolves():
    assert ZoneInfo("Asia/Riyadh").key == "Asia/Riyadh"


def test_t16_error_detail_includes_server_today(client, db):
    seed = _seed(db, suffix="T16")
    hdr = _login(client, seed["bm"])
    resp = client.post(f"{API}/shifts", json={"shift_date": "2026-09-01", "shift_number": 1}, headers=hdr)
    assert resp.status_code == 422
    assert resp.json()["detail"]["server_today"] == ANCHOR.isoformat()
