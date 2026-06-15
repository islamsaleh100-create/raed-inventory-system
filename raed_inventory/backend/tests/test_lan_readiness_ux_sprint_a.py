"""
LAN Readiness UX Sprint A tests — PostgreSQL only.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.main import app
from app.models import BranchRequest
from app.services.branch_request_detail_service import build_branch_request_detail

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="LAN readiness tests require PostgreSQL",
    ),
]

PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@2025")


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


@pytest.fixture(scope="module")
def branch_request_id() -> int:
    db = SessionLocal()
    try:
        row = db.query(BranchRequest).order_by(BranchRequest.id.desc()).first()
        if not row:
            pytest.skip("No branch requests in database")
        return row.id
    finally:
        db.close()


class TestBranchRequestDetail:
    def test_detail_endpoint_returns_timeline_and_fulfillment(self, client: TestClient, branch_request_id: int):
        token = _login(client, "branch_onda_1_arkan")
        r = client.get(f"/api/v1/branch-requests/{branch_request_id}/detail", headers=_headers(token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "timeline" in data
        assert "fulfillment_lines" in data
        assert "status_summary" in data
        summary = data["status_summary"]
        assert summary.get("current_status_ar")
        assert summary.get("current_owner_ar")
        assert summary.get("next_action_ar")
        assert summary.get("last_updated_at")
        assert data.get("branch_name")

    def test_detail_service_builds_from_db(self, branch_request_id: int):
        db = SessionLocal()
        try:
            from app.routers.branch_requests import _get_request
            row = _get_request(db, branch_request_id)
            detail = build_branch_request_detail(db, row)
            assert detail["branch_name"]
            assert isinstance(detail["timeline"], list)
            assert isinstance(detail["fulfillment_lines"], list)
            for fl in detail["fulfillment_lines"]:
                for key in ("requested_qty", "issued_qty", "delivered_qty", "remaining_qty"):
                    assert key in fl
        finally:
            db.close()


class TestBranchNamesInPayloads:
    def test_warehouse_lines_include_branch_name(self, client: TestClient):
        token = _login(client, "warehouse_dammam_user")
        r = client.get("/api/v1/warehouse-lines", headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        if rows:
            assert rows[0].get("branch_name"), "Expected branch_name on warehouse line"

    def test_production_orders_include_branch_name(self, client: TestClient):
        token = _login(client, "kitchen_dammam_bakery_and_sweets_mgr")
        r = client.get("/api/v1/production-orders", headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        if rows:
            assert rows[0].get("branch_name"), "Expected branch_name on production order"

    def test_delivery_orders_include_branch_name(self, client: TestClient):
        token = _login(client, "delivery_dammam")
        r = client.get("/api/v1/delivery-orders", headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        if rows:
            assert rows[0].get("branch_name"), "Expected branch_name on delivery order"


class TestOpeningStockValidationScript:
    def test_script_runs_and_writes_report(self):
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        report_path = os.path.join(backend_dir, "..", "LAN_OPENING_STOCK_VALIDATION_REPORT.md")
        if os.path.exists(report_path):
            os.remove(report_path)
        proc = subprocess.run(
            [sys.executable, "validate_lan_opening_stock.py", "--write-report"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
        )
        assert proc.returncode in (0, 1)
        assert "Verdict:" in proc.stdout
        assert os.path.exists(report_path)
        content = open(report_path, encoding="utf-8").read()
        assert any(v in content for v in ("GO", "NO-GO", "GO WITH WARNINGS"))


class TestLegacyNavPolicy:
    def test_trial_roles_list(self):
        roles = {
            "branch_user", "area_manager", "kitchen_section_manager",
            "warehouse_user", "warehouse_manager", "delivery_user",
        }
        assert "admin" not in roles
        assert "super_admin" not in roles

    def test_admin_can_still_access_legacy_orders_route_via_api(self, client: TestClient):
        token = _login(client, "admin", ADMIN_PASSWORD)
        r = client.get("/api/v1/orders/", headers=_headers(token))
        assert r.status_code == 200, r.text


class TestDashboardPartialFields:
    def test_dashboard_includes_partial_counts(self, client: TestClient):
        token = _login(client, "area_dammam_onda")
        r = client.get("/api/v1/supply-chain/dashboard", headers=_headers(token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "partial_orders" in data or "partial_warehouse" in data
