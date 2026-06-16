"""
LAN Trial Blockers Sprint tests — PostgreSQL only.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.main import app
from app.models import BranchRequest, BranchRequestStatus
from app.services.branch_request_detail_service import build_branch_request_detail

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="LAN trial blocker tests require PostgreSQL",
    ),
]

PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@2025")
BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
SUPPLY_PAGES = FRONTEND_DIR / "src" / "pages" / "supply_chain" / "SupplyChainPages.jsx"
APP_LAYOUT = FRONTEND_DIR / "src" / "components" / "layout" / "AppLayoutV2.jsx"


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


class TestBranchNames:
    def test_warehouse_lines_include_branch_name(self, client: TestClient):
        token = _login(client, "warehouse_dammam_user")
        r = client.get("/api/v1/warehouse-lines", headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        if rows:
            assert rows[0].get("branch_name")

    def test_production_orders_include_branch_name(self, client: TestClient):
        token = _login(client, "kitchen_dammam_bakery_and_sweets_mgr")
        r = client.get("/api/v1/production-orders", headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        if rows:
            assert rows[0].get("branch_name")

    def test_delivery_list_and_detail_include_branch_name(self, client: TestClient):
        token = _login(client, "delivery_dammam")
        r = client.get("/api/v1/delivery-orders", headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        if not rows:
            pytest.skip("No delivery orders in database")
        assert rows[0].get("branch_name")
        detail = client.get(f"/api/v1/delivery-orders/{rows[0]['id']}", headers=_headers(token))
        assert detail.status_code == 200, detail.text
        assert detail.json().get("branch_name")

    def test_request_detail_includes_branch_name(self, client: TestClient, branch_request_id: int):
        token = _login(client, "branch_onda_1_arkan")
        r = client.get(f"/api/v1/branch-requests/{branch_request_id}/detail", headers=_headers(token))
        assert r.status_code == 200, r.text
        assert r.json().get("branch_name")


class TestCurrentOwnerAndNextAction:
    def test_detail_status_summary_fields(self, client: TestClient, branch_request_id: int):
        token = _login(client, "branch_onda_1_arkan")
        r = client.get(f"/api/v1/branch-requests/{branch_request_id}/detail", headers=_headers(token))
        assert r.status_code == 200, r.text
        summary = r.json()["status_summary"]
        assert summary.get("current_owner_ar")
        assert summary.get("next_action_ar")

    def test_workflow_owner_not_empty_for_known_statuses(self, branch_request_id: int):
        db = SessionLocal()
        try:
            from app.routers.branch_requests import _get_request
            row = _get_request(db, branch_request_id)
            detail = build_branch_request_detail(db, row)
            owner = detail["status_summary"]["current_owner_ar"]
            nxt = detail["status_summary"]["next_action_ar"]
            assert owner and owner != "—" or row.status == BranchRequestStatus.AREA_REJECTED
            assert nxt
        finally:
            db.close()


class TestAvailableStockVisibility:
    def test_warehouse_lines_expose_stock_fields(self, client: TestClient):
        token = _login(client, "warehouse_dammam_user")
        r = client.get("/api/v1/warehouse-lines", headers=_headers(token))
        assert r.status_code == 200, r.text
        rows = r.json()
        if not rows:
            pytest.skip("No warehouse lines in database")
        first = rows[0]
        for key in ("available_stock", "current_stock", "reserved_stock", "requested_qty", "issued_qty", "pending_qty"):
            assert key in first


class TestSearchAndFilters:
    def test_branch_requests_search_param_accepted(self, client: TestClient):
        token = _login(client, "area_dammam_onda")
        r = client.get(
            "/api/v1/branch-requests",
            params={"search": "BR", "page_size": 10},
            headers=_headers(token),
        )
        assert r.status_code == 200, r.text
        assert "items" in r.json()

    def test_branch_requests_status_and_date_filters(self, client: TestClient):
        token = _login(client, "area_dammam_onda")
        r = client.get(
            "/api/v1/branch-requests",
            params={"status": "SUBMITTED", "date_from": "2020-01-01T00:00:00", "page_size": 10},
            headers=_headers(token),
        )
        assert r.status_code == 200, r.text

    def test_warehouse_lines_filters(self, client: TestClient):
        token = _login(client, "warehouse_dammam_user")
        r = client.get(
            "/api/v1/warehouse-lines",
            params={"search": "Onda", "status": "PENDING"},
            headers=_headers(token),
        )
        assert r.status_code == 200, r.text

    def test_delivery_orders_filters(self, client: TestClient):
        token = _login(client, "delivery_dammam")
        r = client.get(
            "/api/v1/delivery-orders",
            params={"search": "Khobar", "status": "READY"},
            headers=_headers(token),
        )
        assert r.status_code == 200, r.text


class TestConfirmDialogsPresent:
    def test_supply_chain_pages_define_required_confirms(self):
        text = SUPPLY_PAGES.read_text(encoding="utf-8")
        required_titles = [
            "تأكيد الاعتماد",
            "تأكيد الرفض",
            "تأكيد الصرف الكامل",
            "تأكيد الصرف الجزئي",
            "تأكيد إنشاء أمر تسليم",
            "تأكيد خروج للتسليم",
            "تأكيد التسليم",
        ]
        for title in required_titles:
            assert title in text, f"Missing confirm dialog: {title}"


class TestLegacyNavigationHiding:
    def test_trial_roles_hide_legacy_paths_in_layout(self):
        layout = APP_LAYOUT.read_text(encoding="utf-8")
        assert "LEGACY_TRIAL_HIDDEN_PATHS" in layout
        assert "isLegacyHiddenForTrial" in layout
        assert "/orders" in layout
        assert "warehouse_user" in layout

    def test_admin_legacy_orders_api_still_works(self, client: TestClient):
        token = _login(client, "admin", ADMIN_PASSWORD)
        r = client.get("/api/v1/orders/", headers=_headers(token))
        assert r.status_code == 200, r.text


class TestOpeningStockValidation:
    def test_script_runs_and_writes_report(self):
        report_path = BACKEND_DIR.parent / "LAN_OPENING_STOCK_VALIDATION_REPORT.md"
        if report_path.exists():
            report_path.unlink()
        proc = subprocess.run(
            [sys.executable, "validate_lan_opening_stock.py", "--write-report"],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
        )
        assert proc.returncode in (0, 1)
        assert "Verdict:" in proc.stdout
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert any(v in content for v in ("GO", "NO-GO", "GO WITH WARNINGS"))
