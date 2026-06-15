"""
Phase 4 — Supply Chain workflow E2E validation.

Requires:
  - PostgreSQL (DATABASE_URL from backend/.env)
  - API at PHASE4_API_BASE (default http://localhost:8010)
  - Official users seeded (seed_phase2_official_users.py)
  - Item master imported (import_classified_supply_items.py)

Run API (local shell only):
  RATE_LIMIT_ENABLED=false uvicorn app.main:app --port 8010

Run tests:
  DATABASE_URL=<postgres> PHASE4_API_BASE=http://localhost:8010 \\
    python -m pytest tests/test_phase4_supply_chain_e2e.py -v
"""
from __future__ import annotations

import os
import time
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.database import SessionLocal, engine
from app.models import (
    AuditLog,
    Branch,
    BranchRequest,
    BranchRequestLineStatus,
    BranchRequestStatus,
    Brand,
    Item,
    ItemBrand,
    ItemType,
    ProductionOrder,
    ProductionOrderStatus,
    StockTransaction,
    SupplyDefaultSource,
    SupplySourceType,
    TransactionType,
    User,
    WarehouseLine,
    WarehouseLineSourceType,
    WarehouseLineStatus,
    WarehouseStock,
    BranchStock,
    DeliveryOrderStatus,
)
from app.services.branch_request_split_service import split_branch_request

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Phase 4 E2E tests require PostgreSQL",
    ),
]

BASE = os.environ.get("PHASE4_API_BASE", "http://localhost:8010").rstrip("/")
PASSWORD = os.environ.get("PHASE4_DEMO_PASSWORD", "Raed@Demo2026")
LOGIN_DELAY = float(os.environ.get("PHASE4_LOGIN_DELAY_S", "0.3"))

BRANCH_USER = "branch_onda_1_arkan"
AREA_MANAGER = "area_dammam_onda"
WRONG_AREA_MANAGER = "area_riyadh_all"
KITCHEN_MGR = "kitchen_dammam_bakery_and_sweets_mgr"
WRONG_KITCHEN_MGR = "kitchen_dammam_pizza_mgr"
WAREHOUSE_USER = "warehouse_dammam_user"
DELIVERY_USER = "delivery_dammam"
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
    both_item = (
        db.query(Item)
        .join(ItemBrand)
        .filter(
            ItemBrand.brand_id == brand.id,
            Item.source_type == SupplySourceType.BOTH,
            Item.branch_requestable == True,
            Item.active == True,
        )
        .first()
    )
    raw_item = (
        db.query(Item)
        .join(ItemBrand)
        .filter(
            ItemBrand.brand_id == brand.id,
            Item.item_type == ItemType.raw_material,
            Item.active == True,
        )
        .first()
    )
    not_req = (
        db.query(Item)
        .join(ItemBrand)
        .filter(
            ItemBrand.brand_id == brand.id,
            Item.source_type == SupplySourceType.NOT_REQUESTABLE,
        )
        .first()
    )
    assert kitchen_item and warehouse_item
    return {
        "branch_id": branch.id,
        "brand_id": brand.id,
        "warehouse_id": branch.warehouse_id,
        "kitchen_item_id": kitchen_item.id,
        "kitchen_section_id": kitchen_item.kitchen_section_id,
        "warehouse_item_id": warehouse_item.id,
        "both_item_id": both_item.id if both_item else None,
        "raw_item_id": raw_item.id if raw_item else None,
        "not_requestable_item_id": not_req.id if not_req else None,
    }


def _ensure_warehouse_stock(db: Session, warehouse_id: int, item_id: int, qty: Decimal = Decimal("100")) -> None:
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
    elif Decimal(str(stock.current_qty)) < qty:
        stock.current_qty = qty
    db.commit()


def _create_submit(
    client: httpx.Client,
    ctx: dict,
    item_id: int,
    qty: str = "2",
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
    return request_id


def _approve(client: httpx.Client, request_id: int, area_user: str = AREA_MANAGER) -> dict:
    token = _login(client, area_user)
    time.sleep(LOGIN_DELAY)
    r = client.post(
        f"/api/v1/branch-requests/{request_id}/approve",
        json={},
        headers={**_auth(token), **_idem()},
    )
    assert r.status_code == 200, r.text
    return r.json()


@requires_api
def test_scenario_a_kitchen_item_full_flow(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    request_id = _create_submit(http_client, ctx, ctx["kitchen_item_id"], qty="2")
    approved = _approve(http_client, request_id)
    assert approved["status"] == BranchRequestStatus.SPLIT.value
    line = approved["lines"][0]
    assert line["resolved_source_type"] == SupplyDefaultSource.KITCHEN.value

    po = db.query(ProductionOrder).filter(ProductionOrder.source_request_id == request_id).first()
    assert po is not None
    assert po.kitchen_section_id == ctx["kitchen_section_id"]
    assert po.destination_branch_id == ctx["branch_id"]

    km_token = _login(http_client, KITCHEN_MGR)
    wrong_token = _login(http_client, WRONG_KITCHEN_MGR)
    listed = http_client.get("/api/v1/production-orders", headers=_auth(km_token))
    assert listed.status_code == 200
    assert po.id in {row["id"] for row in listed.json()}
    wrong_list = http_client.get("/api/v1/production-orders", headers=_auth(wrong_token))
    assert po.id not in {row["id"] for row in wrong_list.json()}

    start = http_client.post(
        f"/api/v1/production-orders/{po.id}/start",
        headers={**_auth(km_token), **_idem()},
    )
    assert start.status_code == 200, start.text
    ready = http_client.post(
        f"/api/v1/production-orders/{po.id}/mark-ready",
        headers={**_auth(km_token), **_idem()},
    )
    assert ready.status_code == 200, ready.text
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

    wh_token = _login(http_client, WAREHOUSE_USER)
    issued = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/issue",
        json={},
        headers={**_auth(wh_token), **_idem()},
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == WarehouseLineStatus.READY_FOR_DISPATCH.value

    delivery = http_client.post(
        "/api/v1/delivery-orders",
        json={"warehouse_line_ids": [wh_line.id]},
        headers={**_auth(wh_token), **_idem()},
    )
    assert delivery.status_code == 201, delivery.text
    order_id = delivery.json()["id"]

    d_token = _login(http_client, DELIVERY_USER)
    out = http_client.post(
        f"/api/v1/delivery-orders/{order_id}/out-for-delivery",
        headers={**_auth(d_token), **_idem()},
    )
    assert out.status_code == 200, out.text
    delivered = http_client.post(
        f"/api/v1/delivery-orders/{order_id}/deliver",
        json={"receiver_name": "Arkan Receiver", "delivery_note": "Phase4 kitchen E2E"},
        headers={**_auth(d_token), **_idem()},
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == DeliveryOrderStatus.DELIVERED.value

    db.expire_all()
    tx = (
        db.query(StockTransaction)
        .filter(
            StockTransaction.reference_no == f"DO-{order_id}",
            StockTransaction.transaction_type == TransactionType.branch_receipt,
        )
        .first()
    )
    assert tx is not None
    branch_stock = (
        db.query(BranchStock)
        .filter(BranchStock.branch_id == ctx["branch_id"], BranchStock.item_id == ctx["kitchen_item_id"])
        .first()
    )
    assert branch_stock is not None
    assert Decimal(str(branch_stock.current_qty)) >= Decimal("2")

    actions = {
        row.action
        for row in db.query(AuditLog)
        .filter(AuditLog.entity_id == request_id, AuditLog.entity_type == "branch_request")
        .all()
    }
    assert "request_created" in actions or any("created" in a for a in actions)


@requires_api
def test_scenario_b_warehouse_item_full_flow(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"], Decimal("200"))

    request_id = _create_submit(http_client, ctx, ctx["warehouse_item_id"], qty="3")
    approved = _approve(http_client, request_id)
    assert approved["status"] == BranchRequestStatus.SPLIT.value
    assert approved["lines"][0]["resolved_source_type"] == SupplyDefaultSource.WAREHOUSE.value

    db.expire_all()
    wh_line = (
        db.query(WarehouseLine)
        .filter(
            WarehouseLine.source_request_id == request_id,
            WarehouseLine.source_type == WarehouseLineSourceType.BRANCH_REQUEST,
        )
        .first()
    )
    assert wh_line is not None

    wh_token = _login(http_client, WAREHOUSE_USER)
    received = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/receive",
        headers={**_auth(wh_token), **_idem()},
    )
    assert received.status_code == 200, received.text

    stock_before = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["warehouse_item_id"],
        )
        .first()
    )
    current_before = Decimal(str(stock_before.current_qty))

    issued = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/issue",
        json={},
        headers={**_auth(wh_token), **_idem()},
    )
    assert issued.status_code == 200, issued.text

    db.expire_all()
    stock_after = (
        db.query(WarehouseStock)
        .filter(
            WarehouseStock.warehouse_id == ctx["warehouse_id"],
            WarehouseStock.item_id == ctx["warehouse_item_id"],
        )
        .first()
    )
    assert Decimal(str(stock_after.current_qty)) == current_before - Decimal("3")
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


@requires_api
def test_scenario_c_both_item_documentation(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    if not ctx["both_item_id"]:
        pytest.skip("No BOTH item available for Onda brand in imported item master")
    request_id = _create_submit(http_client, ctx, ctx["both_item_id"], qty="1")
    approved = _approve(http_client, request_id)
    assert approved["lines"][0]["resolved_source_type"] in {
        SupplyDefaultSource.WAREHOUSE.value,
        SupplyDefaultSource.KITCHEN.value,
    }


@requires_api
def test_permission_wrong_area_manager_cannot_approve(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    request_id = _create_submit(http_client, ctx, ctx["warehouse_item_id"], qty="1")
    token = _login(http_client, WRONG_AREA_MANAGER)
    r = http_client.post(
        f"/api/v1/branch-requests/{request_id}/approve",
        json={},
        headers={**_auth(token), **_idem()},
    )
    assert r.status_code == 403


@requires_api
def test_permission_branch_user_cannot_approve(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    request_id = _create_submit(http_client, ctx, ctx["warehouse_item_id"], qty="1")
    token = _login(http_client, BRANCH_USER)
    r = http_client.post(
        f"/api/v1/branch-requests/{request_id}/approve",
        json={},
        headers={**_auth(token), **_idem()},
    )
    assert r.status_code == 403


@requires_api
def test_permission_kitchen_cannot_issue_warehouse_stock(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"])
    request_id = _create_submit(http_client, ctx, ctx["warehouse_item_id"], qty="1")
    _approve(http_client, request_id)
    db.expire_all()
    wh_line = (
        db.query(WarehouseLine)
        .filter(WarehouseLine.source_request_id == request_id)
        .first()
    )
    wh_token = _login(http_client, WAREHOUSE_USER)
    http_client.post(f"/api/v1/warehouse-lines/{wh_line.id}/receive", headers={**_auth(wh_token), **_idem()})
    km_token = _login(http_client, KITCHEN_MGR)
    r = http_client.post(
        f"/api/v1/warehouse-lines/{wh_line.id}/issue",
        json={},
        headers={**_auth(km_token), **_idem()},
    )
    assert r.status_code == 403


@requires_api
def test_permission_delivery_scoped_to_warehouse(http_client: httpx.Client, db: Session):
    token = _login(http_client, DELIVERY_USER)
    me = http_client.get("/api/v1/auth/me", headers=_auth(token)).json()
    assert me.get("warehouse_id") is not None
    r = http_client.get("/api/v1/delivery-orders/ready", headers=_auth(token))
    assert r.status_code == 200, r.text


@requires_api
def test_permission_branch_cannot_request_raw(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    if not ctx["raw_item_id"]:
        pytest.skip("No RAW item linked to Onda brand")
    token = _login(http_client, BRANCH_USER)
    r = http_client.post(
        "/api/v1/branch-requests",
        json={
            "branch_id": ctx["branch_id"],
            "brand_id": ctx["brand_id"],
            "lines": [{"item_id": ctx["raw_item_id"], "qty_requested": "1"}],
        },
        headers={**_auth(token), **_idem()},
    )
    assert r.status_code == 400


@requires_api
def test_permission_branch_cannot_request_not_requestable(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    if not ctx["not_requestable_item_id"]:
        pytest.skip("No NOT_REQUESTABLE item linked to Onda brand")
    token = _login(http_client, BRANCH_USER)
    r = http_client.post(
        "/api/v1/branch-requests",
        json={
            "branch_id": ctx["branch_id"],
            "brand_id": ctx["brand_id"],
            "lines": [{"item_id": ctx["not_requestable_item_id"], "qty_requested": "1"}],
        },
        headers={**_auth(token), **_idem()},
    )
    assert r.status_code == 400


def test_split_unresolvable_source_raises(db: Session):
    """Service-level guard (C-04) — no silent skip."""
    from tests.test_phase3_item_master import _split_fixture  # reuse fixture builder

    request = _split_fixture(
        db,
        source_type=SupplySourceType.WAREHOUSE,
        default_source=SupplyDefaultSource.WAREHOUSE,
        resolved=SupplyDefaultSource.WAREHOUSE,
    )
    request.lines[0].resolved_source_type = None
    db.flush()
    with pytest.raises(AppError) as exc:
        split_branch_request(db, request)
    assert exc.value.error_code == "split.unresolvable_source_type"


@requires_api
def test_manual_split_retry_is_idempotent(http_client: httpx.Client, db: Session):
    ctx = _context(db)
    _ensure_warehouse_stock(db, ctx["warehouse_id"], ctx["warehouse_item_id"])
    request_id = _create_submit(http_client, ctx, ctx["warehouse_item_id"], qty="1")
    _approve(http_client, request_id)
    token = _login(http_client, AREA_MANAGER)
    retry = http_client.post(
        f"/api/v1/branch-requests/{request_id}/split",
        headers={**_auth(token), **_idem()},
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == BranchRequestStatus.SPLIT.value
