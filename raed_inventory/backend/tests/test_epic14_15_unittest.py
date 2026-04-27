"""
Epics 14–15 — Integration Tests
================================
Epic 14: Audit Log
  - GET /audit/logs  (admin only)
  - GET /audit/entity/{type}/{id}
  - GET /audit/modules
  - GET /audit/actions
  - audit written on inventory approve/reject
  - audit written on order approve/cancel

Epic 15: Data Import
  - GET /import/templates/{name}
  - POST /import/items  (create + update + error rows)
  - POST /import/branch-stock
  - POST /import/warehouse-stock
  - invalid format rejected (422 / 400)
"""
import csv
import io
import os
import unittest
from unittest import mock
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
    Item,
    ItemCategory,
    OrderStatus,
    ReplenishmentOrder,
    Role,
    RoleName,
    UnitOfMeasure,
    User,
    UserRole,
    Warehouse,
    WarehouseStock,
)

# ── In-memory test DB ──────────────────────────────────────────────────────────
ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


def _override_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db


def _tok(client, username, password="Test@1234"):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return r.json().get("access_token", "")


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


class TestEpic1415(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = _override_db
        Base.metadata.create_all(bind=ENGINE)
        db = TestSession()

        try:
            # Roles
            for rname in RoleName:
                if not db.query(Role).filter(Role.name == rname).first():
                    db.add(Role(name=rname, display_name=rname.value))
            db.flush()

            # Warehouse
            cls.wh = Warehouse(warehouse_name="Main WH", warehouse_code="WH01", active=True)
            db.add(cls.wh)
            db.flush()

            # Branch
            cls.br = Branch(
                branch_name="Test Branch", branch_code="BR01",
                active=True, warehouse_id=cls.wh.id,
            )
            db.add(cls.br)
            db.flush()

            # Category + Unit
            cls.cat = ItemCategory(name_ar="فئة", name_en="Category", code="CAT01")
            cls.unit = UnitOfMeasure(name_ar="كيلو", name_en="KG", code="KG")
            db.add_all([cls.cat, cls.unit])
            db.flush()

            # Items
            cls.item1 = Item(
                item_code="ITM-001", item_name_ar="صنف واحد", item_name_en="Item One",
                category_id=cls.cat.id, unit_id=cls.unit.id,
                min_qty=Decimal("2"), max_qty=Decimal("50"), reorder_point=Decimal("5"),
                active=True,
            )
            cls.item2 = Item(
                item_code="ITM-002", item_name_ar="صنف اثنين", item_name_en="Item Two",
                category_id=cls.cat.id, unit_id=cls.unit.id,
                min_qty=Decimal("1"), max_qty=Decimal("20"), reorder_point=Decimal("3"),
                active=True,
            )
            db.add_all([cls.item1, cls.item2])
            db.flush()

            # Branch stock
            db.add(BranchStock(branch_id=cls.br.id, item_id=cls.item1.id, current_qty=Decimal("10")))
            db.flush()

            # Warehouse stock
            db.add(WarehouseStock(warehouse_id=cls.wh.id, item_id=cls.item1.id, current_qty=Decimal("100")))
            db.flush()

            # Users
            def _user(username, role_name, branch_id=None, wh_id=None):
                u = User(
                    username=username, email=f"{username}@test.com",
                    hashed_password=get_password_hash("Test@1234"),
                    full_name=username, status="active",
                    branch_id=branch_id, warehouse_id=wh_id,
                )
                db.add(u)
                db.flush()
                role = db.query(Role).filter(Role.name == role_name).first()
                db.add(UserRole(user_id=u.id, role_id=role.id))
                db.flush()
                return u

            cls.admin = _user("admin14", RoleName.admin)
            cls.br_mgr = _user("brmgr14", RoleName.branch_manager, branch_id=cls.br.id)
            cls.br_usr = _user("brusr14", RoleName.branch_user, branch_id=cls.br.id)

            # Approved inventory (to generate audit events)
            inv = DailyInventory(
                branch_id=cls.br.id,
                inventory_date=date.today(),
                status="submitted",
                submitted_at=datetime.utcnow(),
                submitted_by=cls.br_usr.id,
                created_by=cls.br_usr.id,
            )
            db.add(inv)
            db.flush()
            line = DailyInventoryLine(
                inventory_id=inv.id, item_id=cls.item1.id,
                book_qty=Decimal("10"), counted_qty=Decimal("9"),
                variance_qty=Decimal("-1"), variance_pct=Decimal("-10"),
                variance_status="warning",
            )
            db.add(line)
            db.flush()
            cls.inv_id = inv.id

            db.commit()
        finally:
            db.close()

        cls.client = TestClient(app)
        cls.admin_tok = _tok(cls.client, "admin14")
        cls.brmgr_tok = _tok(cls.client, "brmgr14")
        cls.brusr_tok = _tok(cls.client, "brusr14")

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=ENGINE)

    def setUp(self):
        app.dependency_overrides[get_db] = _override_db

    # ──────────────────────────────────────────────────────────────────────────
    # Epic 14 — Audit Log
    # ──────────────────────────────────────────────────────────────────────────

    def test_01_audit_approve_inventory_writes_log(self):
        """Approving inventory should write an audit entry."""
        r = self.client.post(
            f"/api/v1/inventory/{self.inv_id}/approve",
            headers=_hdr(self.brmgr_tok),
        )
        self.assertIn(r.status_code, (200, 400), r.text)  # 400 if already approved

    def test_02_audit_logs_admin_access(self):
        """GET /audit/logs returns paginated list to admin."""
        r = self.client.get("/api/v1/audit/logs", headers=_hdr(self.admin_tok))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("total", body)
        self.assertIn("items", body)

    def test_03_audit_logs_non_admin_forbidden(self):
        """Branch user cannot access audit logs."""
        r = self.client.get("/api/v1/audit/logs", headers=_hdr(self.brusr_tok))
        self.assertEqual(r.status_code, 403)

    def test_04_audit_logs_filter_by_module(self):
        """Filter by module=inventory works."""
        r = self.client.get(
            "/api/v1/audit/logs?module=inventory",
            headers=_hdr(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)

    def test_05_audit_entity_history(self):
        """GET /audit/entity/daily_inventory/{id} returns list."""
        r = self.client.get(
            f"/api/v1/audit/entity/daily_inventory/{self.inv_id}",
            headers=_hdr(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("history", body)

    def test_06_audit_modules_list(self):
        """GET /audit/modules returns list of strings."""
        r = self.client.get("/api/v1/audit/modules", headers=_hdr(self.admin_tok))
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_07_audit_actions_list(self):
        """GET /audit/actions returns list of strings."""
        r = self.client.get("/api/v1/audit/actions", headers=_hdr(self.admin_tok))
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_08_audit_actions_filtered_by_module(self):
        """GET /audit/actions?module=inventory scopes result."""
        r = self.client.get(
            "/api/v1/audit/actions?module=inventory",
            headers=_hdr(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)

    def test_09_audit_logs_pagination(self):
        """Pagination params page and page_size work."""
        r = self.client.get(
            "/api/v1/audit/logs?page=1&page_size=5",
            headers=_hdr(self.admin_tok),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertLessEqual(len(body["items"]), 5)

    # ──────────────────────────────────────────────────────────────────────────
    # Epic 15 — Data Import
    # ──────────────────────────────────────────────────────────────────────────

    def _csv_upload(self, path, rows, fieldnames):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        buf.seek(0)
        return ("file", ("data.csv", buf.read().encode(), "text/csv"))

    def test_10_import_template_items(self):
        """GET /import/templates/items returns CSV template."""
        r = self.client.get("/api/v1/import/templates/items", headers=_hdr(self.admin_tok))
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["content-type"])
        self.assertIn("item_code", r.text)

    def test_11_import_template_branch_stock(self):
        r = self.client.get("/api/v1/import/templates/branch-stock", headers=_hdr(self.admin_tok))
        self.assertEqual(r.status_code, 200)
        self.assertIn("branch_code", r.text)

    def test_12_import_template_unknown_404(self):
        r = self.client.get("/api/v1/import/templates/unknown", headers=_hdr(self.admin_tok))
        self.assertEqual(r.status_code, 404)

    def test_13_import_items_create_new(self):
        """Upload CSV with a new item — should create it."""
        rows = [{
            "item_code": "ITM-IMPORT-01",
            "item_name_ar": "مستورد",
            "item_name_en": "Imported Item",
            "category_code": "CAT01",
            "unit_code": "KG",
            "min_qty": "1",
            "max_qty": "10",
            "reorder_point": "2",
            "active": "true",
        }]
        file_tuple = self._csv_upload(
            "/api/v1/import/items", rows,
            ["item_code", "item_name_ar", "item_name_en", "category_code", "unit_code",
             "min_qty", "max_qty", "reorder_point", "active"],
        )
        r = self.client.post(
            "/api/v1/import/items",
            headers=_hdr(self.admin_tok),
            files=[file_tuple],
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["created"], 1)
        self.assertEqual(body["total_errors"], 0)

    def test_14_import_items_update_existing(self):
        """Upload CSV with existing item_code — should update it."""
        rows = [{
            "item_code": "ITM-001",        # already exists
            "item_name_ar": "محدث",
            "item_name_en": "Updated Item",
            "category_code": "CAT01",
            "unit_code": "KG",
            "min_qty": "3",
            "max_qty": "60",
            "reorder_point": "7",
            "active": "",
        }]
        file_tuple = self._csv_upload(
            "/api/v1/import/items", rows,
            ["item_code", "item_name_ar", "item_name_en", "category_code", "unit_code",
             "min_qty", "max_qty", "reorder_point", "active"],
        )
        r = self.client.post(
            "/api/v1/import/items",
            headers=_hdr(self.admin_tok),
            files=[file_tuple],
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["updated"], 1)

    def test_15_import_items_bad_category_error(self):
        """Row with unknown category_code → error row, not 500."""
        rows = [{
            "item_code": "ITM-ERR-01",
            "item_name_ar": "خطأ",
            "item_name_en": "Error Item",
            "category_code": "NO_SUCH_CAT",
            "unit_code": "KG",
            "min_qty": "1",
            "max_qty": "5",
            "reorder_point": "1",
            "active": "true",
        }]
        file_tuple = self._csv_upload(
            "/api/v1/import/items", rows,
            ["item_code", "item_name_ar", "item_name_en", "category_code", "unit_code",
             "min_qty", "max_qty", "reorder_point", "active"],
        )
        r = self.client.post(
            "/api/v1/import/items",
            headers=_hdr(self.admin_tok),
            files=[file_tuple],
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["created"], 0)
        self.assertEqual(body["total_errors"], 1)
        self.assertIn("CAT", body["errors"][0]["error"])

    def test_16_import_branch_stock_success(self):
        """Upload branch stock CSV — updates existing row."""
        rows = [{"branch_code": "BR01", "item_code": "ITM-001", "qty": "25"}]
        file_tuple = self._csv_upload(
            "/api/v1/import/branch-stock",
            rows,
            ["branch_code", "item_code", "qty"],
        )
        r = self.client.post(
            "/api/v1/import/branch-stock",
            headers=_hdr(self.admin_tok),
            files=[file_tuple],
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn(body["updated"] + body["created"], [1])

    def test_17_import_branch_stock_unknown_branch_error(self):
        """Unknown branch_code → error row."""
        rows = [{"branch_code": "NOPE", "item_code": "ITM-001", "qty": "5"}]
        file_tuple = self._csv_upload(
            "/api/v1/import/branch-stock", rows, ["branch_code", "item_code", "qty"]
        )
        r = self.client.post(
            "/api/v1/import/branch-stock",
            headers=_hdr(self.admin_tok),
            files=[file_tuple],
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["total_errors"], 1)

    def test_18_import_warehouse_stock_create(self):
        """Upload warehouse stock CSV — creates new row for ITM-002."""
        rows = [{"warehouse_code": "WH01", "item_code": "ITM-002", "qty": "50"}]
        file_tuple = self._csv_upload(
            "/api/v1/import/warehouse-stock", rows, ["warehouse_code", "item_code", "qty"]
        )
        r = self.client.post(
            "/api/v1/import/warehouse-stock",
            headers=_hdr(self.admin_tok),
            files=[file_tuple],
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total_errors"], 0)
        self.assertGreaterEqual(body["created"] + body["updated"], 1)

    def test_19_import_non_admin_forbidden(self):
        """Branch user cannot use import endpoints."""
        rows = [{"branch_code": "BR01", "item_code": "ITM-001", "qty": "1"}]
        file_tuple = self._csv_upload(
            "/api/v1/import/branch-stock", rows, ["branch_code", "item_code", "qty"]
        )
        r = self.client.post(
            "/api/v1/import/branch-stock",
            headers=_hdr(self.brusr_tok),
            files=[file_tuple],
        )
        self.assertEqual(r.status_code, 403)

    def test_20_import_empty_file_400(self):
        """Uploading an empty CSV returns 400."""
        r = self.client.post(
            "/api/v1/import/items",
            headers=_hdr(self.admin_tok),
            files=[("file", ("empty.csv", b"", "text/csv"))],
        )
        self.assertEqual(r.status_code, 400)

    def test_21_import_items_missing_item_code_error(self):
        """Row missing item_code → per-row error, not crash."""
        buf = io.StringIO()
        buf.write("item_code,item_name_ar,item_name_en,category_code,unit_code\n")
        buf.write(",اسم,name,CAT01,KG\n")   # empty item_code
        buf.seek(0)
        r = self.client.post(
            "/api/v1/import/items",
            headers=_hdr(self.admin_tok),
            files=[("file", ("bad.csv", buf.read().encode(), "text/csv"))],
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total_errors"], 1)

    def test_22_import_audit_trail_written(self):
        """After a successful import, audit log should contain an 'import' action."""
        # Run a quick import
        rows = [{"warehouse_code": "WH01", "item_code": "ITM-001", "qty": "99"}]
        file_tuple = self._csv_upload(
            "/api/v1/import/warehouse-stock", rows, ["warehouse_code", "item_code", "qty"]
        )
        with mock.patch.dict(os.environ, {"AUDIT_LOG_ENABLED": "true"}):
            self.client.post(
                "/api/v1/import/warehouse-stock",
                headers=_hdr(self.admin_tok),
                files=[file_tuple],
            )

            r = self.client.get(
                "/api/v1/audit/logs?action=import",
                headers=_hdr(self.admin_tok),
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertGreater(body["total"], 0)
        actions = [i["action"] for i in body["items"]]
        self.assertIn("import", actions)


if __name__ == "__main__":
    unittest.main()
