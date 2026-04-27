"""
Epic 3 — Daily Inventory Workflow Improvements
Unit tests covering:
  - URL prefix: /api/v1/inventory, /api/v1/auth, /api/v1/users, /api/v1/orders
  - PATCH single inventory line (counted_qty, variance_reason_id, notes)
  - Variance recalculation after line patch
  - Patch rejected for non-draft inventory
  - Submit idempotency (replay on X-Client-Request-Id)
  - Reopen rejected → draft
  - Reopen non-rejected fails
  - Delete draft inventory
  - Delete non-draft inventory blocked
  - GET /today returns status per branch
  - today: branch-scoped user sees only own branch
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
    Branch, BranchStock, DailyInventory, DailyInventoryLine,
    InventoryStatus, Item, ItemCategory, Role, RoleName,
    UnitOfMeasure, User, UserRole, Warehouse,
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

def _make_user(db, username, role_name, branch_id=None) -> tuple:
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, display_name=role_name.value)
        db.add(role)
        db.flush()
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name=username,
        hashed_password=get_password_hash("Pass@1234"),
        branch_id=branch_id,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    return user


def _login(client, username) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "Pass@1234"}
    )
    return resp.json()["access_token"]


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_master(db):
    wh = Warehouse(warehouse_code="WH01", warehouse_name="Main WH")
    db.add(wh)
    db.flush()
    br = Branch(branch_code="BR01", branch_name="Branch 1", warehouse_id=wh.id)
    db.add(br)
    db.flush()
    cat = ItemCategory(code="CAT01", name_ar="تصنيف", name_en="Cat")
    db.add(cat)
    db.flush()
    unit = UnitOfMeasure(code="KG", name_ar="كيلو", name_en="KG")
    db.add(unit)
    db.flush()
    item = Item(
        item_code="ITEM01", item_name_ar="صنف", item_name_en="Item",
        category_id=cat.id, unit_id=unit.id,
        min_qty=Decimal("5"), max_qty=Decimal("100"),
    )
    db.add(item)
    db.flush()
    stock = BranchStock(
        branch_id=br.id, item_id=item.id,
        current_qty=Decimal("20"), reserved_qty=Decimal("0"), in_transit_qty=Decimal("0"),
    )
    db.add(stock)
    db.commit()
    return wh, br, item


def _create_draft_inventory(db, br_id, item_id, counted_qty=Decimal("18"), user_id=None) -> DailyInventory:
    inv = DailyInventory(
        branch_id=br_id,
        inventory_date=date.today(),
        status=InventoryStatus.draft,
        created_by=user_id or 1,
    )
    db.add(inv)
    db.flush()
    item_row = db.query(Item).filter(Item.id == item_id).first()
    min_q = item_row.min_qty if item_row and item_row.min_qty is not None else Decimal("0")
    below_min = bool(item_row and counted_qty < min_q)
    line = DailyInventoryLine(
        inventory_id=inv.id,
        item_id=item_id,
        book_qty=Decimal("20"),
        counted_qty=counted_qty,
        variance_qty=counted_qty - Decimal("20"),
        variance_pct=Decimal("-10"),
        variance_status="warning",
        below_min_flag=below_min,
        out_of_stock_flag=False,
    )
    db.add(line)
    db.commit()
    db.refresh(inv)
    return inv


# ─────────────────────────────────────────────────────────────────────────
# Test class
# ─────────────────────────────────────────────────────────────────────────

class Epic3InventoryWorkflowTests(unittest.TestCase):

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        self.cm = TestClient(app, raise_server_exceptions=False)
        self.client = self.cm.__enter__()

        self.wh, self.br, self.item = _seed_master(self.db)
        self.admin = _make_user(self.db, "admin3", RoleName.admin)
        self.branch_user = _make_user(
            self.db, "bu3", RoleName.branch_user, branch_id=self.br.id
        )
        self.admin_token = _login(self.client, "admin3")
        self.bu_token = _login(self.client, "bu3")

    def tearDown(self):
        self.cm.__exit__(None, None, None)
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    # ── URL prefix ────────────────────────────────────────────────────────

    def test_auth_endpoint_on_v1_prefix(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin3", "password": "Pass@1234"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access_token", resp.json())

    def test_old_auth_prefix_gone(self):
        resp = self.client.post(
            "/api/auth/login",
            json={"username": "admin3", "password": "Pass@1234"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_inventory_list_on_v1_prefix(self):
        resp = self.client.get("/api/v1/inventory/", headers=_auth(self.admin_token))
        self.assertEqual(resp.status_code, 200)

    def test_old_inventory_prefix_gone(self):
        resp = self.client.get("/api/inventory/", headers=_auth(self.admin_token))
        self.assertEqual(resp.status_code, 404)

    # ── PATCH single line ─────────────────────────────────────────────────

    def test_patch_line_updates_counted_qty_and_recalculates_variance(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        line = inv.lines[0]

        resp = self.client.patch(
            f"/api/v1/inventory/{inv.id}/lines/{line.id}",
            json={"counted_qty": "25.000"},
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        updated_line = next(l for l in data["lines"] if l["id"] == line.id)
        self.assertEqual(Decimal(updated_line["counted_qty"]), Decimal("25"))
        # variance_qty = 25 - 20 = +5
        self.assertEqual(Decimal(updated_line["variance_qty"]), Decimal("5"))
        self.assertFalse(updated_line["out_of_stock_flag"])

    def test_patch_line_out_of_stock_flag_set_when_counted_zero(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        line = inv.lines[0]

        resp = self.client.patch(
            f"/api/v1/inventory/{inv.id}/lines/{line.id}",
            json={"counted_qty": "0"},
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 200)
        updated_line = next(l for l in resp.json()["lines"] if l["id"] == line.id)
        self.assertTrue(updated_line["out_of_stock_flag"])

    def test_patch_line_only_updates_provided_fields(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        line = inv.lines[0]

        # Patch only notes — counted_qty should not change
        resp = self.client.patch(
            f"/api/v1/inventory/{inv.id}/lines/{line.id}",
            json={"notes": "checked manually"},
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 200)
        updated_line = next(l for l in resp.json()["lines"] if l["id"] == line.id)
        self.assertEqual(Decimal(updated_line["counted_qty"]), Decimal("18"))  # unchanged

    def test_patch_line_blocked_for_submitted_inventory(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        inv.status = InventoryStatus.submitted
        self.db.commit()
        line = inv.lines[0]

        resp = self.client.patch(
            f"/api/v1/inventory/{inv.id}/lines/{line.id}",
            json={"counted_qty": "10"},
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "inventory.not_draft")

    def test_patch_line_404_for_unknown_line(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        resp = self.client.patch(
            f"/api/v1/inventory/{inv.id}/lines/9999",
            json={"counted_qty": "10"},
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error_code"], "inventory.line_not_found")

    def test_patch_line_negative_qty_returns_422(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        line = inv.lines[0]
        resp = self.client.patch(
            f"/api/v1/inventory/{inv.id}/lines/{line.id}",
            json={"counted_qty": "-1"},
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 422)

    # ── Submit idempotency ────────────────────────────────────────────────

    def test_submit_with_same_idempotency_key_replays_without_error(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        # Submit once
        r1 = self.client.post(
            f"/api/v1/inventory/{inv.id}/submit",
            headers={**_auth(self.bu_token), "X-Client-Request-Id": "sub-idem-001"},
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["status"], "submitted")

        # Submit again with same key — should not raise
        r2 = self.client.post(
            f"/api/v1/inventory/{inv.id}/submit",
            headers={**_auth(self.bu_token), "X-Client-Request-Id": "sub-idem-001"},
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["status"], "submitted")

    # ── Reopen ────────────────────────────────────────────────────────────

    def test_reopen_rejected_inventory_moves_to_draft(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        inv.status = InventoryStatus.rejected
        inv.rejection_reason = "Too many variances"
        self.db.commit()

        resp = self.client.post(
            f"/api/v1/inventory/{inv.id}/reopen",
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "draft")

    def test_reopen_clears_rejection_reason(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        inv.status = InventoryStatus.rejected
        inv.rejection_reason = "Bad counts"
        self.db.commit()

        self.client.post(
            f"/api/v1/inventory/{inv.id}/reopen",
            headers=_auth(self.bu_token),
        )
        self.db.expire(inv)
        self.db.refresh(inv)
        self.assertIsNone(inv.rejection_reason)

    def test_reopen_non_rejected_inventory_returns_400(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        # Still draft
        resp = self.client.post(
            f"/api/v1/inventory/{inv.id}/reopen",
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "inventory.cannot_reopen")

    # ── Delete draft ──────────────────────────────────────────────────────

    def test_delete_draft_inventory_removes_it_from_db(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        inv_id = inv.id

        resp = self.client.delete(
            f"/api/v1/inventory/{inv_id}",
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 200)

        gone = self.db.query(DailyInventory).filter(DailyInventory.id == inv_id).first()
        self.assertIsNone(gone)

    def test_delete_draft_also_removes_lines(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        line_id = inv.lines[0].id
        inv_id = inv.id

        self.client.delete(f"/api/v1/inventory/{inv_id}", headers=_auth(self.bu_token))

        line_gone = self.db.query(DailyInventoryLine).filter(
            DailyInventoryLine.id == line_id
        ).first()
        self.assertIsNone(line_gone)

    def test_delete_submitted_inventory_returns_400(self):
        inv = _create_draft_inventory(self.db, self.br.id, self.item.id, user_id=self.branch_user.id)
        inv.status = InventoryStatus.submitted
        self.db.commit()

        resp = self.client.delete(
            f"/api/v1/inventory/{inv.id}",
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error_code"], "inventory.cannot_delete")

    def test_delete_nonexistent_inventory_returns_404(self):
        resp = self.client.delete(
            "/api/v1/inventory/9999",
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 404)

    # ── Today status ──────────────────────────────────────────────────────

    def test_today_status_returns_all_branches_for_admin(self):
        # Create a second branch
        br2 = Branch(
            branch_code="BR02", branch_name="Branch 2", warehouse_id=self.wh.id
        )
        self.db.add(br2)
        self.db.commit()

        resp = self.client.get(
            "/api/v1/inventory/today",
            headers=_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        branch_ids = [r["branch_id"] for r in resp.json()]
        self.assertIn(self.br.id, branch_ids)
        self.assertIn(br2.id, branch_ids)

    def test_today_status_shows_not_started_when_no_inventory(self):
        resp = self.client.get(
            "/api/v1/inventory/today",
            headers=_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        record = next(r for r in resp.json() if r["branch_id"] == self.br.id)
        self.assertIsNone(record["status"])
        self.assertIsNone(record["inventory_id"])

    def test_today_status_shows_draft_when_inventory_exists(self):
        _create_draft_inventory(
            self.db, self.br.id, self.item.id, user_id=self.branch_user.id
        )
        resp = self.client.get(
            "/api/v1/inventory/today",
            headers=_auth(self.admin_token),
        )
        record = next(r for r in resp.json() if r["branch_id"] == self.br.id)
        self.assertEqual(record["status"], "draft")
        self.assertIsNotNone(record["inventory_id"])

    def test_today_status_branch_user_sees_only_own_branch(self):
        # Add a second branch — branch user should not see it
        br2 = Branch(
            branch_code="BR03", branch_name="Branch 3", warehouse_id=self.wh.id
        )
        self.db.add(br2)
        self.db.commit()

        resp = self.client.get(
            "/api/v1/inventory/today",
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 200)
        branch_ids = [r["branch_id"] for r in resp.json()]
        self.assertIn(self.br.id, branch_ids)
        self.assertNotIn(br2.id, branch_ids)

    def test_today_status_counts_low_stock_lines(self):
        # counted_qty = 2, min_qty = 5  → below_min_flag = True
        _create_draft_inventory(
            self.db, self.br.id, self.item.id,
            counted_qty=Decimal("2"),
            user_id=self.branch_user.id,
        )
        resp = self.client.get(
            "/api/v1/inventory/today",
            headers=_auth(self.admin_token),
        )
        record = next(r for r in resp.json() if r["branch_id"] == self.br.id)
        self.assertEqual(record["items_below_min"], 1)

    # ── create inventory returns 201 ──────────────────────────────────────

    def test_create_inventory_returns_201(self):
        resp = self.client.post(
            "/api/v1/inventory/",
            json={
                "branch_id": self.br.id,
                "inventory_date": str(date.today()),
                "lines": [{"item_id": self.item.id, "counted_qty": "15.000"}],
            },
            headers=_auth(self.bu_token),
        )
        self.assertEqual(resp.status_code, 201)


if __name__ == "__main__":
    unittest.main()
