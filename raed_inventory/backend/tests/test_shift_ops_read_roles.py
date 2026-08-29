"""Read vs write role separation for shift-ops count/cash (TG-SHIFT-OPS-READ-ROLES, TG-SHIFT-OVERSIGHT)."""
from datetime import date

import pytest

from app.core.security import get_password_hash


@pytest.fixture(autouse=True)
def _enable_shift_cash_for_legacy_tests(monkeypatch):
    monkeypatch.setattr("app.config.settings.SHIFT_CASH_ENABLED", True)


from app.models import (
    AreaManagerAssignment,
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


def _user(db, username: str, role_name: RoleName, branch_id=None, warehouse_id=None) -> User:
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


def _login(client, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed(db):
    wh = Warehouse(warehouse_code="RR-WH", warehouse_name="RR WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(branch_code="RR-B1", branch_name="Read Roles Branch", city="Riyadh", area="Olaya", warehouse_id=wh.id)
    db.add(branch)
    db.flush()
    brand = Brand(name="RR Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code="RR-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    unit = UnitOfMeasure(code="RR-PCS", name_ar="قطعة", name_en="pcs")
    db.add(unit)
    db.flush()
    item = Item(
        item_code="RR-ITEM-1",
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
    users = {
        "branch_manager": _user(db, "rr_mgr", RoleName.branch_manager, branch.id),
        "admin": _user(db, "rr_admin", RoleName.admin),
        "super_admin": _user(db, "rr_super", RoleName.super_admin),
        "internal_auditor": _user(db, "rr_auditor", RoleName.internal_auditor),
        "operations_manager": _user(db, "rr_ops", RoleName.operations_manager),
        "warehouse_user": _user(db, "rr_wh", RoleName.warehouse_user, warehouse_id=wh.id),
    }
    db.commit()
    return {"branch_id": branch.id, "item_id": item.id, "usernames": {k: v.username for k, v in users.items()}}


def _seed_area_manager_scope(db):
    wh = Warehouse(warehouse_code="AM-WH", warehouse_name="AM WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    brand = Brand(name="AM Brand", active=True)
    db.add(brand)
    db.flush()
    branch_in = Branch(branch_code="AM-IN", branch_name="In Scope", city="Riyadh", area="North", warehouse_id=wh.id)
    branch_out = Branch(branch_code="AM-OUT", branch_name="Out Scope", city="Dammam", area="East", warehouse_id=wh.id)
    db.add_all([branch_in, branch_out])
    db.flush()
    db.add_all([
        BranchBrand(branch_id=branch_in.id, brand_id=brand.id),
        BranchBrand(branch_id=branch_out.id, brand_id=brand.id),
    ])
    cat = ItemCategory(code="AM-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    unit = UnitOfMeasure(code="AM-PCS", name_ar="قطعة", name_en="pcs")
    db.add(unit)
    db.flush()
    item = Item(
        item_code="AM-ITEM-1",
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
    for b in (branch_in, branch_out):
        db.add(
            BranchShiftConfig(
                branch_id=b.id,
                shift_number=1,
                shift_name_ar="الشفت 1",
                is_active=True,
                effective_from=date(2020, 1, 1),
                effective_to=None,
            )
        )
    mgr_in = _user(db, "am_mgr_in", RoleName.branch_manager, branch_in.id)
    mgr_out = _user(db, "am_mgr_out", RoleName.branch_manager, branch_out.id)
    am = _user(db, "am_user", RoleName.area_manager)
    db.add(AreaManagerAssignment(user_id=am.id, city="Riyadh", brand_id=brand.id, active=True))
    db.commit()
    return {
        "item_id": item.id,
        "branch_in_id": branch_in.id,
        "branch_out_id": branch_out.id,
        "usernames": {
            "area_manager": am.username,
            "branch_manager_in": mgr_in.username,
            "branch_manager_out": mgr_out.username,
        },
    }


def _open_shift(client, hdr, shift_date="2026-08-18") -> int:
    resp = client.post(
        f"{API}/shifts",
        json={"shift_date": shift_date, "shift_number": 1},
        headers=hdr,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _prepare_shift_with_count_and_cash(client, db):
    seed = _seed(db)
    mgr = _login(client, seed["usernames"]["branch_manager"])
    shift_id = _open_shift(client, mgr)
    assert client.post(f"{API}/shifts/{shift_id}/count", headers=mgr).status_code in (200, 201)
    assert (
        client.put(
            f"{API}/shifts/{shift_id}/cash",
            json={"cash_sales": 100, "cash_refund": 0, "cash_expense": 0},
            headers=mgr,
        ).status_code
        == 200
    )
    return seed, shift_id


def _patch_line_payload(item_id: int) -> dict:
    return {
        "lines": [
            {
                "item_id": item_id,
                "received_qty": 1,
                "returned_qty": 0,
                "damaged_qty": 0,
                "closing_balance": 0,
            }
        ]
    }


def test_admin_can_read_count_and_cash(client, db):
    seed, shift_id = _prepare_shift_with_count_and_cash(client, db)
    hdr = _login(client, seed["usernames"]["admin"])
    assert client.get(f"{API}/shifts/{shift_id}/count", headers=hdr).status_code == 200
    assert client.get(f"{API}/shifts/{shift_id}/cash", headers=hdr).status_code == 200


def test_admin_cannot_write_count_or_cash(client, db):
    seed, shift_id = _prepare_shift_with_count_and_cash(client, db)
    hdr = _login(client, seed["usernames"]["admin"])
    item_id = seed["item_id"]
    assert client.post(f"{API}/shifts/{shift_id}/count", headers=hdr).status_code == 403
    assert (
        client.patch(
            f"{API}/shifts/{shift_id}/count/lines",
            json=_patch_line_payload(item_id),
            headers=hdr,
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"{API}/shifts/{shift_id}/cash",
            json={"cash_sales": 200},
            headers=hdr,
        ).status_code
        == 403
    )
    assert client.post(f"{API}/shifts/{shift_id}/cash/submit", headers=hdr).status_code == 403


def test_super_admin_can_read_and_cannot_write(client, db):
    seed, shift_id = _prepare_shift_with_count_and_cash(client, db)
    hdr = _login(client, seed["usernames"]["super_admin"])
    assert client.get(f"{API}/shifts/{shift_id}/count", headers=hdr).status_code == 200
    assert client.get(f"{API}/shifts/{shift_id}/cash", headers=hdr).status_code == 200
    assert client.post(f"{API}/shifts/{shift_id}/count", headers=hdr).status_code == 403
    assert (
        client.put(
            f"{API}/shifts/{shift_id}/cash",
            json={"cash_sales": 50},
            headers=hdr,
        ).status_code
        == 403
    )


def test_internal_auditor_can_read_count_and_cash(client, db):
    seed, shift_id = _prepare_shift_with_count_and_cash(client, db)
    hdr = _login(client, seed["usernames"]["internal_auditor"])
    assert client.get(f"{API}/shifts/{shift_id}/count", headers=hdr).status_code == 200
    assert client.get(f"{API}/shifts/{shift_id}/cash", headers=hdr).status_code == 200


def test_operations_manager_can_read_count(client, db):
    seed, shift_id = _prepare_shift_with_count_and_cash(client, db)
    hdr = _login(client, seed["usernames"]["operations_manager"])
    assert client.get(f"{API}/shifts/{shift_id}/count", headers=hdr).status_code == 200


def test_area_manager_in_scope_can_read_count(client, db):
    scope = _seed_area_manager_scope(db)
    mgr = _login(client, scope["usernames"]["branch_manager_in"])
    shift_id = _open_shift(client, mgr)
    assert client.post(f"{API}/shifts/{shift_id}/count", headers=mgr).status_code in (200, 201)
    am = _login(client, scope["usernames"]["area_manager"])
    assert client.get(f"{API}/shifts/{shift_id}/count", headers=am).status_code == 200


def test_area_manager_out_of_scope_get_count_forbidden(client, db):
    scope = _seed_area_manager_scope(db)
    mgr = _login(client, scope["usernames"]["branch_manager_out"])
    shift_id = _open_shift(client, mgr)
    assert client.post(f"{API}/shifts/{shift_id}/count", headers=mgr).status_code in (200, 201)
    am = _login(client, scope["usernames"]["area_manager"])
    resp = client.get(f"{API}/shifts/{shift_id}/count", headers=am)
    assert resp.status_code == 403


def test_read_roles_cannot_patch_count_lines(client, db):
    seed, shift_id = _prepare_shift_with_count_and_cash(client, db)
    item_id = seed["item_id"]
    for role_key in ("admin", "super_admin", "internal_auditor", "operations_manager"):
        hdr = _login(client, seed["usernames"][role_key])
        assert (
            client.patch(
                f"{API}/shifts/{shift_id}/count/lines",
                json=_patch_line_payload(item_id),
                headers=hdr,
            ).status_code
            == 403
        )
    scope = _seed_area_manager_scope(db)
    mgr = _login(client, scope["usernames"]["branch_manager_in"])
    shift_in = _open_shift(client, mgr)
    assert client.post(f"{API}/shifts/{shift_in}/count", headers=mgr).status_code in (200, 201)
    am = _login(client, scope["usernames"]["area_manager"])
    assert (
        client.patch(
            f"{API}/shifts/{shift_in}/count/lines",
            json=_patch_line_payload(scope["item_id"]),
            headers=am,
        ).status_code
        == 403
    )


def test_warehouse_user_cannot_read_count(client, db):
    seed, shift_id = _prepare_shift_with_count_and_cash(client, db)
    hdr = _login(client, seed["usernames"]["warehouse_user"])
    assert client.get(f"{API}/shifts/{shift_id}/count", headers=hdr).status_code == 403


def test_branch_manager_read_write_still_works(client, db):
    seed, shift_id = _prepare_shift_with_count_and_cash(client, db)
    hdr = _login(client, seed["usernames"]["branch_manager"])
    assert client.get(f"{API}/shifts/{shift_id}/count", headers=hdr).status_code == 200
    assert client.get(f"{API}/shifts/{shift_id}/cash", headers=hdr).status_code == 200
    assert (
        client.patch(
            f"{API}/shifts/{shift_id}/count/lines",
            json=_patch_line_payload(seed["item_id"]),
            headers=hdr,
        ).status_code
        == 200
    )


def test_area_manager_in_scope_can_read_cash(client, db):
    scope = _seed_area_manager_scope(db)
    mgr = _login(client, scope["usernames"]["branch_manager_in"])
    shift_id = _open_shift(client, mgr)
    assert (
        client.put(
            f"{API}/shifts/{shift_id}/cash",
            json={"cash_sales": 50, "cash_refund": 0, "cash_expense": 0},
            headers=mgr,
        ).status_code
        == 200
    )
    am = _login(client, scope["usernames"]["area_manager"])
    assert client.get(f"{API}/shifts/{shift_id}/cash", headers=am).status_code == 200


def test_area_manager_out_of_scope_get_cash_forbidden(client, db):
    scope = _seed_area_manager_scope(db)
    mgr = _login(client, scope["usernames"]["branch_manager_out"])
    shift_id = _open_shift(client, mgr)
    assert (
        client.put(
            f"{API}/shifts/{shift_id}/cash",
            json={"cash_sales": 50, "cash_refund": 0, "cash_expense": 0},
            headers=mgr,
        ).status_code
        == 200
    )
    am = _login(client, scope["usernames"]["area_manager"])
    assert client.get(f"{API}/shifts/{shift_id}/cash", headers=am).status_code == 403


def test_warehouse_user_cannot_read_cash(client, db):
    seed, shift_id = _prepare_shift_with_count_and_cash(client, db)
    hdr = _login(client, seed["usernames"]["warehouse_user"])
    assert client.get(f"{API}/shifts/{shift_id}/cash", headers=hdr).status_code == 403
