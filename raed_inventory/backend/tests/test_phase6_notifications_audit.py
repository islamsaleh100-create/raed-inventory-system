"""
Phase 6 — Notifications & Audit hardening tests.

Requires:
  - PostgreSQL (DATABASE_URL from backend/.env)
  - API at PHASE6_API_BASE (default http://localhost:8010)
  - Official users seeded (seed_phase2_official_users.py)
  - Item master imported (import_classified_supply_items.py)

Run API (local shell only):
  RATE_LIMIT_ENABLED=false uvicorn app.main:app --port 8010

Run tests:
  DATABASE_URL=<postgres> PHASE6_API_BASE=http://localhost:8010 \\
    python -m pytest tests/test_phase6_notifications_audit.py -v
"""
from __future__ import annotations

import os
import time
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import (
    AuditLog,
    Branch,
    BranchRequestStatus,
    Brand,
    DeliveryOrderStatus,
    Item,
    ItemBrand,
    SupplySourceType,
    WarehouseLine,
    WarehouseLineSourceType,
)

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Phase 6 tests require PostgreSQL",
    ),
]

BASE = os.environ.get("PHASE6_API_BASE", os.environ.get("PHASE5_API_BASE", "http://localhost:8010")).rstrip("/")
PASSWORD = os.environ.get("PHASE6_DEMO_PASSWORD", os.environ.get("PHASE5_DEMO_PASSWORD", "Raed@Demo2026"))
LOGIN_DELAY = float(os.environ.get("PHASE6_LOGIN_DELAY_S", "0.3"))

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
BRAND_NAME = "Onda"
BRANCH_CODE = "BR-DM-ON-ARKAN"


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


def _context(db: Session) -> dict:
    branch = db.query(Branch).filter(Branch.branch_code == BRANCH_CODE).first()
    brand = db.query(Brand).filter(Brand.name == BRAND_NAME).first()
    assert branch and brand
    warehouse_item = (
        db.query(Item)
        .join(ItemBrand)
        .filter(
            ItemBrand.brand_id == brand.id,
            Item.source_type == SupplySourceType.WAREHOUSE,
            Item.branch_requestable == True,
            Item.active == True,
            Item.is_deleted == False,
        )
        .order_by(Item.id.asc())
        .first()
    )
    kitchen_item = (
        db.query(Item)
        .join(ItemBrand)
        .filter(
            ItemBrand.brand_id == brand.id,
            Item.source_type == SupplySourceType.KITCHEN,
            Item.branch_requestable == True,
            Item.active == True,
            Item.is_deleted == False,
        )
        .order_by(Item.id.asc())
        .first()
    )
    assert warehouse_item and kitchen_item
    return {
        "branch_id": branch.id,
        "brand_id": brand.id,
        "warehouse_id": branch.warehouse_id,
        "warehouse_item_id": warehouse_item.id,
        "kitchen_item_id": kitchen_item.id,
    }


def _section_keys(client: httpx.Client, token: str) -> set[str]:
    r = client.get("/api/v1/notifications/summary", headers=_auth(token))
    assert r.status_code == 200, r.text
    return {s["key"] for s in r.json()["sections"]}


def _section_items(client: httpx.Client, token: str, key: str) -> list[dict]:
    r = client.get("/api/v1/notifications/list", headers=_auth(token))
    assert r.status_code == 200, r.text
    for section in r.json()["sections"]:
        if section["key"] == key:
            return section["items"]
    return []


def _create_submit_approve(client: httpx.Client, ctx: dict, item_id: int, qty: str = "2") -> int:
    token = _login(client, BRANCH_USER)
    time.sleep(LOGIN_DELAY)
    created = client.post(
        "/api/v1/branch-requests",
        json={
            "branch_id": ctx["branch_id"],
            "brand_id": ctx["brand_id"],
            "priority": "normal",
            "lines": [{"item_id": item_id, "qty_requested": qty}],
        },
        headers={**_auth(token), **_idem()},
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    submitted = client.post(
        f"/api/v1/branch-requests/{request_id}/submit",
        headers={**_auth(token), **_idem()},
    )
    assert submitted.status_code == 200, submitted.text
    token = _login(client, AREA_MANAGER)
    time.sleep(LOGIN_DELAY)
    approved = client.post(
        f"/api/v1/branch-requests/{request_id}/approve",
        json={},
        headers={**_auth(token), **_idem()},
    )
    assert approved.status_code == 200, approved.text
    return request_id


@requires_api
def test_request_create_and_submit_audit(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    token = _login(http_client, BRANCH_USER)
    created = http_client.post(
        "/api/v1/branch-requests",
        json={
            "branch_id": ctx["branch_id"],
            "brand_id": ctx["brand_id"],
            "priority": "normal",
            "lines": [{"item_id": ctx["warehouse_item_id"], "qty_requested": "1"}],
        },
        headers={**_auth(token), **_idem()},
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    submitted = http_client.post(
        f"/api/v1/branch-requests/{request_id}/submit",
        headers={**_auth(token), **_idem()},
    )
    assert submitted.status_code == 200, submitted.text

    actions = {
        row.action
        for row in db.query(AuditLog)
        .filter(AuditLog.entity_type == "branch_request", AuditLog.entity_id == request_id)
        .all()
    }
    assert "request_created" in actions
    assert "request_submitted" in actions


@requires_api
def test_approval_and_split_audit(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="2")

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "branch_request", AuditLog.entity_id == request_id)
        .order_by(AuditLog.id.asc())
        .all()
    )
    actions = {r.action for r in rows}
    assert "request_approved" in actions
    assert "request_auto_split" in actions

    split_audit = next(r for r in rows if r.action == "request_auto_split")
    assert split_audit.user_id is not None
    assert split_audit.created_at is not None
    new_values = split_audit.new_values or ""
    assert "warehouse_line_ids" in new_values or "status" in new_values


@requires_api
def test_branch_sees_supply_chain_notification_sections(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="2")
    token = _login(http_client, BRANCH_USER)
    keys = _section_keys(http_client, token)
    assert "sc_request_approved" in keys


@requires_api
def test_area_manager_pending_requests_notification(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    token = _login(http_client, BRANCH_USER)
    created = http_client.post(
        "/api/v1/branch-requests",
        json={
            "branch_id": ctx["branch_id"],
            "brand_id": ctx["brand_id"],
            "priority": "normal",
            "lines": [{"item_id": ctx["warehouse_item_id"], "qty_requested": "1"}],
        },
        headers={**_auth(token), **_idem()},
    )
    request_id = created.json()["id"]
    http_client.post(
        f"/api/v1/branch-requests/{request_id}/submit",
        headers={**_auth(token), **_idem()},
    )

    am_token = _login(http_client, AREA_MANAGER)
    keys = _section_keys(http_client, am_token)
    assert "sc_pending_requests" in keys
    pending_items = _section_items(http_client, am_token, "sc_pending_requests")
    assert any(item.get("id") == request_id for item in pending_items)


@requires_api
def test_area_manager_scope_isolation(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    token = _login(http_client, BRANCH_USER)
    created = http_client.post(
        "/api/v1/branch-requests",
        json={
            "branch_id": ctx["branch_id"],
            "brand_id": ctx["brand_id"],
            "priority": "normal",
            "lines": [{"item_id": ctx["warehouse_item_id"], "qty_requested": "1"}],
        },
        headers={**_auth(token), **_idem()},
    )
    request_id = created.json()["id"]
    http_client.post(
        f"/api/v1/branch-requests/{request_id}/submit",
        headers={**_auth(token), **_idem()},
    )

    wrong_token = _login(http_client, WRONG_AREA_MANAGER)
    pending_items = _section_items(http_client, wrong_token, "sc_pending_requests")
    assert all(item.get("id") != request_id for item in pending_items)


@requires_api
def test_kitchen_production_notification_sections(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _create_submit_approve(http_client, ctx, ctx["kitchen_item_id"], qty="2")
    token = _login(http_client, KITCHEN_MGR)
    keys = _section_keys(http_client, token)
    assert "sc_production_order_created" in keys


@requires_api
def test_kitchen_section_scope_isolation(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _create_submit_approve(http_client, ctx, ctx["kitchen_item_id"], qty="2")
    wrong_token = _login(http_client, WRONG_KITCHEN_MGR)
    items = _section_items(http_client, wrong_token, "sc_production_order_created")
    assert items == []


@requires_api
def test_warehouse_receive_notification(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="2")
    token = _login(http_client, WAREHOUSE_USER)
    keys = _section_keys(http_client, token)
    assert "sc_warehouse_receive_required" in keys
    wh_line = (
        db.query(WarehouseLine)
        .filter(
            WarehouseLine.source_request_id == request_id,
            WarehouseLine.source_type == WarehouseLineSourceType.BRANCH_REQUEST,
        )
        .first()
    )
    receive_items = _section_items(http_client, token, "sc_warehouse_receive_required")
    assert any(item.get("id") == wh_line.id for item in receive_items)


@requires_api
def test_warehouse_scope_isolation(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="2")
    wrong_token = _login(http_client, WRONG_WAREHOUSE_USER)
    receive_items = _section_items(http_client, wrong_token, "sc_warehouse_receive_required")
    wh_line = (
        db.query(WarehouseLine)
        .filter(WarehouseLine.source_request_id == request_id)
        .first()
    )
    assert all(item.get("id") != wh_line.id for item in receive_items)


@requires_api
def test_delivery_notification_after_issue(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    from app.models import WarehouseStock

    stock = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["warehouse_item_id"],
        )
        .first()
    )
    if not stock or Decimal(str(stock.current_qty)) < Decimal("50"):
        if not stock:
            stock = WarehouseStock(
                warehouse_id=ctx["warehouse_id"],
                item_id=ctx["warehouse_item_id"],
                current_qty=Decimal("100"),
                reserved_qty=Decimal("0"),
            )
            db.add(stock)
        else:
            stock.current_qty = Decimal("100")
        db.commit()

    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="2")
    wh_line = (
        db.query(WarehouseLine)
        .filter(WarehouseLine.source_request_id == request_id)
        .first()
    )
    wh_token = _login(http_client, WAREHOUSE_USER)
    http_client.post(f"/api/v1/warehouse-lines/{wh_line.id}/receive", headers={**_auth(wh_token), **_idem()})
    http_client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers={**_auth(wh_token), **_idem()})
    http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )

    d_token = _login(http_client, DELIVERY_USER)
    keys = _section_keys(http_client, d_token)
    assert "sc_delivery_ready" in keys

    issue_audit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "warehouse_issue", AuditLog.entity_id == wh_line.id)
        .first()
    )
    assert issue_audit is not None
    create_audit = db.query(AuditLog).filter(AuditLog.action == "delivery_order_created").first()
    assert create_audit is not None


@requires_api
def test_delivery_scope_isolation(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="2")
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    wh_token = _login(http_client, WAREHOUSE_USER)
    http_client.post(f"/api/v1/warehouse-lines/{wh_line.id}/receive", headers={**_auth(wh_token), **_idem()})
    http_client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers={**_auth(wh_token), **_idem()})
    delivery = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    order_id = delivery.json()["id"]

    wrong_token = _login(http_client, WRONG_DELIVERY_USER)
    ready_items = _section_items(http_client, wrong_token, "sc_delivery_ready")
    assert all(item.get("id") != order_id for item in ready_items)


@requires_api
def test_delivered_audit_and_branch_notification(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    from app.models import WarehouseStock

    stock = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["warehouse_item_id"],
        )
        .first()
    )
    if stock:
        stock.current_qty = Decimal("100")
        db.commit()

    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="2")
    wh_line = db.query(WarehouseLine).filter(WarehouseLine.source_request_id == request_id).first()
    wh_token = _login(http_client, WAREHOUSE_USER)
    http_client.post(f"/api/v1/warehouse-lines/{wh_line.id}/receive", headers={**_auth(wh_token), **_idem()})
    http_client.post(f"/api/v1/warehouse-lines/{wh_line.id}/issue", json={}, headers={**_auth(wh_token), **_idem()})
    delivery = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    order_id = delivery.json()["id"]
    d_token = _login(http_client, DELIVERY_USER)
    http_client.post(f"/api/v1/delivery-orders/{order_id}/out-for-delivery", headers={**_auth(d_token), **_idem()})
    delivered = http_client.post(
        f"/api/v1/delivery-orders/{order_id}/deliver",
        json={"receiver_name": "Phase6 Receiver"},
        headers={**_auth(d_token), **_idem()},
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == DeliveryOrderStatus.DELIVERED.value

    deliver_audit = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "delivery_order", AuditLog.entity_id == order_id, AuditLog.action == "delivery_delivered")
        .first()
    )
    assert deliver_audit is not None
    assert deliver_audit.user_id is not None

    branch_token = _login(http_client, BRANCH_USER)
    keys = _section_keys(http_client, branch_token)
    assert "sc_delivered" in keys
