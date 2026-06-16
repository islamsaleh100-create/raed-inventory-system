"""
LAN Trial login cards — single source of truth verification.

Requires PostgreSQL raed_lan_trial (set DATABASE_URL).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.main import app
from app.models import Branch, KitchenSection, KitchenSectionAssignment, Role, User, UserRole, Warehouse

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="LAN login card tests require PostgreSQL",
    ),
    pytest.mark.skipif(
        "lan_trial" not in (os.environ.get("DATABASE_URL") or engine.url.database or ""),
        reason="LAN login card tests require raed_lan_trial database",
    ),
]

BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
LOGIN_PAGE = FRONTEND_DIR / "src" / "pages" / "auth" / "LoginPage.jsx"
LAN_CARDS = FRONTEND_DIR / "src" / "config" / "lanTrialLoginCards.js"
AR_DICT = FRONTEND_DIR / "src" / "i18n" / "dict" / "ar.json"

TRIAL_PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "LanTrial@2026Temp")
ADMIN_PASSWORD = os.environ.get("LAN_TRIAL_ADMIN_PASSWORD", "Admin@2025")
AUDITOR_PASSWORD = os.environ.get("INTERNAL_AUDITOR_PASSWORD", "Raed@2025")

REQUIRED_USERNAMES = [
    "super.admin",
    "admin",
    "audit.officer",
    "area_dammam_onda",
    "area_dammam_restaurants",
    "branch_onda_1_arkan",
    "branch_pizza_1_al_khobar",
    "branch_shawarma_1_khobar",
    "kitchen_dammam_meat_and_chicken_mgr",
    "kitchen_dammam_bakery_and_sweets_mgr",
    "kitchen_dammam_pizza_mgr",
    "warehouse_dammam_manager",
    "warehouse_dammam_user",
    "delivery_dammam",
]

FORBIDDEN_USERNAMES = [
    "am_riyadh",
    "branch.mgr1",
    "wh.mgr1",
    "branch.user1",
    "qa.mgr",
    "ops.mgr",
    "branch_pizza_3_arkan",
    "branch_shawarma_4_arkan",
]

PASSWORD_BY_USER = {
    "admin": ADMIN_PASSWORD,
    "audit.officer": AUDITOR_PASSWORD,
}

ROLE_EXPECTATIONS = {
    "super.admin": {"super_admin"},
    "admin": {"admin"},
    "audit.officer": {"internal_auditor"},
    "area_dammam_onda": {"area_manager"},
    "area_dammam_restaurants": {"area_manager"},
    "branch_onda_1_arkan": {"branch_user", "branch_manager"},
    "branch_pizza_1_al_khobar": {"branch_user", "branch_manager"},
    "branch_shawarma_1_khobar": {"branch_user", "branch_manager"},
    "kitchen_dammam_meat_and_chicken_mgr": {"kitchen_section_manager"},
    "kitchen_dammam_bakery_and_sweets_mgr": {"kitchen_section_manager"},
    "kitchen_dammam_pizza_mgr": {"kitchen_section_manager"},
    "warehouse_dammam_manager": {"warehouse_manager"},
    "warehouse_dammam_user": {"warehouse_user"},
    "delivery_dammam": {"delivery_user"},
}

BRANCH_EXPECTATIONS = {
    "branch_onda_1_arkan": "BR-DM-ON-ARKAN",
    "branch_pizza_1_al_khobar": "BR-DM-RN-KHOBR",
    "branch_shawarma_1_khobar": "BR-DM-SH-KHOBR",
}


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


def _extract_lan_usernames_from_config() -> set[str]:
    text = LAN_CARDS.read_text(encoding="utf-8")
    return set(re.findall(r"username:\s*'([^']+)'", text))


def _login(client: TestClient, username: str) -> dict:
    password = PASSWORD_BY_USER.get(username, TRIAL_PASSWORD)
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


class TestLanLoginUiSource:
    def test_single_lan_section_only(self):
        login_text = LOGIN_PAGE.read_text(encoding="utf-8")
        cards_text = LAN_CARDS.read_text(encoding="utf-8")
        ar = json.loads(AR_DICT.read_text(encoding="utf-8"))

        assert "lanTrialLoginCards" in login_text
        assert "LEGACY_DEMO_ACCOUNTS" not in login_text
        assert 't("auth.demo_hint")' not in login_text
        assert 't(\'auth.demo_hint\')' not in login_text
        lan_title_key = "auth.lan_accounts_title"
        assert ar["auth"]["lan_accounts_title"] == "حسابات تجربة LAN"
        assert ar["auth"]["lan_accounts_notice"].startswith("استخدم هذه الحسابات فقط")

        for forbidden_label in ("بيانات تجريبية", "تطوير فقط"):
            assert forbidden_label not in login_text

        listed = _extract_lan_usernames_from_config()
        assert listed == set(REQUIRED_USERNAMES)
        assert listed.isdisjoint(set(FORBIDDEN_USERNAMES))
        for bad in FORBIDDEN_USERNAMES:
            assert bad not in login_text

    def test_required_usernames_in_config(self):
        listed = _extract_lan_usernames_from_config()
        for username in REQUIRED_USERNAMES:
            assert username in listed


class TestLanLoginAccountsApi:
    @pytest.mark.parametrize("username", REQUIRED_USERNAMES)
    def test_required_account_login_and_me(self, client: TestClient, username: str):
        payload = _login(client, username)
        roles = set(payload["user"]["roles"])
        assert ROLE_EXPECTATIONS[username].issubset(roles)

        token = payload["access_token"]
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, me.text
        assert me.json()["username"] == username

    def test_branch_users_mapped_to_trial_branches(self, client: TestClient, db: Session):
        for username, branch_code in BRANCH_EXPECTATIONS.items():
            payload = _login(client, username)
            user_id = payload["user"]["id"]
            user = db.query(User).filter(User.id == user_id).first()
            branch = db.query(Branch).filter(Branch.id == user.branch_id).first()
            assert branch is not None
            assert branch.branch_code == branch_code

    def test_warehouse_users_have_wh_dm_1(self, client: TestClient, db: Session):
        for username in ("warehouse_dammam_manager", "warehouse_dammam_user", "delivery_dammam"):
            payload = _login(client, username)
            user = db.query(User).filter(User.id == payload["user"]["id"]).first()
            wh = db.query(Warehouse).filter(Warehouse.id == user.warehouse_id).first()
            assert wh is not None
            assert wh.warehouse_code == "WH-DM-1"

    def test_kitchen_users_have_dammam_sections(self, client: TestClient, db: Session):
        expectations = {
            "kitchen_dammam_meat_and_chicken_mgr": "Meat & Chicken",
            "kitchen_dammam_bakery_and_sweets_mgr": "Bakery & Sweets",
            "kitchen_dammam_pizza_mgr": "Pizza",
        }
        for username, section_name in expectations.items():
            payload = _login(client, username)
            user = db.query(User).filter(User.id == payload["user"]["id"]).first()
            section = (
                db.query(KitchenSection)
                .join(KitchenSectionAssignment, KitchenSectionAssignment.kitchen_section_id == KitchenSection.id)
                .filter(KitchenSectionAssignment.user_id == user.id)
                .first()
            )
            assert section is not None
            assert section.name == section_name

    def test_area_managers_active(self, client: TestClient, db: Session):
        for username in ("area_dammam_onda", "area_dammam_restaurants"):
            user = db.query(User).filter(User.username == username).first()
            assert user is not None
            assert str(getattr(user.status, "value", user.status)) == "active"
            payload = _login(client, username)
            assert "area_manager" in payload["user"]["roles"]
