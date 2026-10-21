"""list_shifts server_today field (U3b fix gate)."""
from __future__ import annotations

from datetime import date
import secrets

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
from app.models.branch_shift_ops import BranchShiftConfig
from app.services import shift_ops_date_validation as sdv

API = "/api/v1/shift-ops"
PASSWORD = "Aa1!" + secrets.token_urlsafe(12)
ANCHOR = date(2026, 9, 10)


@pytest.fixture(autouse=True)
def _anchor_today(monkeypatch):
    monkeypatch.setattr(settings, "SHIFT_DATE_VALIDATION_ENABLED", True)
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


def _seed(db, *, suffix: str, shift_configs: tuple[int, ...] = (1, 2)) -> dict:
    wh = Warehouse(warehouse_code=f"ST-{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"ST-{suffix}-B1",
        branch_name="Server Today Branch",
        city="Riyadh",
        area="Olaya",
        warehouse_id=wh.id,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"ST {suffix}", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"ST-{suffix}-C", name_ar="f", name_en="c")
    unit = UnitOfMeasure(code=f"ST-{suffix}-U", name_ar="u", name_en="u")
    db.add(cat)
    db.add(unit)
    db.flush()
    item = Item(
        item_code=f"ST-{suffix}-I1",
        item_name_ar="i",
        item_name_en="i",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()
    db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
    for n in shift_configs:
        db.add(
            BranchShiftConfig(
                branch_id=branch.id,
                shift_number=n,
                shift_name_ar=f"s{n}",
                is_active=True,
                effective_from=date(2020, 1, 1),
            )
        )
    bm = _user(db, f"st_{suffix}_bm", RoleName.branch_manager, branch.id)
    am = _user(db, f"st_{suffix}_am", RoleName.area_manager)
    admin = _user(db, f"st_{suffix}_admin", RoleName.admin)
    db.commit()
    return {
        "branch_id": branch.id,
        "bm": bm.username,
        "am": am.username,
        "admin": admin.username,
    }


def test_t1_server_today_matches_patched_clock(client, db):
    seed = _seed(db, suffix="T1")
    hdr = _login(client, seed["bm"])
    resp = client.get(f"{API}/shifts", headers=hdr)
    assert resp.status_code == 200
    assert resp.json()["server_today"] == ANCHOR.isoformat()


def test_t2_server_today_all_roles_and_empty_config(client, db):
    seed = _seed(db, suffix="T2", shift_configs=(1, 2))
    empty = _seed(db, suffix="T2E", shift_configs=())
    for user in (seed["bm"], seed["am"], seed["admin"]):
        hdr = _login(client, user)
        body = client.get(f"{API}/shifts", headers=hdr).json()
        assert body["server_today"] == ANCHOR.isoformat()
    hdr_empty = _login(client, empty["bm"])
    body_empty = client.get(f"{API}/shifts", headers=hdr_empty).json()
    assert body_empty["server_today"] == ANCHOR.isoformat()
    assert body_empty["available_shift_numbers"] == []


def test_t3_server_today_unchanged_by_filters(client, db):
    seed = _seed(db, suffix="T3")
    hdr = _login(client, seed["bm"])
    base = client.get(f"{API}/shifts", headers=hdr).json()["server_today"]
    filtered = client.get(
        f"{API}/shifts",
        params={
            "date_from": "2020-01-01",
            "date_to": "2030-01-01",
            "partial_only": True,
            "exception_only": True,
        },
        headers=hdr,
    ).json()
    assert filtered["server_today"] == base


def test_t4_d1_detail_server_today_matches_list(client, db, monkeypatch):
    seed = _seed(db, suffix="T4")
    hdr = _login(client, seed["bm"])
    list_st = client.get(f"{API}/shifts", headers=hdr).json()["server_today"]
    future = client.post(
        f"{API}/shifts",
        json={"shift_date": "2030-01-01", "shift_number": 1},
        headers=hdr,
    )
    assert future.status_code == 422
    assert future.json()["detail"]["server_today"] == list_st


def test_t5_list_shape_unchanged(client, db):
    seed = _seed(db, suffix="T5")
    hdr = _login(client, seed["bm"])
    body = client.get(f"{API}/shifts", headers=hdr).json()
    assert set(body.keys()) >= {"total", "items", "available_shift_numbers", "server_today"}
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)
    assert isinstance(body["available_shift_numbers"], list)
