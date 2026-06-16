"""
Branch request catalog UI — LAN trial validation.

Requires PostgreSQL raed_lan_trial (set DATABASE_URL).
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.main import app
from app.models import (
    Branch,
    BranchBrand,
    BranchRequestStatus,
    Brand,
    Item,
    ItemBrand,
    ItemType,
    ProductionOrder,
    SupplySourceType,
    User,
    WarehouseLine,
)

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Branch request catalog tests require PostgreSQL",
    ),
    pytest.mark.skipif(
        "lan_trial" not in (os.environ.get("DATABASE_URL") or engine.url.database or ""),
        reason="Branch request catalog tests require raed_lan_trial database",
    ),
]

BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
SUPPLY_PAGES = FRONTEND_DIR / "src" / "pages" / "supply_chain" / "SupplyChainPages.jsx"
CATALOG_FORM = FRONTEND_DIR / "src" / "pages" / "supply_chain" / "BranchRequestCatalogForm.jsx"

BRANCH_USER = "branch_onda_1_arkan"
AREA_MANAGER = "area_dammam_onda"
TRIAL_PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "LanTrial@2026Temp")


@pytest.fixture(scope="module")
def client() -> TestClient:
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    return TestClient(app)


@pytest.fixture(scope="module")
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _login(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": TRIAL_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _branch_context(db: Session, username: str) -> dict:
    user = db.query(User).filter(User.username == username).first()
    assert user is not None
    branch = db.query(Branch).filter(Branch.id == user.branch_id).first()
    assert branch is not None
    brand_link = db.query(BranchBrand).filter(BranchBrand.branch_id == branch.id).first()
    assert brand_link is not None
    brand = db.query(Brand).filter(Brand.id == brand_link.brand_id).first()
    assert brand is not None
    return {"user": user, "branch": branch, "brand": brand}


def _allowed_items(client: TestClient, token: str, branch_id: int, brand_id: int) -> list[dict]:
    response = client.get(
        "/api/v1/branch-requests/allowed-items",
        params={"branch_id": branch_id, "brand_id": brand_id},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _find_item(db: Session, brand_id: int, source: SupplySourceType) -> Item | None:
    return (
        db.query(Item)
        .join(ItemBrand, ItemBrand.item_id == Item.id)
        .filter(
            ItemBrand.brand_id == brand_id,
            Item.active == True,
            Item.branch_requestable == True,
            Item.is_deleted == False,
            Item.source_type == source,
            Item.item_type != ItemType.raw_material,
        )
        .first()
    )


class TestBranchRequestCatalogFrontendSource:
    def test_branch_user_uses_catalog_form_not_legacy_dropdowns(self):
        pages = SUPPLY_PAGES.read_text(encoding="utf-8")
        catalog = CATALOG_FORM.read_text(encoding="utf-8")

        assert "BranchRequestCatalogForm" in pages
        assert "useCatalogForm" in pages
        assert "handleCatalogSubmit" in pages
        submit_block = pages.split("handleCatalogSubmit")[1].split("const handleCreate")[0]
        assert "source_type" not in submit_block

        assert 'data-testid="branch-request-catalog"' in catalog
        assert "إرسال الطلب" in catalog
        assert "بحث باسم الصنف" in catalog
        assert "فلتر التصنيف" in catalog
        assert "المصدر" not in catalog
        assert "source_type" not in catalog
        assert 'data-testid="catalog-submit-request"' in catalog
        assert "catalog-qty-" in catalog
        assert "الفرع:" in catalog
        assert "البراند:" in catalog
        assert "sc-branch-request-brand" not in pages.split("useCatalogForm &&")[1].split("!useCatalogForm")[0]

    def test_legacy_form_kept_for_admin_branch_selection(self):
        pages = SUPPLY_PAGES.read_text(encoding="utf-8")
        assert "sc-branch-request-source" in pages
        assert "!useCatalogForm" in pages


class TestBranchRequestCatalogAllowedItems:
    def test_allowed_items_match_branch_brand_rules(self, client: TestClient, db: Session):
        token = _login(client, BRANCH_USER)
        ctx = _branch_context(db, BRANCH_USER)
        items = _allowed_items(client, token, ctx["branch"].id, ctx["brand"].id)
        assert len(items) > 0

        allowed_ids = {row["id"] for row in items}
        brand_item_ids = {
            row.item_id
            for row in db.query(ItemBrand).filter(ItemBrand.brand_id == ctx["brand"].id).all()
        }

        for row in items:
            assert row["active"] is True
            assert row.get("branch_requestable") is True
            assert row["id"] in brand_item_ids
            assert row.get("source_type") != SupplySourceType.NOT_REQUESTABLE.value
            assert row.get("item_type") != ItemType.raw_material.value

        raw_in_brand = (
            db.query(Item)
            .join(ItemBrand, ItemBrand.item_id == Item.id)
            .filter(
                ItemBrand.brand_id == ctx["brand"].id,
                Item.item_type == ItemType.raw_material,
                Item.active == True,
            )
            .all()
        )
        for raw in raw_in_brand:
            assert raw.id not in allowed_ids

        inactive = (
            db.query(Item)
            .join(ItemBrand, ItemBrand.item_id == Item.id)
            .filter(ItemBrand.brand_id == ctx["brand"].id, Item.active == False)
            .first()
        )
        if inactive:
            assert inactive.id not in allowed_ids

        other_brand = db.query(Brand).filter(Brand.id != ctx["brand"].id, Brand.active == True).first()
        if other_brand:
            foreign = (
                db.query(Item)
                .join(ItemBrand, ItemBrand.item_id == Item.id)
                .filter(
                    ItemBrand.brand_id == other_brand.id,
                    Item.active == True,
                    Item.branch_requestable == True,
                    Item.item_type != ItemType.raw_material,
                )
                .first()
            )
            if foreign and foreign.id not in brand_item_ids:
                assert foreign.id not in allowed_ids


class TestBranchRequestCatalogSubmitFlow:
    def test_create_without_source_type_succeeds(self, client: TestClient, db: Session):
        token = _login(client, BRANCH_USER)
        ctx = _branch_context(db, BRANCH_USER)
        wh_item = _find_item(db, ctx["brand"].id, SupplySourceType.WAREHOUSE)
        assert wh_item is not None

        payload = {
            "branch_id": ctx["branch"].id,
            "brand_id": ctx["brand"].id,
            "lines": [{"item_id": wh_item.id, "qty_requested": "2"}],
        }
        created = client.post(
            "/api/v1/branch-requests",
            json=payload,
            headers={**_auth(token), "X-Idempotency-Key": f"catalog-wh-{uuid4()}"},
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["status"] == BranchRequestStatus.DRAFT.value

    def test_branch_source_override_is_ignored(self, client: TestClient, db: Session):
        token = _login(client, BRANCH_USER)
        ctx = _branch_context(db, BRANCH_USER)
        wh_item = _find_item(db, ctx["brand"].id, SupplySourceType.WAREHOUSE)
        assert wh_item is not None

        payload = {
            "branch_id": ctx["branch"].id,
            "brand_id": ctx["brand"].id,
            "lines": [
                {
                    "item_id": wh_item.id,
                    "qty_requested": "3",
                    "source_type": "KITCHEN",
                }
            ],
        }
        created = client.post(
            "/api/v1/branch-requests",
            json=payload,
            headers={**_auth(token), "X-Idempotency-Key": f"catalog-ignore-src-{uuid4()}"},
        )
        assert created.status_code == 201, created.text
        request_id = created.json()["id"]

        detail = client.get(f"/api/v1/branch-requests/{request_id}", headers=_auth(token))
        assert detail.status_code == 200, detail.text
        line = detail.json()["lines"][0]
        assert line["source_type"] in (SupplySourceType.WAREHOUSE.value, "WAREHOUSE")

    def test_warehouse_item_submit_and_auto_split(self, client: TestClient, db: Session):
        token = _login(client, BRANCH_USER)
        area_token = _login(client, AREA_MANAGER)
        ctx = _branch_context(db, BRANCH_USER)
        wh_item = _find_item(db, ctx["brand"].id, SupplySourceType.WAREHOUSE)
        assert wh_item is not None

        created = client.post(
            "/api/v1/branch-requests",
            json={
                "branch_id": ctx["branch"].id,
                "brand_id": ctx["brand"].id,
                "lines": [{"item_id": wh_item.id, "qty_requested": "4"}],
            },
            headers={**_auth(token), "X-Idempotency-Key": f"catalog-wh-flow-{uuid4()}"},
        )
        assert created.status_code == 201, created.text
        request_id = created.json()["id"]
        submitted = client.post(f"/api/v1/branch-requests/{request_id}/submit", headers=_auth(token))
        assert submitted.status_code == 200, submitted.text

        approved = client.post(
            f"/api/v1/branch-requests/{request_id}/approve",
            json={},
            headers={**_auth(area_token), "X-Idempotency-Key": f"catalog-wh-approve-{uuid4()}"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] in (
            BranchRequestStatus.SPLIT.value,
            BranchRequestStatus.IN_EXECUTION.value,
        )

        wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
        assert wh_line is not None

    def test_kitchen_item_submit_and_auto_split(self, client: TestClient, db: Session):
        token = _login(client, BRANCH_USER)
        area_token = _login(client, AREA_MANAGER)
        ctx = _branch_context(db, BRANCH_USER)
        kit_item = _find_item(db, ctx["brand"].id, SupplySourceType.KITCHEN)
        if kit_item is None:
            kit_item = (
                db.query(Item)
                .join(ItemBrand, ItemBrand.item_id == Item.id)
                .filter(
                    ItemBrand.brand_id == ctx["brand"].id,
                    Item.active == True,
                    Item.branch_requestable == True,
                    Item.source_type.in_([SupplySourceType.KITCHEN, SupplySourceType.BOTH]),
                )
                .first()
            )
        assert kit_item is not None

        created = client.post(
            "/api/v1/branch-requests",
            json={
                "branch_id": ctx["branch"].id,
                "brand_id": ctx["brand"].id,
                "lines": [{"item_id": kit_item.id, "qty_requested": "5"}],
            },
            headers={**_auth(token), "X-Idempotency-Key": f"catalog-kit-flow-{uuid4()}"},
        )
        assert created.status_code == 201, created.text
        request_id = created.json()["id"]
        submitted = client.post(f"/api/v1/branch-requests/{request_id}/submit", headers=_auth(token))
        assert submitted.status_code == 200, submitted.text

        approved = client.post(
            f"/api/v1/branch-requests/{request_id}/approve",
            json={},
            headers={**_auth(area_token), "X-Idempotency-Key": f"catalog-kit-approve-{uuid4()}"},
        )
        assert approved.status_code == 200, approved.text

        po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
        wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
        assert po is not None or wh_line is not None

    def test_only_positive_qty_lines_required(self, client: TestClient, db: Session):
        token = _login(client, BRANCH_USER)
        ctx = _branch_context(db, BRANCH_USER)
        wh_item = _find_item(db, ctx["brand"].id, SupplySourceType.WAREHOUSE)
        assert wh_item is not None

        bad = client.post(
            "/api/v1/branch-requests",
            json={
                "branch_id": ctx["branch"].id,
                "brand_id": ctx["brand"].id,
                "lines": [],
            },
            headers=_auth(token),
        )
        assert bad.status_code == 422

        bad_qty = client.post(
            "/api/v1/branch-requests",
            json={
                "branch_id": ctx["branch"].id,
                "brand_id": ctx["brand"].id,
                "lines": [{"item_id": wh_item.id, "qty_requested": "0"}],
            },
            headers=_auth(token),
        )
        assert bad_qty.status_code == 422
