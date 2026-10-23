"""Submit count after business-day rollover — shift_date stays on open day D (U3b)."""
from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest

from app.config import settings
from app.core.security import get_password_hash
from app.models import (
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
from app.models.branch_shift_ops import BranchShift, BranchShiftConfig, ShiftSectionStatus
from app.services import shift_ops_date_validation as sdv

API = "/api/v1/shift-ops"
PASSWORD = "Aa1!" + secrets.token_urlsafe(12)
DAY_D = date(2026, 8, 15)


@pytest.fixture(autouse=True)
def _validation_enabled(monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_DATE_VALIDATION_ENABLED", True)


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


def _seed(db, *, suffix: str = "MID"):
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-B1",
        branch_name="Midnight Submit Branch",
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
    unit = UnitOfMeasure(code=f"{suffix}-PCS", name_ar="قطعة", name_en="pcs")
    db.add(cat)
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
    bm = _user(db, f"{suffix}_bm", RoleName.branch_manager, branch.id)
    db.commit()
    return {"branch_id": branch.id, "item_id": item.id, "bm": bm.username}


def test_branch_manager_submit_after_midnight_keeps_shift_date(client, db, monkeypatch):
    """Open on D, fill count, rollover to D+1, submit — date stays D; D+1 open allowed."""
    monkeypatch.setattr(settings, "SHIFT_CASH_ENABLED", False)
    day_d = DAY_D
    day_d1 = day_d + timedelta(days=1)
    monkeypatch.setattr(sdv, "shift_open_today", lambda: day_d)

    seed = _seed(db, suffix="MIDN")
    hdr = _login(client, seed["bm"])
    opened = client.post(
        f"{API}/shifts",
        json={"shift_date": day_d.isoformat(), "shift_number": 1},
        headers=hdr,
    )
    assert opened.status_code == 201, opened.text
    shift_id = opened.json()["id"]

    assert client.post(f"{API}/shifts/{shift_id}/count", headers=hdr).status_code in (200, 201)
    count_body = client.get(f"{API}/shifts/{shift_id}/count", headers=hdr).json()
    lines = [
        {
            "item_id": ln["item_id"],
            "received_qty": 1,
            "returned_qty": 0,
            "damaged_qty": 0,
            "closing_balance": float(ln["opening_balance"]) + 1,
        }
        for ln in count_body["lines"]
    ]
    patch = client.patch(f"{API}/shifts/{shift_id}/count/lines", json={"lines": lines}, headers=hdr)
    assert patch.status_code == 200, patch.text

    monkeypatch.setattr(sdv, "shift_open_today", lambda: day_d1)
    submit = client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr)
    assert submit.status_code == 200, submit.text

    db.expire_all()
    shift = db.query(BranchShift).filter(BranchShift.id == shift_id).one()
    assert shift.shift_date == day_d
    detail = client.get(f"{API}/shifts/{shift_id}", headers=hdr).json()
    assert detail["count_status"] == ShiftSectionStatus.submitted.value

    later = client.post(
        f"{API}/shifts",
        json={"shift_date": day_d1.isoformat(), "shift_number": 1},
        headers=hdr,
    )
    assert later.status_code == 201, later.text
