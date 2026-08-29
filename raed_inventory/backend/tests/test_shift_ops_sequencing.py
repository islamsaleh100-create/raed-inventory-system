from datetime import date, datetime, timedelta

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
    BranchShift,
    BranchShiftExceptionType,
    BranchShiftStatus,
)
from app.core.errors import AppError
from app.services.shift_ops_service import validate_config_no_overlap


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
    wh = Warehouse(warehouse_code="SQ-WH", warehouse_name="SQ WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(branch_code="SQ-B1", branch_name="Seq Branch", city="Riyadh", area="Olaya", warehouse_id=wh.id)
    db.add(branch)
    db.flush()
    brand = Brand(name="SQ Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code="SQ-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    db.flush()
    unit = UnitOfMeasure(code="SQ-PCS", name_ar="قطعة", name_en="pcs")
    db.add(unit)
    db.flush()
    item = Item(
        item_code="SQ-ITEM-1",
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
    _user(db, "sq_mgr", RoleName.branch_manager, branch.id)
    am_user = _user(db, "sq_am", RoleName.area_manager)
    db.add(AreaManagerAssignment(user_id=am_user.id, city="Riyadh", brand_id=brand.id, active=True))
    db.commit()
    return branch.id


def test_previous_shift_blocks_open(client, db):
    _seed(db)
    token = _login(client, "sq_mgr")
    first = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-01", "shift_number": 1},
        headers=_auth(token),
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-01", "shift_number": 2},
        headers=_auth(token),
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "PREVIOUS_SHIFT_NOT_CLOSED"


def test_branch_manager_cannot_override(client, db):
    _seed(db)
    branch_token = _login(client, "sq_mgr")
    client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-02", "shift_number": 1},
        headers=_auth(branch_token),
    )
    mgr_token = _login(client, "sq_mgr")
    resp = client.post(
        "/api/v1/shift-ops/shifts",
        json={
            "shift_date": "2026-08-02",
            "shift_number": 2,
            "override": True,
            "override_reason": "Manager trying override",
        },
        headers=_auth(mgr_token),
    )
    assert resp.status_code == 403


def test_area_manager_override_locks_previous(client, db):
    _seed(db)
    branch_token = _login(client, "sq_mgr")
    first = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-03", "shift_number": 1},
        headers=_auth(branch_token),
    ).json()
    am_token = _login(client, "sq_am")
    second = client.post(
        "/api/v1/shift-ops/shifts",
        json={
            "branch_id": first["branch_id"],
            "shift_date": "2026-08-03",
            "shift_number": 2,
            "override": True,
            "override_reason": "Area manager override test",
        },
        headers=_auth(am_token),
    )
    assert second.status_code == 201
    prev = db.query(BranchShift).filter(BranchShift.id == first["id"]).one()
    assert prev.status == BranchShiftStatus.exception_locked.value
    assert prev.exception_type == BranchShiftExceptionType.stuck_previous.value


def test_post_count_is_idempotent(client, db):
    _seed(db)
    token = _login(client, "sq_mgr")
    shift = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-04", "shift_number": 1},
        headers=_auth(token),
    ).json()
    first = client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/count", headers=_auth(token))
    second = client.post(f"/api/v1/shift-ops/shifts/{shift['id']}/count", headers=_auth(token))
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["items_frozen_at"] == second.json()["items_frozen_at"]
    assert len(first.json()["lines"]) == len(second.json()["lines"])


def test_close_no_activity_without_stuck_previous(client, db):
    _seed(db)
    token = _login(client, "sq_mgr")
    am_token = _login(client, "sq_am")
    shift = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-05", "shift_number": 1},
        headers=_auth(token),
    ).json()
    resp = client.post(
        f"/api/v1/shift-ops/shifts/{shift['id']}/close-no-activity",
        json={"exception_type": "branch_closed", "reason": "Branch closed for maintenance"},
        headers=_auth(am_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == BranchShiftStatus.exception_locked.value
    assert body["exception_type"] == BranchShiftExceptionType.branch_closed.value
    assert body["count_status"] is None


def test_config_overlap_rejected(db):
    from app.models.branch_shift_ops import BranchShiftConfig

    branch_id = _seed(db)
    db.add(
        BranchShiftConfig(
            branch_id=branch_id,
            shift_number=1,
            shift_name_ar="صباحي",
            effective_from=date(2026, 8, 1),
            effective_to=date(2026, 8, 31),
        )
    )
    db.commit()
    try:
        validate_config_no_overlap(
            db,
            branch_id=branch_id,
            shift_number=1,
            effective_from=date(2026, 8, 15),
            effective_to=None,
        )
        raised = False
    except AppError as exc:
        raised = True
        assert exc.error_code == "shift_ops.config_overlap"
    assert raised


def test_reopen_window_from_submission_time(db, client):
    _seed(db)
    token = _login(client, "sq_mgr")
    am_token = _login(client, "sq_am")
    shift_resp = client.post(
        "/api/v1/shift-ops/shifts",
        json={"shift_date": "2026-08-06", "shift_number": 1},
        headers=_auth(token),
    ).json()
    shift_id = shift_resp["id"]

    count = client.post(f"/api/v1/shift-ops/shifts/{shift_id}/count", headers=_auth(token)).json()
    line = count["lines"][0]
    client.patch(
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
    client.post(f"/api/v1/shift-ops/shifts/{shift_id}/count/submit", headers=_auth(token))
    client.put(
        f"/api/v1/shift-ops/shifts/{shift_id}/cash",
        json={
            "total_sale": 100,
            "bill_count": 1,
            "mada_sales": 0,
            "cash_sales": 100,
            "app_sales": 0,
            "cash_expense": 0,
            "cash_float_carried_forward": 0,
            "cash_deposited": 100,
        },
        headers=_auth(token),
    )
    client.post(f"/api/v1/shift-ops/shifts/{shift_id}/cash/submit", headers=_auth(token))

    shift = db.query(BranchShift).filter(BranchShift.id == shift_id).one()
    submitted_at = datetime.utcnow() - timedelta(hours=30)
    if shift.count:
        shift.count.submitted_at = submitted_at
    if shift.cash:
        shift.cash.submitted_at = submitted_at
    shift.submitted_at = submitted_at
    db.commit()

    ok = client.post(
        f"/api/v1/shift-ops/shifts/{shift_id}/reopen",
        json={"target": "cash", "reason": "Fix cash entry mistake"},
        headers=_auth(am_token),
    )
    assert ok.status_code == 200
