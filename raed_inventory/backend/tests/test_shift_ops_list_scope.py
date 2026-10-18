"""
List-scope: GET /shifts without branch_id must match can_access_branch default-deny.
"""
from __future__ import annotations

from datetime import date
import secrets

import pytest

from app.core.auth import GLOBAL_BRANCH_ACCESS_ROLES
from app.core.security import get_password_hash
from app.models import (
    AreaManagerAssignment,
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
from app.models.branch_shift_ops import BranchShiftConfig

API = "/api/v1/shift-ops"
PASSWORD = "Aa1!" + secrets.token_urlsafe(12)

GLOBAL_LIST_ROLES = (
    RoleName.super_admin,
    RoleName.admin,
    RoleName.operations_manager,
    RoleName.internal_auditor,
)

DENY_LIST_ROLES_WITH_BRANCH = (
    RoleName.warehouse_user,
    RoleName.warehouse_manager,
    RoleName.quality_visitor,
    RoleName.trainer,
    RoleName.evaluator,
)


def test_global_branch_access_roles_matches_can_access_branch_set():
    assert {r.value for r in GLOBAL_LIST_ROLES} == set(GLOBAL_BRANCH_ACCESS_ROLES)


def _role(db, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if not row:
        row = Role(name=name, display_name=name.value, description="")
        db.add(row)
        db.flush()
    return row


def _user(
    db,
    username: str,
    role_name: RoleName,
    *,
    branch_id: int | None = None,
    warehouse_id: int | None = None,
) -> User:
    role = _role(db, role_name)
    row = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash(PASSWORD),
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        status="active",
        is_deleted=False,
    )
    db.add(row)
    db.flush()
    db.add(UserRole(user_id=row.id, role_id=role.id))
    db.flush()
    return row


def _seed_branch(db, code: str, wh: Warehouse) -> int:
    branch = Branch(
        branch_code=f"{code}-BR",
        branch_name=f"Branch {code}",
        city="Riyadh",
        area="Test",
        warehouse_id=wh.id,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"{code} Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"{code}-C", name_ar="f", name_en="c")
    db.add(cat)
    unit = UnitOfMeasure(code=f"{code}-U", name_ar="u", name_en="u")
    db.add(unit)
    db.flush()
    item = Item(
        item_code=f"{code}-IT",
        item_name_ar="x",
        item_name_en="x",
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
            shift_name_ar="1",
            is_active=True,
            effective_from=date(2020, 1, 1),
            effective_to=None,
        )
    )
    return branch.id


def _login(client, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _open_shift(client, hdr, day: str) -> int:
    resp = client.post(
        f"{API}/shifts",
        json={"shift_date": day, "shift_number": 1},
        headers=hdr,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _list_payload(client, hdr, **params) -> dict:
    resp = client.get(f"{API}/shifts", headers=hdr, params=params or None)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _list_ids(client, hdr, **params) -> set[int]:
    return {row["id"] for row in _list_payload(client, hdr, **params)["items"]}


@pytest.fixture()
def two_branch_shifts(db, client):
    wh = Warehouse(warehouse_code="LS-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch_a = _seed_branch(db, "LS-A", wh)
    branch_b = _seed_branch(db, "LS-B", wh)

    mgr_a = _user(db, "ls_a_mgr", RoleName.branch_manager, branch_id=branch_a, warehouse_id=wh.id)
    mgr_b = _user(db, "ls_b_mgr", RoleName.branch_manager, branch_id=branch_b, warehouse_id=wh.id)
    db.commit()

    hdr_a = _login(client, mgr_a.username)
    hdr_b = _login(client, mgr_b.username)
    shift_a = _open_shift(client, hdr_a, "2026-11-01")
    shift_b = _open_shift(client, hdr_b, "2026-11-02")

    users: dict[str, str] = {
        "branch_manager_a": mgr_a.username,
        "branch_user_a": _user(db, "ls_a_bu", RoleName.branch_user, branch_id=branch_a).username,
        "branch_user_no_branch": _user(db, "ls_nobu", RoleName.branch_user, branch_id=None).username,
    }
    for rn in DENY_LIST_ROLES_WITH_BRANCH:
        users[f"{rn.value}_with_branch"] = _user(
            db, f"ls_a_{rn.value}", rn, branch_id=branch_a, warehouse_id=wh.id
        ).username
        users[f"{rn.value}_no_branch"] = _user(
            db, f"ls_nb_{rn.value}", rn, branch_id=None, warehouse_id=wh.id
        ).username
    for rn in GLOBAL_LIST_ROLES:
        users[f"{rn.value}_global"] = _user(
            db, f"ls_g_{rn.value}", rn, branch_id=branch_a, warehouse_id=wh.id
        ).username

    db.commit()

    return {
        "branch_a": branch_a,
        "branch_b": branch_b,
        "shift_a": shift_a,
        "shift_b": shift_b,
        "users": users,
    }


@pytest.fixture()
def area_manager_two_branches(db, client):
    wh = Warehouse(warehouse_code="LSAM-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch_in = _seed_branch(db, "LSAM-IN", wh)
    brand_id = db.query(BranchBrand).filter(BranchBrand.branch_id == branch_in).one().brand_id
    branch_out = Branch(
        branch_code="LSAM-OUT-BR",
        branch_name="Out",
        city="Dammam",
        area="East",
        warehouse_id=wh.id,
    )
    db.add(branch_out)
    db.flush()
    db.add(BranchBrand(branch_id=branch_out.id, brand_id=brand_id))
    db.add(
        BranchShiftConfig(
            branch_id=branch_out.id,
            shift_number=1,
            shift_name_ar="1",
            is_active=True,
            effective_from=date(2020, 1, 1),
            effective_to=None,
        )
    )
    am = _user(db, "ls_am_user", RoleName.area_manager)
    db.add(AreaManagerAssignment(user_id=am.id, city="Riyadh", brand_id=brand_id, active=True))
    mgr_in = _user(db, "ls_am_mgr_in", RoleName.branch_manager, branch_id=branch_in)
    mgr_out = _user(db, "ls_am_mgr_out", RoleName.branch_manager, branch_id=branch_out.id)
    db.commit()
    shift_in = _open_shift(client, _login(client, mgr_in.username), "2026-11-03")
    shift_out = _open_shift(client, _login(client, mgr_out.username), "2026-11-04")
    return {
        "branch_in": branch_in,
        "branch_out": branch_out,
        "shift_in": shift_in,
        "shift_out": shift_out,
        "am_user": am.username,
    }


def test_branch_manager_sees_own_branch_only(client, two_branch_shifts):
    data = two_branch_shifts
    hdr = _login(client, data["users"]["branch_manager_a"])
    ids = _list_ids(client, hdr)
    assert data["shift_a"] in ids
    assert data["shift_b"] not in ids


def test_branch_user_with_branch_sees_own_only(client, two_branch_shifts):
    data = two_branch_shifts
    hdr = _login(client, data["users"]["branch_user_a"])
    ids = _list_ids(client, hdr)
    assert data["shift_a"] in ids
    assert data["shift_b"] not in ids


def test_branch_user_without_branch_id_gets_empty_list(client, two_branch_shifts):
    hdr = _login(client, two_branch_shifts["users"]["branch_user_no_branch"])
    body = _list_payload(client, hdr)
    assert body["items"] == []
    assert body["available_shift_numbers"] == []


@pytest.mark.parametrize("role_name", DENY_LIST_ROLES_WITH_BRANCH)
def test_non_branch_role_with_branch_id_gets_empty_list(client, two_branch_shifts, role_name):
    data = two_branch_shifts
    hdr = _login(client, data["users"][f"{role_name.value}_with_branch"])
    body = _list_payload(client, hdr)
    assert body["items"] == []
    assert body["available_shift_numbers"] == []
    # Explicit branch query must not leak open-shift hints either (403 before list body).
    resp = client.get(
        f"{API}/shifts",
        headers=hdr,
        params={"branch_id": data["branch_a"]},
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("role_name", DENY_LIST_ROLES_WITH_BRANCH)
def test_non_branch_role_without_branch_id_gets_empty_list(client, two_branch_shifts, role_name):
    hdr = _login(client, two_branch_shifts["users"][f"{role_name.value}_no_branch"])
    body = _list_payload(client, hdr)
    assert body["items"] == []
    assert body["available_shift_numbers"] == []


@pytest.mark.parametrize("role_name", GLOBAL_LIST_ROLES)
def test_global_roles_see_all_branches(client, two_branch_shifts, role_name):
    data = two_branch_shifts
    hdr = _login(client, data["users"][f"{role_name.value}_global"])
    ids = _list_ids(client, hdr)
    assert data["shift_a"] in ids
    assert data["shift_b"] in ids


def test_area_manager_sees_only_scope(client, area_manager_two_branches):
    data = area_manager_two_branches
    hdr = _login(client, data["am_user"])
    ids = _list_ids(client, hdr)
    assert data["shift_in"] in ids
    assert data["shift_out"] not in ids


def test_explicit_other_branch_id_forbidden_for_branch_user(client, two_branch_shifts):
    data = two_branch_shifts
    hdr = _login(client, data["users"]["branch_user_a"])
    resp = client.get(f"{API}/shifts", headers=hdr, params={"branch_id": data["branch_b"]})
    assert resp.status_code == 403
