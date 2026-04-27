from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import AppError
from app.core.security import create_access_token, get_password_hash
from app.database import get_db
from app.main import app
from app.models import (
    Base,
    Branch,
    BranchStock,
    DailyInventory,
    DailyInventoryLine,
    InventoryStatus,
    Item,
    ItemCategory,
    OrderStatus,
    OrderType,
    ReplenishmentOrder,
    ReplenishmentOrderLine,
    Role,
    RoleName,
    UnitOfMeasure,
    User,
    UserRole,
    Warehouse,
    WarehouseStock,
)
from app.schemas import InventoryCreate, InventoryLineCreate
from app.services.inventory_service import create_or_update_inventory


SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _create_role(db, role_name: RoleName):
    role = Role(
        name=role_name,
        display_name=role_name.value,
        description=f"{role_name.value} role",
    )
    db.add(role)
    db.flush()
    return role


def _create_user(db, username: str, role_name: RoleName, branch_id=None, warehouse_id=None):
    role = db.query(Role).filter(Role.name == role_name).first() or _create_role(db, role_name)
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash("password123"),
        branch_id=branch_id,
        warehouse_id=warehouse_id,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(user: User):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _seed_base_entities(db):
    warehouse_1 = Warehouse(warehouse_code="WH1", warehouse_name="Warehouse 1", active=True)
    warehouse_2 = Warehouse(warehouse_code="WH2", warehouse_name="Warehouse 2", active=True)
    db.add_all([warehouse_1, warehouse_2])
    db.flush()

    branch_1 = Branch(
        branch_code="BR1",
        branch_name="Branch 1",
        warehouse_id=warehouse_1.id,
        active=True,
    )
    branch_2 = Branch(
        branch_code="BR2",
        branch_name="Branch 2",
        warehouse_id=warehouse_2.id,
        active=True,
    )
    db.add_all([branch_1, branch_2])
    db.flush()

    category = ItemCategory(code="CAT1", name_ar="تصنيف", name_en="Category", active=True)
    unit = UnitOfMeasure(code="PCS", name_ar="حبة", name_en="Piece", active=True)
    db.add_all([category, unit])
    db.flush()

    item = Item(
        item_code="ITEM1",
        item_name_ar="صنف 1",
        item_name_en="Item 1",
        category_id=category.id,
        unit_id=unit.id,
        min_qty=Decimal("5"),
        max_qty=Decimal("20"),
        reorder_point=Decimal("6"),
        safety_stock=Decimal("2"),
        active=True,
        branch_requestable=True,
    )
    db.add(item)
    db.commit()

    return {
        "warehouse_1": warehouse_1,
        "warehouse_2": warehouse_2,
        "branch_1": branch_1,
        "branch_2": branch_2,
        "item": item,
    }


def _seed_inventory(db, branch_id: int, item_id: int, status: InventoryStatus):
    inventory = DailyInventory(
        branch_id=branch_id,
        inventory_date=date(2026, 4, 14),
        status=status,
        created_by=1,
    )
    db.add(inventory)
    db.flush()
    line = DailyInventoryLine(
        inventory_id=inventory.id,
        item_id=item_id,
        book_qty=Decimal("5"),
        counted_qty=Decimal("4"),
        variance_qty=Decimal("-1"),
        variance_pct=Decimal("-20"),
        variance_status="warning",
    )
    db.add(line)
    db.commit()
    db.refresh(inventory)
    return inventory


def _seed_order(db, branch_id: int, warehouse_id: int, item_id: int, status: OrderStatus):
    order = ReplenishmentOrder(
        order_no=f"ORD-{branch_id}-{warehouse_id}",
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        order_type=OrderType.auto_replenishment,
        status=status,
        order_date=date(2026, 4, 14),
        created_by=1,
    )
    db.add(order)
    db.flush()
    line = ReplenishmentOrderLine(
        order_id=order.id,
        item_id=item_id,
        suggested_qty=Decimal("5"),
        branch_requested_qty=Decimal("5"),
        wh_approved_qty=Decimal("0"),
        line_status="pending",
    )
    db.add(line)
    db.commit()
    db.refresh(order)
    return order


def test_branch_user_cannot_access_other_branch_inventory(client):
    db = TestingSessionLocal()
    seeded = _seed_base_entities(db)
    user = _create_user(db, "branch.user", RoleName.branch_user, branch_id=seeded["branch_1"].id)
    inventory = _seed_inventory(db, seeded["branch_2"].id, seeded["item"].id, InventoryStatus.submitted)
    headers = _auth_headers(user)

    response = client.get(f"/api/v1/inventory/{inventory.id}", headers=headers)

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "inventory.access_denied"
    assert body["message"] == "Access denied for this inventory"
    assert body["detail"]["inventory_id"] == inventory.id
    db.close()


def test_branch_user_cannot_review_other_branch_order(client):
    db = TestingSessionLocal()
    seeded = _seed_base_entities(db)
    user = _create_user(db, "branch.user", RoleName.branch_user, branch_id=seeded["branch_1"].id)
    order = _seed_order(
        db,
        seeded["branch_2"].id,
        seeded["warehouse_2"].id,
        seeded["item"].id,
        OrderStatus.system_generated,
    )
    headers = _auth_headers(user)

    response = client.post(
        f"/api/v1/orders/{order.id}/branch-review",
        headers=headers,
        json={"lines": []},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "orders.branch_access_denied"
    assert body["message"] == "Access denied for this branch order"
    db.close()


def test_warehouse_user_cannot_access_other_warehouse_order(client):
    db = TestingSessionLocal()
    seeded = _seed_base_entities(db)
    user = _create_user(
        db,
        "warehouse.user",
        RoleName.warehouse_user,
        warehouse_id=seeded["warehouse_1"].id,
    )
    order = _seed_order(
        db,
        seeded["branch_2"].id,
        seeded["warehouse_2"].id,
        seeded["item"].id,
        OrderStatus.submitted_to_warehouse,
    )
    headers = _auth_headers(user)

    response = client.post(
        f"/api/v1/orders/{order.id}/warehouse-review",
        headers=headers,
        json={"lines": []},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "orders.warehouse_access_denied"
    assert body["message"] == "Access denied for this warehouse order"
    db.close()


def test_branch_dashboard_blocks_other_branch_access(client):
    db = TestingSessionLocal()
    seeded = _seed_base_entities(db)
    user = _create_user(db, "branch.manager", RoleName.branch_manager, branch_id=seeded["branch_1"].id)
    headers = _auth_headers(user)

    response = client.get(f"/api/v1/dashboard/branch/{seeded['branch_2'].id}", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied for this branch"
    db.close()


def test_duplicate_approved_inventory_returns_business_error():
    db = TestingSessionLocal()
    seeded = _seed_base_entities(db)
    user = _create_user(db, "admin.user", RoleName.admin)
    db.add(
        BranchStock(
            branch_id=seeded["branch_1"].id,
            item_id=seeded["item"].id,
            current_qty=Decimal("5"),
        )
    )
    db.commit()

    _seed_inventory(db, seeded["branch_1"].id, seeded["item"].id, InventoryStatus.approved)

    with pytest.raises(AppError) as exc_info:
        create_or_update_inventory(
            db,
            InventoryCreate(
                branch_id=seeded["branch_1"].id,
                inventory_date=date(2026, 4, 14),
                lines=[
                    InventoryLineCreate(
                        item_id=seeded["item"].id,
                        counted_qty=Decimal("5"),
                        variance_reason_id=None,
                        notes=None,
                    )
                ],
                notes=None,
            ),
            user,
        )

    assert exc_info.value.message == "Inventory already approved for this date"
    db.close()


def test_direct_warehouse_approval_sets_fully_approved_status(client):
    db = TestingSessionLocal()
    seeded = _seed_base_entities(db)
    user = _create_user(
        db,
        "warehouse.manager",
        RoleName.warehouse_manager,
        warehouse_id=seeded["warehouse_1"].id,
    )
    order = _seed_order(
        db,
        seeded["branch_1"].id,
        seeded["warehouse_1"].id,
        seeded["item"].id,
        OrderStatus.submitted_to_warehouse,
    )
    db.add(
        WarehouseStock(
            warehouse_id=seeded["warehouse_1"].id,
            item_id=seeded["item"].id,
            current_qty=Decimal("100"),
            reserved_qty=Decimal("0"),
        )
    )
    db.commit()
    headers = _auth_headers(user)

    response = client.post(f"/api/v1/orders/{order.id}/approve", headers=headers)

    assert response.status_code == 200
    db.refresh(order)
    assert order.status == OrderStatus.approved
    assert response.json()["message"] == "Order approved"
    db.close()


def test_global_exception_handler_hides_internal_details(client, monkeypatch):
    db = TestingSessionLocal()
    seeded = _seed_base_entities(db)
    user = _create_user(db, "branch.user", RoleName.branch_user, branch_id=seeded["branch_1"].id)
    headers = _auth_headers(user)

    from app.routers import inventory as inventory_router

    def boom(*args, **kwargs):
        raise RuntimeError("sensitive database details")

    monkeypatch.setattr(inventory_router.inventory_service, "get_inventory_list", boom)

    response = client.get("/api/v1/inventory/", headers=headers)

    assert response.status_code == 500
    body = response.json()
    assert body["message"] == "Internal server error"
    assert body.get("detail") is None
    assert "sensitive" not in response.text
    db.close()
