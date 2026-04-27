"""
Epics 10-13 — Integration Tests
Covers:
  Epic 10: Auto-replenishment trigger, preview, idempotency
  Epic 11: Dashboard global KPIs, branch trend, alerts summary
  Epic 12: Export endpoints (CSV + XLSX)
  Epic 13: TenantMiddleware pass-through, X-Tenant-ID header
"""
import unittest
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
    UnitOfMeasure,
    User,
    UserRole,
    Warehouse,
    WarehouseStock,
)

# ─────────────────────────────────────────────────────────────────────────
# DB setup
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


def _login(client, username):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Pass@1234"},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────
# Test class
# ─────────────────────────────────────────────────────────────────────────

class TestEpic10To13(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app, raise_server_exceptions=True)
        db = TestingSessionLocal()

        # Seed data
        cls.warehouse = Warehouse(
            warehouse_name="مستودع رئيسي", warehouse_code="WH-MAIN", active=True
        )
        db.add(cls.warehouse)
        db.flush()

        cls.branch = Branch(
            branch_name="فرع المركز", branch_code="BR-CTR",
            active=True, warehouse_id=cls.warehouse.id,
        )
        db.add(cls.branch)
        db.flush()

        cat = ItemCategory(name_ar="مواد غذائية", name_en="Food", code="FOOD")
        unit = UnitOfMeasure(name_ar="كرتون", name_en="Carton", code="CTN")
        db.add_all([cat, unit])
        db.flush()

        cls.item = Item(
            item_code="FOOD001",
            item_name_ar="عصير برتقال",
            item_name_en="Orange Juice",
            category_id=cat.id,
            unit_id=unit.id,
            active=True,
            branch_requestable=True,
            reorder_point=Decimal("10"),
            min_qty=Decimal("5"),
            safety_stock=Decimal("2"),
        )
        db.add(cls.item)
        db.flush()

        # Give branch some stock (below reorder point → should trigger replenishment)
        cls.branch_stock = BranchStock(
            branch_id=cls.branch.id,
            item_id=cls.item.id,
            current_qty=Decimal("3"),
        )
        db.add(cls.branch_stock)
        db.flush()

        # Create an approved inventory for trigger-replenishment test
        cls.approved_inv = DailyInventory(
            branch_id=cls.branch.id,
            inventory_date=date.today(),
            status=InventoryStatus.approved,
            created_by=1,
            approved_at=datetime.utcnow(),
        )
        db.add(cls.approved_inv)
        db.flush()

        # Also a draft inventory for the "not approved" test
        cls.draft_inv = DailyInventory(
            branch_id=cls.branch.id,
            inventory_date=date(2025, 1, 1),
            status=InventoryStatus.draft,
            created_by=1,
        )
        db.add(cls.draft_inv)
        db.flush()

        # Users
        cls.admin = _user(db, "admin_e10", RoleName.admin)
        cls.branch_mgr = _user(db, "bmgr_e10", RoleName.branch_manager, branch_id=cls.branch.id)
        cls.wh_mgr = _user(db, "wmgr_e10", RoleName.warehouse_manager, warehouse_id=cls.warehouse.id)

        db.close()

        # Tokens
        cls.admin_tok = _login(cls.client, "admin_e10")
        cls.branch_mgr_tok = _login(cls.client, "bmgr_e10")

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 10 — Auto-replenishment trigger
    # ──────────────────────────────────────────────────────────────────────

    def test_e10_trigger_replenishment_approved_inventory(self):
        r = self.client.post(
            f"/api/v1/inventory/{self.approved_inv.id}/trigger-replenishment",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertIn("message", body)
        # Either an order was created or no items needed
        self.assertIn("order_id", body)

    def test_e10_trigger_replenishment_draft_inventory_blocked(self):
        r = self.client.post(
            f"/api/v1/inventory/{self.draft_inv.id}/trigger-replenishment",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("not_approved", r.json().get("error_code", ""))

    def test_e10_trigger_replenishment_idempotent(self):
        """Calling trigger twice returns the same order."""
        r1 = self.client.post(
            f"/api/v1/inventory/{self.approved_inv.id}/trigger-replenishment",
            headers=_auth(self.admin_tok),
        )
        r2 = self.client.post(
            f"/api/v1/inventory/{self.approved_inv.id}/trigger-replenishment",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        # Both should return same order_id if an order was created
        if r1.json().get("order_id") and r2.json().get("order_id"):
            self.assertEqual(r1.json()["order_id"], r2.json()["order_id"])

    def test_e10_trigger_not_found(self):
        r = self.client.post(
            "/api/v1/inventory/999999/trigger-replenishment",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 404)

    def test_e10_replenishment_preview(self):
        r = self.client.get(
            f"/api/v1/inventory/branches/{self.branch.id}/replenishment-preview",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("preview_lines", body)
        self.assertIn("items_evaluated", body)
        self.assertIn("branch_id", body)
        self.assertEqual(body["branch_id"], self.branch.id)

    def test_e10_preview_custom_days_of_cover(self):
        r = self.client.get(
            f"/api/v1/inventory/branches/{self.branch.id}/replenishment-preview",
            params={"days_of_cover": 7},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["days_of_cover"], 7)

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 11 — Dashboard enhancements
    # ──────────────────────────────────────────────────────────────────────

    def test_e11_global_kpis(self):
        r = self.client.get(
            "/api/v1/dashboard/global",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("total_branches", body)
        self.assertIn("total_warehouses", body)
        self.assertIn("compliance_rate_today", body)
        self.assertIn("active_orders", body)
        self.assertIn("out_of_stock_items", body)
        self.assertIn("pending_inventory_approvals", body)
        # Our test branch should appear
        self.assertGreaterEqual(body["total_branches"], 1)

    def test_e11_branch_trend(self):
        r = self.client.get(
            f"/api/v1/dashboard/branch/{self.branch.id}/trend",
            params={"days": 7},
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("trend", body)
        self.assertEqual(len(body["trend"]), 7)
        self.assertEqual(body["days"], 7)
        for entry in body["trend"]:
            self.assertIn("date", entry)
            self.assertIn("inventory_status", entry)
            self.assertIn("orders_count", entry)

    def test_e11_alerts_summary(self):
        r = self.client.get(
            "/api/v1/dashboard/alerts-summary",
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("low_stock", body)
        self.assertIn("out_of_stock", body)
        self.assertIn("pending_inventory_approvals", body)
        self.assertIn("total_alerts", body)
        self.assertIn("missing_inventory_today", body)

    def test_e11_branch_dashboard_still_works(self):
        """Existing branch dashboard not broken by Epic 11 changes."""
        r = self.client.get(
            f"/api/v1/dashboard/branch/{self.branch.id}",
            headers=_auth(self.branch_mgr_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("branch_id", body)
        self.assertIn("items_out_of_stock", body)

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 12 — Data export
    # ──────────────────────────────────────────────────────────────────────

    def test_e12_export_branch_stock_csv(self):
        r = self.client.get(
            f"/api/v1/export/stock/branches/{self.branch.id}",
            params={"format": "csv"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers.get("content-type", ""))
        content = r.text
        self.assertIn("item_id", content)
        self.assertIn("current_qty", content)

    def test_e12_export_warehouse_stock_csv(self):
        r = self.client.get(
            f"/api/v1/export/stock/warehouses/{self.warehouse.id}",
            params={"format": "csv"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers.get("content-type", ""))

    def test_e12_export_order_summary_csv(self):
        r = self.client.get(
            "/api/v1/export/order-summary",
            params={"format": "csv"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers.get("content-type", ""))

    def test_e12_export_variance_report_csv(self):
        r = self.client.get(
            "/api/v1/export/variance-report",
            params={"format": "csv"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers.get("content-type", ""))

    def test_e12_export_inventory_compliance_csv(self):
        r = self.client.get(
            "/api/v1/export/inventory-compliance",
            params={"date_from": "2026-04-01", "date_to": "2026-04-07", "format": "csv"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers.get("content-type", ""))

    def test_e12_export_xlsx_returns_file(self):
        """XLSX export either returns xlsx or falls back to CSV gracefully."""
        r = self.client.get(
            f"/api/v1/export/stock/branches/{self.branch.id}",
            params={"format": "xlsx"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        ct = r.headers.get("content-type", "")
        self.assertTrue(
            "spreadsheetml" in ct or "text/csv" in ct,
            f"Unexpected content-type: {ct}",
        )

    def test_e12_export_ledger_csv(self):
        r = self.client.get(
            f"/api/v1/export/ledger/branches/{self.branch.id}",
            params={"format": "csv"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers.get("content-type", ""))

    def test_e12_invalid_format_rejected(self):
        r = self.client.get(
            f"/api/v1/export/stock/branches/{self.branch.id}",
            params={"format": "pdf"},
            headers=_auth(self.admin_tok),
        )
        self.assertEqual(r.status_code, 422)

    # ──────────────────────────────────────────────────────────────────────
    # EPIC 13 — Tenant middleware
    # ──────────────────────────────────────────────────────────────────────

    def test_e13_x_tenant_id_header_ignored_in_single_tenant_mode(self):
        """In single-tenant mode, X-Tenant-ID header should be accepted without error."""
        r = self.client.get(
            "/api/v1/health",
            headers={**_auth(self.admin_tok), "X-Tenant-ID": "1"},
        )
        self.assertEqual(r.status_code, 200)

    def test_e13_invalid_tenant_id_header_in_multi_tenant_mode_would_fail(self):
        """
        In single-tenant mode this passes. The middleware only enforces in
        MULTI_TENANT_ENABLED=True. This test documents expected behavior.
        """
        from app.config import settings
        # In single-tenant mode (default), any X-Tenant-ID is ignored
        r = self.client.get(
            "/api/v1/health",
            headers={**_auth(self.admin_tok), "X-Tenant-ID": "not-an-int"},
        )
        # Should still succeed (single-tenant passthrough)
        self.assertEqual(r.status_code, 200)

    def test_e13_tenant_context_default_is_1(self):
        """get_current_tenant_id() returns DEFAULT_TENANT_ID=1."""
        from app.core.tenant import get_current_tenant_id
        from app.config import settings
        self.assertEqual(get_current_tenant_id(), settings.DEFAULT_TENANT_ID)
        self.assertEqual(get_current_tenant_id(), 1)

    def test_e13_multi_tenant_flag_exists_in_settings(self):
        from app.config import settings
        self.assertFalse(settings.MULTI_TENANT_ENABLED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
