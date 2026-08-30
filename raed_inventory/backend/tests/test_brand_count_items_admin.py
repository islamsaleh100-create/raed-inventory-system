"""Admin API for brand_shift_count_items + open-count order stability."""
from datetime import date

import pytest

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

MASTER = "/api/v1/master"
SHIFT = "/api/v1/shift-ops"
PASSWORD = "Pass@2026"


@pytest.fixture(autouse=True)
def _enable_shift_cash(monkeypatch):
    monkeypatch.setattr("app.config.settings.SHIFT_CASH_ENABLED", True)


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


def _seed_multi(db, *, items: int = 3, suffix: str = "BCI"):
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-B1", branch_name="Count Branch", city="Riyadh",
        area="Olaya", warehouse_id=wh.id, active=True, is_deleted=False,
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

    item_ids = []
    cfg_ids = []
    for i in range(items):
        item = Item(
            item_code=f"{suffix}-ITEM-{i}", item_name_ar=f"صنف {i}", item_name_en=f"Item {i}",
            category_id=cat.id, unit_id=unit.id, active=True, is_deleted=False,
        )
        db.add(item)
        db.flush()
        db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
        cfg = BrandShiftCountItem(
            brand_id=brand.id, item_id=item.id, display_order=i + 1, is_active=True,
        )
        db.add(cfg)
        db.flush()
        item_ids.append(item.id)
        cfg_ids.append(cfg.id)

    db.add(BranchShiftConfig(
        branch_id=branch.id, shift_number=1, shift_name_ar="الشفت 1",
        is_active=True, effective_from=date(2020, 1, 1), effective_to=None,
    ))
    branch_user = _user(db, f"{suffix}.branch", RoleName.branch_manager, branch_id=branch.id)
    admin_user = _user(db, f"{suffix}.admin", RoleName.admin)
    db.commit()
    return {
        "brand_id": brand.id,
        "branch_id": branch.id,
        "item_ids": item_ids,
        "cfg_ids": cfg_ids,
        "usernames": {"branch": f"{suffix}.branch", "admin": f"{suffix}.admin"},
    }


def _open_shift(client, hdr, branch_id):
    resp = client.post(
        f"{SHIFT}/shifts",
        headers=hdr,
        json={"branch_id": branch_id, "shift_date": "2026-08-30", "shift_number": 1},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _line_item_order(payload: dict) -> list[int]:
    lines = sorted(payload["lines"], key=lambda ln: ln["id"])
    return [ln["item_id"] for ln in lines]


def _fill_and_submit_count(client, hdr, shift_id):
    created = client.post(f"{SHIFT}/shifts/{shift_id}/count", headers=hdr)
    assert created.status_code in (200, 201), created.text
    lines = created.json()["lines"]
    payload = {"lines": [
        {
            "item_id": ln["item_id"], "received_qty": 0, "returned_qty": 0,
            "damaged_qty": 0, "closing_balance": float(ln["opening_balance"]),
        } for ln in lines
    ]}
    assert client.patch(f"{SHIFT}/shifts/{shift_id}/count/lines", json=payload, headers=hdr).status_code == 200
    resp = client.post(f"{SHIFT}/shifts/{shift_id}/count/submit", headers=hdr)
    assert resp.status_code == 200, resp.text
    return resp


def _fill_and_submit_cash(client, hdr, shift_id):
    body = {
        "total_sale": 100, "bill_count": 2, "mada_sales": 60, "cash_sales": 40,
        "app_sales": 0, "refund_bill": 0, "exchange_amount": 0, "expiry_amount": 0,
        "cash_expense": 0, "cash_float_carried_forward": 0, "cash_deposited": 40,
    }
    assert client.put(f"{SHIFT}/shifts/{shift_id}/cash", json=body, headers=hdr).status_code == 200
    resp = client.post(f"{SHIFT}/shifts/{shift_id}/cash/submit", headers=hdr)
    assert resp.status_code == 200, resp.text
    return resp


def test_branch_manager_forbidden_on_count_items_api(db, client):
    seed = _seed_multi(db, suffix="BCI403")
    bhdr = _login(client, seed["usernames"]["branch"])
    resp = client.get(f"{MASTER}/brands/{seed['brand_id']}/count-items", headers=bhdr)
    assert resp.status_code == 403


def test_admin_can_list_brand_count_items(db, client):
    seed = _seed_multi(db, suffix="BCI200")
    ahdr = _login(client, seed["usernames"]["admin"])
    resp = client.get(f"{MASTER}/brands/{seed['brand_id']}/count-items", headers=ahdr)
    assert resp.status_code == 200
    body = resp.json()
    assert body["branch_count"] == 1
    assert len(body["items"]) == 3
    assert body["branches"][0]["branch_code"] == "BCI200-B1"


def test_duplicate_count_item_arabic_error(db, client):
    seed = _seed_multi(db, items=1, suffix="BCIdup")
    ahdr = _login(client, seed["usernames"]["admin"])
    resp = client.post(
        f"{MASTER}/brands/{seed['brand_id']}/count-items",
        headers=ahdr,
        json={"item_id": seed["item_ids"][0]},
    )
    assert resp.status_code == 400
    assert "مضاف مسبقاً" in resp.json()["message"]


def test_inactive_item_rejected(db, client):
    seed = _seed_multi(db, items=1, suffix="BCIinact")
    ahdr = _login(client, seed["usernames"]["admin"])
    inactive = Item(
        item_code="BCI-INACT", item_name_ar="معطّل", item_name_en="Off",
        category_id=db.query(ItemCategory).filter(ItemCategory.code == "BCIinact-CAT").first().id,
        unit_id=db.query(UnitOfMeasure).filter(UnitOfMeasure.code == "BCIinact-PCS").first().id,
        active=False, is_deleted=False,
    )
    db.add(inactive)
    db.commit()
    resp = client.post(
        f"{MASTER}/brands/{seed['brand_id']}/count-items",
        headers=ahdr,
        json={"item_id": inactive.id},
    )
    assert resp.status_code == 400
    assert "غير نشط" in resp.json()["message"]


def test_is_active_patch(db, client):
    seed = _seed_multi(db, suffix="BCIact")
    ahdr = _login(client, seed["usernames"]["admin"])
    row_id = seed["cfg_ids"][0]
    resp = client.patch(
        f"{MASTER}/brands/{seed['brand_id']}/count-items/{row_id}",
        headers=ahdr,
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_open_count_order_stable_after_brand_list_change(db, client):
    """P0: reorder/disable in admin must not reshuffle an open count."""
    seed = _seed_multi(db, items=3, suffix="BCIord")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr, seed["branch_id"])
    created = client.post(f"{SHIFT}/shifts/{shift_id}/count", headers=bhdr)
    assert created.status_code == 201
    before_order = _line_item_order(created.json())
    assert len(before_order) == 3

    # Simulate admin reorder + disable on brand list
    cfg0, cfg1, cfg2 = seed["cfg_ids"]
    assert client.patch(
        f"{MASTER}/brands/{seed['brand_id']}/count-items/{cfg0}",
        headers=ahdr,
        json={"display_order": 30},
    ).status_code == 200
    assert client.patch(
        f"{MASTER}/brands/{seed['brand_id']}/count-items/{cfg2}",
        headers=ahdr,
        json={"display_order": 1},
    ).status_code == 200
    assert client.patch(
        f"{MASTER}/brands/{seed['brand_id']}/count-items/{cfg1}",
        headers=ahdr,
        json={"is_active": False},
    ).status_code == 200

    after = client.get(f"{SHIFT}/shifts/{shift_id}/count", headers=bhdr)
    assert after.status_code == 200
    after_order = _line_item_order(after.json())
    assert after_order == before_order, "open count line order must stay frozen"
    assert len(after_order) == 3, "disabled brand item must remain in open count lines"


def test_new_item_appears_only_in_next_count(db, client):
    seed = _seed_multi(db, items=2, suffix="BCInew")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr, seed["branch_id"])
    first = client.post(f"{SHIFT}/shifts/{shift_id}/count", headers=bhdr)
    assert first.status_code == 201
    original_len = len(first.json()["lines"])

    new_item = Item(
        item_code="BCInew-LATE", item_name_ar="جديد", item_name_en="New",
        category_id=db.query(ItemCategory).filter(ItemCategory.code == "BCInew-CAT").first().id,
        unit_id=db.query(UnitOfMeasure).filter(UnitOfMeasure.code == "BCInew-PCS").first().id,
        active=True, is_deleted=False,
    )
    db.add(new_item)
    db.flush()
    add_resp = client.post(
        f"{MASTER}/brands/{seed['brand_id']}/count-items",
        headers=ahdr,
        json={"item_id": new_item.id},
    )
    assert add_resp.status_code == 201

    still = client.get(f"{SHIFT}/shifts/{shift_id}/count", headers=bhdr).json()
    assert len(still["lines"]) == original_len

    _fill_and_submit_count(client, bhdr, shift_id)
    _fill_and_submit_cash(client, bhdr, shift_id)

    resp2 = client.post(
        f"{SHIFT}/shifts",
        headers=bhdr,
        json={"branch_id": seed["branch_id"], "shift_date": "2026-08-31", "shift_number": 1},
    )
    assert resp2.status_code == 201, resp2.text
    shift2_id = resp2.json()["id"]
    second = client.post(f"{SHIFT}/shifts/{shift2_id}/count", headers=bhdr)
    assert second.status_code == 201
    assert len(second.json()["lines"]) == original_len + 1
