from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import get_password_hash
from app.models import (
    AuditLog,
    AreaManagerAssignment,
    IdempotencyRequest,
    Brand,
    Branch,
    BranchBrand,
    BranchRequest,
    BranchRequestLineStatus,
    BranchRequestStatus,
    BranchStock,
    DeliveryOrder,
    DeliveryOrderLine,
    DeliveryOrderLineStatus,
    DeliveryOrderStatus,
    Item,
    ItemBrand,
    ItemCategory,
    KitchenSection,
    KitchenSectionAssignment,
    KitchenMaterialRequestStatus,
    ProductionOrder,
    ProductionOrderStatus,
    PurchaseRequest,
    PurchaseRequestStatus,
    Supplier,
    Role,
    RoleName,
    SupplyDefaultSource,
    SupplySourceType,
    StockTransaction,
    TransactionType,
    UnitOfMeasure,
    User,
    UserRole,
    UserStatus,
    Warehouse,
    WarehouseLine,
    WarehouseLineSourceType,
    WarehouseLineStatus,
    WarehouseStock,
)


def _role(db: Session, name: RoleName) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if role:
        return role
    role = Role(name=name, display_name=name.value, description="")
    db.add(role)
    db.flush()
    return role


def _user(db: Session, username: str, role_name: RoleName, branch_id: int | None = None) -> User:
    role = _role(db, role_name)
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash("Pass@2026"),
        status=UserStatus.active,
        branch_id=branch_id,
        is_deleted=False,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()
    return user


def _seed(db: Session) -> dict:
    wh = Warehouse(warehouse_code="SC-WH", warehouse_name="SC WH", location="Riyadh", active=True)
    wh_other = Warehouse(warehouse_code="SC-WH-2", warehouse_name="SC WH 2", location="Dammam", active=True)
    db.add_all([wh, wh_other])
    db.flush()

    branch_riyadh = Branch(branch_code="SC-RUH", branch_name="Riyadh Branch", city="Riyadh", area="", warehouse_id=wh.id)
    branch_dammam = Branch(branch_code="SC-DMM", branch_name="Dammam Branch", city="Dammam", area="", warehouse_id=wh_other.id)
    db.add_all([branch_riyadh, branch_dammam])
    db.flush()

    onda = Brand(name="Onda", active=True)
    shawarma = Brand(name="Shawarma", active=True)
    db.add_all([onda, shawarma])
    db.flush()
    db.add_all([
        BranchBrand(branch_id=branch_riyadh.id, brand_id=onda.id),
        BranchBrand(branch_id=branch_dammam.id, brand_id=shawarma.id),
    ])

    cat = ItemCategory(code="SC-CAT", name_ar="Supply", name_en="Supply")
    unit = UnitOfMeasure(code="SC-U", name_ar="Unit", name_en="Unit")
    db.add_all([cat, unit])
    db.flush()
    section_hot = KitchenSection(name="Hot Kitchen", active=True)
    section_cold = KitchenSection(name="Cold Kitchen", active=True)
    section_extra = KitchenSection(name="Extra Kitchen", active=True)
    db.add_all([section_hot, section_cold, section_extra])
    db.flush()

    item_onda = Item(
        item_code="SC-ONDA-1",
        item_name_ar="Onda Item",
        item_name_en="Onda Item",
        category_id=cat.id,
        unit_id=unit.id,
        source_type=SupplySourceType.WAREHOUSE,
        default_source=SupplyDefaultSource.WAREHOUSE,
    )
    item_kitchen = Item(
        item_code="SC-KIT-1",
        item_name_ar="Kitchen Item",
        item_name_en="Kitchen Item",
        category_id=cat.id,
        unit_id=unit.id,
        source_type=SupplySourceType.KITCHEN,
        default_source=SupplyDefaultSource.KITCHEN,
        kitchen_section_id=section_hot.id,
    )
    item_other = Item(
        item_code="SC-SHAW-1",
        item_name_ar="Shawarma Item",
        item_name_en="Shawarma Item",
        category_id=cat.id,
        unit_id=unit.id,
    )
    db.add_all([item_onda, item_kitchen, item_other])
    db.flush()
    db.add_all([
        ItemBrand(item_id=item_onda.id, brand_id=onda.id),
        ItemBrand(item_id=item_kitchen.id, brand_id=onda.id),
        ItemBrand(item_id=item_other.id, brand_id=shawarma.id),
    ])

    branch_user = _user(db, "sc_branch_user", RoleName.branch_user, branch_riyadh.id)
    branch_user_other = _user(db, "sc_branch_other", RoleName.branch_user, branch_dammam.id)
    area_riyadh_onda = _user(db, "sc_area_onda", RoleName.area_manager)
    area_dammam_shawarma = _user(db, "sc_area_shawarma", RoleName.area_manager)
    admin = _user(db, "sc_admin", RoleName.admin)
    super_admin = _user(db, "sc_super_admin", RoleName.super_admin)
    section_mgr = _user(db, "sc_section_mgr", RoleName.kitchen_section_manager)
    other_section_mgr = _user(db, "sc_other_section_mgr", RoleName.kitchen_section_manager)
    unassigned_section_mgr = _user(db, "sc_unassigned_section_mgr", RoleName.kitchen_section_manager)
    wh_user = _user(db, "sc_wh_user", RoleName.warehouse_user)
    wh_other_user = _user(db, "sc_wh_other", RoleName.warehouse_user)
    wh_other_mgr = _user(db, "sc_wh_other_mgr", RoleName.warehouse_manager)
    delivery_user = _user(db, "sc_delivery_user", RoleName.delivery_user)
    wh_user.warehouse_id = wh.id
    wh_other_user.warehouse_id = wh_other.id
    wh_other_mgr.warehouse_id = wh_other.id
    db.flush()

    db.add_all([
        AreaManagerAssignment(user_id=area_riyadh_onda.id, city="Riyadh", brand_id=onda.id, active=True),
        AreaManagerAssignment(user_id=area_dammam_shawarma.id, city="Dammam", brand_id=shawarma.id, active=True),
        KitchenSectionAssignment(user_id=section_mgr.id, kitchen_section_id=section_hot.id, active=True),
        KitchenSectionAssignment(user_id=other_section_mgr.id, kitchen_section_id=section_cold.id, active=True),
    ])
    db.add(WarehouseStock(
        warehouse_id=wh.id,
        item_id=item_onda.id,
        current_qty=Decimal("100"),
        reserved_qty=Decimal("0"),
    ))
    db.add(WarehouseStock(
        warehouse_id=wh_other.id,
        item_id=item_other.id,
        current_qty=Decimal("50"),
        reserved_qty=Decimal("0"),
    ))
    db.commit()

    return {
        "branch_riyadh": branch_riyadh.id,
        "branch_dammam": branch_dammam.id,
        "onda": onda.id,
        "shawarma": shawarma.id,
        "item_onda": item_onda.id,
        "item_kitchen": item_kitchen.id,
        "item_other": item_other.id,
        "warehouse": wh.id,
        "warehouse_other": wh_other.id,
        "section_hot": section_hot.id,
        "section_cold": section_cold.id,
        "section_extra": section_extra.id,
        "area_onda_user": area_riyadh_onda.id,
        "branch_user": branch_user.id,
        "section_mgr": section_mgr.id,
        "unassigned_section_mgr": unassigned_section_mgr.id,
        "delivery_user": delivery_user.id,
        "super_admin": super_admin.id,
    }


def _login(client, username: str) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "Pass@2026"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_payload(seed: dict, **overrides) -> dict:
    payload = {
        "branch_id": seed["branch_riyadh"],
        "brand_id": seed["onda"],
        "priority": "normal",
        "lines": [{"item_id": seed["item_onda"], "qty_requested": "5"}],
    }
    payload.update(overrides)
    return payload


def _create_and_submit(client, seed: dict) -> int:
    token = _login(client, "sc_branch_user")
    created = client.post("/api/v1/branch-requests", json=_create_payload(seed), headers=_auth(token))
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    submitted = client.post(f"/api/v1/branch-requests/{request_id}/submit", headers=_auth(token))
    assert submitted.status_code == 200, submitted.text
    return request_id


def _create_submit_approve(client, seed: dict, payload: dict | None = None) -> int:
    token = _login(client, "sc_branch_user")
    created = client.post("/api/v1/branch-requests", json=payload or _create_payload(seed), headers=_auth(token))
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    submitted = client.post(f"/api/v1/branch-requests/{request_id}/submit", headers=_auth(token))
    assert submitted.status_code == 200, submitted.text
    area_token = _login(client, "sc_area_onda")
    approved = client.post(f"/api/v1/branch-requests/{request_id}/approve", json={}, headers=_auth(area_token))
    assert approved.status_code == 200, approved.text
    return request_id


def _split_request(client, request_id: int):
    token = _login(client, "sc_area_onda")
    r = client.post(f"/api/v1/branch-requests/{request_id}/split", headers=_auth(token))
    assert r.status_code == 200, r.text
    return r


def _create_submit_approve_other_warehouse_request(client, seed: dict) -> int:
    branch_token = _login(client, "sc_branch_other")
    created = client.post(
        "/api/v1/branch-requests",
        json={
            "branch_id": seed["branch_dammam"],
            "brand_id": seed["shawarma"],
            "priority": "normal",
            "lines": [{"item_id": seed["item_other"], "qty_requested": "4"}],
        },
        headers=_auth(branch_token),
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    submitted = client.post(f"/api/v1/branch-requests/{request_id}/submit", headers=_auth(branch_token))
    assert submitted.status_code == 200, submitted.text
    area_token = _login(client, "sc_area_shawarma")
    approved = client.post(f"/api/v1/branch-requests/{request_id}/approve", json={}, headers=_auth(area_token))
    assert approved.status_code == 200, approved.text
    split = client.post(f"/api/v1/branch-requests/{request_id}/split", headers=_auth(area_token))
    assert split.status_code == 200, split.text
    return request_id


def _ready_warehouse_line(client, seed: dict, db: Session) -> WarehouseLine:
    request_id = _create_submit_approve(client, seed)
    _split_request(client, request_id)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_user")
    issued = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers=_auth(token))
    assert issued.status_code == 200, issued.text
    db.refresh(wh_line)
    return wh_line


def _ready_other_warehouse_line(client, seed: dict, db: Session) -> WarehouseLine:
    request_id = _create_submit_approve_other_warehouse_request(client, seed)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_other")
    issued = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers=_auth(token))
    assert issued.status_code == 200, issued.text
    db.refresh(wh_line)
    return wh_line


def _create_delivery_order(client, warehouse_line_id: int, username: str = "sc_wh_user") -> dict:
    token = _login(client, username)
    r = client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [warehouse_line_id]},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def seeded(db: Session):
    return _seed(db)


def test_allowed_items_are_filtered_by_request_brand(seeded, client):
    token = _login(client, "sc_branch_user")
    r = client.get(
        f"/api/v1/branch-requests/allowed-items?branch_id={seeded['branch_riyadh']}&brand_id={seeded['onda']}",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    ids = {item["id"] for item in r.json()}
    assert seeded["item_onda"] in ids
    assert seeded["item_other"] not in ids


def test_allowed_items_infers_single_branch_brand(seeded, client):
    token = _login(client, "sc_branch_user")
    r = client.get(
        f"/api/v1/branch-requests/allowed-items?branch_id={seeded['branch_riyadh']}",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    ids = {item["id"] for item in r.json()}
    assert seeded["item_onda"] in ids
    assert seeded["item_kitchen"] in ids
    assert seeded["item_other"] not in ids


def test_allowed_items_requires_brand_for_multi_brand_branch(seeded, client, db: Session):
    db.add(BranchBrand(branch_id=seeded["branch_dammam"], brand_id=seeded["onda"]))
    db.commit()
    token = _login(client, "sc_branch_other")
    r = client.get(
        f"/api/v1/branch-requests/allowed-items?branch_id={seeded['branch_dammam']}",
        headers=_auth(token),
    )
    assert r.status_code == 400, r.text
    assert r.json()["error_code"] == "branch_requests.brand_id_required"


def test_request_brand_must_belong_to_branch(seeded, client):
    token = _login(client, "sc_branch_user")
    r = client.post(
        "/api/v1/branch-requests",
        json=_create_payload(seeded, brand_id=seeded["shawarma"]),
        headers=_auth(token),
    )
    assert r.status_code == 400


def test_branch_user_can_create_and_submit_own_request(seeded, client):
    request_id = _create_and_submit(client, seeded)
    body = client.get(
        f"/api/v1/branch-requests/{request_id}",
        headers=_auth(_login(client, "sc_branch_user")),
    ).json()
    assert body["status"] == BranchRequestStatus.SUBMITTED.value
    assert body["lines"][0]["status"] == "SUBMITTED"


def test_branch_user_cannot_create_for_another_branch(seeded, client):
    token = _login(client, "sc_branch_user")
    r = client.post(
        "/api/v1/branch-requests",
        json=_create_payload(seeded, branch_id=seeded["branch_dammam"], brand_id=seeded["shawarma"]),
        headers=_auth(token),
    )
    assert r.status_code == 403


def test_area_manager_sees_only_matching_city_and_brand_requests(seeded, client):
    request_id = _create_and_submit(client, seeded)
    good_token = _login(client, "sc_area_onda")
    bad_token = _login(client, "sc_area_shawarma")

    good = client.get("/api/v1/branch-requests", headers=_auth(good_token))
    bad = client.get("/api/v1/branch-requests", headers=_auth(bad_token))

    assert good.status_code == 200, good.text
    assert request_id in {row["id"] for row in good.json()["items"]}
    assert bad.status_code == 200, bad.text
    assert request_id not in {row["id"] for row in bad.json()["items"]}


def test_area_manager_cannot_see_draft_request(seeded, client):
    branch_token = _login(client, "sc_branch_user")
    created = client.post("/api/v1/branch-requests", json=_create_payload(seeded), headers=_auth(branch_token))
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    area_token = _login(client, "sc_area_onda")
    listed = client.get("/api/v1/branch-requests", headers=_auth(area_token))
    assert request_id not in {row["id"] for row in listed.json()["items"]}
    detail = client.get(f"/api/v1/branch-requests/{request_id}", headers=_auth(area_token))
    assert detail.status_code == 403


def test_reject_without_note_fails(seeded, client):
    request_id = _create_and_submit(client, seeded)
    token = _login(client, "sc_area_onda")
    r = client.post(f"/api/v1/branch-requests/{request_id}/reject", json={}, headers=_auth(token))
    assert r.status_code == 422


def test_modify_and_approve_without_note_fails(seeded, client):
    request_id = _create_and_submit(client, seeded)
    token = _login(client, "sc_area_onda")
    details = client.get(f"/api/v1/branch-requests/{request_id}", headers=_auth(token)).json()
    line_id = details["lines"][0]["id"]
    r = client.post(
        f"/api/v1/branch-requests/{request_id}/modify-and-approve",
        json={"lines": [{"line_id": line_id, "qty_approved": "3"}]},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_approve_succeeds(seeded, client):
    request_id = _create_and_submit(client, seeded)
    token = _login(client, "sc_area_onda")
    r = client.post(f"/api/v1/branch-requests/{request_id}/approve", json={}, headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == BranchRequestStatus.SPLIT.value
    assert Decimal(r.json()["lines"][0]["qty_approved"]) == Decimal("5")


def test_reject_succeeds_with_note(seeded, client):
    request_id = _create_and_submit(client, seeded)
    token = _login(client, "sc_area_onda")
    r = client.post(
        f"/api/v1/branch-requests/{request_id}/reject",
        json={"rejection_note": "Not needed"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == BranchRequestStatus.AREA_REJECTED.value
    assert r.json()["rejection_note"] == "Not needed"


def test_modify_and_approve_updates_approved_quantities(seeded, client):
    request_id = _create_and_submit(client, seeded)
    token = _login(client, "sc_area_onda")
    details = client.get(f"/api/v1/branch-requests/{request_id}", headers=_auth(token)).json()
    line_id = details["lines"][0]["id"]
    r = client.post(
        f"/api/v1/branch-requests/{request_id}/modify-and-approve",
        json={"approval_note": "Reduce qty", "lines": [{"line_id": line_id, "qty_approved": "2"}]},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["lines"][0]["qty_approved"]) == Decimal("2")
    assert r.json()["approval_note"] == "Reduce qty"


def test_qty_approved_cannot_exceed_requested(seeded, client):
    request_id = _create_and_submit(client, seeded)
    token = _login(client, "sc_area_onda")
    details = client.get(f"/api/v1/branch-requests/{request_id}", headers=_auth(token)).json()
    line_id = details["lines"][0]["id"]
    r = client.post(
        f"/api/v1/branch-requests/{request_id}/modify-and-approve",
        json={"approval_note": "too high", "lines": [{"line_id": line_id, "qty_approved": "99"}]},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "branch_requests.qty_approved_exceeds_requested"


def test_item_not_assigned_to_brand_is_rejected(seeded, client):
    token = _login(client, "sc_branch_user")
    r = client.post(
        "/api/v1/branch-requests",
        json=_create_payload(seeded, lines=[{"item_id": seeded["item_other"], "qty_requested": "4"}]),
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "branch_requests.item_not_allowed_for_brand"


def test_admin_bypass_allows_cross_branch_create_and_approve(seeded, client, db: Session):
    admin_token = _login(client, "sc_admin")
    r = client.post(
        "/api/v1/branch-requests",
        json=_create_payload(seeded),
        headers=_auth(admin_token),
    )
    assert r.status_code == 201, r.text
    request_id = r.json()["id"]
    submitted = client.post(f"/api/v1/branch-requests/{request_id}/submit", headers=_auth(admin_token))
    assert submitted.status_code == 200, submitted.text
    approved = client.post(f"/api/v1/branch-requests/{request_id}/approve", json={}, headers=_auth(admin_token))
    assert approved.status_code == 200, approved.text
    assert db.query(BranchRequest).filter(BranchRequest.id == request_id).first().status == BranchRequestStatus.SPLIT


def test_duplicate_active_area_assignment_rejected(seeded, client):
    token = _login(client, "sc_admin")
    r = client.post(
        "/api/v1/master/area-manager-assignments",
        json={"user_id": seeded["area_onda_user"], "city": "Riyadh", "brand_id": seeded["onda"], "active": True},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "master.duplicate_area_manager_assignment"


def test_assignment_to_non_area_manager_rejected(seeded, client):
    token = _login(client, "sc_admin")
    r = client.post(
        "/api/v1/master/area-manager-assignments",
        json={"user_id": seeded["branch_user"], "city": "Riyadh", "brand_id": seeded["onda"], "active": True},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "master.user_not_area_manager"


def test_kitchen_section_assignment_create_succeeds_for_valid_section_manager(seeded, client):
    token = _login(client, "sc_admin")
    r = client.post(
        "/api/v1/master/kitchen-section-assignments",
        json={
            "user_id": seeded["unassigned_section_mgr"],
            "kitchen_section_id": seeded["section_extra"],
            "active": True,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["kitchen_section_id"] == seeded["section_extra"]


def test_kitchen_section_assignment_rejects_non_section_manager(seeded, client):
    token = _login(client, "sc_admin")
    r = client.post(
        "/api/v1/master/kitchen-section-assignments",
        json={"user_id": seeded["branch_user"], "kitchen_section_id": seeded["section_extra"], "active": True},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "master.user_not_kitchen_section_manager"


def test_duplicate_active_kitchen_section_assignment_rejected(seeded, client):
    token = _login(client, "sc_admin")
    r = client.post(
        "/api/v1/master/kitchen-section-assignments",
        json={"user_id": seeded["section_mgr"], "kitchen_section_id": seeded["section_hot"], "active": True},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "master.duplicate_kitchen_section_assignment"


def test_split_creates_warehouse_line_for_warehouse_source(seeded, client, db: Session):
    request_id = _create_submit_approve(client, seeded)
    _split_request(client, request_id)
    wh_line = db.query(WarehouseLine).filter(
        WarehouseLine.source_request_id == request_id,
        WarehouseLine.source_type == WarehouseLineSourceType.BRANCH_REQUEST,
    ).first()
    assert wh_line is not None
    assert wh_line.item_id == seeded["item_onda"]
    assert wh_line.pending_qty == Decimal("5")


def test_split_reserves_warehouse_stock_for_warehouse_source(seeded, client, db: Session):
    stock = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == seeded["warehouse"],
        WarehouseStock.item_id == seeded["item_onda"],
    ).first()
    assert stock.reserved_qty == Decimal("0")

    request_id = _create_submit_approve(client, seeded)
    _split_request(client, request_id)

    db.refresh(stock)
    assert stock.current_qty == Decimal("100")
    assert stock.reserved_qty == Decimal("5")


def test_master_kitchens_and_section_kitchen_ids_shape(seeded, client):
    token = _login(client, "sc_branch_user")
    kr = client.get("/api/v1/master/kitchens", headers=_auth(token))
    assert kr.status_code == 200
    assert isinstance(kr.json(), list)
    sec = client.get("/api/v1/master/kitchen-sections", headers=_auth(token))
    assert sec.status_code == 200
    for row in sec.json():
        assert "kitchen_ids" in row
        assert isinstance(row["kitchen_ids"], list)


def test_master_create_kitchen_admin_and_duplicate_rejected(seeded, client):
    token = _login(client, "sc_admin")
    body = {
        "name": "pytest kitchen unique",
        "city": "pytest city",
        "active": True,
        "section_ids": [seeded["section_hot"]],
    }
    r = client.post("/api/v1/master/kitchens", json=body, headers=_auth(token))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == body["name"]
    assert data["city"] == body["city"]
    assert seeded["section_hot"] in (data.get("section_ids") or [])
    dup = client.post("/api/v1/master/kitchens", json=body, headers=_auth(token))
    assert dup.status_code == 400
    assert dup.json().get("error_code") == "master.kitchen_exists"


def test_warehouse_branch_request_receive_then_issue(seeded, client, db: Session):
    request_id = _create_submit_approve(client, seeded)
    _split_request(client, request_id)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    assert wh_line.status == WarehouseLineStatus.PENDING
    token = _login(client, "sc_wh_user")
    rx = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/receive", headers=_auth(token))
    assert rx.status_code == 200, rx.text
    assert rx.json()["status"] == "AVAILABLE"
    rx2 = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/receive", headers=_auth(token))
    assert rx2.status_code == 200
    assert rx2.json()["status"] == "AVAILABLE"
    issued = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers=_auth(token))
    assert issued.status_code == 200
    assert issued.json()["status"] == "READY_FOR_DISPATCH"
    bad = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/receive", headers=_auth(token))
    assert bad.status_code == 400
    assert bad.json()["error_code"] == "warehouse_lines.receive_invalid_status"


def test_split_creates_production_order_for_kitchen_source(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    assert po is not None
    assert po.destination_branch_id == seeded["branch_riyadh"]
    assert po.kitchen_section_id == seeded["section_hot"]
    assert po.status == ProductionOrderStatus.PENDING


def test_split_is_idempotent_safe(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[
        {"item_id": seeded["item_onda"], "qty_requested": "5"},
        {"item_id": seeded["item_kitchen"], "qty_requested": "6"},
    ])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    _split_request(client, request_id)
    wh_count = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).count()
    po_count = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).count()
    assert wh_count == 1
    assert po_count == 1


def test_submit_populates_snapshots(seeded, client, db: Session):
    token = _login(client, "sc_branch_user")
    created = client.post("/api/v1/branch-requests", json=_create_payload(seeded), headers=_auth(token))
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    submitted = client.post(
        f"/api/v1/branch-requests/{request_id}/submit",
        headers={**_auth(token), "X-Idempotency-Key": "submit-snapshots-1"},
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["brand_name_snapshot"] == "Onda"
    assert body["lines"][0]["item_code_snapshot"] == "SC-ONDA-1"
    assert body["lines"][0]["item_name_en_snapshot"] == "Onda Item"
    assert body["lines"][0]["unit_code_snapshot"] == "SC-U"


def test_submit_is_idempotent_safe(seeded, client, db: Session):
    token = _login(client, "sc_branch_user")
    created = client.post("/api/v1/branch-requests", json=_create_payload(seeded), headers=_auth(token))
    request_id = created.json()["id"]
    headers = {**_auth(token), "X-Idempotency-Key": "submit-repeat-1"}
    first = client.post(f"/api/v1/branch-requests/{request_id}/submit", headers=headers)
    second = client.post(f"/api/v1/branch-requests/{request_id}/submit", headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["status"] == BranchRequestStatus.SUBMITTED.value


def test_production_order_requires_destination_branch_id(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    assert po.destination_branch_id == seeded["branch_riyadh"]


def test_section_isolation_works(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()

    wrong_token = _login(client, "sc_other_section_mgr")
    denied = client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(wrong_token))
    assert denied.status_code == 403

    right_token = _login(client, "sc_section_mgr")
    ok = client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(right_token))
    assert ok.status_code == 200, ok.text


def test_kitchen_section_manager_sees_only_assigned_section_orders(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    token = _login(client, "sc_section_mgr")
    rows = client.get("/api/v1/production-orders", headers=_auth(token))
    assert rows.status_code == 200, rows.text
    assert {r["kitchen_section_id"] for r in rows.json()} == {seeded["section_hot"]}


def test_kitchen_section_manager_cannot_get_other_section_order(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_other_section_mgr")
    r = client.get(f"/api/v1/production-orders/{po.id}", headers=_auth(token))
    assert r.status_code == 403


def test_production_start_partial_ready_and_send_to_warehouse(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_section_mgr")

    started = client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(token))
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "IN_PROGRESS"

    partial = client.post(
        f"/api/v1/production-orders/{po.id}/mark-partial-ready",
        json={"qty_ready": "3", "notes": "half done"},
        headers=_auth(token),
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["status"] == "PARTIAL_READY"

    sent = client.post(f"/api/v1/production-orders/{po.id}/send-to-warehouse", headers=_auth(token))
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "PARTIAL_READY"
    assert Decimal(sent.json()["qty_sent_to_warehouse"]) == Decimal("3")
    wh = db.query(WarehouseLine).filter(
        WarehouseLine.source_request_id == request_id,
        WarehouseLine.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT,
    ).first()
    assert wh is not None
    assert wh.branch_id == seeded["branch_riyadh"]
    assert wh.status == WarehouseLineStatus.AVAILABLE


def test_partial_send_preserves_remaining_production_and_line_not_ready(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_section_mgr")
    client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(token))
    client.post(
        f"/api/v1/production-orders/{po.id}/mark-partial-ready",
        json={"qty_ready": "3"},
        headers=_auth(token),
    )

    sent = client.post(f"/api/v1/production-orders/{po.id}/send-to-warehouse", headers=_auth(token))
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["status"] == "PARTIAL_READY"
    assert Decimal(body["qty_ready"]) == Decimal("3")
    assert Decimal(body["qty_sent_to_warehouse"]) == Decimal("3")

    db.refresh(po)
    assert po.qty_requested - po.qty_sent_to_warehouse == Decimal("3")
    assert po.source_request_line.status == BranchRequestLineStatus.PARTIAL_WAREHOUSE


def test_partial_send_repeated_does_not_double_count_stock(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_section_mgr")
    client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(token))
    client.post(
        f"/api/v1/production-orders/{po.id}/mark-partial-ready",
        json={"qty_ready": "3"},
        headers=_auth(token),
    )
    first = client.post(f"/api/v1/production-orders/{po.id}/send-to-warehouse", headers=_auth(token))
    second = client.post(f"/api/v1/production-orders/{po.id}/send-to-warehouse", headers=_auth(token))
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    stock = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == seeded["warehouse"],
        WarehouseStock.item_id == seeded["item_kitchen"],
    ).first()
    assert stock.current_qty == Decimal("3")
    wh = db.query(WarehouseLine).filter(
        WarehouseLine.source_request_id == request_id,
        WarehouseLine.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT,
    ).first()
    assert wh.requested_qty == Decimal("3")
    assert wh.pending_qty == Decimal("3")


def test_partial_then_full_completion_updates_warehouse_line_and_marks_ready(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_section_mgr")
    client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(token))
    client.post(
        f"/api/v1/production-orders/{po.id}/mark-partial-ready",
        json={"qty_ready": "3"},
        headers=_auth(token),
    )
    client.post(f"/api/v1/production-orders/{po.id}/send-to-warehouse", headers=_auth(token))

    ready = client.post(f"/api/v1/production-orders/{po.id}/mark-ready", headers=_auth(token))
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "READY"
    final = client.post(f"/api/v1/production-orders/{po.id}/send-to-warehouse", headers=_auth(token))
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "SENT_TO_WAREHOUSE"
    assert Decimal(final.json()["qty_sent_to_warehouse"]) == Decimal("6")

    stock = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == seeded["warehouse"],
        WarehouseStock.item_id == seeded["item_kitchen"],
    ).first()
    assert stock.current_qty == Decimal("6")
    wh = db.query(WarehouseLine).filter(
        WarehouseLine.source_request_id == request_id,
        WarehouseLine.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT,
    ).first()
    assert wh.requested_qty == Decimal("6")
    assert wh.pending_qty == Decimal("6")
    db.refresh(po)
    assert po.source_request_line.status == BranchRequestLineStatus.READY_IN_WAREHOUSE


def test_send_to_warehouse_increases_warehouse_stock_and_posts_ledger(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_section_mgr")
    client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(token))
    client.post(f"/api/v1/production-orders/{po.id}/mark-ready", headers=_auth(token))

    before = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == seeded["warehouse"],
        WarehouseStock.item_id == seeded["item_kitchen"],
    ).first()
    assert before is None

    sent = client.post(f"/api/v1/production-orders/{po.id}/send-to-warehouse", headers=_auth(token))
    assert sent.status_code == 200, sent.text
    stock = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == seeded["warehouse"],
        WarehouseStock.item_id == seeded["item_kitchen"],
    ).first()
    assert stock is not None
    assert stock.current_qty == Decimal("6")
    tx = db.query(StockTransaction).filter(
        StockTransaction.reference_no.like(f"PO-{po.id}-%"),
        StockTransaction.transaction_type == TransactionType.adjustment_in,
    ).first()
    assert tx is not None
    assert tx.destination_type == "warehouse"
    assert tx.source_type == "kitchen_output"


def test_production_mark_ready_requires_in_progress(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_section_mgr")
    early = client.post(f"/api/v1/production-orders/{po.id}/mark-ready", headers=_auth(token))
    assert early.status_code == 400
    client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(token))
    ready = client.post(f"/api/v1/production-orders/{po.id}/mark-ready", headers=_auth(token))
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "READY"


def test_production_partial_ready_requires_in_progress(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_section_mgr")
    early = client.post(
        f"/api/v1/production-orders/{po.id}/mark-partial-ready",
        json={"qty_ready": "3"},
        headers=_auth(token),
    )
    assert early.status_code == 400


def test_request_materials_sets_waiting_status(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_section_mgr")
    r = client.post(
        f"/api/v1/production-orders/{po.id}/request-materials",
        json={"item_id": seeded["item_onda"], "qty": "2", "notes": "need material"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    db.refresh(po)
    assert po.status == ProductionOrderStatus.WAITING_FOR_MATERIALS


def test_material_request_can_be_approved_and_issued_by_warehouse(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    section_token = _login(client, "sc_section_mgr")
    asked = client.post(
        f"/api/v1/production-orders/{po.id}/request-materials",
        json={"item_id": seeded["item_onda"], "qty": "2", "notes": "need material"},
        headers=_auth(section_token),
    )
    assert asked.status_code == 201, asked.text
    material_id = asked.json()["id"]

    admin_token = _login(client, "sc_admin")
    approved = client.post(
        f"/api/v1/production-orders/material-requests/{material_id}/approve",
        json={"notes": "approved"},
        headers=_auth(admin_token),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == KitchenMaterialRequestStatus.APPROVED.value

    wh_token = _login(client, "sc_wh_user")
    issued = client.post(
        f"/api/v1/production-orders/material-requests/{material_id}/issue",
        json={"notes": "issued"},
        headers=_auth(wh_token),
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == KitchenMaterialRequestStatus.ISSUED.value
    db.refresh(po)
    assert po.status == ProductionOrderStatus.IN_PROGRESS


def test_material_request_can_be_rejected_and_returns_order_to_in_progress(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    section_token = _login(client, "sc_section_mgr")
    asked = client.post(
        f"/api/v1/production-orders/{po.id}/request-materials",
        json={"item_id": seeded["item_onda"], "qty": "2", "notes": "need material"},
        headers=_auth(section_token),
    )
    assert asked.status_code == 201, asked.text
    material_id = asked.json()["id"]

    admin_token = _login(client, "sc_admin")
    rejected = client.post(
        f"/api/v1/production-orders/material-requests/{material_id}/reject",
        json={"reason": "not available now"},
        headers=_auth(admin_token),
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == KitchenMaterialRequestStatus.REJECTED.value
    db.refresh(po)
    assert po.status == ProductionOrderStatus.IN_PROGRESS


def test_warehouse_issue_deducts_stock_at_issue_time_only(seeded, client, db: Session):
    stock = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == seeded["warehouse"],
        WarehouseStock.item_id == seeded["item_onda"],
    ).first()
    assert stock.current_qty == Decimal("100")
    request_id = _create_submit_approve(client, seeded)
    assert stock.current_qty == Decimal("100")
    _split_request(client, request_id)
    db.refresh(stock)
    assert stock.current_qty == Decimal("100")

    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_user")
    issued = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers=_auth(token))
    assert issued.status_code == 200, issued.text
    db.refresh(stock)
    assert stock.current_qty == Decimal("95")
    assert stock.reserved_qty == Decimal("0")


def test_issue_is_idempotent_and_does_not_double_deduct(seeded, client, db: Session):
    stock = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == seeded["warehouse"],
        WarehouseStock.item_id == seeded["item_onda"],
    ).first()
    request_id = _create_submit_approve(client, seeded)
    _split_request(client, request_id)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_user")
    headers = {**_auth(token), "X-Idempotency-Key": "issue-repeat-1"}
    first = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers=headers)
    second = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    db.refresh(stock)
    assert stock.current_qty == Decimal("95")


def test_partial_issue_releases_only_issued_reserved_qty(seeded, client, db: Session):
    stock = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == seeded["warehouse"],
        WarehouseStock.item_id == seeded["item_onda"],
    ).first()
    request_id = _create_submit_approve(client, seeded)
    _split_request(client, request_id)
    db.refresh(stock)
    assert stock.reserved_qty == Decimal("5")

    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_user")
    issued = client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/partial-issue",
        json={"qty": "3", "delay_reason": "short stock"},
        headers=_auth(token),
    )
    assert issued.status_code == 200, issued.text
    db.refresh(stock)
    assert stock.current_qty == Decimal("97")
    assert stock.reserved_qty == Decimal("2")


def test_partial_issue_requires_delay_reason(seeded, client, db: Session):
    request_id = _create_submit_approve(client, seeded)
    _split_request(client, request_id)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_user")
    r = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/partial-issue", json={"qty": "2"}, headers=_auth(token))
    assert r.status_code == 400
    assert r.json()["error_code"] == "warehouse_lines.delay_reason_required"


def test_partial_issue_updates_issued_pending_and_status(seeded, client, db: Session):
    request_id = _create_submit_approve(client, seeded)
    _split_request(client, request_id)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_user")
    r = client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/partial-issue",
        json={"qty": "3", "delay_reason": "short stock"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert Decimal(body["issued_qty"]) == Decimal("3")
    assert Decimal(body["pending_qty"]) == Decimal("2")
    assert body["status"] == "PARTIAL"


def test_warehouse_user_cannot_access_another_warehouse_line(seeded, client, db: Session):
    request_id = _create_submit_approve_other_warehouse_request(client, seeded)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_user")
    r = client.get(f"/api/v1/warehouse-lines/{wh_line.id}", headers=_auth(token))
    assert r.status_code == 403


def test_warehouse_manager_cannot_issue_another_warehouse_line(seeded, client, db: Session):
    request_id = _create_submit_approve(client, seeded)
    _split_request(client, request_id)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_other_mgr")
    r = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers=_auth(token))
    assert r.status_code == 403


def test_admin_has_global_warehouse_access(seeded, client, db: Session):
    request_id = _create_submit_approve_other_warehouse_request(client, seeded)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_admin")
    r = client.get(f"/api/v1/warehouse-lines/{wh_line.id}", headers=_auth(token))
    assert r.status_code == 200, r.text


def test_delivery_order_can_be_created_only_from_ready_for_dispatch_line(seeded, client, db: Session):
    wh_line = _ready_warehouse_line(client, seeded, db)
    body = _create_delivery_order(client, wh_line.id)
    assert body["status"] == DeliveryOrderStatus.READY.value
    assert body["branch_id"] == seeded["branch_riyadh"]
    assert body["brand_id"] == seeded["onda"]
    assert Decimal(body["lines"][0]["qty_dispatched"]) == Decimal("5")


def test_delivery_order_rejects_mixed_branches(seeded, client, db: Session):
    wh_line = _ready_warehouse_line(client, seeded, db)
    other_line = _ready_other_warehouse_line(client, seeded, db)
    token = _login(client, "sc_admin")
    r = client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id, other_line.id]},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "delivery_orders.mixed_branches"


def test_delivery_order_rejects_non_ready_warehouse_line(seeded, client, db: Session):
    request_id = _create_submit_approve(client, seeded)
    _split_request(client, request_id)
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    token = _login(client, "sc_wh_user")
    r = client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "delivery_orders.line_not_ready"


def test_warehouse_user_cannot_create_delivery_for_another_warehouse(seeded, client, db: Session):
    other_line = _ready_other_warehouse_line(client, seeded, db)
    token = _login(client, "sc_wh_user")
    r = client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [other_line.id]},
        headers=_auth(token),
    )
    assert r.status_code == 403
    assert r.json()["error_code"] == "delivery_orders.warehouse_access_denied"


def test_delivery_user_can_move_order_out_for_delivery_and_deliver(seeded, client, db: Session):
    wh_line = _ready_warehouse_line(client, seeded, db)
    order = _create_delivery_order(client, wh_line.id)
    token = _login(client, "sc_delivery_user")

    out = client.post(f"/api/v1/delivery-orders/{order['id']}/out-for-delivery", headers=_auth(token))
    assert out.status_code == 200, out.text
    assert out.json()["status"] == DeliveryOrderStatus.OUT_FOR_DELIVERY.value
    assert out.json()["lines"][0]["status"] == DeliveryOrderLineStatus.OUT_FOR_DELIVERY.value

    delivered = client.post(
        f"/api/v1/delivery-orders/{order['id']}/deliver",
        json={"receiver_name": "Branch Receiver", "delivery_note": "Delivered ok"},
        headers=_auth(token),
    )
    assert delivered.status_code == 200, delivered.text
    body = delivered.json()
    assert body["status"] == DeliveryOrderStatus.DELIVERED.value
    assert body["delivered_by"] == seeded["delivery_user"]
    assert body["lines"][0]["status"] == DeliveryOrderLineStatus.DELIVERED.value
    assert Decimal(body["lines"][0]["qty_delivered"]) == Decimal("5")


def test_delivery_updates_branch_stock_and_receipt_ledger(seeded, client, db: Session):
    wh_line = _ready_warehouse_line(client, seeded, db)
    source_line = wh_line.source_request_line
    request_id = wh_line.source_request_id
    order = _create_delivery_order(client, wh_line.id)
    token = _login(client, "sc_delivery_user")
    client.post(f"/api/v1/delivery-orders/{order['id']}/out-for-delivery", headers=_auth(token))
    delivered = client.post(f"/api/v1/delivery-orders/{order['id']}/deliver", json={}, headers=_auth(token))
    assert delivered.status_code == 200, delivered.text

    stock = db.query(BranchStock).filter(
        BranchStock.branch_id == seeded["branch_riyadh"],
        BranchStock.item_id == seeded["item_onda"],
    ).first()
    assert stock is not None
    assert stock.current_qty == Decimal("5")
    tx = db.query(StockTransaction).filter(
        StockTransaction.reference_no == f"DO-{order['id']}",
        StockTransaction.transaction_type == TransactionType.branch_receipt,
    ).first()
    assert tx is not None
    assert tx.destination_type == "branch"
    db.refresh(wh_line)
    db.refresh(source_line)
    request_row = db.query(BranchRequest).filter(BranchRequest.id == request_id).first()
    assert wh_line.status == WarehouseLineStatus.DELIVERED
    assert source_line.status == BranchRequestLineStatus.DELIVERED


def test_delivery_supports_partial_receipt_without_over_crediting_branch_stock(seeded, client, db: Session):
    wh_line = _ready_warehouse_line(client, seeded, db)
    order = _create_delivery_order(client, wh_line.id)
    token = _login(client, "sc_delivery_user")
    client.post(f"/api/v1/delivery-orders/{order['id']}/out-for-delivery", headers=_auth(token))
    delivered = client.post(
        f"/api/v1/delivery-orders/{order['id']}/deliver",
        json={
            "receiver_name": "Branch Receiver",
            "delivery_note": "Short received",
            "lines": [{"line_id": order["lines"][0]["id"], "qty_received": "3", "shortage_reason": "missing carton"}],
        },
        headers=_auth(token),
    )
    assert delivered.status_code == 200, delivered.text
    body = delivered.json()
    assert body["status"] == DeliveryOrderStatus.PARTIAL_DELIVERED.value
    assert body["lines"][0]["status"] == DeliveryOrderLineStatus.PARTIAL_DELIVERED.value
    assert Decimal(body["lines"][0]["qty_delivered"]) == Decimal("3")
    assert Decimal(body["lines"][0]["shortage_qty"]) == Decimal("2")

    stock = db.query(BranchStock).filter(
        BranchStock.branch_id == seeded["branch_riyadh"],
        BranchStock.item_id == seeded["item_onda"],
    ).first()
    assert stock.current_qty == Decimal("3")


def test_deliver_is_idempotent_and_does_not_double_increment_branch_stock(seeded, client, db: Session):
    wh_line = _ready_warehouse_line(client, seeded, db)
    order = _create_delivery_order(client, wh_line.id)
    token = _login(client, "sc_delivery_user")
    client.post(f"/api/v1/delivery-orders/{order['id']}/out-for-delivery", headers=_auth(token))
    headers = {**_auth(token), "X-Idempotency-Key": "deliver-repeat-1"}
    first = client.post(f"/api/v1/delivery-orders/{order['id']}/deliver", json={}, headers=headers)
    second = client.post(f"/api/v1/delivery-orders/{order['id']}/deliver", json={}, headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    stock = db.query(BranchStock).filter(
        BranchStock.branch_id == seeded["branch_riyadh"],
        BranchStock.item_id == seeded["item_onda"],
    ).first()
    assert stock.current_qty == Decimal("5")


def test_deliver_idempotency_key_after_prior_deliver_without_key_is_completed(seeded, client, db: Session):
    """Using X-Idempotency-Key on a no-op retry must not leave a stuck pending idempotency row."""
    wh_line = _ready_warehouse_line(client, seeded, db)
    order = _create_delivery_order(client, wh_line.id)
    token = _login(client, "sc_delivery_user")
    client.post(f"/api/v1/delivery-orders/{order['id']}/out-for-delivery", headers=_auth(token))
    assert client.post(f"/api/v1/delivery-orders/{order['id']}/deliver", json={}, headers=_auth(token)).status_code == 200
    key = "deliver-post-success-key-1"
    assert (
        client.post(
            f"/api/v1/delivery-orders/{order['id']}/deliver",
            json={},
            headers={**_auth(token), "X-Idempotency-Key": key},
        ).status_code
        == 200
    )
    row = (
        db.query(IdempotencyRequest)
        .filter(
            IdempotencyRequest.tenant_id == settings.DEFAULT_TENANT_ID,
            IdempotencyRequest.client_request_id == key,
            IdempotencyRequest.operation_name == "delivery_orders.deliver",
        )
        .first()
    )
    assert row is not None
    assert row.status == "completed"


def test_branch_request_audit_includes_old_and_new_values(seeded, client, db: Session, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")
    request_id = _create_and_submit(client, seeded)
    token = _login(client, "sc_area_onda")
    approved = client.post(
        f"/api/v1/branch-requests/{request_id}/approve",
        json={},
        headers={**_auth(token), "X-Idempotency-Key": "approve-audit-1"},
    )
    assert approved.status_code == 200, approved.text

    audit = db.query(AuditLog).filter(
        AuditLog.entity_type == "branch_request",
        AuditLog.entity_id == request_id,
        AuditLog.action == "request_approved",
    ).order_by(AuditLog.id.desc()).first()
    assert audit is not None
    assert audit.old_values is not None
    assert audit.new_values is not None


def test_procurement_supplier_and_purchase_request_skeleton(seeded, client, db: Session):
    token = _login(client, "sc_admin")
    supplier = client.post(
        "/api/v1/procurement/suppliers",
        json={"supplier_code": "SUP-001", "name": "Demo Supplier", "active": True},
        headers=_auth(token),
    )
    assert supplier.status_code == 201, supplier.text
    assert db.query(Supplier).filter(Supplier.supplier_code == "SUP-001").first() is not None

    pr = client.post(
        "/api/v1/procurement/purchase-requests",
        json={
            "warehouse_id": seeded["warehouse"],
            "notes": "Need more stock",
            "lines": [{"item_id": seeded["item_onda"], "qty_requested": "10"}],
        },
        headers=_auth(token),
    )
    assert pr.status_code == 201, pr.text
    body = pr.json()
    assert body["warehouse_id"] == seeded["warehouse"]
    assert body["status"] == PurchaseRequestStatus.DRAFT.value
    assert db.query(PurchaseRequest).count() >= 1


def test_delivery_labels_endpoint_returns_printable_content(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    section_token = _login(client, "sc_section_mgr")
    client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(section_token))
    client.post(f"/api/v1/production-orders/{po.id}/mark-ready", headers=_auth(section_token))
    client.post(f"/api/v1/production-orders/{po.id}/send-to-warehouse", headers=_auth(section_token))
    wh_line = db.query(WarehouseLine).filter(
        WarehouseLine.source_request_id == request_id,
        WarehouseLine.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT,
    ).first()
    wh_token = _login(client, "sc_wh_user")
    issued = client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers=_auth(wh_token))
    assert issued.status_code == 200, issued.text
    order = _create_delivery_order(client, wh_line.id)

    r = client.get(f"/api/v1/delivery-orders/{order['id']}/labels", headers=_auth(wh_token))
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers["content-type"]
    assert "Hot Kitchen" in r.text
    assert "Kitchen Item" in r.text


def test_supply_chain_dashboard_returns_expected_kpi_structure(seeded, client):
    _create_and_submit(client, seeded)
    token = _login(client, "sc_admin")
    r = client.get("/api/v1/supply-chain/dashboard", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"pending_approvals", "in_production", "warehouse_delays", "partial_orders", "top_requested_items"}
    assert body["pending_approvals"] >= 1
    assert isinstance(body["top_requested_items"], list)


def test_super_admin_overview_returns_phase_a_structure(seeded, client):
    _create_and_submit(client, seeded)
    token = _login(client, "sc_super_admin")
    r = client.get("/api/v1/supply-chain/super-admin-overview", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"generated_at", "summary", "alerts", "pipeline", "operations", "analytics", "data_health", "governance"}
    assert set(body["summary"].keys()) == {
        "total_requests_today",
        "pending_approvals",
        "in_production",
        "warehouse_pending",
        "out_for_delivery",
        "delivered",
        "delayed",
        "partial",
        "active_branches",
        "active_users",
    }
    assert isinstance(body["alerts"], list)
    assert isinstance(body["pipeline"], list)
    assert len(body["pipeline"]) == 6
    assert set(body["operations"].keys()) == {"branches", "area_managers", "kitchen", "warehouse", "delivery"}
    assert set(body["operations"]["branches"].keys()) == {"top_requesting", "delayed_branches"}
    assert set(body["operations"]["delivery"].keys()) == {"by_city", "top_branches"}
    assert set(body["analytics"].keys()) == {"performance", "top_items"}
    assert set(body["data_health"].keys()) == {
        "users_without_scope",
        "users_without_roles",
        "inactive_branch_users",
        "branches_without_brand_links",
        "items_without_brand_links",
        "kitchen_assignments_without_city",
        "branch_requestable_hidden_conflicts",
    }
    assert set(body["governance"].keys()) == {"role_distribution", "recent_audit"}
    assert body["summary"]["pending_approvals"] >= 1


def test_admin_global_access_to_delivery_order_for_other_warehouse(seeded, client, db: Session):
    other_line = _ready_other_warehouse_line(client, seeded, db)
    token = _login(client, "sc_admin")
    created = client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [other_line.id]},
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    fetched = client.get(f"/api/v1/delivery-orders/{created.json()['id']}", headers=_auth(token))
    assert fetched.status_code == 200, fetched.text


def test_legacy_replenishment_order_router_still_imports():
    from app.routers import orders as legacy_orders

    assert legacy_orders.router is not None


def test_api_v1_ready_reports_database_ok(client):
    r = client.get("/api/v1/ready")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "ready"
    assert body.get("database") == "ok"


def test_kitchen_never_dispatches_directly_to_branch(seeded, client, db: Session):
    payload = _create_payload(seeded, lines=[{"item_id": seeded["item_kitchen"], "qty_requested": "6"}])
    request_id = _create_submit_approve(client, seeded, payload)
    _split_request(client, request_id)
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    token = _login(client, "sc_section_mgr")
    client.post(f"/api/v1/production-orders/{po.id}/start", headers=_auth(token))
    client.post(f"/api/v1/production-orders/{po.id}/mark-ready", headers=_auth(token))
    sent = client.post(f"/api/v1/production-orders/{po.id}/send-to-warehouse", headers=_auth(token))
    assert sent.status_code == 200, sent.text
    assert db.query(BranchStock).filter(
        BranchStock.branch_id == seeded["branch_riyadh"],
        BranchStock.item_id == seeded["item_kitchen"],
    ).first() is None
