from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

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
from app.models.branch_shift_ops import (
    BranchShiftCash,
    BranchShiftCount,
    BranchShiftCountLine,
    ShiftCountRowStatus,
    ShiftSectionStatus,
)
from app.services import shift_ops_service


@pytest.fixture(autouse=True)
def _enable_shift_cash_for_legacy_tests(monkeypatch):
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
    wh = Warehouse(warehouse_code="SA-WH", warehouse_name="SA WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(branch_code="SA-B1", branch_name="API Branch", city="Riyadh", area="Olaya", warehouse_id=wh.id)
    db.add(branch)
    db.flush()
    brand = Brand(name="SA Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code="SA-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    db.flush()
    unit = UnitOfMeasure(code="SA-PCS", name_ar="قطعة", name_en="pcs")
    db.add(unit)
    db.flush()
    item1 = Item(
        item_code="SA-ITEM-1",
        item_name_ar="صنف 1",
        item_name_en="Item 1",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    item2 = Item(
        item_code="SA-ITEM-2",
        item_name_ar="صنف 2",
        item_name_en="Item 2",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add_all([item1, item2])
    db.flush()
    db.add(ItemBrand(item_id=item1.id, brand_id=brand.id))
    db.add(ItemBrand(item_id=item2.id, brand_id=brand.id))
    db.add(BrandShiftCountItem(brand_id=brand.id, item_id=item1.id, display_order=1, is_active=True))
    _user(db, "sa_branch", RoleName.branch_manager, branch.id)
    _user(db, "sa_admin", RoleName.admin)
    db.commit()
    return branch.id, item1.id, item2.id, brand.id


def test_independent_count_and_cash_submit(client, db):
    _seed(db)
    token = _login(client, "sa_branch")
    shift = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-10", "shift_number": 1},
        headers=_auth(token),
    ).json()

    count = client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/count", headers=_auth(token)).json()
    line = count["lines"][0]
    client.patch(
        f"/api/v1/shift-ops/shifts/{shift['id']}/count/lines",
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
    count_submit = client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/count/submit", headers=_auth(token))
    assert count_submit.status_code == 200

    detail = client.get(f"/api/v1/shift-ops/shifts/{shift['id']}", headers=_auth(token)).json()
    assert detail["count_status"] == "submitted"
    assert detail["cash_status"] is None
    assert detail["is_partial"] is True
    assert detail["status"] == "draft"


def test_cash_save_returns_informational_fields(client, db):
    _seed(db)
    token = _login(client, "sa_branch")
    shift = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-11", "shift_number": 1},
        headers=_auth(token),
    ).json()
    resp = client.put(
        f"/api/v1/shift-ops/shifts/{shift['id']}/cash",
        json={
            "total_sale": 650,
            "bill_count": 1,
            "mada_sales": 0,
            "cash_sales": 650,
            "app_sales": 0,
            "refund_bill": 1,
            "exchange_amount": 2,
            "expiry_amount": 3,
            "cash_expense": 0,
            "cash_float_carried_forward": 500,
            "cash_deposited": 150,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["expected_deposited"] == "150.00"
    assert body["cash_variance"] == "0.00"
    assert body["informational_fields"]["informational"] is True


def test_frozen_list_ignores_new_brand_item(client, db):
    branch_id, item1_id, item2_id, brand_id = _seed(db)
    token = _login(client, "sa_branch")
    shift = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-12", "shift_number": 1},
        headers=_auth(token),
    ).json()
    first_count = client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/count", headers=_auth(token)).json()
    assert len(first_count["lines"]) == 1

    db.add(BrandShiftCountItem(brand_id=brand_id, item_id=item2_id, display_order=2, is_active=True))
    db.commit()

    second_count = client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/count", headers=_auth(token)).json()
    assert len(second_count["lines"]) == 1
    assert second_count["id"] == first_count["id"]


def test_create_or_get_count_integrity_error_returns_winner_once(client, db, monkeypatch):
    branch_id, item1_id, _item2_id, _brand_id = _seed(db)
    token = _login(client, "sa_branch")
    shift = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-14", "shift_number": 1},
        headers=_auth(token),
    ).json()
    user = db.query(User).filter(User.username == "sa_branch").one()
    winner = BranchShiftCount(
        shift_id=shift["id"],
        status=ShiftSectionStatus.draft.value,
        items_frozen_at=datetime.utcnow(),
        created_by=user.id,
    )
    db.add(winner)
    db.flush()
    db.add(
        BranchShiftCountLine(
            count_id=winner.id,
            item_id=item1_id,
            item_name_snapshot="صنف 1",
            unit_snapshot="قطعة",
            opening_balance=0,
            row_status=ShiftCountRowStatus.incomplete.value,
        )
    )
    db.flush()

    monkeypatch.setattr(
        shift_ops_service,
        "_get_shift",
        lambda _db, _shift_id: SimpleNamespace(id=shift["id"], branch_id=branch_id, count=None),
    )

    count, created = shift_ops_service.create_or_get_count(db, user, shift["id"])

    assert created is False
    assert count.id == winner.id
    assert db.query(BranchShiftCount).filter_by(shift_id=shift["id"]).count() == 1
    assert db.query(BranchShiftCountLine).filter_by(count_id=winner.id).count() == 1


def test_cash_save_persists_validation_errors_and_submit_still_blocks(client, db):
    _seed(db)
    token = _login(client, "sa_branch")
    shift = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-15", "shift_number": 1},
        headers=_auth(token),
    ).json()
    body = {
        "total_sale": 1000,
        "bill_count": 40,
        "mada_sales": 350,
        "cash_sales": 650,
        "app_sales": 0,
        "refund_bill": 1,
        "exchange_amount": 0,
        "expiry_amount": 0,
        "cash_expense": 0,
        "cash_float_carried_forward": 500,
        "cash_deposited": 130,
    }
    saved = client.put(
        f"/api/v1/shift-ops/shifts/{shift['id']}/cash",
        json=body,
        headers=_auth(token),
    )
    assert saved.status_code == 200, saved.text
    payload = saved.json()
    assert payload["cash_variance"] == "-20.00"
    assert payload["validation_errors"]
    assert {e["code"] for e in payload["validation_errors"]} == {"CASH_VARIANCE_REASON_REQUIRED"}

    cash = db.query(BranchShiftCash).filter_by(shift_id=shift["id"]).one()
    assert Decimal(str(cash.cash_deposited)) == Decimal("130.00")
    assert Decimal(str(cash.cash_variance)) == Decimal("-20.00")

    submitted = client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/cash/submit", headers=_auth(token))
    assert submitted.status_code == 422
    assert submitted.json()["detail"]["errors"][0]["code"] == "CASH_VARIANCE_REASON_REQUIRED"


def test_negative_movement_in_report_section(client, db):
    _seed(db)
    token = _login(client, "sa_branch")
    admin_token = _login(client, "sa_admin")

    shift1 = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-13", "shift_number": 1},
        headers=_auth(token),
    ).json()
    count1 = client.post(f"/api/v1/shift-ops/shifts/{shift1['id']}/count", headers=_auth(token)).json()
    line = count1["lines"][0]
    client.patch(
        f"/api/v1/shift-ops/shifts/{shift1['id']}/count/lines",
        json={
            "lines": [
                {
                    "item_id": ln["item_id"],
                    "received_qty": 0,
                    "returned_qty": 0,
                    "damaged_qty": 0,
                    "closing_balance": 10 if ln["item_id"] == line["item_id"] else float(ln["opening_balance"]),
                }
                for ln in count1["lines"]
            ]
        },
        headers=_auth(token),
    )
    client.post(f"/api/v1/shift-ops/shifts/{shift1['id']}/count/submit", headers=_auth(token))
    client.put(
        f"/api/v1/shift-ops/shifts/{shift1['id']}/cash",
        json={
            "total_sale": 0,
            "bill_count": 0,
            "mada_sales": 0,
            "cash_sales": 0,
            "app_sales": 0,
            "cash_expense": 0,
            "cash_float_carried_forward": 0,
            "cash_deposited": 0,
        },
        headers=_auth(token),
    )
    client.post(f"/api/v1/shift-ops/shifts/{shift1['id']}/cash/submit", headers=_auth(token))

    opening_report = client.get("/api/v1/shift-ops/reports/shift-operations", headers=_auth(admin_token)).json()
    opening_row = next(i for i in opening_report["items"] if i["id"] == shift1["id"])
    assert opening_row["is_opening_count"] is True
    assert opening_row["negative_movement_exceptions"] == []
    assert len(opening_row["opening_balance_lines"]) >= 1

    shift = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-14", "shift_number": 1},
        headers=_auth(token),
    ).json()
    count = client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/count", headers=_auth(token)).json()
    line2 = next(ln for ln in count["lines"] if ln["item_id"] == line["item_id"])
    client.patch(
        f"/api/v1/shift-ops/shifts/{shift['id']}/count/lines",
        json={
            "lines": [
                {
                    "item_id": line2["item_id"],
                    "received_qty": 0,
                    "returned_qty": 0,
                    "damaged_qty": 0,
                    "closing_balance": float(line2["opening_balance"]) + 5,
                    "movement_exception_reason": "Unregistered stock arrival",
                }
            ]
        },
        headers=_auth(token),
    )
    client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/count/submit", headers=_auth(token))
    client.put(
        f"/api/v1/shift-ops/shifts/{shift['id']}/cash",
        json={
            "total_sale": 0,
            "bill_count": 0,
            "mada_sales": 0,
            "cash_sales": 0,
            "app_sales": 0,
            "cash_expense": 0,
            "cash_float_carried_forward": 0,
            "cash_deposited": 0,
        },
        headers=_auth(token),
    )
    client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/cash/submit", headers=_auth(token))

    report = client.get("/api/v1/shift-ops/reports/shift-operations", headers=_auth(admin_token)).json()
    row = next(i for i in report["items"] if i["id"] == shift["id"])
    assert row["is_opening_count"] is False
    assert row["negative_movement_exceptions"]
    assert Decimal(row["movement_diff_total"]) == Decimal("0")
