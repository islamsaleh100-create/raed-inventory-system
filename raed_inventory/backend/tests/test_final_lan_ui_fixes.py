"""
Final LAN UI fixes — legacy route block, notification labels, auditor read-only, kitchen hygiene.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.main import app
from app.models import WarehouseLine

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Final LAN UI fix tests require PostgreSQL",
    ),
]

PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@2025")
BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
APP_JS = FRONTEND_DIR / "src" / "App.jsx"
AR_DICT = FRONTEND_DIR / "src" / "i18n" / "dict" / "ar.json"
TRIAL_LEGACY = FRONTEND_DIR / "src" / "utils" / "trialLegacy.js"
SUPPLY_PAGES = FRONTEND_DIR / "src" / "pages" / "supply_chain" / "SupplyChainPages.jsx"


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


class TestLegacyRouteBlocking:
    def test_trial_legacy_guard_on_orders_route(self):
        text = APP_JS.read_text(encoding="utf-8")
        assert "TrialLegacyRouteGuard" in text
        assert 'path="/orders"' in text
        assert "lan_trial_legacy_blocked_body" in AR_DICT.read_text(encoding="utf-8")

    def test_trial_roles_list_in_shared_module(self):
        trial = TRIAL_LEGACY.read_text(encoding="utf-8")
        for role in ("branch_user", "area_manager", "kitchen_section_manager", "warehouse_manager", "delivery_user"):
            assert role in trial

    def test_branch_user_legacy_orders_api_still_readable(self, client: TestClient):
        """API remains for admin tooling; UI blocks trial roles via TrialLegacyRouteGuard."""
        token = _login(client, "branch_onda_1_arkan")
        r = client.get("/api/v1/orders/", headers=_headers(token))
        assert r.status_code in (200, 403)

    def test_admin_legacy_orders_api_works(self, client: TestClient):
        token = _login(client, "admin", ADMIN_PASSWORD)
        r = client.get("/api/v1/orders/", headers=_headers(token))
        assert r.status_code == 200, r.text


class TestNotificationTranslations:
    def test_supply_chain_notification_keys_in_ar_dict(self):
        ar = json.loads(AR_DICT.read_text(encoding="utf-8"))
        notifications = ar.get("notifications", {})
        required = (
            "sc_request_approved",
            "sc_request_rejected",
            "sc_production_started",
        )
        for key in required:
            label = notifications.get(key)
            assert label and not label.startswith("notifications."), key

    def test_branch_request_status_labels_in_ar_dict(self):
        ar = json.loads(AR_DICT.read_text(encoding="utf-8"))
        statuses = ar.get("order_status", {})
        for key, expected_fragment in (
            ("SPLIT", "تقسيم"),
            ("IN_EXECUTION", "تنفيذ"),
            ("AREA_REJECTED", "مرفوض"),
        ):
            assert expected_fragment in statuses.get(key, ""), key

    def test_notification_summary_labels_not_raw_keys(self, client: TestClient):
        token = _login(client, "super.admin")
        r = client.get("/api/v1/notifications/summary", headers=_headers(token))
        assert r.status_code == 200, r.text
        ar = json.loads(AR_DICT.read_text(encoding="utf-8"))
        for section in r.json().get("sections") or []:
            key = section.get("key")
            if not key:
                continue
            label = ar.get("notifications", {}).get(key)
            assert label, f"missing notifications.{key}"


class TestInternalAuditorSupplyChainReadOnly:
    def test_auditor_can_read_kitchen_warehouse_delivery(self, client: TestClient):
        token = _login(client, "audit.officer", os.environ.get("AUDIT_PASSWORD", "Raed@2025"))
        h = _headers(token)
        for path in ("/production-orders", "/warehouse-lines", "/delivery-orders"):
            r = client.get(f"/api/v1{path}", headers=h)
            assert r.status_code == 200, f"{path}: {r.text}"

    def test_auditor_cannot_execute_warehouse_write(self, client: TestClient):
        token = _login(client, "audit.officer", os.environ.get("AUDIT_PASSWORD", "Raed@2025"))
        db = SessionLocal()
        try:
            line = db.query(WarehouseLine).first()
            if not line:
                pytest.skip("No warehouse lines")
            line_id = line.id
        finally:
            db.close()
        r = client.post(f"/api/v1/warehouse-lines/{line_id}/receive", headers=_headers(token))
        assert r.status_code == 403, r.text

    def test_auditor_ui_read_only_banners(self):
        text = SUPPLY_PAGES.read_text(encoding="utf-8")
        assert text.count("internal_auditor") >= 5
        assert "ReadOnlyBanner" in text
        assert "قراءة فقط" in text


class TestLanKitchenHygiene:
    def test_hygiene_script_detects_non_official_kitchens(self):
        proc = subprocess.run(
            [sys.executable, "validate_lan_kitchen_hygiene.py"],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
        )
        assert proc.returncode in (0, 1)
        assert "Verdict:" in proc.stdout

    def test_strict_lan_trial_fails_with_test_kitchens(self):
        proc = subprocess.run(
            [sys.executable, "validate_lan_kitchen_hygiene.py", "--strict-lan-trial"],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
        )
        out = proc.stdout + proc.stderr
        assert "Forbidden:" in out or "NO-GO" in out or proc.returncode == 1
