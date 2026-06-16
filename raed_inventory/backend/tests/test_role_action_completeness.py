"""
Role action completeness audit — required screens/actions reachable (PostgreSQL).
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
from app.models import Branch, BranchBrand, Item, ItemBrand, SupplySourceType

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Role action completeness tests require PostgreSQL",
    ),
]

PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@2025")
AUDITOR_PASSWORD = os.environ.get("INTERNAL_AUDITOR_PASSWORD", "Raed@2025")

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"
APP_LAYOUT = FRONTEND / "src" / "components" / "layout" / "AppLayoutV2.jsx"
DETAIL_PAGE = FRONTEND / "src" / "pages" / "supply_chain" / "BranchRequestDetailPage.jsx"
SUPPLY_PAGES = FRONTEND / "src" / "pages" / "supply_chain" / "SupplyChainPages.jsx"


@pytest.fixture(scope="module")
def client() -> TestClient:
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    return TestClient(app)


def _login(client: TestClient, username: str, password: str = PASSWORD) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


ROLE_REQUIRED_GETS: dict[str, list[str]] = {
    "branch_onda_1_arkan": [
        "/api/v1/supply-chain/dashboard",
        "/api/v1/branch-requests",
        "/api/v1/notifications/summary",
    ],
    "area_dammam_onda": [
        "/api/v1/supply-chain/dashboard",
        "/api/v1/branch-requests",
        "/api/v1/branch-requests?status=SUBMITTED&page_size=5",
        "/api/v1/notifications/summary",
    ],
    "kitchen_dammam_bakery_and_sweets_mgr": [
        "/api/v1/supply-chain/dashboard",
        "/api/v1/production-orders",
        "/api/v1/notifications/summary",
    ],
    "warehouse_dammam_user": [
        "/api/v1/supply-chain/dashboard",
        "/api/v1/warehouse-lines",
        "/api/v1/notifications/summary",
    ],
    "warehouse_dammam_manager": [
        "/api/v1/supply-chain/dashboard",
        "/api/v1/warehouse-lines",
    ],
    "delivery_dammam": [
        "/api/v1/supply-chain/dashboard",
        "/api/v1/delivery-orders",
        "/api/v1/notifications/summary",
    ],
    "admin": [
        "/api/v1/supply-chain/dashboard",
        "/api/v1/orders/",
    ],
    "super.admin": [
        "/api/v1/supply-chain/super-admin-overview",
        "/api/v1/branch-requests",
    ],
    "audit.officer": [
        "/api/v1/audit/findings/dashboard/summary",
        "/api/v1/branch-requests",
        "/api/v1/warehouse-lines",
        "/api/v1/delivery-orders",
    ],
}


class TestRequiredEndpointsReachable:
    @pytest.mark.parametrize("username,paths", [
        (user, paths) for user, paths in ROLE_REQUIRED_GETS.items()
    ])
    def test_role_can_reach_daily_endpoints(self, client: TestClient, username: str, paths: list[str]):
        pwd = ADMIN_PASSWORD if username == "admin" else AUDITOR_PASSWORD if username == "audit.officer" else PASSWORD
        token = _login(client, username, pwd)
        for path in paths:
            r = client.get(path, headers=_headers(token))
            assert r.status_code == 200, f"{username} GET {path}: {r.status_code} {r.text[:200]}"


class TestBranchUserSubmitDraftCompleteness:
    def test_branch_user_can_submit_saved_draft(self, client: TestClient):
        token = _login(client, "branch_onda_1_arkan")
        db = SessionLocal()
        try:
            branch = db.query(Branch).filter(Branch.branch_code == "BR-DM-ON-ARKAN").first()
            assert branch
            brand_link = db.query(BranchBrand).filter(BranchBrand.branch_id == branch.id).first()
            assert brand_link
            item = (
                db.query(Item)
                .join(ItemBrand, ItemBrand.item_id == Item.id)
                .filter(
                    ItemBrand.brand_id == brand_link.brand_id,
                    Item.active == True,
                    Item.branch_requestable == True,
                    Item.source_type == SupplySourceType.WAREHOUSE,
                    Item.is_deleted == False,
                )
                .first()
            )
            assert item
            brand_id = brand_link.brand_id
            branch_id = branch.id
            item_id = item.id
        finally:
            db.close()

        create = client.post(
            "/api/v1/branch-requests",
            json={
                "branch_id": branch_id,
                "brand_id": brand_id,
                "lines": [{"item_id": item_id, "qty_requested": "2"}],
            },
            headers={**_headers(token), "X-Idempotency-Key": str(uuid4())},
        )
        assert create.status_code == 201, create.text
        request_id = create.json()["id"]
        assert create.json()["status"] == "DRAFT"

        submit = client.post(
            f"/api/v1/branch-requests/{request_id}/submit",
            headers={**_headers(token), "X-Idempotency-Key": str(uuid4())},
        )
        assert submit.status_code == 200, submit.text
        assert submit.json()["status"] == "SUBMITTED"

        detail = client.get(f"/api/v1/branch-requests/{request_id}/detail", headers=_headers(token))
        assert detail.status_code == 200, detail.text
        assert detail.json().get("timeline") is not None


class TestAreaManagerScopedListCompleteness:
    def test_area_manager_list_without_branch_id(self, client: TestClient):
        token = _login(client, "area_dammam_onda")
        r = client.get("/api/v1/branch-requests", params={"page_size": 20}, headers=_headers(token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body


class TestFrontendCompletenessArtifacts:
    def test_notifications_in_sidebar_nav(self):
        text = APP_LAYOUT.read_text(encoding="utf-8")
        assert "to: '/notifications'" in text
        assert "nav.notifications" in text

    def test_submit_draft_on_detail_page(self):
        text = DETAIL_PAGE.read_text(encoding="utf-8")
        assert "submitBranchRequest" in text
        assert "request.status === 'DRAFT'" in text

    def test_submit_draft_on_list_page(self):
        text = SUPPLY_PAGES.read_text(encoding="utf-8")
        assert "handleSubmitDraft" in text

    def test_delivery_shortage_inputs_present(self):
        text = SUPPLY_PAGES.read_text(encoding="utf-8")
        assert "shortageReason" in text
        assert "qty_received" in text

    def test_kitchen_status_action_helpers(self):
        text = SUPPLY_PAGES.read_text(encoding="utf-8")
        assert "productionCanSendToWarehouse" in text

    def test_warehouse_stock_columns(self):
        text = SUPPLY_PAGES.read_text(encoding="utf-8")
        assert "المخزون المتاح" in text


class TestInternalAuditorReadCompleteness:
    def test_auditor_detail_endpoint(self, client: TestClient):
        token = _login(client, "area_dammam_onda")
        listed = client.get(
            "/api/v1/branch-requests",
            params={"page_size": 1},
            headers=_headers(token),
        )
        items = listed.json().get("items") or []
        if not items:
            pytest.skip("No branch requests for detail test")
        request_id = items[0]["id"]
        auditor = _login(client, "audit.officer", AUDITOR_PASSWORD)
        r = client.get(f"/api/v1/branch-requests/{request_id}/detail", headers=_headers(auditor))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("timeline") is not None
        assert data.get("status_summary")
