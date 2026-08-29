"""SHIFT_CASH_ENABLED defer-cash behavior (TG-DEFER-CASH / TG-CLOSE-EVERYTHING)."""
from datetime import date, timedelta

import pytest

from app.config import settings
from app.core.security import get_password_hash
from app.models import (
    Branch,
    BranchBrand,
    Brand,
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
from app.models.branch_shift_ops import BranchShiftConfig, BrandShiftCountItem

API = "/api/v1/shift-ops"
PASSWORD = "Pass@2026"


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


def _seed(db, *, items: int = 1, suffix: str = "DC"):
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-BR", branch_name=f"{suffix} Branch", city="Riyadh", area="Olaya", warehouse_id=wh.id
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"{suffix}-CAT", name_ar="cat", name_en="Cat")
    db.add(cat)
    unit = UnitOfMeasure(code=f"{suffix}-PCS", name_ar="pcs", name_en="pcs")
    db.add(unit)
    db.flush()
    item_ids = []
    for i in range(items):
        item = Item(
            item_code=f"{suffix}-ITEM-{i}",
            item_name_ar=f"item {i}",
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
            shift_name_ar="shift 1",
            is_active=True,
            effective_from=date(2020, 1, 1),
            effective_to=None,
        )
    )
    _user(db, f"{suffix}_mgr", RoleName.branch_manager, branch.id)
    db.commit()
    return branch.id, item_ids, f"{suffix}_mgr"


def _open_and_fill_count(client, hdr, item_ids, shift_date: str):
    shift_id = client.post(
        f"{API}/shifts", json={"shift_date": shift_date, "shift_number": 1}, headers=hdr
    ).json()["id"]
    client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    lines = [
        {
            "item_id": iid,
            "received_qty": 1,
            "returned_qty": 0,
            "damaged_qty": 0,
            "closing_balance": 0,
        }
        for iid in item_ids
    ]
    client.patch(f"{API}/shifts/{shift_id}/count/lines", json={"lines": lines}, headers=hdr)
    client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr)
    return shift_id


def test_count_only_submits_shift_when_cash_disabled(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_CASH_ENABLED", False)
    _, item_ids, mgr = _seed(db, suffix="DC1")
    hdr = _login(client, mgr)
    shift_id = _open_and_fill_count(client, hdr, item_ids, "2026-08-18")
    shift = client.get(f"{API}/shifts/{shift_id}", headers=hdr).json()
    assert shift["status"] == "submitted"
    assert shift["submitted_at"] is not None
    assert shift["is_partial"] is False


def test_next_day_open_succeeds_after_count_only(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_CASH_ENABLED", False)
    _, item_ids, mgr = _seed(db, suffix="DC2")
    hdr = _login(client, mgr)
    _open_and_fill_count(client, hdr, item_ids, "2026-08-18")
    tomorrow = (date(2026, 8, 18) + timedelta(days=1)).isoformat()
    resp = client.post(f"{API}/shifts", json={"shift_date": tomorrow, "shift_number": 1}, headers=hdr)
    assert resp.status_code == 201, resp.text


def test_count_only_keeps_draft_when_cash_enabled(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_CASH_ENABLED", True)
    _, item_ids, mgr = _seed(db, suffix="DC3")
    hdr = _login(client, mgr)
    shift_id = _open_and_fill_count(client, hdr, item_ids, "2026-08-18")
    shift = client.get(f"{API}/shifts/{shift_id}", headers=hdr).json()
    assert shift["status"] == "draft"
    assert shift["is_partial"] is True
