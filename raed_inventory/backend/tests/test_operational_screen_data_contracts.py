"""
Operational screen data contracts — verify UI-facing endpoints return required fields.

These tests hit the same REST paths used by SupplyChainPages.jsx and BranchRequestDetailPage.jsx.
PostgreSQL only; RATE_LIMIT_ENABLED=false in module fixture.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.main import app
from app.models import BranchRequest, WarehouseLine, WarehouseLineStatus

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Operational screen data contract tests require PostgreSQL",
    ),
]

PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")

# UI screen → endpoint mapping (SupplyChainPages / BranchRequestDetailPage)
UI_ENDPOINTS = {
    "branch_requests_list": "/api/v1/branch-requests",
    "branch_request_detail": "/api/v1/branch-requests/{id}/detail",
    "area_approvals_list": "/api/v1/branch-requests?status=SUBMITTED",
    "kitchen_production_queue": "/api/v1/production-orders",
    "warehouse_execution_list": "/api/v1/warehouse-lines",
    "delivery_orders_list": "/api/v1/delivery-orders",
}


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


def _branch_linked_warehouse_line(rows: list[dict]) -> dict | None:
    for row in rows:
        if row.get("branch_id") and row.get("branch_name"):
            return row
    return None


@pytest.fixture(scope="module")
def sample_branch_request_id() -> int:
    db = SessionLocal()
    try:
        row = db.query(BranchRequest).order_by(BranchRequest.id.desc()).first()
        if not row:
            pytest.skip("No branch requests in database")
        return row.id
    finally:
        db.close()


class TestWarehouseExecutionDataContract:
    """SupplyChainWarehousePage → GET /api/v1/warehouse-lines"""

    def test_list_includes_branch_and_stock_fields(self, client: TestClient):
        token = _login(client, "warehouse_dammam_manager")
        r = client.get(UI_ENDPOINTS["warehouse_execution_list"], headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows, "Expected at least one warehouse line for dammam manager"
        line = _branch_linked_warehouse_line(rows)
        assert line, "Expected branch-linked warehouse line with branch_name"
        assert "branch_name" in line
        assert "available_stock" in line
        assert "current_stock" in line
        assert "reserved_stock" in line
        assert line["available_stock"] is not None or line["current_stock"] is not None

    def test_get_detail_includes_branch_and_stock_fields(self, client: TestClient):
        token = _login(client, "warehouse_dammam_manager")
        rows = client.get(UI_ENDPOINTS["warehouse_execution_list"], headers=_headers(token)).json()
        line = _branch_linked_warehouse_line(rows)
        assert line
        r = client.get(f"/api/v1/warehouse-lines/{line['id']}", headers=_headers(token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("branch_name") == line["branch_name"]
        assert "available_stock" in data
        assert "current_stock" in data

    def test_mutation_response_includes_enriched_fields(self, client: TestClient):
        token = _login(client, "warehouse_dammam_manager")
        db = SessionLocal()
        try:
            pending = (
                db.query(WarehouseLine)
                .filter(WarehouseLine.status == WarehouseLineStatus.PENDING)
                .order_by(WarehouseLine.id.desc())
                .first()
            )
        finally:
            db.close()
        if not pending:
            pytest.skip("No PENDING warehouse line for receive mutation contract test")
        r = client.post(
            f"/api/v1/warehouse-lines/{pending.id}/receive",
            headers={**_headers(token), "X-Idempotency-Key": f"contract-receive-{pending.id}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("branch_name"), "Receive response must include branch_name for UI refresh"
        assert "available_stock" in data
        assert "current_stock" in data


class TestBranchRequestDataContract:
    """Branch requests list + detail screens."""

    def test_branch_list_includes_branch_name(self, client: TestClient):
        token = _login(client, "branch_onda_1_arkan")
        r = client.get(f"{UI_ENDPOINTS['branch_requests_list']}?page_size=5", headers=_headers(token))
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert items
        assert items[0].get("request_no")
        assert items[0].get("branch_name")

    def test_branch_detail_includes_owner_timeline_quantities(
        self, client: TestClient, sample_branch_request_id: int
    ):
        token = _login(client, "branch_onda_1_arkan")
        path = UI_ENDPOINTS["branch_request_detail"].format(id=sample_branch_request_id)
        r = client.get(path, headers=_headers(token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("branch_name")
        summary = data.get("status_summary") or {}
        assert summary.get("current_owner_ar")
        assert summary.get("next_action_ar")
        assert isinstance(data.get("timeline"), list)
        assert data["timeline"], "Expected non-empty timeline for seeded request"
        fulfillment = data.get("fulfillment_lines") or []
        assert fulfillment
        fl = fulfillment[0]
        for key in ("requested_qty", "issued_qty", "delivered_qty", "remaining_qty"):
            assert key in fl


class TestAreaManagerDataContract:
    """SupplyChainApprovalsPage → GET /api/v1/branch-requests?status=SUBMITTED"""

    def test_pending_list_includes_branch_name(self, client: TestClient):
        token = _login(client, "area_dammam_onda")
        r = client.get(f"{UI_ENDPOINTS['area_approvals_list']}&page_size=20", headers=_headers(token))
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        if not items:
            pytest.skip("No SUBMITTED branch requests in scope")
        assert items[0].get("branch_name")
        assert items[0].get("request_no")
        assert items[0].get("status") == "SUBMITTED"


class TestKitchenProductionDataContract:
    """Kitchen production queue → GET /api/v1/production-orders"""

    def test_list_includes_branch_and_status(self, client: TestClient):
        token = _login(client, "kitchen_dammam_bakery_and_sweets_mgr")
        r = client.get(UI_ENDPOINTS["kitchen_production_queue"], headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows
        row = rows[0]
        assert row.get("branch_name")
        assert row.get("status")
        assert row.get("item") or row.get("item_id")

    def test_get_includes_branch_name(self, client: TestClient):
        token = _login(client, "kitchen_dammam_bakery_and_sweets_mgr")
        rows = client.get(UI_ENDPOINTS["kitchen_production_queue"], headers=_headers(token)).json()
        order_id = rows[0]["id"]
        r = client.get(f"/api/v1/production-orders/{order_id}", headers=_headers(token))
        assert r.status_code == 200, r.text
        assert r.json().get("branch_name")


class TestDeliveryDataContract:
    """SupplyChainDeliveryPage → GET /api/v1/delivery-orders"""

    def test_list_includes_branch_and_line_quantities(self, client: TestClient):
        token = _login(client, "delivery_dammam")
        r = client.get(UI_ENDPOINTS["delivery_orders_list"], headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows
        order = rows[0]
        assert order.get("branch_name")
        assert order.get("status")
        lines = order.get("lines") or []
        assert lines
        line = lines[0]
        for key in ("qty_dispatched", "qty_delivered", "shortage_qty"):
            assert key in line
        assert line.get("item") or line.get("item_id")

    def test_get_includes_branch_name(self, client: TestClient):
        token = _login(client, "delivery_dammam")
        rows = client.get(UI_ENDPOINTS["delivery_orders_list"], headers=_headers(token)).json()
        order_id = rows[0]["id"]
        r = client.get(f"/api/v1/delivery-orders/{order_id}", headers=_headers(token))
        assert r.status_code == 200, r.text
        assert r.json().get("branch_name")
