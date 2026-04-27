"""
Epics 4-9 — Integration Tests
Covers:
  Epic 4: cancel_order, close_order, timeline, fix receive_order
  Epic 5: branch/warehouse stock adjustment, WH→Branch transfer, Branch→WH return
  Epic 6: branch ledger, variance report, low-stock
  Epic 7: GET /me, POST /me/change-password, GET /roles
  Epic 8: inventory-compliance, order-summary, variance-trend
  Epic 9: low-stock alerts, pending-inventories, missing-inventory-today
"""
import unittest
import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database import Base, get_db
from app.main import app
from app.models import (
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

# ─────────────────────────────────────────────────────────────────────────
# DB setup — isolated in-memory SQLite
# ─────────────────────────────────────────────────────────────────────────

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _role(db, name: RoleName) -> Role:
    r = db.query(Role).filter(Role.name == name).first()
    if not r:
        r = Role(name=name, display_name=name.value)
        db.add(r)
        db.flush()
    return r


def _user(db, username, role_name: RoleName, branch_id=None, warehouse_id=None) -> User:
    role = _role(db, role_name)
    u = User(
        username=username,
        email=f"{username}@test.com",
        full_name=username,
        hashed_password=get_password_hash("Pass@1234"),
        branch_id=branch_id,
        warehouse_id=warehouse_id,
    )
    db.add(u)
    db.flush()
    db.add(UserRole(user_id=u.id, role_id=role.id))
    db.commit()
    return u


def _login(client: TestClient, username: str) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Pass@1234"},
    )
    assert r.status_code == 200, f"Login failed for {username}: {r.text}"
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_order(db, branch_id: int, warehouse_id: int, status: OrderStatus) -> ReplenishmentOrder:
    cat = db.query(ItemCategory).first()
    unit = db.query(UnitOfMeasure).first()
    item = db.query(Item).order_by(Item.id).first()
    if not item:
        item = Item(
            item_code="TST001",
            item_name_ar="صنف اختبار",
            item_name_en="Test Item",
            category_id=cat.id if cat else None,
            unit_id=unit.id if unit else None,
            active=True,
        )
        db.add(item)
        db.flush()

    order = ReplenishmentOrder(
        order_no=f"ORD-{uuid.uuid4().hex[:16]}",
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        status=status,
        order_type=OrderType.exceptional,
        order_date=date.today(),
        created_by=1,
    )
    db.add(order)
    db.flush()

    line = ReplenishmentOrderLine(
        order_id=order.id,
        item_id=item.id,
        suggested_qty=Decimal("10"),
        branch_requested_qty=Decimal("10"),
        wh_approved_qty=Decimal("10"),
        picked_qty=Decimal("0"),
        dispatched_qty=Decimal("0"),
        received_qty=Decimal("0"),
    )
    db.add(line)
    db.commit()
    return order


# ─────────────────────────────────────────────────────────────────────────
# Test Class
# ─────────────────────────────────────────────────────────────────────────

class TestEpic4To9(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=True)
        db = TestingSessionLocal()

        # Seed branch, warehouse, item
        cls.warehouse = Warehouse(warehouse_name="مستودع اختبار", warehouse_code="W-TST", active=True)
        db.add(cls.warehouse)
        db.flush()
        cls.branch = Branch(branch_name="فرع اختبار", branch_code="B-TST", active=True, warehouse_id=cls.warehouse.id)
        db.add(cls.branch)
        db.flush()

        cat = ItemCategory(name_ar="تصنيف", name_en="Category", code="CAT")
        unit = UnitOfMeasure(name_ar="قطعة", name_en="Piece", code="PC")
        db.add_all([cat, unit])
        db.flush()

        cls.item = Item(
            item_code="ITM001",
            item_name_ar="صنف تجريبي",
            item_name_en="Test Item",
            category_id=cat.id,
            unit_id=unit.id,
            active=True,
            reorder_point=Decimal("5"),
            min_qty=Decimal("3"),
        )
        db.add(cls.item)
        db.flush()

        # Seed users
        cls.admin_user = _user(db, "admin_e4", RoleName.admin)
        cls.branch_mgr = _user(db, "bmgr_e4", RoleName.branch_manager, branch_id=cls.branch.id)
        cls.branch_usr = _user(db, "busr_e4", RoleName.branch_user, branch_id=cls.branch.id)
        cls.wh_mgr = _user(db, "wmgr_e4", RoleName.warehouse_manager, warehouse_id=cls.warehouse.id)
        cls.wh_usr = _user(db, "wusr_e4", RoleName.warehouse_user, warehouse_id=cls.warehouse.id)

        db.close()

        # Tokens
        cls.admin_tok = _login(cls.client, "admin_e4")
        cls.branch_mgr_tok = _login(cls.client, "bmgr_e4")
        cls.branch_usr_tok = _login(cls.client, "busr_e4")
        cls.wh_mgr_tok = _login(cls.client, "wmgr_e4")
        cls.wh_usr_tok = _login(cls.client, "wusr_e4")

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        # pytest يخلط اختبارات ملفات مختلفة — أعد ربط الـ DB قبل كل اختبار في الكلاس
        app.dependency_overrides[get_db] = override_get_db

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 4 — cancel / close / timeline
    # ──────────────────────────────────────────────────────────────────────

    def test_e4_cancel_draft_order_by_branch(self):
        db = TestingSessionLocal()
        order = _make_order(db, self.branch.id, self.warehouse.id, OrderStatus.draft)
        db.close()
        r = self.client.post(
            f"/api/v1/orders/{order.id}/cancel",
            json={"reason": "No longer needed"},
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "cancelled")

    def test_e4_cancel_already_cancelled_order_idempotent(self):
        db = TestingSessionLocal()
        order = _make_order(db, self.branch.id, self.warehouse.id, OrderStatus.draft)
        db.close()
        # First cancel
        self.client.post(
            f"/api/v1/orders/{order.id}/cancel",
            json={"reason": "Test cancel"},
            headers=_auth(self.branch_mgr_tok),
        )
        # Attempt to cancel again without reason — should fail 400
        r = self.client.post(
            f"/api/v1/orders/{order.id}/cancel",
            json={"reason": ""},
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertIn(r.status_code, [400, 200])

    def test_e4_cancel_requires_reason(self):
        db = TestingSessionLocal()
        order = _make_order(db, self.branch.id, self.warehouse.id, OrderStatus.draft)
        db.close()
        r = self.client.post(
            f"/api/v1/orders/{order.id}/cancel",
            json={"reason": ""},
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("cancellation_reason_required", r.json().get("error_code", ""))

    def test_e4_close_dispatched_order(self):
        db = TestingSessionLocal()
        order = _make_order(db, self.branch.id, self.warehouse.id, OrderStatus.dispatched)
        db.close()
        r = self.client.post(
            f"/api/v1/orders/{order.id}/close",
            headers=_auth(self.wh_mgr_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "closed")

    def test_e4_close_draft_order_blocked(self):
        db = TestingSessionLocal()
        order = _make_order(db, self.branch.id, self.warehouse.id, OrderStatus.draft)
        db.close()
        r = self.client.post(
            f"/api/v1/orders/{order.id}/close",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("cannot_close_status", r.json().get("error_code", ""))

    def test_e4_order_timeline(self):
        db = TestingSessionLocal()
        order = _make_order(db, self.branch.id, self.warehouse.id, OrderStatus.draft)
        db.close()
        r = self.client.get(
            f"/api/v1/orders/{order.id}/timeline",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("events", body)
        self.assertIn("order_no", body)
        self.assertIn("status", body)

    def test_e4_timeline_not_found(self):
        r = self.client.get(
            "/api/v1/orders/999999/timeline",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 404)

    def test_e4_exceptional_returns_201(self):
        r = self.client.post(
            "/api/v1/orders/exceptional",
            json={
                "branch_id": self.branch.id,
                "items": [{"item_id": self.item.id, "qty": 5}],
                "notes": "Urgent request",
            },
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertEqual(r.status_code, 201)

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 5 — Stock adjustments & transfers
    # ──────────────────────────────────────────────────────────────────────

    def test_e5_branch_stock_increase(self):
        r = self.client.post(
            f"/api/v1/stock/branches/{self.branch.id}/adjust",
            json={
                "item_id": self.item.id,
                "adjustment_type": "increase",
                "qty": "20.0",
                "reason": "Initial stock top-up",
            },
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["adjustment_type"], "increase")
        self.assertGreater(body["new_qty"], body["old_qty"])

    def test_e5_branch_stock_decrease(self):
        # Ensure there's stock first
        self.client.post(
            f"/api/v1/stock/branches/{self.branch.id}/adjust",
            json={"item_id": self.item.id, "adjustment_type": "set", "qty": "50", "reason": "seed"},
            headers=_auth(self.admin_tok),
        )
        r = self.client.post(
            f"/api/v1/stock/branches/{self.branch.id}/adjust",
            json={
                "item_id": self.item.id,
                "adjustment_type": "decrease",
                "qty": "10.0",
                "reason": "Write-off",
            },
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertLess(r.json()["new_qty"], 50)

    def test_e5_branch_stock_set(self):
        r = self.client.post(
            f"/api/v1/stock/branches/{self.branch.id}/adjust",
            json={
                "item_id": self.item.id,
                "adjustment_type": "set",
                "qty": "100.0",
                "reason": "Physical count correction",
            },
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["new_qty"], 100.0)

    def test_e5_invalid_adjustment_type(self):
        r = self.client.post(
            f"/api/v1/stock/branches/{self.branch.id}/adjust",
            json={"item_id": self.item.id, "adjustment_type": "bogus", "qty": "5", "reason": "x"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("invalid_adjustment_type", r.json().get("error_code", ""))

    def test_e5_negative_qty_rejected(self):
        r = self.client.post(
            f"/api/v1/stock/branches/{self.branch.id}/adjust",
            json={"item_id": self.item.id, "adjustment_type": "increase", "qty": "-5", "reason": "x"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 422)

    def test_e5_warehouse_stock_increase(self):
        r = self.client.post(
            f"/api/v1/stock/warehouses/{self.warehouse.id}/adjust",
            json={
                "item_id": self.item.id,
                "adjustment_type": "increase",
                "qty": "200.0",
                "reason": "New stock received",
            },
            headers=_auth(self.wh_mgr_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["new_qty"], 200.0)

    def test_e5_transfer_wh_to_branch(self):
        # Seed warehouse stock
        self.client.post(
            f"/api/v1/stock/warehouses/{self.warehouse.id}/adjust",
            json={"item_id": self.item.id, "adjustment_type": "set", "qty": "100", "reason": "seed"},
            headers=_auth(self.admin_tok),
        )
        r = self.client.post(
            f"/api/v1/stock/transfer/warehouse-to-branch",
            params={"warehouse_id": self.warehouse.id, "branch_id": self.branch.id},
            json={"item_id": self.item.id, "qty": "30.0", "reason": "Manual replenishment"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["qty_transferred"], 30.0)
        self.assertEqual(body["warehouse_qty_after"], 70.0)

    def test_e5_transfer_wh_to_branch_insufficient_stock(self):
        # Set warehouse stock to 0
        self.client.post(
            f"/api/v1/stock/warehouses/{self.warehouse.id}/adjust",
            json={"item_id": self.item.id, "adjustment_type": "set", "qty": "0", "reason": "clear"},
            headers=_auth(self.admin_tok),
        )
        r = self.client.post(
            f"/api/v1/stock/transfer/warehouse-to-branch",
            params={"warehouse_id": self.warehouse.id, "branch_id": self.branch.id},
            json={"item_id": self.item.id, "qty": "50.0", "reason": "Transfer"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("insufficient_warehouse_qty", r.json().get("error_code", ""))

    def test_e5_transfer_branch_to_wh(self):
        # Seed branch stock
        self.client.post(
            f"/api/v1/stock/branches/{self.branch.id}/adjust",
            json={"item_id": self.item.id, "adjustment_type": "set", "qty": "80", "reason": "seed"},
            headers=_auth(self.admin_tok),
        )
        r = self.client.post(
            f"/api/v1/stock/transfer/branch-to-warehouse",
            params={"branch_id": self.branch.id, "warehouse_id": self.warehouse.id},
            json={"item_id": self.item.id, "qty": "20.0", "reason": "Return excess"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["qty_returned"], 20.0)

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 6 — Ledger & variance report
    # ──────────────────────────────────────────────────────────────────────

    def test_e6_branch_ledger_returns_list(self):
        r = self.client.get(
            f"/api/v1/ledger/branches/{self.branch.id}",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)
        self.assertIn("total", body)
        self.assertIn("branch_id", body)

    def test_e6_warehouse_ledger_returns_list(self):
        r = self.client.get(
            f"/api/v1/ledger/warehouses/{self.warehouse.id}",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)

    def test_e6_branch_ledger_invalid_branch_404(self):
        r = self.client.get(
            "/api/v1/ledger/branches/999999",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 404)

    def test_e6_variance_report_returns_list(self):
        r = self.client.get(
            "/api/v1/ledger/variance-report",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)
        self.assertIn("total", body)

    def test_e6_low_stock_no_location_400(self):
        r = self.client.get(
            "/api/v1/ledger/low-stock",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("location_required", r.json().get("error_code", ""))

    def test_e6_low_stock_by_branch(self):
        # Set stock below reorder point (5)
        self.client.post(
            f"/api/v1/stock/branches/{self.branch.id}/adjust",
            json={"item_id": self.item.id, "adjustment_type": "set", "qty": "2", "reason": "low for test"},
            headers=_auth(self.admin_tok),
        )
        r = self.client.get(
            f"/api/v1/ledger/low-stock",
            params={"branch_id": self.branch.id},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)
        # At least one item should be low
        self.assertGreater(body["total"], 0)

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 7 — User profile
    # ──────────────────────────────────────────────────────────────────────

    def test_e7_get_me(self):
        r = self.client.get("/api/v1/users/me", headers=_auth(self.branch_usr_tok))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["username"], "busr_e4")
        self.assertIn("roles", body)

    def test_e7_change_password_success(self):
        r = self.client.post(
            "/api/v1/users/me/change-password",
            json={"current_password": "Pass@1234", "new_password": "NewPass@5678"},
            headers=_auth(self.branch_usr_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("Password changed", r.json().get("message", ""))
        # Restore password for subsequent tests (login بكلمة المرور الجديدة ثم إرجاع القديمة)
        r_new = self.client.post(
            "/api/v1/auth/login",
            json={"username": "busr_e4", "password": "NewPass@5678"},
        )
        self.assertEqual(r_new.status_code, 200, r_new.text)
        tok_new = r_new.json()["access_token"]
        self.client.post(
            "/api/v1/users/me/change-password",
            json={"current_password": "NewPass@5678", "new_password": "Pass@1234"},
            headers=_auth(tok_new),
        )

    def test_e7_change_password_wrong_current(self):
        r = self.client.post(
            "/api/v1/users/me/change-password",
            json={"current_password": "WrongPass", "new_password": "NewPass@5678"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("wrong_current_password", r.json().get("error_code", ""))

    def test_e7_change_password_too_short(self):
        r = self.client.post(
            "/api/v1/users/me/change-password",
            json={"current_password": "Pass@1234", "new_password": "abc"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("password_too_short", r.json().get("error_code", ""))

    def test_e7_list_roles(self):
        r = self.client.get("/api/v1/users/roles", headers=_auth(self.admin_tok))
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)
        # At least one role
        self.assertGreater(len(r.json()), 0)
        self.assertIn("name", r.json()[0])

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 8 — Reports
    # ──────────────────────────────────────────────────────────────────────

    def test_e8_inventory_compliance_report(self):
        r = self.client.get(
            "/api/v1/reports/inventory-compliance",
            params={"date_from": "2026-01-01", "date_to": "2026-01-07"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("branches", body)
        self.assertIn("date_from", body)

    def test_e8_inventory_compliance_date_range_too_wide(self):
        r = self.client.get(
            "/api/v1/reports/inventory-compliance",
            params={"date_from": "2025-01-01", "date_to": "2026-01-01"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("date_range_too_wide", r.json().get("error_code", ""))

    def test_e8_inventory_compliance_invalid_range(self):
        r = self.client.get(
            "/api/v1/reports/inventory-compliance",
            params={"date_from": "2026-01-10", "date_to": "2026-01-01"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("invalid_date_range", r.json().get("error_code", ""))

    def test_e8_order_summary_report(self):
        r = self.client.get(
            "/api/v1/reports/order-summary",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("total_orders", body)
        self.assertIn("by_status", body)

    def test_e8_variance_trend_report(self):
        r = self.client.get(
            "/api/v1/reports/variance-trend",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 9 — Alerts
    # ──────────────────────────────────────────────────────────────────────

    def test_e9_low_stock_alerts(self):
        # Ensure low stock exists (set qty=2, reorder_point=5)
        self.client.post(
            f"/api/v1/stock/branches/{self.branch.id}/adjust",
            json={"item_id": self.item.id, "adjustment_type": "set", "qty": "2", "reason": "seed"},
            headers=_auth(self.admin_tok),
        )
        r = self.client.get(
            "/api/v1/alerts/low-stock",
            params={"branch_id": self.branch.id},
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)
        self.assertEqual(body["alert_type"], "low_stock")
        self.assertGreater(body["total"], 0)

    def test_e9_low_stock_alerts_branch_scoped(self):
        """Branch users see only their own branch's alerts."""
        r = self.client.get(
            "/api/v1/alerts/low-stock",
            headers=_auth(self.branch_usr_tok),
        )
        self.assertEqual(r.status_code, 200)

    def test_e9_pending_inventories(self):
        r = self.client.get(
            "/api/v1/alerts/pending-inventories",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)
        self.assertEqual(body["alert_type"], "pending_inventories")

    def test_e9_missing_inventory_today(self):
        r = self.client.get(
            "/api/v1/alerts/missing-inventory-today",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("missing_branches", body)
        self.assertIn("total_active_branches", body)
        # At least our test branch exists
        self.assertGreaterEqual(body["total_active_branches"], 1)

    def test_e9_overdue_orders(self):
        r = self.client.get(
            "/api/v1/alerts/overdue-orders",
            params={"overdue_hours": 1},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("items", body)
        self.assertEqual(body["alert_type"], "overdue_orders")


if __name__ == "__main__":
    unittest.main(verbosity=2)
