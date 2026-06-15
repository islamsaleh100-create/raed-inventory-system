"""
Phase 5 — Warehouse & Delivery hardening tests.

Requires:
  - PostgreSQL (DATABASE_URL from backend/.env)
  - API at PHASE5_API_BASE (default http://localhost:8010)
  - Official users seeded (seed_phase2_official_users.py)
  - Item master imported (import_classified_supply_items.py)

Run API (local shell only):
  RATE_LIMIT_ENABLED=false uvicorn app.main:app --port 8010

Run tests:
  DATABASE_URL=<postgres> PHASE5_API_BASE=http://localhost:8010 \\
    python -m pytest tests/test_phase5_warehouse_delivery_hardening.py -v
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
    BranchRequestLineStatus,
    BranchRequestStatus,
    Brand,
    BranchStock,
    DeliveryOrderStatus,
    Item,
    ItemBrand,
    ProductionOrder,
    StockTransaction,
    SupplySourceType,
    TransactionType,
    WarehouseLine,
    WarehouseLineSourceType,
    WarehouseLineStatus,
    WarehouseStock,
)

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Phase 5 tests require PostgreSQL",
    ),
]

BASE = os.environ.get("PHASE5_API_BASE", os.environ.get("PHASE4_API_BASE", "http://localhost:8010")).rstrip("/")
PASSWORD = os.environ.get("PHASE5_DEMO_PASSWORD", os.environ.get("PHASE4_DEMO_PASSWORD", "Raed@Demo2026"))
LOGIN_DELAY = float(os.environ.get("PHASE5_LOGIN_DELAY_S", "0.3"))

BRANCH_USER = "branch_onda_1_arkan"
AREA_MANAGER = "area_dammam_onda"
KITCHEN_MGR = "kitchen_dammam_bakery_and_sweets_mgr"
WAREHOUSE_USER = "warehouse_dammam_user"
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
        "kitchen_section_id": kitchen_item.kitchen_section_id,
    }


def _ensure_warehouse_stock(db: Session, warehouse_id: int, item_id: int, qty: Decimal) -> WarehouseStock:
    stock = (
        db.query(WarehouseStock)
        .filter(WarehouseStock.warehouse_id == warehouse_id, WarehouseStock.item_id == item_id)
        .first()
    )
    if not stock:
        stock = WarehouseStock(
            warehouse_id=warehouse_id,
            item_id=item_id,
            current_qty=qty,
            reserved_qty=Decimal("0"),
        )
        db.add(stock)
    else:
        stock.current_qty = qty
    db.commit()
    db.refresh(stock)
    return stock


def _create_submit_approve(
    client: httpx.Client,
    ctx: dict,
    item_id: int,
    qty: str,
) -> int:
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
    assert approved.json()["status"] == BranchRequestStatus.SPLIT.value
    return request_id


def _warehouse_line_for_request(db: Session, request_id: int) -> WarehouseLine:
    row = (
        db.query(WarehouseLine)
        .filter(
            WarehouseLine.source_request_id == request_id,
            WarehouseLine.source_type == WarehouseLineSourceType.BRANCH_REQUEST,
        )
        .first()
    )
    assert row is not None
    return row


def _receive_and_issue_full(client: httpx.Client, wh_line_id: int, wh_token: str) -> dict:
    received = client.post(
        f"/api/v1/warehouse-lines/{wh_line_id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    assert received.status_code == 200, received.text
    issued = client.post(
        f"/api/v1/warehouse-lines/{wh_line_id}/issue",
        json={},
        headers={**_auth(wh_token), **_idem()},
    )
    assert issued.status_code == 200, issued.text
    return issued.json()


@requires_api
def test_full_issue_success(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("100"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="4")
    wh_line = _warehouse_line_for_request(db, request_id)
    wh_token = _login(http_client, WAREHOUSE_USER)

    stock_before = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["warehouse_item_id"],
        )
        .first()
    )
    current_before = Decimal(str(stock_before.current_qty))

    _receive_and_issue_full(http_client, wh_line.id, wh_token)

    db.expire_all()
    stock_after = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["warehouse_item_id"],
        )
        .first()
    )
    assert Decimal(str(stock_after.current_qty)) == current_before - Decimal("4")
    assert Decimal(str(stock_after.current_qty)) >= Decimal("0")

    ledger = (
        db.query(StockTransaction)
        .filter(
            StockTransaction.reference_no == f"WL-{wh_line.id}",
            StockTransaction.transaction_type == TransactionType.warehouse_issue,
        )
        .first()
    )
    assert ledger is not None


@requires_api
def test_issue_rejects_when_stock_unavailable(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("50"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="8")
    wh_line = _warehouse_line_for_request(db, request_id)

    stock = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["warehouse_item_id"],
        )
        .first()
    )
    stock.current_qty = Decimal("2")
    db.commit()

    wh_token = _login(http_client, WAREHOUSE_USER)
    http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    issued = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/issue",
        json={},
        headers={**_auth(wh_token), **_idem()},
    )
    assert issued.status_code == 400, issued.text
    assert issued.json()["error_code"] == "warehouse_lines.insufficient_stock"

    db.expire_all()
    stock = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["warehouse_item_id"],
        )
        .first()
    )
    assert Decimal(str(stock.current_qty)) == Decimal("2")


@requires_api
def test_partial_issue_preserves_remainder_and_delay_reason(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("100"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="6")
    wh_line = _warehouse_line_for_request(db, request_id)
    wh_token = _login(http_client, WAREHOUSE_USER)
    http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    partial = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/partial-issue",
        json={"qty": "2", "delay_reason": "supplier delay"},
        headers={**_auth(wh_token), **_idem()},
    )
    assert partial.status_code == 200, partial.text
    body = partial.json()
    assert Decimal(body["issued_qty"]) == Decimal("2")
    assert Decimal(body["pending_qty"]) == Decimal("4")
    assert body["status"] == WarehouseLineStatus.PARTIAL.value
    assert body["delay_reason"] == "supplier delay"

    db.expire_all()
    line = db.query(WarehouseLine).filter(WarehouseLine.id == wh_line.id).first()
    assert line.source_request_line.status == BranchRequestLineStatus.PARTIAL_WAREHOUSE


@requires_api
def test_partial_issue_allows_delivery_for_issued_quantity(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("100"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="5")
    wh_line = _warehouse_line_for_request(db, request_id)
    wh_token = _login(http_client, WAREHOUSE_USER)
    http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    partial = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/partial-issue",
        json={"qty": "3", "delay_reason": "short pick"},
        headers={**_auth(wh_token), **_idem()},
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["status"] == WarehouseLineStatus.PARTIAL.value

    delivery = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    assert delivery.status_code == 201, delivery.text
    assert Decimal(delivery.json()["lines"][0]["qty_dispatched"]) == Decimal("3")


@requires_api
def test_duplicate_receive_is_idempotent(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("100"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="2")
    wh_line = _warehouse_line_for_request(db, request_id)
    wh_token = _login(http_client, WAREHOUSE_USER)

    first = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    second = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == WarehouseLineStatus.AVAILABLE.value
    assert second.json()["status"] == WarehouseLineStatus.AVAILABLE.value


@requires_api
def test_kitchen_send_receive_does_not_double_stock(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    request_id = _create_submit_approve(http_client, ctx, ctx["kitchen_item_id"], qty="2")
    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    assert po is not None

    km_token = _login(http_client, KITCHEN_MGR)
    http_client.post(f"/api/v1/production-orders/{po.id}/start", headers={**_auth(km_token), **_idem()})
    http_client.post(f"/api/v1/production-orders/{po.id}/mark-ready", headers={**_auth(km_token), **_idem()})
    sent = http_client.post(
        f"/api/v1/production-orders/{po.id}/send-to-warehouse",
        headers={**_auth(km_token), **_idem()},
    )
    assert sent.status_code == 200, sent.text

    db.expire_all()
    wh_line = (
        db.query(WarehouseLine)
        .filter(
            WarehouseLine.source_request_id == request_id,
            WarehouseLine.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT,
        )
        .first()
    )
    assert wh_line is not None

    stock_after_send = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["kitchen_item_id"],
        )
        .first()
    )
    qty_after_send = Decimal(str(stock_after_send.current_qty)) if stock_after_send else Decimal("0")

    wh_token = _login(http_client, WAREHOUSE_USER)
    recv1 = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    recv2 = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    assert recv1.status_code == 200, recv1.text
    assert recv2.status_code == 200, recv2.text

    db.expire_all()
    stock_after_receive = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["kitchen_item_id"],
        )
        .first()
    )
    assert Decimal(str(stock_after_receive.current_qty)) == qty_after_send


@requires_api
def test_delivery_uses_issued_quantity_only(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("100"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="7")
    wh_line = _warehouse_line_for_request(db, request_id)
    wh_token = _login(http_client, WAREHOUSE_USER)
    http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    partial = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/partial-issue",
        json={"qty": "4", "delay_reason": "partial stock"},
        headers={**_auth(wh_token), **_idem()},
    )
    assert partial.status_code == 200, partial.text

    delivery = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    assert delivery.status_code == 201, delivery.text
    line = delivery.json()["lines"][0]
    assert Decimal(line["qty_dispatched"]) == Decimal("4")
    assert Decimal(line["qty_dispatched"]) != Decimal("7")


@requires_api
def test_duplicate_delivery_line_rejected(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("100"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="3")
    wh_line = _warehouse_line_for_request(db, request_id)
    wh_token = _login(http_client, WAREHOUSE_USER)
    _receive_and_issue_full(http_client, wh_line.id, wh_token)

    first = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    second = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 400, second.text
    assert second.json()["error_code"] == "delivery_orders.line_already_in_delivery"


@requires_api
def test_delivery_cannot_exceed_dispatched_quantity(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("100"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="5")
    wh_line = _warehouse_line_for_request(db, request_id)
    wh_token = _login(http_client, WAREHOUSE_USER)
    _receive_and_issue_full(http_client, wh_line.id, wh_token)

    delivery = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    assert delivery.status_code == 201, delivery.text
    order = delivery.json()
    order_id = order["id"]
    line_id = order["lines"][0]["id"]

    d_token = _login(http_client, DELIVERY_USER)
    http_client.post(
        f"/api/v1/delivery-orders/{order_id}/out-for-delivery",
        headers={**_auth(d_token), **_idem()},
    )
    over = http_client.post(
        f"/api/v1/delivery-orders/{order_id}/deliver",
        json={
            "receiver_name": "Receiver",
            "lines": [{"line_id": line_id, "qty_received": "6", "shortage_reason": "test"}],
        },
        headers={**_auth(d_token), **_idem()},
    )
    assert over.status_code == 400, over.text
    assert over.json()["error_code"] == "delivery_orders.invalid_received_qty"


@requires_api
def test_delivered_updates_branch_stock_and_partial_records_shortage(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("100"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="5")
    wh_line = _warehouse_line_for_request(db, request_id)
    wh_token = _login(http_client, WAREHOUSE_USER)
    _receive_and_issue_full(http_client, wh_line.id, wh_token)

    delivery = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    order = delivery.json()
    order_id = order["id"]
    line_id = order["lines"][0]["id"]

    branch_stock_before = (
        db.query(BranchStock)
        .filter(BranchStock.branch_id == ctx["branch_id"], BranchStock.item_id == ctx["warehouse_item_id"])
        .first()
    )
    before_qty = Decimal(str(branch_stock_before.current_qty)) if branch_stock_before else Decimal("0")

    d_token = _login(http_client, DELIVERY_USER)
    http_client.post(
        f"/api/v1/delivery-orders/{order_id}/out-for-delivery",
        headers={**_auth(d_token), **_idem()},
    )
    delivered = http_client.post(
        f"/api/v1/delivery-orders/{order_id}/deliver",
        json={
            "receiver_name": "Arkan Receiver",
            "lines": [{"line_id": line_id, "qty_received": "3", "shortage_reason": "damaged in transit"}],
        },
        headers={**_auth(d_token), **_idem()},
    )
    assert delivered.status_code == 200, delivered.text
    body = delivered.json()
    assert body["status"] == DeliveryOrderStatus.PARTIAL_DELIVERED.value
    assert Decimal(body["lines"][0]["shortage_qty"]) == Decimal("2")
    assert body["lines"][0]["shortage_reason"] == "damaged in transit"

    db.expire_all()
    branch_stock_after = (
        db.query(BranchStock)
        .filter(BranchStock.branch_id == ctx["branch_id"], BranchStock.item_id == ctx["warehouse_item_id"])
        .first()
    )
    assert Decimal(str(branch_stock_after.current_qty)) == before_qty + Decimal("3")

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "delivery_order",
            AuditLog.entity_id == order_id,
            AuditLog.action == "delivery_partial_delivered",
        )
        .first()
    )
    assert audit is not None


@requires_api
def test_delivery_user_cannot_access_other_warehouse_scope(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("100"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="2")
    wh_line = _warehouse_line_for_request(db, request_id)
    wh_token = _login(http_client, WAREHOUSE_USER)
    _receive_and_issue_full(http_client, wh_line.id, wh_token)

    delivery = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    order_id = delivery.json()["id"]

    wrong_token = _login(http_client, WRONG_DELIVERY_USER)
    out = http_client.post(
        f"/api/v1/delivery-orders/{order_id}/out-for-delivery",
        headers={**_auth(wrong_token), **_idem()},
    )
    assert out.status_code == 403


@requires_api
def test_phase4_warehouse_happy_path_regression(http_client: httpx.Client, db: Session):
    """Regression: Phase 4 scenario B warehouse item full flow still passes."""
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("200"))
    request_id = _create_submit_approve(http_client, ctx, ctx["warehouse_item_id"], qty="3")
    wh_line = _warehouse_line_for_request(db, request_id)
    assert wh_line is not None

    wh_token = _login(http_client, WAREHOUSE_USER)
    _receive_and_issue_full(http_client, wh_line.id, wh_token)

    delivery = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    assert delivery.status_code == 201, delivery.text
    order_id = delivery.json()["id"]

    d_token = _login(http_client, DELIVERY_USER)
    http_client.post(
        f"/api/v1/delivery-orders/{order_id}/out-for-delivery",
        headers={**_auth(d_token), **_idem()},
    )
    delivered = http_client.post(
        f"/api/v1/delivery-orders/{order_id}/deliver",
        json={"receiver_name": "Arkan Receiver"},
        headers={**_auth(d_token), **_idem()},
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == DeliveryOrderStatus.DELIVERED.value
