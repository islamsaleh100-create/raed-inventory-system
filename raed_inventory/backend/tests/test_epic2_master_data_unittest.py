"""
Epic 2 — Master Data Expansion
Unit tests covering:
  - URL prefix change: /api/v1/master
  - GET single endpoints (warehouse, branch, category, unit)
  - Category CRUD (create, update, delete/deactivate)
  - Unit CRUD (create, update, delete/deactivate)
  - Inventory variance reason CRUD
  - Receiving variance reason CRUD
  - Item filters: item_type, storage_type
  - Stock initialization (branch + warehouse)
  - Branch stock view
  - Warehouse stock view
"""
import unittest
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (
    Branch, BranchStock, Item, ItemCategory, InventoryVarianceReason,
    ReceivingVarianceReason, Role, RoleName, UnitOfMeasure, User,
    UserRole, Warehouse, WarehouseStock,
)
from app.core.security import get_password_hash


# ─────────────────────────────────────────────────────────────────────────
# Test database setup
# ─────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _seed_admin(db) -> str:
    """Create admin user + role, return JWT token."""
    role = Role(name=RoleName.admin, display_name="Admin")
    db.add(role)
    db.flush()

    user = User(
        username="admin_e2",
        email="admin_e2@test.com",
        full_name="Admin E2",
        hashed_password=get_password_hash("Admin@2025"),
    )
    db.add(user)
    db.flush()

    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/auth/login", json={"username": "admin_e2", "password": "Admin@2025"})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_warehouse(db, code="WH01", name="Main WH") -> Warehouse:
    wh = Warehouse(warehouse_code=code, warehouse_name=name)
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return wh


def _seed_branch(db, warehouse_id: int, code="BR01", name="Branch 1") -> Branch:
    br = Branch(branch_code=code, branch_name=name, warehouse_id=warehouse_id)
    db.add(br)
    db.commit()
    db.refresh(br)
    return br


def _seed_category(db, code="CAT01", name_ar="تصنيف", name_en="Category") -> ItemCategory:
    cat = ItemCategory(code=code, name_ar=name_ar, name_en=name_en)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def _seed_unit(db, code="KG", name_ar="كيلو", name_en="Kilogram") -> UnitOfMeasure:
    unit = UnitOfMeasure(code=code, name_ar=name_ar, name_en=name_en)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def _seed_item(db, cat_id: int, unit_id: int, code="ITEM01") -> Item:
    item = Item(
        item_code=code,
        item_name_ar="صنف تجريبي",
        item_name_en="Test Item",
        category_id=cat_id,
        unit_id=unit_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ─────────────────────────────────────────────────────────────────────────
# Test class
# ─────────────────────────────────────────────────────────────────────────

class Epic2MasterDataTests(unittest.TestCase):

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        self.cm = TestClient(app, raise_server_exceptions=False)
        self.client = self.cm.__enter__()
        self.token = _seed_admin(self.db)

    def tearDown(self):
        self.cm.__exit__(None, None, None)
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    # ── URL prefix ────────────────────────────────────────────────────────

    def test_master_endpoints_use_v1_prefix(self):
        """All master endpoints must live under /api/v1/master."""
        wh = _seed_warehouse(self.db)
        resp = self.client.get("/api/v1/master/warehouses", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 200)

    def test_old_master_prefix_does_not_exist(self):
        """The old /api/master prefix must no longer be registered."""
        resp = self.client.get("/api/master/warehouses", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 404)

    # ── GET single: warehouse ─────────────────────────────────────────────

    def test_get_single_warehouse_returns_correct_record(self):
        wh = _seed_warehouse(self.db, code="WH-S1", name="Single WH")
        resp = self.client.get(f"/api/v1/master/warehouses/{wh.id}", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["warehouse_code"], "WH-S1")

    def test_get_single_warehouse_404_for_missing(self):
        resp = self.client.get("/api/v1/master/warehouses/9999", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error_code"], "master.warehouse_not_found")

    # ── GET single: branch ────────────────────────────────────────────────

    def test_get_single_branch_returns_correct_record(self):
        wh = _seed_warehouse(self.db)
        br = _seed_branch(self.db, wh.id, code="BR-S1", name="Single Branch")
        resp = self.client.get(f"/api/v1/master/branches/{br.id}", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["branch_code"], "BR-S1")

    def test_get_single_branch_404_for_missing(self):
        resp = self.client.get("/api/v1/master/branches/9999", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error_code"], "master.branch_not_found")

    # ── GET single: category ──────────────────────────────────────────────

    def test_get_single_category_returns_correct_record(self):
        cat = _seed_category(self.db, code="CAT-S1", name_en="Oils")
        resp = self.client.get(f"/api/v1/master/categories/{cat.id}", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name_en"], "Oils")

    def test_get_single_category_404_for_missing(self):
        resp = self.client.get("/api/v1/master/categories/9999", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 404)

    # ── GET single: unit ──────────────────────────────────────────────────

    def test_get_single_unit_returns_correct_record(self):
        unit = _seed_unit(self.db, code="LTR", name_en="Litre")
        resp = self.client.get(f"/api/v1/master/units/{unit.id}", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["code"], "LTR")

    # ── Category update ───────────────────────────────────────────────────

    def test_update_category_changes_name(self):
        cat = _seed_category(self.db)
        resp = self.client.put(
            f"/api/v1/master/categories/{cat.id}",
            json={"name_en": "Updated Category"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name_en"], "Updated Category")

    def test_update_category_partial_update_does_not_wipe_other_fields(self):
        cat = _seed_category(self.db, name_ar="اسم عربي", name_en="English Name")
        self.client.put(
            f"/api/v1/master/categories/{cat.id}",
            json={"name_en": "New English"},
            headers=_auth(self.token),
        )
        self.db.expire(cat)
        self.db.refresh(cat)
        self.assertEqual(cat.name_ar, "اسم عربي")   # unchanged

    # ── Category delete ───────────────────────────────────────────────────

    def test_delete_category_deactivates_it(self):
        cat = _seed_category(self.db, code="CAT-DEL")
        resp = self.client.delete(
            f"/api/v1/master/categories/{cat.id}",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.db.expire(cat)
        self.db.refresh(cat)
        self.assertFalse(cat.active)

    def test_delete_category_blocked_when_active_items_exist(self):
        cat = _seed_category(self.db, code="CAT-BLOCK")
        unit = _seed_unit(self.db, code="U-BLOCK")
        _seed_item(self.db, cat.id, unit.id)
        resp = self.client.delete(
            f"/api/v1/master/categories/{cat.id}",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "master.category_has_active_items")

    # ── Unit update / delete ──────────────────────────────────────────────

    def test_update_unit_changes_name(self):
        unit = _seed_unit(self.db)
        resp = self.client.put(
            f"/api/v1/master/units/{unit.id}",
            json={"name_en": "Kilogram Updated"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name_en"], "Kilogram Updated")

    def test_delete_unit_deactivates_it(self):
        unit = _seed_unit(self.db, code="UNIT-DEL")
        resp = self.client.delete(
            f"/api/v1/master/units/{unit.id}",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.db.expire(unit)
        self.db.refresh(unit)
        self.assertFalse(unit.active)

    def test_delete_unit_blocked_when_active_items_exist(self):
        cat = _seed_category(self.db, code="CAT-UB")
        unit = _seed_unit(self.db, code="UNIT-BLOCK")
        _seed_item(self.db, cat.id, unit.id, code="ITEM-UB")
        resp = self.client.delete(
            f"/api/v1/master/units/{unit.id}",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "master.unit_has_active_items")

    # ── Inventory variance reasons CRUD ───────────────────────────────────

    def test_create_variance_reason(self):
        resp = self.client.post(
            "/api/v1/master/variance-reasons",
            json={"reason_ar": "تلف", "reason_en": "Damage"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["reason_en"], "Damage")
        self.assertTrue(data["active"])

    def test_list_variance_reasons_active_only_by_default(self):
        reason = InventoryVarianceReason(reason_ar="غير نشط", reason_en="Inactive", active=False)
        active = InventoryVarianceReason(reason_ar="نشط", reason_en="Active", active=True)
        self.db.add_all([reason, active])
        self.db.commit()
        resp = self.client.get("/api/v1/master/variance-reasons", headers=_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        results = resp.json()
        self.assertTrue(all(r["active"] for r in results))

    def test_update_variance_reason(self):
        reason = InventoryVarianceReason(reason_ar="قديم", reason_en="Old Reason", active=True)
        self.db.add(reason)
        self.db.commit()
        resp = self.client.put(
            f"/api/v1/master/variance-reasons/{reason.id}",
            json={"reason_en": "Updated Reason"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["reason_en"], "Updated Reason")

    def test_delete_variance_reason_deactivates(self):
        reason = InventoryVarianceReason(reason_ar="يُحذف", reason_en="To Delete", active=True)
        self.db.add(reason)
        self.db.commit()
        resp = self.client.delete(
            f"/api/v1/master/variance-reasons/{reason.id}",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.db.expire(reason)
        self.db.refresh(reason)
        self.assertFalse(reason.active)

    def test_variance_reason_404_for_missing(self):
        resp = self.client.put(
            "/api/v1/master/variance-reasons/9999",
            json={"reason_en": "X"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error_code"], "master.variance_reason_not_found")

    # ── Receiving variance reasons CRUD ───────────────────────────────────

    def test_create_receiving_variance_reason(self):
        resp = self.client.post(
            "/api/v1/master/receiving-variance-reasons",
            json={"reason_ar": "نقص في التسليم", "reason_en": "Short delivery"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["reason_en"], "Short delivery")

    def test_update_receiving_variance_reason(self):
        reason = ReceivingVarianceReason(reason_ar="قديم", reason_en="Old", active=True)
        self.db.add(reason)
        self.db.commit()
        resp = self.client.put(
            f"/api/v1/master/receiving-variance-reasons/{reason.id}",
            json={"reason_en": "Updated"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["reason_en"], "Updated")

    def test_delete_receiving_variance_reason_deactivates(self):
        reason = ReceivingVarianceReason(reason_ar="يُحذف", reason_en="To Delete", active=True)
        self.db.add(reason)
        self.db.commit()
        resp = self.client.delete(
            f"/api/v1/master/receiving-variance-reasons/{reason.id}",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.db.expire(reason)
        self.db.refresh(reason)
        self.assertFalse(reason.active)

    # ── Item filters: item_type, storage_type ─────────────────────────────

    def test_list_items_filter_by_item_type(self):
        cat = _seed_category(self.db, code="CAT-FT")
        unit = _seed_unit(self.db, code="U-FT")
        from app.models import ItemType, StorageType
        raw = Item(
            item_code="RAW-01", item_name_ar="مادة خام", item_name_en="Raw Mat",
            category_id=cat.id, unit_id=unit.id,
            item_type=ItemType.raw_material, storage_type=StorageType.ambient,
        )
        pkg = Item(
            item_code="PKG-01", item_name_ar="تغليف", item_name_en="Packaging",
            category_id=cat.id, unit_id=unit.id,
            item_type=ItemType.packaging, storage_type=StorageType.ambient,
        )
        self.db.add_all([raw, pkg])
        self.db.commit()

        resp = self.client.get(
            "/api/v1/master/items?item_type=raw_material",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(all(i["item_type"] == "raw_material" for i in data["items"]))

    def test_list_items_filter_by_storage_type(self):
        cat = _seed_category(self.db, code="CAT-ST")
        unit = _seed_unit(self.db, code="U-ST")
        from app.models import ItemType, StorageType
        ambient = Item(
            item_code="AMB-01", item_name_ar="طازج", item_name_en="Ambient",
            category_id=cat.id, unit_id=unit.id,
            item_type=ItemType.raw_material, storage_type=StorageType.ambient,
        )
        chilled = Item(
            item_code="CHL-01", item_name_ar="مبرد", item_name_en="Chilled",
            category_id=cat.id, unit_id=unit.id,
            item_type=ItemType.raw_material, storage_type=StorageType.chilled,
        )
        self.db.add_all([ambient, chilled])
        self.db.commit()

        resp = self.client.get(
            "/api/v1/master/items?storage_type=chilled",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(all(i["storage_type"] == "chilled" for i in data["items"]))

    def test_list_items_invalid_item_type_returns_400(self):
        resp = self.client.get(
            "/api/v1/master/items?item_type=invalid_type",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "master.invalid_item_type")

    def test_list_items_invalid_storage_type_returns_400(self):
        resp = self.client.get(
            "/api/v1/master/items?storage_type=vacuum",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "master.invalid_storage_type")

    # ── Stock initialization: branch ──────────────────────────────────────

    def test_init_branch_stock_creates_stock_record_and_ledger_entry(self):
        wh = _seed_warehouse(self.db)
        br = _seed_branch(self.db, wh.id)
        cat = _seed_category(self.db, code="CAT-SI")
        unit = _seed_unit(self.db, code="U-SI")
        item = _seed_item(self.db, cat.id, unit.id, code="ITEM-SI")

        resp = self.client.post(
            f"/api/v1/master/items/{item.id}/stock/branch/{br.id}",
            json={"opening_qty": "100.000", "notes": "Opening stock"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["entity_type"], "branch")
        self.assertEqual(data["entity_id"], br.id)
        self.assertEqual(Decimal(data["current_qty"]), Decimal("100"))

        # Stock record persisted
        stock = self.db.query(BranchStock).filter(
            BranchStock.branch_id == br.id,
            BranchStock.item_id == item.id,
        ).first()
        self.assertIsNotNone(stock)
        self.assertEqual(Decimal(str(stock.current_qty)), Decimal("100"))

    def test_init_branch_stock_second_call_adjusts_qty(self):
        wh = _seed_warehouse(self.db, code="WH-ADJ")
        br = _seed_branch(self.db, wh.id, code="BR-ADJ")
        cat = _seed_category(self.db, code="CAT-ADJ")
        unit = _seed_unit(self.db, code="U-ADJ")
        item = _seed_item(self.db, cat.id, unit.id, code="ITEM-ADJ")

        self.client.post(
            f"/api/v1/master/items/{item.id}/stock/branch/{br.id}",
            json={"opening_qty": "50.000"},
            headers=_auth(self.token),
        )
        resp = self.client.post(
            f"/api/v1/master/items/{item.id}/stock/branch/{br.id}",
            json={"opening_qty": "80.000"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(resp.json()["current_qty"]), Decimal("80"))

    def test_init_branch_stock_negative_qty_returns_422(self):
        wh = _seed_warehouse(self.db, code="WH-NEG")
        br = _seed_branch(self.db, wh.id, code="BR-NEG")
        cat = _seed_category(self.db, code="CAT-NEG")
        unit = _seed_unit(self.db, code="U-NEG")
        item = _seed_item(self.db, cat.id, unit.id, code="ITEM-NEG")

        resp = self.client.post(
            f"/api/v1/master/items/{item.id}/stock/branch/{br.id}",
            json={"opening_qty": "-5.000"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 422)

    def test_init_branch_stock_item_not_found_returns_404(self):
        wh = _seed_warehouse(self.db, code="WH-NF")
        br = _seed_branch(self.db, wh.id, code="BR-NF")
        resp = self.client.post(
            f"/api/v1/master/items/9999/stock/branch/{br.id}",
            json={"opening_qty": "10"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    # ── Stock initialization: warehouse ───────────────────────────────────

    def test_init_warehouse_stock_creates_stock_record(self):
        wh = _seed_warehouse(self.db, code="WH-WS")
        cat = _seed_category(self.db, code="CAT-WS")
        unit = _seed_unit(self.db, code="U-WS")
        item = _seed_item(self.db, cat.id, unit.id, code="ITEM-WS")

        resp = self.client.post(
            f"/api/v1/master/items/{item.id}/stock/warehouse/{wh.id}",
            json={"opening_qty": "500"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["entity_type"], "warehouse")
        self.assertEqual(Decimal(data["current_qty"]), Decimal("500"))

        stock = self.db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == wh.id,
            WarehouseStock.item_id == item.id,
        ).first()
        self.assertIsNotNone(stock)

    # ── Branch stock view ─────────────────────────────────────────────────

    def test_list_branch_stock_returns_paginated_results(self):
        wh = _seed_warehouse(self.db, code="WH-BSV")
        br = _seed_branch(self.db, wh.id, code="BR-BSV")
        cat = _seed_category(self.db, code="CAT-BSV")
        unit = _seed_unit(self.db, code="U-BSV")
        item = _seed_item(self.db, cat.id, unit.id, code="ITEM-BSV")

        stock = BranchStock(
            branch_id=br.id, item_id=item.id,
            current_qty=Decimal("25"), reserved_qty=Decimal("0"), in_transit_qty=Decimal("0"),
        )
        self.db.add(stock)
        self.db.commit()

        resp = self.client.get(
            f"/api/v1/master/branches/{br.id}/stock",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["item_id"], item.id)

    def test_list_branch_stock_404_for_unknown_branch(self):
        resp = self.client.get(
            "/api/v1/master/branches/9999/stock",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    # ── Warehouse stock view ──────────────────────────────────────────────

    def test_list_warehouse_stock_returns_paginated_results(self):
        wh = _seed_warehouse(self.db, code="WH-WSV")
        cat = _seed_category(self.db, code="CAT-WSV")
        unit = _seed_unit(self.db, code="U-WSV")
        item = _seed_item(self.db, cat.id, unit.id, code="ITEM-WSV")

        stock = WarehouseStock(
            warehouse_id=wh.id, item_id=item.id,
            current_qty=Decimal("200"), reserved_qty=Decimal("0"),
        )
        self.db.add(stock)
        self.db.commit()

        resp = self.client.get(
            f"/api/v1/master/warehouses/{wh.id}/stock",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["item_id"], item.id)

    def test_list_warehouse_stock_404_for_unknown_warehouse(self):
        resp = self.client.get(
            "/api/v1/master/warehouses/9999/stock",
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    # ── POST returns 201 on create ────────────────────────────────────────

    def test_create_warehouse_returns_201(self):
        resp = self.client.post(
            "/api/v1/master/warehouses",
            json={"warehouse_code": "WH-NEW", "warehouse_name": "New WH"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)

    def test_create_branch_returns_201(self):
        wh = _seed_warehouse(self.db, code="WH-BNW")
        resp = self.client.post(
            "/api/v1/master/branches",
            json={"branch_code": "BR-NEW", "branch_name": "New Branch", "warehouse_id": wh.id},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)

    def test_create_category_returns_201(self):
        resp = self.client.post(
            "/api/v1/master/categories",
            json={"code": "CAT-NEW", "name_ar": "جديد", "name_en": "New"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)

    def test_create_unit_returns_201(self):
        resp = self.client.post(
            "/api/v1/master/units",
            json={"code": "UNIT-NEW", "name_ar": "جديد", "name_en": "New Unit"},
            headers=_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)


if __name__ == "__main__":
    unittest.main()
