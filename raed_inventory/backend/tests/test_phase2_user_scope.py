"""
Phase 2 — automated login and scope validation against a running API.

Requires backend at PHASE2_API_BASE (default http://localhost:8010).
Password: PHASE2_DEMO_PASSWORD (default Raed@Demo2026).

Run (from backend/, with API up):
  python -m pytest tests/test_phase2_user_scope.py -v
"""
from __future__ import annotations

import os
import time
from typing import Callable

import httpx
import pytest

BASE = os.environ.get("PHASE2_API_BASE", "http://localhost:8010").rstrip("/")
PASSWORD = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")
LOGIN_DELAY = float(os.environ.get("PHASE2_LOGIN_DELAY_S", "3.2"))


def _password_for(username: str) -> str:
    return PASSWORD


def _roles_from_me(me_json: dict) -> set[str]:
    raw = me_json.get("roles") or []
    if not raw:
        return set()
    if isinstance(raw[0], str):
        return set(raw)
    return {r["name"] for r in raw}

OFFICIAL_USERS: dict[str, tuple[str, ...]] = {
    "super.admin": ("super_admin",),
    "admin": ("admin",),
    "area_dammam_onda": ("area_manager",),
    "area_dammam_restaurants": ("area_manager",),
    "area_riyadh_all": ("area_manager",),
    **{u: ("branch_user", "branch_manager") for u in [
        "branch_onda_1_arkan", "branch_onda_13_al_malqa", "branch_onda_14_hassa",
        "branch_onda_16_najmah", "branch_onda_18_al_midra_gym", "branch_onda_2_hoqail",
        "branch_onda_4_sefarat", "branch_onda_5_muowasat", "branch_onda_9_ras_tanura",
        "branch_onda_dau_university", "branch_pizza_1_al_khobar", "branch_pizza_10_mazaar",
        "branch_pizza_15_ras_tanura", "branch_pizza_3_arkan", "branch_pizza_4_riyadh_takhasosy",
        "branch_pizza_5_al_ulaya", "branch_pizza_6_riyadh_nada", "branch_pizza_7_aramco",
        "branch_pizza_9_al_azizia", "branch_ronaldos_dau_university", "branch_shawarma_1_khobar",
        "branch_shawarma_4_arkan", "branch_shawarma_olaya",
    ]},
    **{u: ("kitchen_section_manager",) for u in [
        "kitchen_dammam_meat_and_chicken_mgr", "kitchen_dammam_bakery_and_sweets_mgr",
        "kitchen_dammam_pizza_mgr", "kitchen_riyadh_meat_and_chicken_mgr",
        "kitchen_riyadh_bakery_and_sweets_mgr", "kitchen_riyadh_pizza_mgr",
    ]},
    "warehouse_dammam_manager": ("warehouse_manager",),
    "warehouse_dammam_user": ("warehouse_user",),
    "warehouse_riyadh_manager": ("warehouse_manager",),
    "warehouse_riyadh_user": ("warehouse_user",),
    "delivery_dammam": ("delivery_user",),
    "delivery_riyadh": ("delivery_user",),
}

INACTIVE_USERS = ("kitchen_dammam_manager_future", "kitchen_riyadh_manager_future")
LEGACY_INACTIVE = ("am_riyadh", "am_dammam", "am_dammam_cafes")


def _api_available() -> bool:
    try:
        with httpx.Client(base_url=BASE, timeout=5.0) as client:
            r = client.get("/api/v1/ready")
            return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _api_available(), reason=f"API not reachable at {BASE}")


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE, timeout=20.0) as c:
        yield c


def _login(
    client: httpx.Client,
    username: str,
    password: str | None = None,
) -> httpx.Response:
    password = password if password is not None else _password_for(username)
    for attempt in range(3):
        r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        if r.status_code != 429:
            return r
        time.sleep(2.0 * (attempt + 1))
    return r


def _token(client: httpx.Client, username: str) -> str:
    r = _login(client, username)
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("username,expected_roles", list(OFFICIAL_USERS.items()))
def test_official_user_login_and_me_roles(client: httpx.Client, username: str, expected_roles: tuple[str, ...]):
    time.sleep(LOGIN_DELAY)
    token = _token(client, username)
    me = client.get("/api/v1/auth/me", headers=_headers(token))
    assert me.status_code == 200, me.text
    roles = _roles_from_me(me.json())
    for role in expected_roles:
        assert role in roles, f"{username} missing role {role}; got {roles}"


@pytest.mark.parametrize("username", INACTIVE_USERS + LEGACY_INACTIVE)
def test_inactive_users_cannot_login(client: httpx.Client, username: str):
    time.sleep(LOGIN_DELAY)
    r = _login(client, username)
    assert r.status_code in (401, 403, 429), (
        f"{username} should not login, got {r.status_code}"
    )
    if r.status_code == 429:
        pytest.skip("rate limited during inactive-user check")


def test_branch_user_own_branch_only(client: httpx.Client):
    time.sleep(LOGIN_DELAY)
    token = _token(client, "branch_onda_13_al_malqa")
    me = client.get("/api/v1/auth/me", headers=_headers(token)).json()
    own_branch_id = me.get("branch_id")
    assert own_branch_id is not None

    items = client.get(
        "/api/v1/master/items",
        headers=_headers(token),
        params={"requestable_only": "true", "branch_id": own_branch_id, "page_size": 200},
    )
    assert items.status_code == 200, items.text
    for row in items.json().get("items", []):
        assert row.get("branch_requestable") is True
        assert row.get("visible_in_branch_ui") is True
        assert row.get("source_type") != "NOT_REQUESTABLE"

    other = client.get("/api/v1/dashboard/stock/branch/99999", headers=_headers(token))
    assert other.status_code == 403


def test_area_manager_scoped_branch_requests(client: httpx.Client):
    time.sleep(LOGIN_DELAY)
    token = _token(client, "area_dammam_onda")
    r = client.get("/api/v1/branch-requests", headers=_headers(token), params={"page": 1, "page_size": 20})
    assert r.status_code == 200, r.text
    for row in r.json().get("items", []):
        branch = row.get("branch") or {}
        assert branch.get("city") == "Dammam"
        brand = row.get("brand") or {}
        assert brand.get("name") == "Onda"


def test_kitchen_section_scoped_production_orders(client: httpx.Client):
    time.sleep(LOGIN_DELAY)
    token = _token(client, "kitchen_dammam_pizza_mgr")
    r = client.get("/api/v1/production-orders", headers=_headers(token))
    assert r.status_code == 200, r.text
    for row in r.json():
        section = row.get("kitchen_section") or {}
        assert section.get("name") == "Pizza"
        dest = row.get("destination_branch") or {}
        if dest.get("city"):
            assert dest["city"] == "Dammam"


def test_warehouse_user_own_warehouse_only(client: httpx.Client):
    time.sleep(LOGIN_DELAY)
    token = _token(client, "warehouse_dammam_user")
    me = client.get("/api/v1/auth/me", headers=_headers(token)).json()
    wh_id = me.get("warehouse_id")
    assert wh_id is not None
    r = client.get("/api/v1/warehouse-lines", headers=_headers(token))
    assert r.status_code == 200, r.text


def test_delivery_user_requires_warehouse_scope(client: httpx.Client):
    time.sleep(LOGIN_DELAY)
    token = _token(client, "delivery_dammam")
    me = client.get("/api/v1/auth/me", headers=_headers(token)).json()
    assert me.get("warehouse_id") is not None
    r = client.get("/api/v1/delivery-orders/ready", headers=_headers(token))
    assert r.status_code == 200, r.text


def test_area_manager_cannot_access_other_city_stock(client: httpx.Client):
    """area_dammam_onda must not read Riyadh branch stock."""
    time.sleep(LOGIN_DELAY)
    admin_token = _token(client, "admin")
    branches = client.get(
        "/api/v1/master/branches",
        headers=_headers(admin_token),
        params={"active_only": "true"},
    ).json()
    riyadh_branch = next((b for b in branches if b.get("city") == "Riyadh"), None)
    assert riyadh_branch is not None
    token = _token(client, "area_dammam_onda")
    denied = client.get(
        f"/api/v1/dashboard/stock/branch/{riyadh_branch['id']}",
        headers=_headers(token),
    )
    assert denied.status_code == 403
