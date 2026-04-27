from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

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
    StockTransaction,
    TransactionType,
    UnitOfMeasure,
    User,
    UserRole,
    Warehouse,
    WarehouseStock,
)
from app.routers import inventory as inventory_router
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


def create_role(db, role_name: RoleName):
    role = Role(
        name=role_name,
        display_name=role_name.value,
        description=f"{role_name.value} role",
    )
    db.add(role)
    db.flush()
    return role


def create_user(db, username: str, role_name: RoleName, branch_id=None, warehouse_id=None):
    role = db.query(Role).filter(Role.name == role_name).first() or create_role(db, role_name)
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
    return user


def auth_headers(user: User):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def seed_base_entities(db):
    warehouse_1 = Warehouse(warehouse_code="WH1", warehouse_name="Warehouse 1", active=True)
    warehouse_2 = Warehouse(warehouse_code="WH2", warehouse_name="Warehouse 2", active=True)
    db.add_all([warehouse_1, warehouse_2])
    db.flush()

    branch_1 = Branch(branch_code="BR1", branch_name="Branch 1", warehouse_id=warehouse_1.id, active=True)
    branch_2 = Branch(branch_code="BR2", branch_name="Branch 2", warehouse_id=warehouse_2.id, active=True)
    db.add_all([branch_1, branch_2])
    db.flush()

    category = ItemCategory(code="CAT1", name_ar="Category AR", name_en="Category", active=True)
    unit = UnitOfMeasure(code="PCS", name_ar="Piece AR", name_en="Piece", active=True)
    db.add_all([category, unit])
    db.flush()

    item = Item(
        item_code="ITEM1",
        item_name_ar="Item AR",
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


def seed_inventory(db, branch_id: int, item_id: int, status: InventoryStatus, created_by: int):
    inventory = DailyInventory(
        branch_id=branch_id,
        inventory_date=date(2026, 4, 14),
        status=status,
        created_by=created_by,
    )
    db.add(inventory)
    db.flush()
    db.add(
        DailyInventoryLine(
            inventory_id=inventory.id,
            item_id=item_id,
            book_qty=Decimal("5"),
            counted_qty=Decimal("4"),
            variance_qty=Decimal("-1"),
            variance_pct=Decimal("-20"),
            variance_status="warning",
        )
    )
    db.commit()
    return inventory


def seed_order(db, branch_id: int, warehouse_id: int, item_id: int, status: OrderStatus, created_by: int):
    order = ReplenishmentOrder(
        order_no=f"ORD-{branch_id}-{warehouse_id}-{status.value}",
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        order_type=OrderType.auto_replenishment,
        status=status,
        order_date=date(2026, 4, 14),
        created_by=created_by,
    )
    db.add(order)
    db.flush()
    db.add(
        ReplenishmentOrderLine(
            order_id=order.id,
            item_id=item_id,
            suggested_qty=Decimal("5"),
            branch_requested_qty=Decimal("5"),
            wh_approved_qty=Decimal("0"),
            line_status="pending",
        )
    )
    db.commit()
    return order


def ensure_warehouse_stock(db, warehouse_id: int, item_id: int, qty: Decimal = Decimal("1000")):
    ws = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == warehouse_id,
            WarehouseStock.item_id == item_id,
        )
        .first()
    )
    if ws:
        ws.current_qty = qty
    else:
        db.add(
            WarehouseStock(
                warehouse_id=warehouse_id,
                item_id=item_id,
                current_qty=qty,
            )
        )
    db.commit()


class SecurityAndWorkflowFixesTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        self.client_manager = TestClient(app, raise_server_exceptions=False)
        self.client = self.client_manager.__enter__()

    def tearDown(self):
        self.client_manager.__exit__(None, None, None)
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_branch_user_cannot_access_other_branch_inventory(self):
        seeded = seed_base_entities(self.db)
        user = create_user(self.db, "branch.user", RoleName.branch_user, branch_id=seeded["branch_1"].id)
        inventory = seed_inventory(
            self.db,
            seeded["branch_2"].id,
            seeded["item"].id,
            InventoryStatus.submitted,
            created_by=user.id,
        )

        response = self.client.get(f"/api/v1/inventory/{inventory.id}", headers=auth_headers(user))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_code"], "inventory.access_denied")
        self.assertEqual(response.json()["message"], "Access denied for this inventory")
        self.assertEqual(response.json()["detail"]["inventory_id"], inventory.id)

    def test_branch_user_cannot_review_other_branch_order(self):
        seeded = seed_base_entities(self.db)
        user = create_user(self.db, "branch.user", RoleName.branch_user, branch_id=seeded["branch_1"].id)
        order = seed_order(
            self.db,
            seeded["branch_2"].id,
            seeded["warehouse_2"].id,
            seeded["item"].id,
            OrderStatus.system_generated,
            created_by=user.id,
        )

        response = self.client.post(
            f"/api/v1/orders/{order.id}/branch-review",
            headers=auth_headers(user),
            json={"lines": []},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_code"], "orders.branch_access_denied")
        self.assertEqual(response.json()["message"], "Access denied for this branch order")

    def test_warehouse_user_cannot_access_other_warehouse_order(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "warehouse.user",
            RoleName.warehouse_user,
            warehouse_id=seeded["warehouse_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_2"].id,
            seeded["warehouse_2"].id,
            seeded["item"].id,
            OrderStatus.submitted_to_warehouse,
            created_by=user.id,
        )

        response = self.client.post(
            f"/api/v1/orders/{order.id}/warehouse-review",
            headers=auth_headers(user),
            json={"lines": []},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error_code"], "orders.warehouse_access_denied")
        self.assertEqual(response.json()["message"], "Access denied for this warehouse order")

    def test_branch_dashboard_blocks_other_branch_access(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "branch.manager",
            RoleName.branch_manager,
            branch_id=seeded["branch_1"].id,
        )

        response = self.client.get(
            f"/api/v1/dashboard/branch/{seeded['branch_2'].id}",
            headers=auth_headers(user),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Access denied for this branch")

    def test_duplicate_approved_inventory_returns_business_error(self):
        seeded = seed_base_entities(self.db)
        user = create_user(self.db, "admin.user", RoleName.admin)
        self.db.add(
            BranchStock(
                branch_id=seeded["branch_1"].id,
                item_id=seeded["item"].id,
                current_qty=Decimal("5"),
            )
        )
        self.db.commit()
        seed_inventory(
            self.db,
            seeded["branch_1"].id,
            seeded["item"].id,
            InventoryStatus.approved,
            created_by=user.id,
        )

        with self.assertRaises(AppError) as ctx:
            create_or_update_inventory(
                self.db,
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

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error_code, "inventory.already_approved_for_date")
        self.assertEqual(ctx.exception.message, "Inventory already approved for this date")

    def test_direct_warehouse_approval_sets_fully_approved_status(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "warehouse.manager",
            RoleName.warehouse_manager,
            warehouse_id=seeded["warehouse_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.submitted_to_warehouse,
            created_by=user.id,
        )
        ensure_warehouse_stock(self.db, seeded["warehouse_1"].id, seeded["item"].id)

        response = self.client.post(f"/api/v1/orders/{order.id}/approve", headers=auth_headers(user))

        self.assertEqual(response.status_code, 200)
        self.db.refresh(order)
        self.assertEqual(order.status, OrderStatus.approved)
        self.assertEqual(response.json()["message"], "Order approved")

    def test_approve_replays_completed_idempotent_request(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "warehouse.manager",
            RoleName.warehouse_manager,
            warehouse_id=seeded["warehouse_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.submitted_to_warehouse,
            created_by=user.id,
        )
        ensure_warehouse_stock(self.db, seeded["warehouse_1"].id, seeded["item"].id)
        headers = auth_headers(user)
        headers["X-Client-Request-Id"] = "approve-order-001"

        first = self.client.post(f"/api/v1/orders/{order.id}/approve", headers=headers)
        second = self.client.post(f"/api/v1/orders/{order.id}/approve", headers=headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["_idempotency"]["replayed"], True)
        self.db.refresh(order)
        self.assertEqual(order.status, OrderStatus.approved)

    def test_start_picking_replays_completed_idempotent_request(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "warehouse.picker",
            RoleName.warehouse_user,
            warehouse_id=seeded["warehouse_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.approved,
            created_by=user.id,
        )
        headers = auth_headers(user)
        headers["X-Client-Request-Id"] = "start-picking-001"

        first = self.client.post(f"/api/v1/orders/{order.id}/start-picking", headers=headers)
        second = self.client.post(f"/api/v1/orders/{order.id}/start-picking", headers=headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["_idempotency"]["replayed"], True)
        self.db.refresh(order)
        self.assertEqual(order.status, OrderStatus.picking)

    def test_submit_to_warehouse_replays_completed_idempotent_request(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "branch.manager",
            RoleName.branch_manager,
            branch_id=seeded["branch_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.branch_reviewed,
            created_by=user.id,
        )
        headers = auth_headers(user)
        headers["X-Client-Request-Id"] = "submit-order-001"

        first = self.client.post(f"/api/v1/orders/{order.id}/submit-to-warehouse", headers=headers)
        second = self.client.post(f"/api/v1/orders/{order.id}/submit-to-warehouse", headers=headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["message"], "Order submitted to warehouse")
        self.assertEqual(second.json()["message"], "Order submitted to warehouse")
        self.assertEqual(second.json()["_idempotency"]["replayed"], True)
        self.db.refresh(order)
        self.assertEqual(order.status, OrderStatus.submitted_to_warehouse)

    def test_dispatch_replays_completed_idempotent_request_without_double_stock_effect(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "warehouse.dispatcher",
            RoleName.warehouse_user,
            warehouse_id=seeded["warehouse_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.picking,
            created_by=user.id,
        )
        line = self.db.query(ReplenishmentOrderLine).filter(ReplenishmentOrderLine.order_id == order.id).first()
        line.wh_approved_qty = Decimal("5")
        self.db.add(
            WarehouseStock(
                warehouse_id=seeded["warehouse_1"].id,
                item_id=seeded["item"].id,
                current_qty=Decimal("20"),
            )
        )
        self.db.commit()

        headers = auth_headers(user)
        headers["X-Client-Request-Id"] = "dispatch-order-001"
        payload = {
            "dispatch_note_no": "DN-TEST-001",
            "lines": [{"line_id": line.id, "dispatched_qty": 5}],
        }

        first = self.client.post(f"/api/v1/orders/{order.id}/dispatch", headers=headers, json=payload)
        second = self.client.post(f"/api/v1/orders/{order.id}/dispatch", headers=headers, json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["_idempotency"]["replayed"], True)

        self.db.refresh(order)
        wh_stock = self.db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == seeded["warehouse_1"].id,
            WarehouseStock.item_id == seeded["item"].id,
        ).first()
        branch_stock = self.db.query(BranchStock).filter(
            BranchStock.branch_id == seeded["branch_1"].id,
            BranchStock.item_id == seeded["item"].id,
        ).first()
        tx_count = self.db.query(StockTransaction).filter(
            StockTransaction.reference_no == order.order_no,
            StockTransaction.transaction_type == TransactionType.warehouse_dispatch,
        ).count()

        self.assertEqual(order.status, OrderStatus.dispatched)
        self.assertEqual(order.dispatch_note_no, "DN-TEST-001")
        self.assertEqual(wh_stock.current_qty, Decimal("15"))
        self.assertIsNotNone(branch_stock)
        self.assertEqual(branch_stock.in_transit_qty, Decimal("5"))
        self.assertEqual(tx_count, 1)

    def test_orders_error_model_uses_error_code_message_detail_shape(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "warehouse.dispatcher",
            RoleName.warehouse_user,
            warehouse_id=seeded["warehouse_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.approved,
            created_by=user.id,
        )

        response = self.client.post(f"/api/v1/orders/{order.id}/dispatch", headers=auth_headers(user), json={"lines": []})

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error_code"], "orders.invalid_dispatch_status")
        self.assertEqual(payload["message"], "Order is not in picking status")
        self.assertEqual(payload["detail"]["order_id"], order.id)
        self.assertEqual(payload["detail"]["status"], OrderStatus.approved.value)

    def test_reject_requires_reason_with_standard_error_model(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "warehouse.manager",
            RoleName.warehouse_manager,
            warehouse_id=seeded["warehouse_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.under_review,
            created_by=user.id,
        )

        response = self.client.post(
            f"/api/v1/orders/{order.id}/reject",
            headers=auth_headers(user),
            json={"reason": ""},
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error_code"], "orders.rejection_reason_required")
        self.assertEqual(payload["message"], "Rejection reason required")
        self.assertEqual(payload["detail"]["order_id"], order.id)

    def test_receive_replays_completed_idempotent_request_without_double_stock_effect(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "branch.receiver",
            RoleName.branch_user,
            branch_id=seeded["branch_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.dispatched,
            created_by=user.id,
        )
        line = self.db.query(ReplenishmentOrderLine).filter(ReplenishmentOrderLine.order_id == order.id).first()
        line.dispatched_qty = Decimal("5")
        line.line_status = "dispatched"
        self.db.add(
            BranchStock(
                branch_id=seeded["branch_1"].id,
                item_id=seeded["item"].id,
                current_qty=Decimal("3"),
                in_transit_qty=Decimal("5"),
            )
        )
        self.db.commit()

        headers = auth_headers(user)
        headers["X-Client-Request-Id"] = "receive-order-001"
        payload = {
            "lines": [{"line_id": line.id, "received_qty": 5, "damaged_qty": 0, "missing_qty": 0}],
        }

        first = self.client.post(f"/api/v1/orders/{order.id}/receive", headers=headers, json=payload)
        second = self.client.post(f"/api/v1/orders/{order.id}/receive", headers=headers, json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["_idempotency"]["replayed"], True)

        self.db.refresh(order)
        branch_stock = self.db.query(BranchStock).filter(
            BranchStock.branch_id == seeded["branch_1"].id,
            BranchStock.item_id == seeded["item"].id,
        ).first()
        tx_count = self.db.query(StockTransaction).filter(
            StockTransaction.reference_no == order.order_no,
            StockTransaction.transaction_type == TransactionType.branch_receipt,
        ).count()

        self.assertEqual(order.status, OrderStatus.closed)
        self.assertEqual(branch_stock.current_qty, Decimal("8"))
        self.assertEqual(branch_stock.in_transit_qty, Decimal("0"))
        self.assertEqual(tx_count, 1)

    def test_global_exception_handler_hides_internal_details(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "branch.safe",
            RoleName.branch_user,
            branch_id=seeded["branch_1"].id,
        )

        with patch.object(
            inventory_router.inventory_service,
            "get_inventory_list",
            side_effect=RuntimeError("sensitive database details"),
        ):
            response = self.client.get("/api/v1/inventory/", headers=auth_headers(user))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error_code"], "internal_server_error")
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIsNone(response.json()["detail"])
        self.assertNotIn("sensitive", response.text)

    def test_master_items_support_expanded_master_data_fields(self):
        seeded = seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master", RoleName.admin)

        create_response = self.client.post(
            "/api/v1/master/items",
            headers=auth_headers(admin),
            json={
                "item_code": "ITEM2",
                "item_name_ar": "حليب كامل",
                "item_name_en": "Full Milk",
                "category_id": seeded["item"].category_id,
                "unit_id": seeded["item"].unit_id,
                "item_type": "raw_material",
                "storage_type": "chilled",
                "purchase_unit_id": seeded["item"].unit_id,
                "supply_unit_id": seeded["item"].unit_id,
                "conversion_ratio": "12",
                "branch_requestable": True,
                "active": True,
                "min_qty": "2",
                "max_qty": "20",
                "reorder_point": "4",
                "safety_stock": "1",
                "lead_time_days": 3,
                "shelf_life_days": 7,
                "average_consumption_mode": "last_14_days",
                "critical_item": True,
            },
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["item_type"], "raw_material")
        self.assertEqual(created["storage_type"], "chilled")
        self.assertEqual(created["purchase_unit_id"], seeded["item"].unit_id)
        self.assertEqual(created["supply_unit_id"], seeded["item"].unit_id)
        self.assertEqual(Decimal(str(created["conversion_ratio"])), Decimal("12"))
        self.assertEqual(created["shelf_life_days"], 7)

        update_response = self.client.put(
            f"/api/v1/master/items/{created['id']}",
            headers=auth_headers(admin),
            json={
                "item_type": "consumable",
                "storage_type": "ambient",
                "conversion_ratio": "6.5",
                "shelf_life_days": 30,
            },
        )

        self.assertEqual(update_response.status_code, 200)
        updated = update_response.json()
        self.assertEqual(updated["item_type"], "consumable")
        self.assertEqual(updated["storage_type"], "ambient")
        self.assertEqual(Decimal(str(updated["conversion_ratio"])), Decimal("6.5"))
        self.assertEqual(updated["shelf_life_days"], 30)

        get_response = self.client.get(
            f"/api/v1/master/items/{created['id']}",
            headers=auth_headers(admin),
        )
        self.assertEqual(get_response.status_code, 200)
        fetched = get_response.json()
        self.assertEqual(fetched["purchase_unit"]["id"], seeded["item"].unit_id)
        self.assertEqual(fetched["supply_unit"]["id"], seeded["item"].unit_id)

        list_response = self.client.get(
            "/api/v1/master/items",
            headers=auth_headers(admin),
            params={"search": "ITEM2"},
        )
        self.assertEqual(list_response.status_code, 200)
        listing = list_response.json()
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["items"][0]["purchase_unit"]["id"], seeded["item"].unit_id)

    def test_master_item_requires_purchase_and_supply_units_together(self):
        seeded = seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.units", RoleName.admin)

        response = self.client.post(
            "/api/v1/master/items",
            headers=auth_headers(admin),
            json={
                "item_code": "ITEM3",
                "item_name_ar": "كوب",
                "item_name_en": "Cup",
                "category_id": seeded["item"].category_id,
                "unit_id": seeded["item"].unit_id,
                "purchase_unit_id": seeded["item"].unit_id,
                "conversion_ratio": "24",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("purchase_unit_id and supply_unit_id must be provided together", response.text)

    def test_master_item_rejects_non_positive_conversion_ratio(self):
        seeded = seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.ratio", RoleName.admin)

        response = self.client.post(
            "/api/v1/master/items",
            headers=auth_headers(admin),
            json={
                "item_code": "ITEM4",
                "item_name_ar": "سكر",
                "item_name_en": "Sugar",
                "category_id": seeded["item"].category_id,
                "unit_id": seeded["item"].unit_id,
                "purchase_unit_id": seeded["item"].unit_id,
                "supply_unit_id": seeded["item"].unit_id,
                "conversion_ratio": "0",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("conversion_ratio must be greater than zero", response.text)

    def test_master_item_duplicate_code_uses_standard_error_model(self):
        seeded = seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.dup", RoleName.admin)

        response = self.client.post(
            "/api/v1/master/items",
            headers=auth_headers(admin),
            json={
                "item_code": seeded["item"].item_code,
                "item_name_ar": "مكرر",
                "item_name_en": "Duplicate",
                "category_id": seeded["item"].category_id,
                "unit_id": seeded["item"].unit_id,
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error_code"], "master.item_code_exists")
        self.assertEqual(payload["message"], "Item code already exists")
        self.assertEqual(payload["detail"]["item_code"], seeded["item"].item_code)

    def test_master_item_not_found_uses_standard_error_model(self):
        seeded = seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.missing", RoleName.admin)

        response = self.client.get(
            "/api/v1/master/items/99999",
            headers=auth_headers(admin),
        )

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["error_code"], "master.item_not_found")
        self.assertEqual(payload["message"], "Item not found")
        self.assertEqual(payload["detail"]["item_id"], 99999)

    def test_master_item_missing_category_uses_standard_error_model(self):
        seeded = seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.badcat", RoleName.admin)

        response = self.client.post(
            "/api/v1/master/items",
            headers=auth_headers(admin),
            json={
                "item_code": "ITEM_BAD_CAT",
                "item_name_ar": "خطأ تصنيف",
                "item_name_en": "Bad Category",
                "category_id": 99999,
                "unit_id": seeded["item"].unit_id,
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error_code"], "master.category_not_found")
        self.assertEqual(payload["message"], "Category not found")
        self.assertEqual(payload["detail"]["category_id"], 99999)

    def test_master_item_missing_unit_uses_standard_error_model(self):
        seeded = seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.badunit", RoleName.admin)

        response = self.client.post(
            "/api/v1/master/items",
            headers=auth_headers(admin),
            json={
                "item_code": "ITEM_BAD_UNIT",
                "item_name_ar": "خطأ وحدة",
                "item_name_en": "Bad Unit",
                "category_id": seeded["item"].category_id,
                "unit_id": 99999,
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error_code"], "master.unit_not_found")
        self.assertEqual(payload["message"], "unit_id not found")
        self.assertEqual(payload["detail"]["field"], "unit_id")
        self.assertEqual(payload["detail"]["unit_id"], 99999)

    def test_master_item_stock_card_returns_ledger_transactions(self):
        seeded = seed_base_entities(self.db)
        warehouse_user = create_user(
            self.db,
            "warehouse.stockcard",
            RoleName.warehouse_user,
            warehouse_id=seeded["warehouse_1"].id,
        )
        branch_user = create_user(
            self.db,
            "branch.stockcard",
            RoleName.branch_user,
            branch_id=seeded["branch_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.picking,
            created_by=warehouse_user.id,
        )
        line = self.db.query(ReplenishmentOrderLine).filter(ReplenishmentOrderLine.order_id == order.id).first()
        line.wh_approved_qty = Decimal("5")
        self.db.add(
            WarehouseStock(
                warehouse_id=seeded["warehouse_1"].id,
                item_id=seeded["item"].id,
                current_qty=Decimal("20"),
            )
        )
        self.db.commit()

        dispatch_headers = auth_headers(warehouse_user)
        dispatch_headers["X-Client-Request-Id"] = "stock-card-dispatch-001"
        dispatch_response = self.client.post(
            f"/api/v1/orders/{order.id}/dispatch",
            headers=dispatch_headers,
            json={
                "dispatch_note_no": "DN-STOCK-CARD-001",
                "lines": [{"line_id": line.id, "dispatched_qty": 5}],
            },
        )
        self.assertEqual(dispatch_response.status_code, 200)

        receive_headers = auth_headers(branch_user)
        receive_headers["X-Client-Request-Id"] = "stock-card-receive-001"
        receive_response = self.client.post(
            f"/api/v1/orders/{order.id}/receive",
            headers=receive_headers,
            json={"lines": [{"line_id": line.id, "received_qty": 5, "damaged_qty": 0, "missing_qty": 0}]},
        )
        self.assertEqual(receive_response.status_code, 200)

        response = self.client.get(
            f"/api/v1/master/items/{seeded['item'].id}/stock-card",
            headers=auth_headers(warehouse_user),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["item_id"], seeded["item"].id)
        self.assertEqual(payload["item_code"], seeded["item"].item_code)
        self.assertEqual(len(payload["transactions"]), 2)
        transaction_types = {row["transaction_type"] for row in payload["transactions"]}
        self.assertEqual(
            transaction_types,
            {
                TransactionType.warehouse_dispatch.value,
                TransactionType.branch_receipt.value,
            },
        )
        self.assertTrue(all(row["reference_no"] == order.order_no for row in payload["transactions"]))

    def test_master_item_stock_card_not_found_uses_standard_error_model(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "warehouse.stockcard.missing",
            RoleName.warehouse_user,
            warehouse_id=seeded["warehouse_1"].id,
        )

        response = self.client.get(
            "/api/v1/master/items/99999/stock-card",
            headers=auth_headers(user),
        )

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["error_code"], "ledger.item_not_found")
        self.assertEqual(payload["message"], "Item not found")
        self.assertEqual(payload["detail"]["item_id"], 99999)

    def test_master_item_stock_card_supports_transaction_type_filter(self):
        seeded = seed_base_entities(self.db)
        warehouse_user = create_user(
            self.db,
            "warehouse.stockcard.filter",
            RoleName.warehouse_user,
            warehouse_id=seeded["warehouse_1"].id,
        )
        branch_user = create_user(
            self.db,
            "branch.stockcard.filter",
            RoleName.branch_user,
            branch_id=seeded["branch_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.picking,
            created_by=warehouse_user.id,
        )
        line = self.db.query(ReplenishmentOrderLine).filter(ReplenishmentOrderLine.order_id == order.id).first()
        line.wh_approved_qty = Decimal("5")
        self.db.add(
            WarehouseStock(
                warehouse_id=seeded["warehouse_1"].id,
                item_id=seeded["item"].id,
                current_qty=Decimal("20"),
            )
        )
        self.db.commit()

        self.client.post(
            f"/api/v1/orders/{order.id}/dispatch",
            headers={**auth_headers(warehouse_user), "X-Client-Request-Id": "stock-card-filter-dispatch-001"},
            json={"dispatch_note_no": "DN-STOCK-CARD-FILTER", "lines": [{"line_id": line.id, "dispatched_qty": 5}]},
        )
        self.client.post(
            f"/api/v1/orders/{order.id}/receive",
            headers={**auth_headers(branch_user), "X-Client-Request-Id": "stock-card-filter-receive-001"},
            json={"lines": [{"line_id": line.id, "received_qty": 5, "damaged_qty": 0, "missing_qty": 0}]},
        )

        response = self.client.get(
            f"/api/v1/master/items/{seeded['item'].id}/stock-card",
            headers=auth_headers(warehouse_user),
            params={"transaction_type": TransactionType.warehouse_dispatch.value},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["transactions"]), 1)
        self.assertEqual(
            payload["transactions"][0]["transaction_type"],
            TransactionType.warehouse_dispatch.value,
        )

    def test_master_item_stock_card_rejects_invalid_transaction_type_filter(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "warehouse.stockcard.invalidfilter",
            RoleName.warehouse_user,
            warehouse_id=seeded["warehouse_1"].id,
        )

        response = self.client.get(
            f"/api/v1/master/items/{seeded['item'].id}/stock-card",
            headers=auth_headers(user),
            params={"transaction_type": "not-a-real-transaction"},
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error_code"], "ledger.invalid_transaction_type_filter")
        self.assertEqual(payload["message"], "Invalid transaction_type filter")
        self.assertEqual(payload["detail"]["transaction_type"], "not-a-real-transaction")

    def test_master_item_stock_card_supports_reference_filter(self):
        seeded = seed_base_entities(self.db)
        warehouse_user = create_user(
            self.db,
            "warehouse.stockcard.reference",
            RoleName.warehouse_user,
            warehouse_id=seeded["warehouse_1"].id,
        )
        branch_user = create_user(
            self.db,
            "branch.stockcard.reference",
            RoleName.branch_user,
            branch_id=seeded["branch_1"].id,
        )
        order = seed_order(
            self.db,
            seeded["branch_1"].id,
            seeded["warehouse_1"].id,
            seeded["item"].id,
            OrderStatus.picking,
            created_by=warehouse_user.id,
        )
        line = self.db.query(ReplenishmentOrderLine).filter(ReplenishmentOrderLine.order_id == order.id).first()
        line.wh_approved_qty = Decimal("5")
        self.db.add(
            WarehouseStock(
                warehouse_id=seeded["warehouse_1"].id,
                item_id=seeded["item"].id,
                current_qty=Decimal("20"),
            )
        )
        self.db.commit()

        self.client.post(
            f"/api/v1/orders/{order.id}/dispatch",
            headers={**auth_headers(warehouse_user), "X-Client-Request-Id": "stock-card-reference-dispatch-001"},
            json={"dispatch_note_no": "DN-STOCK-CARD-REF", "lines": [{"line_id": line.id, "dispatched_qty": 5}]},
        )
        self.client.post(
            f"/api/v1/orders/{order.id}/receive",
            headers={**auth_headers(branch_user), "X-Client-Request-Id": "stock-card-reference-receive-001"},
            json={"lines": [{"line_id": line.id, "received_qty": 5, "damaged_qty": 0, "missing_qty": 0}]},
        )

        response = self.client.get(
            f"/api/v1/master/items/{seeded['item'].id}/stock-card",
            headers=auth_headers(warehouse_user),
            params={"reference_no": order.order_no},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["transactions"]), 2)
        self.assertTrue(all(row["reference_no"] == order.order_no for row in payload["transactions"]))

    def test_master_category_create_list_and_duplicate_error_model(self):
        seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.category", RoleName.admin)

        create_response = self.client.post(
            "/api/v1/master/categories",
            headers=auth_headers(admin),
            json={"code": "CAT2", "name_ar": "مشروبات", "name_en": "Beverages", "active": True},
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["code"], "CAT2")

        list_response = self.client.get("/api/v1/master/categories", headers=auth_headers(admin))
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(any(item["code"] == "CAT2" for item in list_response.json()))

        duplicate_response = self.client.post(
            "/api/v1/master/categories",
            headers=auth_headers(admin),
            json={"code": "CAT2", "name_ar": "مكرر", "name_en": "Duplicate", "active": True},
        )
        self.assertEqual(duplicate_response.status_code, 400)
        payload = duplicate_response.json()
        self.assertEqual(payload["error_code"], "master.category_code_exists")
        self.assertEqual(payload["message"], "Category code exists")
        self.assertEqual(payload["detail"]["code"], "CAT2")

    def test_master_unit_create_list_and_duplicate_error_model(self):
        seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.unit", RoleName.admin)

        create_response = self.client.post(
            "/api/v1/master/units",
            headers=auth_headers(admin),
            json={"code": "BOX", "name_ar": "صندوق", "name_en": "Box", "active": True},
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["code"], "BOX")

        list_response = self.client.get("/api/v1/master/units", headers=auth_headers(admin))
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(any(item["code"] == "BOX" for item in list_response.json()))

        duplicate_response = self.client.post(
            "/api/v1/master/units",
            headers=auth_headers(admin),
            json={"code": "BOX", "name_ar": "مكرر", "name_en": "Duplicate", "active": True},
        )
        self.assertEqual(duplicate_response.status_code, 400)
        payload = duplicate_response.json()
        self.assertEqual(payload["error_code"], "master.unit_code_exists")
        self.assertEqual(payload["message"], "Unit code exists")
        self.assertEqual(payload["detail"]["code"], "BOX")

    def test_master_warehouse_duplicate_and_not_found_error_model(self):
        seeded = seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.warehouse", RoleName.admin)

        duplicate_response = self.client.post(
            "/api/v1/master/warehouses",
            headers=auth_headers(admin),
            json={
                "warehouse_code": seeded["warehouse_1"].warehouse_code,
                "warehouse_name": "Duplicate Warehouse",
                "location": "Riyadh",
                "active": True,
            },
        )
        self.assertEqual(duplicate_response.status_code, 400)
        duplicate_payload = duplicate_response.json()
        self.assertEqual(duplicate_payload["error_code"], "master.warehouse_code_exists")
        self.assertEqual(duplicate_payload["message"], "Warehouse code already exists")

        missing_response = self.client.put(
            "/api/v1/master/warehouses/99999",
            headers=auth_headers(admin),
            json={"warehouse_name": "Missing"},
        )
        self.assertEqual(missing_response.status_code, 404)
        missing_payload = missing_response.json()
        self.assertEqual(missing_payload["error_code"], "master.warehouse_not_found")
        self.assertEqual(missing_payload["message"], "Warehouse not found")
        self.assertEqual(missing_payload["detail"]["warehouse_id"], 99999)

    def test_master_branch_duplicate_missing_branch_and_missing_warehouse_error_model(self):
        seeded = seed_base_entities(self.db)
        admin = create_user(self.db, "admin.master.branch", RoleName.admin)

        duplicate_response = self.client.post(
            "/api/v1/master/branches",
            headers=auth_headers(admin),
            json={
                "branch_code": seeded["branch_1"].branch_code,
                "branch_name": "Duplicate Branch",
                "city": "Riyadh",
                "area": "Center",
                "warehouse_id": seeded["warehouse_1"].id,
                "active": True,
            },
        )
        self.assertEqual(duplicate_response.status_code, 400)
        duplicate_payload = duplicate_response.json()
        self.assertEqual(duplicate_payload["error_code"], "master.branch_code_exists")
        self.assertEqual(duplicate_payload["message"], "Branch code already exists")

        missing_warehouse_response = self.client.post(
            "/api/v1/master/branches",
            headers=auth_headers(admin),
            json={
                "branch_code": "BRX",
                "branch_name": "Branch X",
                "city": "Riyadh",
                "area": "North",
                "warehouse_id": 99999,
                "active": True,
            },
        )
        self.assertEqual(missing_warehouse_response.status_code, 400)
        missing_wh_payload = missing_warehouse_response.json()
        self.assertEqual(missing_wh_payload["error_code"], "master.warehouse_not_found")
        self.assertEqual(missing_wh_payload["message"], "Warehouse not found")

        missing_branch_response = self.client.put(
            "/api/v1/master/branches/99999",
            headers=auth_headers(admin),
            json={"branch_name": "Missing"},
        )
        self.assertEqual(missing_branch_response.status_code, 404)
        missing_branch_payload = missing_branch_response.json()
        self.assertEqual(missing_branch_payload["error_code"], "master.branch_not_found")
        self.assertEqual(missing_branch_payload["message"], "Branch not found")
        self.assertEqual(missing_branch_payload["detail"]["branch_id"], 99999)

    def test_inventory_reject_requires_reason_with_standard_error_model(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "branch.manager.inv",
            RoleName.branch_manager,
            branch_id=seeded["branch_1"].id,
        )
        inventory = seed_inventory(
            self.db,
            seeded["branch_1"].id,
            seeded["item"].id,
            InventoryStatus.submitted,
            created_by=user.id,
        )

        response = self.client.post(
            f"/api/v1/inventory/{inventory.id}/reject",
            headers=auth_headers(user),
            json={"reason": ""},
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error_code"], "inventory.rejection_reason_required")
        self.assertEqual(payload["message"], "Rejection reason is required")
        self.assertEqual(payload["detail"]["inventory_id"], inventory.id)

    def test_inventory_approve_replays_completed_idempotent_request_without_double_stock_effect(self):
        seeded = seed_base_entities(self.db)
        user = create_user(
            self.db,
            "branch.manager.approve",
            RoleName.branch_manager,
            branch_id=seeded["branch_1"].id,
        )
        inventory = seed_inventory(
            self.db,
            seeded["branch_1"].id,
            seeded["item"].id,
            InventoryStatus.submitted,
            created_by=user.id,
        )
        self.db.add(
            BranchStock(
                branch_id=seeded["branch_1"].id,
                item_id=seeded["item"].id,
                current_qty=Decimal("5"),
            )
        )
        self.db.commit()

        headers = auth_headers(user)
        headers["X-Client-Request-Id"] = "approve-inventory-001"

        with patch(
            "app.services.inventory_service.replenishment_service.generate_replenishment_order",
            return_value=None,
        ):
            first = self.client.post(f"/api/v1/inventory/{inventory.id}/approve", headers=headers)
            second = self.client.post(f"/api/v1/inventory/{inventory.id}/approve", headers=headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["_idempotency"]["replayed"], True)

        self.db.refresh(inventory)
        stock = self.db.query(BranchStock).filter(
            BranchStock.branch_id == seeded["branch_1"].id,
            BranchStock.item_id == seeded["item"].id,
        ).first()
        tx_count = self.db.query(StockTransaction).filter(
            StockTransaction.reference_no == f"INV-{inventory.id}",
            StockTransaction.transaction_type == TransactionType.inventory_adjustment,
        ).count()

        self.assertEqual(inventory.status, InventoryStatus.approved)
        self.assertEqual(stock.current_qty, Decimal("4"))
        self.assertEqual(tx_count, 1)


if __name__ == "__main__":
    unittest.main()
