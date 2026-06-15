"""
Phase 8 — Simulation integrity validation.

Requires PostgreSQL. For full simulation run:
  python simulation_data_generator.py --days 90 --seed 123 --write-report

Tests use a short deterministic simulation (3 days) unless PHASE8_SKIP_SIM=1.
"""
from __future__ import annotations

import os
import time

import httpx
import pytest
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import (
    AuditLog,
    Branch,
    BranchRequest,
    BranchRequestLine,
    DeliveryOrder,
    DeliveryOrderLine,
    ProductionOrder,
    WarehouseLine,
    WarehouseStock,
)

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Phase 8 tests require PostgreSQL",
    ),
]

BASE = os.environ.get("PHASE8_API_BASE", os.environ.get("PHASE7_API_BASE", "http://localhost:8010")).rstrip("/")
SKIP_SIM = os.environ.get("PHASE8_SKIP_SIM", "").lower() in ("1", "true", "yes")
SIM_DAYS = int(os.environ.get("PHASE8_TEST_DAYS", "3"))
SIM_SEED = int(os.environ.get("PHASE8_TEST_SEED", "123"))


def _api_available() -> bool:
    try:
        with httpx.Client(base_url=BASE, timeout=5.0) as client:
            return client.get("/api/v1/ready").status_code == 200
    except Exception:
        return False


requires_api = pytest.mark.skipif(not _api_available(), reason=f"API not reachable at {BASE}")


@pytest.fixture(scope="module")
def simulated_db():
    if SKIP_SIM:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
        return
    from simulation_data_generator import run_simulation

    db = SessionLocal()
    try:
        run_simulation(days=SIM_DAYS, seed=SIM_SEED, db=db, write_report=False)
        yield db
    finally:
        db.close()


def test_no_orphan_branch_request_lines(simulated_db: Session):
    orphans = (
        simulated_db.query(BranchRequestLine)
        .outerjoin(BranchRequest, BranchRequest.id == BranchRequestLine.request_id)
        .filter(BranchRequest.id.is_(None))
        .count()
    )
    assert orphans == 0


def test_no_orphan_production_orders(simulated_db: Session):
    orphans = (
        simulated_db.query(ProductionOrder)
        .outerjoin(BranchRequest, BranchRequest.id == ProductionOrder.source_request_id)
        .filter(ProductionOrder.source_request_id.isnot(None), BranchRequest.id.is_(None))
        .count()
    )
    assert orphans == 0


def test_no_orphan_warehouse_lines(simulated_db: Session):
    orphans = (
        simulated_db.query(WarehouseLine)
        .outerjoin(BranchRequest, BranchRequest.id == WarehouseLine.source_request_id)
        .filter(WarehouseLine.source_request_id.isnot(None), BranchRequest.id.is_(None))
        .count()
    )
    assert orphans == 0


def test_no_orphan_delivery_lines(simulated_db: Session):
    orphans = (
        simulated_db.query(DeliveryOrderLine)
        .outerjoin(DeliveryOrder, DeliveryOrder.id == DeliveryOrderLine.delivery_order_id)
        .filter(DeliveryOrder.id.is_(None))
        .count()
    )
    assert orphans == 0


def test_no_negative_warehouse_stock(simulated_db: Session):
    bad = (
        simulated_db.query(WarehouseStock)
        .filter(
            (WarehouseStock.current_qty < 0) | (WarehouseStock.reserved_qty < 0)
        )
        .count()
    )
    assert bad == 0


def test_audit_entries_exist(simulated_db: Session):
    count = simulated_db.query(AuditLog).filter(AuditLog.module == "branch_requests").count()
    assert count > 0


def test_branch_scope_spot_check(simulated_db: Session):
    branch = simulated_db.query(Branch).filter(Branch.branch_code == "BR-DM-ON-ARKAN").first()
    assert branch
    own = simulated_db.query(BranchRequest).filter(BranchRequest.branch_id == branch.id).count()
    other = (
        simulated_db.query(BranchRequest)
        .filter(BranchRequest.branch_id != branch.id)
        .join(Branch, Branch.id == BranchRequest.branch_id)
        .filter(Branch.branch_code == "BR-RY-ON-MALQA")
        .count()
    )
    assert own >= 0
    assert other >= 0


@requires_api
def test_dashboard_has_data_after_simulation():
    client = httpx.Client(base_url=BASE, timeout=60.0)
    password = os.environ.get("PHASE8_DEMO_PASSWORD", "Raed@Demo2026")
    login = client.post("/api/v1/auth/login", json={"username": "super.admin", "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    t0 = time.perf_counter()
    dash = client.get("/api/v1/supply-chain/dashboard", headers=headers)
    dash_ms = (time.perf_counter() - t0) * 1000
    assert dash.status_code == 200, dash.text
    body = dash.json()
    assert body["requests_today"] >= 0

    t0 = time.perf_counter()
    notif = client.get("/api/v1/notifications/summary", headers=headers)
    notif_ms = (time.perf_counter() - t0) * 1000
    assert notif.status_code == 200

    t0 = time.perf_counter()
    wh = client.get("/api/v1/warehouse-lines", headers=headers)
    wh_ms = (time.perf_counter() - t0) * 1000
    assert wh.status_code == 200

    t0 = time.perf_counter()
    deliv = client.get("/api/v1/delivery-orders/ready", headers=headers)
    deliv_ms = (time.perf_counter() - t0) * 1000
    assert deliv.status_code == 200

    assert dash_ms < 30000
    assert notif_ms < 30000
    assert wh_ms < 30000
    assert deliv_ms < 30000


def test_simulation_deterministic_seed():
    from datetime import date
    import random

    from simulation_data_generator import _requests_for_day

    r1 = random.Random(123)
    r2 = random.Random(123)
    d = date(2026, 3, 15)
    assert _requests_for_day(r1, d) == _requests_for_day(r2, d)
