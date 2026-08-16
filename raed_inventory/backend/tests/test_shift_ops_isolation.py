from datetime import date
from decimal import Decimal
from pathlib import Path

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
from app.models.branch_shift_ops import BrandShiftCountItem


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
        hashed_password=get_password_hash("Pass@2026"),
        branch_id=branch_id,
        status="active",
        is_deleted=False,
    )
    db.add(row)
    db.flush()
    db.add(UserRole(user_id=row.id, role_id=role.id))
    db.flush()
    return row


def _login(client, username: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "Pass@2026"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed(db):
    wh = Warehouse(warehouse_code="SO-WH", warehouse_name="SO WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(branch_code="SO-B1", branch_name="Shift Branch", city="Riyadh", area="Olaya", warehouse_id=wh.id)
    db.add(branch)
    db.flush()
    brand = Brand(name="SO Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code="SO-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    db.flush()
    unit = UnitOfMeasure(code="SO-PCS", name_ar="قطعة", name_en="pcs")
    db.add(unit)
    db.flush()
    item = Item(
        item_code="SO-ITEM-1",
        item_name_ar="صنف 1",
        item_name_en="Item 1",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()
    db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
    db.add(BrandShiftCountItem(brand_id=brand.id, item_id=item.id, display_order=1, is_active=True))
    branch_user = _user(db, "so_branch_user", RoleName.branch_user, branch.id)
    db.commit()
    return {"branch_id": branch.id, "item_id": item.id, "brand_id": brand.id, "branch_user": branch_user.username}


def test_shift_ops_service_has_no_forbidden_imports():
    service_path = Path(__file__).resolve().parents[1] / "app" / "services" / "shift_ops_service.py"
    router_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "shift_ops.py"
    forbidden = (
        "replenishment_service",
        "stock_ledger_service",
        "branch_request_split_service",
        "inventory_service",
    )
    for path in (service_path, router_path):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text


def test_count_submit_does_not_touch_replenishment(db, client):
    seed = _seed(db)
    token = _login(client, seed["branch_user"])
    open_resp = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-01", "shift_number": 1},
        headers=_auth(token),
    )
    assert open_resp.status_code == 201
    shift_id = open_resp.json()["id"]

    count_resp = client.post(f"/api/v1/shift-ops/shifts/{shift_id}/count", headers=_auth(token))
    assert count_resp.status_code == 201
    line = count_resp.json()["lines"][0]
    patch_resp = client.patch(
        f"/api/v1/shift-ops/shifts/{shift_id}/count/lines",
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
        headers=_auth(token),
    )
    assert patch_resp.status_code == 200
    submit_resp = client.post(f"/api/v1/shift-ops/shifts/{shift_id}/count/submit", headers=_auth(token))
    assert submit_resp.status_code == 200

    from app.models import ReplenishmentOrder

    assert db.query(ReplenishmentOrder).count() == 0
