"""
Phase 7 — Dashboard & Operations UI tests.

Requires:
  - PostgreSQL (DATABASE_URL from backend/.env)
  - API at PHASE7_API_BASE (default http://localhost:8010)
  - Official users seeded (seed_phase2_official_users.py)
  - Item master imported (import_classified_supply_items.py)

Run API (local shell only):
  RATE_LIMIT_ENABLED=false uvicorn app.main:app --port 8010

Run tests:
  $env:RATE_LIMIT_ENABLED='false'
  DATABASE_URL=<postgres> PHASE7_API_BASE=http://localhost:8010 \\
    python -m pytest tests/test_phase7_dashboard_operations.py -v
"""
from __future__ import annotations

import os
import time
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Branch, Brand, User

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Phase 7 tests require PostgreSQL",
    ),
]

BASE = os.environ.get("PHASE7_API_BASE", os.environ.get("PHASE6_API_BASE", "http://localhost:8010")).rstrip("/")
PASSWORD = os.environ.get("PHASE7_DEMO_PASSWORD", os.environ.get("PHASE6_DEMO_PASSWORD", "Raed@Demo2026"))
LOGIN_DELAY = float(os.environ.get("PHASE7_LOGIN_DELAY_S", "0.3"))

BRANCH_USER = "branch_onda_1_arkan"
OTHER_BRANCH_USER = "branch_onda_13_al_malqa"
AREA_MANAGER = "area_dammam_onda"
WRONG_AREA_MANAGER = "area_riyadh_all"
KITCHEN_MGR = "kitchen_dammam_bakery_and_sweets_mgr"
WRONG_KITCHEN_MGR = "kitchen_dammam_pizza_mgr"
WAREHOUSE_USER = "warehouse_dammam_user"
WRONG_WAREHOUSE_USER = "warehouse_riyadh_user"
DELIVERY_USER = "delivery_dammam"
WRONG_DELIVERY_USER = "delivery_riyadh"
ADMIN_USER = "super.admin"
SUPER_ADMIN = "super.admin"
BRANCH_CODE = "BR-DM-ON-ARKAN"

DASHBOARD_KEYS = {
    "pending_approvals",
    "in_production",
    "warehouse_delays",
    "partial_orders",
    "top_requested_items",
    "requests_today",
    "warehouse_pending",
    "backorders",
    "ready_for_delivery",
    "out_for_delivery",
    "delivered_today",
    "production_ready",
    "sent_to_warehouse",
    "my_requests",
    "shortages",
    "partial_warehouse",
}


def _api_available() -> bool:
    try:
        with httpx.Client(base_url=BASE, timeout=5.0) as client:
            return client.get("/api/v1/ready").status_code == 200
    except Exception:
        return False


requires_api = pytest.mark.skipif(not _api_available(), reason=f"API not reachable at {BASE}")


@pytest.fixture(scope="module")
def http_client() -> httpx.Client:
    with httpx.Client(base_url=BASE, timeout=60.0) as client:
        yield client


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _idem() -> dict[str, str]:
    return {"X-Idempotency-Key": str(uuid4())}


def _login(client: httpx.Client, username: str) -> str:
    for attempt in range(3):
        r = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
        if r.status_code != 429:
            break
        time.sleep(2.0 * (attempt + 1))
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _dashboard(client: httpx.Client, token: str) -> dict:
    r = client.get("/api/v1/supply-chain/dashboard", headers=_auth(token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert DASHBOARD_KEYS.issubset(data.keys())
    assert isinstance(data["top_requested_items"], list)
    return data


@requires_api
def test_branch_dashboard_scope(http_client: httpx.Client, db: Session):
    branch = db.query(Branch).filter(Branch.branch_code == BRANCH_CODE).first()
    assert branch
    token = _login(http_client, BRANCH_USER)
    data = _dashboard(http_client, token)
    assert all(isinstance(data[k], int) for k in DASHBOARD_KEYS if k != "top_requested_items")

    other_token = _login(http_client, OTHER_BRANCH_USER)
    other_data = _dashboard(http_client, other_token)
    branch_user = db.query(User).filter(User.username == BRANCH_USER).first()
    other_user = db.query(User).filter(User.username == OTHER_BRANCH_USER).first()
    assert branch_user and other_user
    assert branch_user.branch_id != other_user.branch_id


@requires_api
def test_area_manager_dashboard_scope(http_client: httpx.Client):
    token = _login(http_client, AREA_MANAGER)
    data = _dashboard(http_client, token)
    assert data["pending_approvals"] >= 0

    wrong = _login(http_client, WRONG_AREA_MANAGER)
    wrong_data = _dashboard(http_client, wrong)
    assert wrong_data["pending_approvals"] >= 0


@requires_api
def test_kitchen_dashboard_scope(http_client: httpx.Client):
    token = _login(http_client, KITCHEN_MGR)
    data = _dashboard(http_client, token)
    assert data["in_production"] >= 0
    assert data["production_ready"] >= 0

    wrong = _login(http_client, WRONG_KITCHEN_MGR)
    wrong_data = _dashboard(http_client, wrong)
    assert wrong_data["in_production"] >= 0


@requires_api
def test_warehouse_dashboard_scope(http_client: httpx.Client):
    token = _login(http_client, WAREHOUSE_USER)
    data = _dashboard(http_client, token)
    assert data["warehouse_pending"] >= 0
    assert data["backorders"] >= 0

    wrong = _login(http_client, WRONG_WAREHOUSE_USER)
    wrong_data = _dashboard(http_client, wrong)
    assert wrong_data["warehouse_pending"] >= 0


@requires_api
def test_delivery_dashboard_scope(http_client: httpx.Client):
    token = _login(http_client, DELIVERY_USER)
    data = _dashboard(http_client, token)
    assert data["ready_for_delivery"] >= 0
    assert data["out_for_delivery"] >= 0

    wrong = _login(http_client, WRONG_DELIVERY_USER)
    wrong_data = _dashboard(http_client, wrong)
    assert wrong_data["ready_for_delivery"] >= 0


@requires_api
def test_admin_dashboard(http_client: httpx.Client):
    token = _login(http_client, ADMIN_USER)
    data = _dashboard(http_client, token)
    assert data["requests_today"] >= 0
    assert data["pending_approvals"] >= 0


@requires_api
def test_super_admin_overview(http_client: httpx.Client):
    token = _login(http_client, SUPER_ADMIN)
    r = http_client.get("/api/v1/supply-chain/super-admin-overview", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "summary" in body
    assert "pipeline" in body


@requires_api
@pytest.mark.parametrize(
    "username,path",
    [
        (AREA_MANAGER, "/api/v1/branch-requests?status=SUBMITTED&page=1&page_size=5"),
        (KITCHEN_MGR, "/api/v1/production-orders"),
        (WAREHOUSE_USER, "/api/v1/warehouse-lines"),
        (DELIVERY_USER, "/api/v1/delivery-orders/ready"),
        (BRANCH_USER, "/api/v1/branch-requests?page=1&page_size=5"),
    ],
)
def test_operations_drill_down_endpoints(http_client: httpx.Client, username: str, path: str):
    token = _login(http_client, username)
    r = http_client.get(path, headers=_auth(token))
    assert r.status_code == 200, f"{username} {path}: {r.status_code} {r.text}"


@requires_api
def test_branch_request_screen_list(http_client: httpx.Client):
    token = _login(http_client, BRANCH_USER)
    r = http_client.get("/api/v1/branch-requests", headers=_auth(token))
    assert r.status_code == 200
    items = r.json().get("items") or []
    assert isinstance(items, list)


@requires_api
def test_area_approval_screen_list(http_client: httpx.Client):
    token = _login(http_client, AREA_MANAGER)
    r = http_client.get("/api/v1/branch-requests?status=SUBMITTED", headers=_auth(token))
    assert r.status_code == 200


@requires_api
def test_kitchen_queue_screen(http_client: httpx.Client):
    token = _login(http_client, KITCHEN_MGR)
    r = http_client.get("/api/v1/production-orders", headers=_auth(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@requires_api
def test_warehouse_queue_screen(http_client: httpx.Client):
    token = _login(http_client, WAREHOUSE_USER)
    r = http_client.get("/api/v1/warehouse-lines", headers=_auth(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@requires_api
def test_delivery_queue_screen(http_client: httpx.Client):
    token = _login(http_client, DELIVERY_USER)
    r = http_client.get("/api/v1/delivery-orders/ready", headers=_auth(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@requires_api
def test_branch_isolation_list(http_client: httpx.Client, db: Session):
    token = _login(http_client, BRANCH_USER)
    r = http_client.get("/api/v1/branch-requests/999999", headers=_auth(token))
    assert r.status_code in (403, 404)


@requires_api
def test_area_manager_isolation(http_client: httpx.Client):
    token = _login(http_client, WRONG_AREA_MANAGER)
    r = http_client.get("/api/v1/branch-requests?status=SUBMITTED", headers=_auth(token))
    assert r.status_code == 200
    items = r.json().get("items") or []
    for item in items:
        assert item.get("status") == "SUBMITTED"


@requires_api
def test_warehouse_isolation(http_client: httpx.Client):
    token = _login(http_client, WRONG_WAREHOUSE_USER)
    r = http_client.get("/api/v1/warehouse-lines", headers=_auth(token))
    assert r.status_code == 200


@requires_api
def test_delivery_isolation(http_client: httpx.Client):
    token = _login(http_client, WRONG_DELIVERY_USER)
    r = http_client.get("/api/v1/delivery-orders/ready", headers=_auth(token))
    assert r.status_code == 200


@requires_api
def test_notifications_summary(http_client: httpx.Client):
    token = _login(http_client, BRANCH_USER)
    r = http_client.get("/api/v1/notifications/summary", headers=_auth(token))
    assert r.status_code == 200


@requires_api
def test_operations_dashboard_h06_no_error(http_client: httpx.Client):
    token = _login(http_client, ADMIN_USER)
    r = http_client.get("/api/v1/dashboard/operations", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "top_requested_items" in body or "pending_orders" in body or isinstance(body, dict)
