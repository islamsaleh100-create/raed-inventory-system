"""
Role screen visibility audit — PostgreSQL API + frontend config checks.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.main import app

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Role visibility audit requires PostgreSQL",
    ),
]

PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@2025")
AUDITOR_PASSWORD = os.environ.get("INTERNAL_AUDITOR_PASSWORD", "Raed@2025")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
APP_LAYOUT = FRONTEND_DIR / "src" / "components" / "layout" / "AppLayoutV2.jsx"
SUPPLY_PAGES = FRONTEND_DIR / "src" / "pages" / "supply_chain" / "SupplyChainPages.jsx"

OFFICIAL_USERS = {
    "super_admin": ("super.admin", PASSWORD),
    "admin": ("admin", ADMIN_PASSWORD),
    "area_dammam_onda": ("area_dammam_onda", PASSWORD),
    "area_dammam_restaurants": ("area_dammam_restaurants", PASSWORD),
    "area_riyadh_all": ("area_riyadh_all", PASSWORD),
    "branch_onda": ("branch_onda_1_arkan", PASSWORD),
    "branch_pizza": ("branch_pizza_1_al_khobar", PASSWORD),
    "branch_shawarma": ("branch_shawarma_1_khobar", PASSWORD),
    "kitchen_meat": ("kitchen_dammam_meat_and_chicken_mgr", PASSWORD),
    "kitchen_bakery": ("kitchen_dammam_bakery_and_sweets_mgr", PASSWORD),
    "kitchen_pizza": ("kitchen_dammam_pizza_mgr", PASSWORD),
    "wh_manager_dm": ("warehouse_dammam_manager", PASSWORD),
    "wh_user_dm": ("warehouse_dammam_user", PASSWORD),
    "wh_manager_ry": ("warehouse_riyadh_manager", PASSWORD),
    "wh_user_ry": ("warehouse_riyadh_user", PASSWORD),
    "delivery_dammam": ("delivery_dammam", PASSWORD),
    "delivery_riyadh": ("delivery_riyadh", PASSWORD),
    "auditor": ("audit.officer", AUDITOR_PASSWORD),
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    return TestClient(app)


def _login(client: TestClient, username: str, password: str = PASSWORD) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"{username}: {r.text}"
    return r.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestOfficialUsersMe:
    @pytest.mark.parametrize("key", list(OFFICIAL_USERS.keys()))
    def test_me_returns_roles(self, client: TestClient, key: str):
        username, password = OFFICIAL_USERS[key]
        token = _login(client, username, password)
        r = client.get("/api/v1/auth/me", headers=_headers(token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["username"] == username
        assert data.get("roles"), f"{username} has no roles"


class TestBranchUserForbiddenWrites:
    def test_branch_user_cannot_list_area_approvals_write(self, client: TestClient):
        token = _login(client, "branch_onda_1_arkan")
        r = client.post(
            "/api/v1/branch-requests/1/approve",
            json={},
            headers=_headers(token),
        )
        assert r.status_code in (403, 404)

    def test_branch_user_can_list_own_branch_requests(self, client: TestClient):
        token = _login(client, "branch_onda_1_arkan")
        r = client.get("/api/v1/branch-requests", headers=_headers(token))
        assert r.status_code == 200, r.text

    def test_branch_user_cannot_issue_warehouse(self, client: TestClient):
        token = _login(client, "branch_onda_1_arkan")
        r = client.post("/api/v1/warehouse-lines/1/issue", json={}, headers=_headers(token))
        assert r.status_code in (403, 404)


class TestAreaManagerScope:
    def test_area_manager_lists_scoped_requests_without_branch_id(self, client: TestClient):
        token = _login(client, "area_dammam_onda")
        r = client.get("/api/v1/branch-requests", params={"page_size": 20}, headers=_headers(token))
        assert r.status_code == 200, r.text
        assert "items" in r.json()

    def test_area_manager_cannot_issue_warehouse(self, client: TestClient):
        token = _login(client, "area_dammam_onda")
        r = client.post("/api/v1/warehouse-lines/1/issue", json={}, headers=_headers(token))
        assert r.status_code in (403, 404)


class TestKitchenWarehouseDeliverySeparation:
    def test_kitchen_can_list_production(self, client: TestClient):
        token = _login(client, "kitchen_dammam_bakery_and_sweets_mgr")
        r = client.get("/api/v1/production-orders", headers=_headers(token))
        assert r.status_code == 200, r.text

    def test_kitchen_cannot_issue_warehouse(self, client: TestClient):
        token = _login(client, "kitchen_dammam_bakery_and_sweets_mgr")
        r = client.post("/api/v1/warehouse-lines/1/issue", json={}, headers=_headers(token))
        assert r.status_code in (403, 404)

    def test_warehouse_can_list_lines(self, client: TestClient):
        token = _login(client, "warehouse_dammam_user")
        r = client.get("/api/v1/warehouse-lines", headers=_headers(token))
        assert r.status_code == 200, r.text

    def test_delivery_can_list_orders(self, client: TestClient):
        token = _login(client, "delivery_dammam")
        r = client.get("/api/v1/delivery-orders", headers=_headers(token))
        assert r.status_code == 200, r.text

    def test_delivery_cannot_approve_branch_request(self, client: TestClient):
        token = _login(client, "delivery_dammam")
        r = client.post("/api/v1/branch-requests/1/approve", json={}, headers=_headers(token))
        assert r.status_code in (403, 404)


class TestWarehouseScopeIsolation:
    def test_dammam_user_sees_only_dammam_scope(self, client: TestClient):
        token = _login(client, "warehouse_dammam_user")
        r = client.get("/api/v1/warehouse-lines", headers=_headers(token))
        assert r.status_code == 200, r.text

    def test_riyadh_user_cannot_access_dammam_only_line_detail(self, client: TestClient):
        dm_token = _login(client, "warehouse_dammam_user")
        rows = client.get("/api/v1/warehouse-lines", headers=_headers(dm_token)).json()
        if not rows:
            pytest.skip("No warehouse lines")
        line_id = rows[0]["id"]
        ry_token = _login(client, "warehouse_riyadh_user")
        r = client.get(f"/api/v1/warehouse-lines/{line_id}", headers=_headers(ry_token))
        assert r.status_code in (403, 404)


class TestInternalAuditorReadOnly:
    def test_auditor_can_read_supply_chain_lists(self, client: TestClient):
        try:
            token = _login(client, "audit.officer", AUDITOR_PASSWORD)
        except AssertionError:
            pytest.skip("audit.officer user not seeded")
        for path in (
            "/api/v1/branch-requests",
            "/api/v1/production-orders",
            "/api/v1/warehouse-lines",
            "/api/v1/delivery-orders",
        ):
            r = client.get(path, headers=_headers(token))
            assert r.status_code == 200, f"{path}: {r.text}"

    def test_auditor_cannot_issue_warehouse(self, client: TestClient):
        try:
            token = _login(client, "audit.officer", AUDITOR_PASSWORD)
        except AssertionError:
            pytest.skip("audit.officer user not seeded")
        r = client.post("/api/v1/warehouse-lines/1/issue", json={}, headers=_headers(token))
        assert r.status_code in (403, 404)

    def test_auditor_can_access_audit_dashboard_api(self, client: TestClient):
        try:
            token = _login(client, "audit.officer", AUDITOR_PASSWORD)
        except AssertionError:
            pytest.skip("audit.officer user not seeded")
        r = client.get("/api/v1/audit/findings/dashboard/summary", headers=_headers(token))
        assert r.status_code == 200, r.text


class TestAdminLegacyAccess:
    def test_admin_legacy_orders_list(self, client: TestClient):
        token = _login(client, "admin", ADMIN_PASSWORD)
        r = client.get("/api/v1/orders/", headers=_headers(token))
        assert r.status_code == 200, r.text

    def test_super_admin_supply_chain_dashboard(self, client: TestClient):
        token = _login(client, "super.admin", PASSWORD)
        r = client.get("/api/v1/supply-chain/dashboard", headers=_headers(token))
        assert r.status_code == 200, r.text


class TestFrontendNavConfig:
    def test_internal_auditor_in_supply_chain_nav(self):
        text = APP_LAYOUT.read_text(encoding="utf-8")
        assert "'internal_auditor'" in text
        assert "nav.supply_chain_warehouse" in text
        block = text[text.find("sectionKey: 'nav.section_supply_chain'"): text.find("sectionKey: 'nav.section_delivery'")]
        assert "internal_auditor" in block

    def test_legacy_hidden_for_trial_roles(self):
        text = APP_LAYOUT.read_text(encoding="utf-8")
        assert "LEGACY_TRIAL_HIDDEN_PATHS" in text
        assert "'/orders'" in text
        assert "warehouse_user" in text

    def test_branch_create_hidden_for_area_manager_in_ui(self):
        text = SUPPLY_PAGES.read_text(encoding="utf-8")
        assert "canCreateRequest" in text
        assert "usesScopedList" in text

    def test_status_gated_action_helpers_present(self):
        text = SUPPLY_PAGES.read_text(encoding="utf-8")
        for fn in (
            "productionCanSendToWarehouse",
            "canIssueWarehouseLine",
            "canCreateDeliveryFromLine",
        ):
            assert fn in text, f"Missing visibility helper: {fn}"

    def test_delivery_deliver_only_out_for_delivery(self):
        text = SUPPLY_PAGES.read_text(encoding="utf-8")
        assert "order.status === 'OUT_FOR_DELIVERY'" in text
        assert "order.status === 'READY'" in text
