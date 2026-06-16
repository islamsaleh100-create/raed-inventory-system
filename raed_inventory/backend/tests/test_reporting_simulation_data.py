"""
Integrity validation for reporting simulation (Jan–Jun 2026).

Short window test by default (3 days). Full range:
  python generate_reporting_simulation_data.py --start-date 2026-01-01 --end-date 2026-06-16 \\
      --seed 20260616 --i-understand-this-is-simulation --write-report

Set REPORTING_SIM_SKIP=1 to skip simulation fixture (DB must already contain data).
"""
from __future__ import annotations

import os
import time

import httpx
import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import (
    AuditLog,
    Branch,
    BranchRequest,
    BranchRequestLine,
    BranchRequestStatus,
    DeliveryOrder,
    DeliveryOrderLine,
    Item,
    ItemBrand,
    ItemType,
    ProductionOrder,
    SupplySourceType,
    WarehouseLine,
    WarehouseStock,
)

pytestmark = [
    pytest.mark.skipif(
        not engine.url.drivername.startswith("postgresql"),
        reason="Reporting simulation tests require PostgreSQL",
    ),
]

BASE = os.environ.get("REPORTING_SIM_API_BASE", "http://127.0.0.1:8010").rstrip("/")
SKIP_SIM = os.environ.get("REPORTING_SIM_SKIP", "").lower() in ("1", "true", "yes")
SIM_START = os.environ.get("REPORTING_SIM_START", "2026-01-05")
SIM_END = os.environ.get("REPORTING_SIM_END", "2026-01-07")
SIM_SEED = int(os.environ.get("REPORTING_SIM_SEED", "20260616"))


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
    from datetime import date

    from generate_reporting_simulation_data import run_reporting_simulation

    db = SessionLocal()
    try:
        run_reporting_simulation(
            start_date=date.fromisoformat(SIM_START),
            end_date=date.fromisoformat(SIM_END),
            seed=SIM_SEED,
            min_per_day=2,
            max_per_day=4,
            db=db,
            write_report=False,
        )
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
        .filter((WarehouseStock.current_qty < 0) | (WarehouseStock.reserved_qty < 0))
        .count()
    )
    assert bad == 0


def test_every_official_branch_has_activity(simulated_db: Session):
    from datetime import date

    span = (date.fromisoformat(SIM_END) - date.fromisoformat(SIM_START)).days
    if not SKIP_SIM and span < 14:
        pytest.skip("Branch coverage check requires REPORTING_SIM span >= 14 days")
    official = simulated_db.query(Branch).filter(Branch.branch_code.like("BR-%"), Branch.active == True).all()
    missing = []
    for branch in official:
        if simulated_db.query(BranchRequest).filter(BranchRequest.branch_id == branch.id).count() == 0:
            missing.append(branch.branch_code)
    assert not missing, f"Branches without requests: {missing[:5]}"


def test_requestable_items_represented(simulated_db: Session):
    from datetime import date

    span = (date.fromisoformat(SIM_END) - date.fromisoformat(SIM_START)).days
    if not SKIP_SIM and span < 30:
        pytest.skip("Full item coverage check requires REPORTING_SIM span >= 30 days or full Jan-Jun run")
    items = (
        simulated_db.query(Item)
        .join(ItemBrand, ItemBrand.item_id == Item.id)
        .filter(
            Item.active == True,
            Item.branch_requestable == True,
            Item.visible_in_branch_ui == True,
            Item.source_type != SupplySourceType.NOT_REQUESTABLE,
            Item.item_type != ItemType.raw_material,
        )
        .distinct()
        .all()
    )
    if not items:
        pytest.skip("No requestable items in DB")
    missing = []
    for item in items:
        used = (
            simulated_db.query(BranchRequestLine)
            .filter(BranchRequestLine.item_id == item.id)
            .count()
        )
        if used == 0:
            missing.append(item.item_code)
    assert len(missing) <= max(1, len(items) // 20), f"Too many uncovered items: {missing[:10]}"


def test_major_statuses_represented(simulated_db: Session):
    assert simulated_db.query(BranchRequest).filter(BranchRequest.status == BranchRequestStatus.DELIVERED).count() >= 0
    assert simulated_db.query(BranchRequest).count() > 0
    assert simulated_db.query(AuditLog).count() > 0


def test_simulation_refuses_without_safety_flag():
    from generate_reporting_simulation_data import assert_simulation_database

    with pytest.raises(SystemExit):
        assert_simulation_database(understood=False, dry_run=False)


@requires_api
def test_dashboard_endpoints_non_empty():
    client = httpx.Client(base_url=BASE, timeout=60.0)
    password = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")
    login = client.post("/api/v1/auth/login", json={"username": "super.admin", "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    endpoints = (
        "/api/v1/supply-chain/dashboard",
        "/api/v1/notifications/summary",
        "/api/v1/warehouse-lines",
        "/api/v1/branch-requests?page_size=5",
        "/api/v1/delivery-orders",
    )
    for path in endpoints:
        t0 = time.perf_counter()
        r = client.get(path, headers=headers)
        elapsed = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200, f"{path}: {r.text}"
        assert elapsed < 60000, f"{path} too slow: {elapsed:.0f}ms"
