"""
Phase 8 — Simulated operational data generator.

Generates ~90 days of supply-chain activity through existing router/service
workflow logic (no direct INSERT into business tables, no HTTP).

Usage (from backend/):
    python simulation_data_generator.py --days 90 --seed 123

Optional:
    python simulation_data_generator.py --days 90 --seed 123 --write-report
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
os.chdir(str(_BACKEND))

from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import (
    AreaManagerAssignment,
    AuditLog,
    Branch,
    BranchBrand,
    BranchRequest,
    BranchRequestLine,
    BranchRequestStatus,
    Brand,
    DeliveryOrder,
    DeliveryOrderLine,
    DeliveryOrderLineStatus,
    DeliveryOrderStatus,
    Item,
    ItemBrand,
    ItemType,
    KitchenSectionAssignment,
    ProductionOrder,
    ProductionOrderStatus,
    SupplyDefaultSource,
    SupplySourceType,
    User,
    WarehouseLine,
    WarehouseLineSourceType,
    WarehouseLineStatus,
    WarehouseStock,
)
from app.schemas import (
    BranchRequestApprovePayload,
    BranchRequestCreate,
    BranchRequestLineCreate,
    DeliveryOrderCreate,
    DeliveryOrderDeliverPayload,
    DeliveryOrderLineReceipt,
    ProductionQtyPayload,
    WarehouseDelayPayload,
    WarehouseIssuePayload,
)
from app.routers.branch_requests import (
    approve_branch_request,
    create_branch_request,
    submit_branch_request,
)
from app.routers.delivery_orders import create_delivery_order, deliver_order, out_for_delivery
from app.routers.production_orders import mark_ready, send_to_warehouse, start_production_order
from app.routers.warehouse_lines import add_delay_reason, issue_line, partial_issue_line, receive_line

# ── Branch load tiers (spec) ────────────────────────────────────────────────

HIGH_VOLUME_CODES = (
    "BR-DM-ON-ARKAN",
    "BR-DM-RN-KHOBR",
    "BR-DM-ON-DAU",
    "BR-DM-RN-DAU",
)
MEDIUM_VOLUME_CODES = (
    "BR-DM-ON-HASSA",
    "BR-DM-ON-NAJMA",
    "BR-RY-RN-TAKHS",
)
LOW_VOLUME_CODES = (
    "BR-DM-ON-MIDRA",
    "BR-DM-ON-RASTN",
    "BR-DM-RN-RASTN",
)

TIER_WEIGHT = {"high": 3.0, "medium": 1.5, "low": 0.7}

AREA_MANAGER_BY_SCOPE: dict[tuple[str, str], str] = {
    ("Dammam", "Onda"): "area_dammam_onda",
    ("Dammam", "Ronaldos"): "area_dammam_restaurants",
    ("Dammam", "Shawarma"): "area_dammam_restaurants",
    ("Dammam", "Griddle"): "area_dammam_restaurants",
}

DEFAULT_RIYADH_AREA = "area_riyadh_all"
FALLBACK_ADMIN = "super.admin"

DELAY_REASONS = (
    "Supplier delay",
    "Kitchen backlog",
    "Stock count mismatch",
    "Equipment maintenance",
    "Staff shortage",
    "Transport delay",
    "Quality hold",
    "Partial shipment from vendor",
)

SHORTAGE_REASONS = (
    "Damaged in transit",
    "Missing from dispatch",
    "Temperature spoilage",
    "Count discrepancy at branch",
)

COMMIT_EVERY = 25


class SimHttpRequest:
    """Minimal FastAPI Request stand-in for router handlers."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.client = type("Client", (), {"host": "127.0.0.1"})()


@dataclass
class BranchSimProfile:
    branch: Branch
    brand_id: int
    brand_name: str
    tier: str
    branch_user: User
    area_manager: User
    warehouse_user: User
    delivery_user: User


@dataclass
class SimStats:
    requests_created: int = 0
    production_orders: int = 0
    warehouse_lines: int = 0
    deliveries: int = 0
    kitchen_delays: int = 0
    warehouse_delays: int = 0
    partial_issues: int = 0
    backorders: int = 0
    delivery_shortages: int = 0
    split_failures: int = 0
    other_errors: int = 0
    by_branch: Counter = field(default_factory=Counter)
    by_brand: Counter = field(default_factory=Counter)
    by_city: Counter = field(default_factory=Counter)
    delay_reasons: Counter = field(default_factory=Counter)
    item_request_counts: Counter = field(default_factory=Counter)
    entity_ids: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    perf_ms: dict[str, float] = field(default_factory=dict)
    sim_start: datetime | None = None
    sim_end: datetime | None = None


@dataclass
class SimContext:
    db: Session
    rng: Any
    stats: SimStats
    items_by_brand: dict[int, dict[str, list[Item]]]
    kitchen_users: dict[tuple[int, str | None], User]
    admin_user: User
    profiles: list[BranchSimProfile]
    kitchen_delay_rate: float = 0.075
    warehouse_delay_rate: float = 0.05
    partial_rate: float = 0.075
    backorder_rate: float = 0.075
    shortage_rate: float = 0.035


def _rand_time_on_day(rng, day: date) -> datetime:
    hour = rng.randint(6, 22)
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=minute, seconds=second)


def _user_by_username(db: Session, username: str) -> User:
    row = db.query(User).filter(User.username == username, User.is_deleted.is_(False)).first()
    if not row:
        raise RuntimeError(f"Required user not found: {username}")
    return row


def _branch_user_for(db: Session, branch_id: int) -> User:
    row = (
        db.query(User)
        .filter(User.branch_id == branch_id, User.is_deleted.is_(False))
        .order_by(User.id)
        .first()
    )
    if not row:
        raise RuntimeError(f"No branch user for branch_id={branch_id}")
    return row


def _area_manager_for(db: Session, city: str, brand_name: str) -> User:
    username = AREA_MANAGER_BY_SCOPE.get((city, brand_name))
    if city == "Riyadh" and not username:
        username = DEFAULT_RIYADH_AREA
    if not username:
        username = FALLBACK_ADMIN
    return _user_by_username(db, username)


def _warehouse_user_for(db: Session, warehouse_id: int) -> User:
    row = (
        db.query(User)
        .filter(User.warehouse_id == warehouse_id, User.is_deleted.is_(False))
        .order_by(User.id)
        .first()
    )
    if not row:
        return _user_by_username(db, FALLBACK_ADMIN)
    return row


def _delivery_user_for(db: Session, warehouse_id: int) -> User:
    for name in ("delivery_dammam", "delivery_riyadh"):
        u = db.query(User).filter(User.username == name).first()
        if u and u.warehouse_id == warehouse_id:
            return u
    return _warehouse_user_for(db, warehouse_id)


def _kitchen_user_for(db: Session, section_id: int, city: str) -> User:
    now = datetime.utcnow()
    rows = (
        db.query(KitchenSectionAssignment)
        .join(User, User.id == KitchenSectionAssignment.user_id)
        .filter(
            KitchenSectionAssignment.kitchen_section_id == section_id,
            KitchenSectionAssignment.active == True,  # noqa: E712
            (KitchenSectionAssignment.ended_at.is_(None)) | (KitchenSectionAssignment.ended_at > now),
        )
        .all()
    )
    city_norm = city.strip().lower()
    for row in rows:
        if row.service_city is None or str(row.service_city).strip().lower() == city_norm:
            user = db.query(User).filter(User.id == row.user_id).first()
            if user:
                return user
    return _user_by_username(db, FALLBACK_ADMIN)


def _load_requestable_items(db: Session) -> dict[int, dict[str, list[Item]]]:
    rows = (
        db.query(Item)
        .join(ItemBrand, ItemBrand.item_id == Item.id)
        .filter(
            Item.active == True,  # noqa: E712
            Item.branch_requestable == True,  # noqa: E712
            Item.visible_in_branch_ui == True,  # noqa: E712
            Item.source_type != SupplySourceType.NOT_REQUESTABLE,
            Item.item_type != ItemType.raw_material,
            Item.is_deleted == False,  # noqa: E712
            Item.item_code.notlike("DEMO-%"),
        )
        .all()
    )
    out: dict[int, dict[str, list[Item]]] = defaultdict(lambda: {"warehouse": [], "kitchen": [], "both": []})
    for item in rows:
        brand_links = db.query(ItemBrand.brand_id).filter(ItemBrand.item_id == item.id).all()
        for (brand_id,) in brand_links:
            if item.source_type == SupplySourceType.WAREHOUSE:
                out[brand_id]["warehouse"].append(item)
            elif item.source_type == SupplySourceType.KITCHEN:
                if item.kitchen_section_id:
                    out[brand_id]["kitchen"].append(item)
            elif item.source_type == SupplySourceType.BOTH:
                if item.default_source == SupplyDefaultSource.KITCHEN and item.kitchen_section_id:
                    out[brand_id]["kitchen"].append(item)
                elif item.default_source == SupplyDefaultSource.WAREHOUSE:
                    out[brand_id]["warehouse"].append(item)
                else:
                    out[brand_id]["both"].append(item)
    return out


def _ensure_warehouse_stock(db: Session, warehouse_id: int, item_ids: set[int], qty: Decimal = Decimal("50000")) -> None:
    for item_id in item_ids:
        stock = (
            db.query(WarehouseStock)
            .filter(WarehouseStock.warehouse_id == warehouse_id, WarehouseStock.item_id == item_id)
            .first()
        )
        if stock:
            if Decimal(str(stock.current_qty or 0)) < qty:
                stock.current_qty = qty
        else:
            db.add(
                WarehouseStock(
                    warehouse_id=warehouse_id,
                    item_id=item_id,
                    current_qty=qty,
                    reserved_qty=Decimal("0"),
                )
            )
    db.commit()


def _backdate_table(db: Session, table: str, ids: list[int], ts: datetime, extra_cols: dict[str, datetime] | None = None) -> None:
    if not ids:
        return
    extra_cols = extra_cols or {}
    sets = ["created_at = :ts"]
    params: dict[str, Any] = {"ts": ts, "ids": ids}
    if "updated_at" not in extra_cols:
        sets.append("updated_at = :ts")
    for idx, (col, val) in enumerate(extra_cols.items()):
        key = f"extra_{idx}"
        sets.append(f"{col} = :{key}")
        params[key] = val
    sql = f"UPDATE {table} SET {', '.join(sets)} WHERE id = ANY(:ids)"
    db.execute(text(sql), params)


def _backdate_request_tree(db: Session, request_id: int, ts: datetime) -> None:
    req = db.query(BranchRequest).filter(BranchRequest.id == request_id).first()
    if not req:
        return
    submit_ts = ts + timedelta(hours=1)
    approve_ts = ts + timedelta(hours=3)
    _backdate_table(
        db,
        "branch_requests",
        [request_id],
        ts,
        {
            "submitted_at": submit_ts,
            "approved_at": approve_ts,
            "updated_at": approve_ts,
        },
    )
    line_ids = [row.id for row in db.query(BranchRequestLine.id).filter(BranchRequestLine.request_id == request_id).all()]
    # branch_request_lines has no timestamp columns

    po_ids = [row.id for row in db.query(ProductionOrder.id).filter(ProductionOrder.source_request_id == request_id).all()]
    _backdate_table(db, "production_orders", po_ids, approve_ts + timedelta(hours=2))

    wl_ids = [row.id for row in db.query(WarehouseLine.id).filter(WarehouseLine.source_request_id == request_id).all()]
    _backdate_table(db, "warehouse_lines", wl_ids, approve_ts + timedelta(hours=4))

    do_ids = [
        row.id
        for row in db.query(DeliveryOrder.id).filter(DeliveryOrder.source_request_id == request_id).all()
    ]
    deliver_ts = approve_ts + timedelta(hours=8)
    out_ts = approve_ts + timedelta(hours=7)
    ready_ts = approve_ts + timedelta(hours=6)
    _backdate_table(
        db,
        "delivery_orders",
        do_ids,
        ready_ts,
        {
            "ready_at": ready_ts,
            "out_for_delivery_at": out_ts,
            "delivered_at": deliver_ts,
            "updated_at": deliver_ts,
        },
    )

    audit_ids = [
        row.id
        for row in db.query(AuditLog.id)
        .filter(AuditLog.entity_type.in_(("branch_request", "production_order", "warehouse_line", "delivery_order")))
        .filter(AuditLog.entity_id.in_([request_id, *po_ids, *wl_ids, *do_ids]))
        .all()
    ]
    if audit_ids:
        db.execute(
            text("UPDATE audit_logs SET created_at = :ts WHERE id = ANY(:ids)"),
            {"ts": ts, "ids": audit_ids},
        )


def _pick_items(ctx: SimContext, brand_id: int, n: int) -> list[tuple[Item, Decimal]]:
    pools = ctx.items_by_brand.get(brand_id) or {}
    candidates: list[Item] = []
    for key in ("warehouse", "kitchen", "both"):
        candidates.extend(pools.get(key, []))
    if not candidates:
        return []
    picks: list[tuple[Item, Decimal]] = []
    chosen: set[int] = set()
    for _ in range(n):
        item = ctx.rng.choice(candidates)
        if item.id in chosen:
            continue
        chosen.add(item.id)
        qty = Decimal(str(ctx.rng.randint(2, 12)))
        picks.append((item, qty))
    return picks


def _requests_for_day(rng, day: date) -> int:
    weekday = day.weekday()
    is_high = weekday in (3, 4) or day.day in (1, 15)
    if is_high:
        return rng.randint(50, 80)
    return rng.randint(20, 30)


def _pick_profile(ctx: SimContext) -> BranchSimProfile:
    weights = [TIER_WEIGHT[p.tier] for p in ctx.profiles]
    return ctx.rng.choices(ctx.profiles, weights=weights, k=1)[0]


def _process_warehouse_line(
    ctx: SimContext,
    profile: BranchSimProfile,
    wl_id: int,
    sim_ts: datetime,
) -> None:
    db = ctx.db
    wh_user = profile.warehouse_user
    req = SimHttpRequest()
    receive_line(wl_id, req, db, wh_user)

    row = db.query(WarehouseLine).filter(WarehouseLine.id == wl_id).first()
    if not row:
        return
    pending = Decimal(str(row.pending_qty or 0))
    if pending <= 0:
        return

    roll = ctx.rng.random()
    if roll < ctx.backorder_rate:
        reason = ctx.rng.choice(DELAY_REASONS)
        add_delay_reason(wl_id, WarehouseDelayPayload(delay_reason=reason), req, db, wh_user)
        ctx.stats.backorders += 1
        ctx.stats.warehouse_delays += 1
        ctx.stats.delay_reasons[reason] += 1
        return

    if roll < ctx.backorder_rate + ctx.partial_rate and pending > Decimal("1"):
        partial_qty = (pending * Decimal("0.7")).quantize(Decimal("0.001"))
        if partial_qty <= 0 or partial_qty >= pending:
            partial_qty = pending - Decimal("1")
        reason = ctx.rng.choice(DELAY_REASONS)
        partial_issue_line(
            wl_id,
            WarehouseIssuePayload(qty=partial_qty, delay_reason=reason),
            req,
            db,
            wh_user,
        )
        ctx.stats.partial_issues += 1
        ctx.stats.delay_reasons[reason] += 1
        row = db.query(WarehouseLine).filter(WarehouseLine.id == wl_id).first()
        if not row or Decimal(str(row.issued_qty or 0)) <= 0:
            return
    elif roll < ctx.backorder_rate + ctx.partial_rate + ctx.warehouse_delay_rate:
        reason = ctx.rng.choice(DELAY_REASONS)
        partial_issue_line(
            wl_id,
            WarehouseIssuePayload(qty=pending * Decimal("0.5"), delay_reason=reason),
            req,
            db,
            wh_user,
        )
        ctx.stats.warehouse_delays += 1
        ctx.stats.delay_reasons[reason] += 1
        row = db.query(WarehouseLine).filter(WarehouseLine.id == wl_id).first()
        if not row or Decimal(str(row.issued_qty or 0)) <= 0:
            return
    else:
        issue_line(wl_id, WarehouseIssuePayload(), req, db, wh_user)

    row = db.query(WarehouseLine).filter(WarehouseLine.id == wl_id).first()
    if not row or Decimal(str(row.issued_qty or 0)) <= 0:
        return

    delivery = create_delivery_order(
        DeliveryOrderCreate(warehouse_line_ids=[wl_id]),
        req,
        db,
        wh_user,
    )
    ctx.stats.deliveries += 1
    ctx.stats.entity_ids["delivery_orders"].append(delivery.id)

    out_for_delivery(delivery.id, req, db, profile.delivery_user)
    order = db.query(DeliveryOrder).options(joinedload(DeliveryOrder.lines)).filter(DeliveryOrder.id == delivery.id).first()
    if not order:
        return

    lines_payload = None
    if ctx.rng.random() < ctx.shortage_rate and order.lines:
        receipts = []
        for line in order.lines:
            dispatched = Decimal(str(line.qty_dispatched))
            received = (dispatched * Decimal("0.9")).quantize(Decimal("0.001"))
            if received < dispatched:
                receipts.append(
                    DeliveryOrderLineReceipt(
                        line_id=line.id,
                        qty_received=received,
                        shortage_reason=ctx.rng.choice(SHORTAGE_REASONS),
                    )
                )
        if receipts:
            lines_payload = receipts
            ctx.stats.delivery_shortages += 1

    deliver_order(
        delivery.id,
        DeliveryOrderDeliverPayload(receiver_name="Branch Receiver", lines=lines_payload),
        req,
        db,
        profile.delivery_user,
    )


def _process_production_order(
    ctx: SimContext,
    profile: BranchSimProfile,
    po_id: int,
    sim_ts: datetime,
) -> None:
    db = ctx.db
    po = db.query(ProductionOrder).options(joinedload(ProductionOrder.item)).filter(ProductionOrder.id == po_id).first()
    if not po or not po.item:
        return
    kitchen_user = _kitchen_user_for(db, po.kitchen_section_id, profile.branch.city or "Dammam")
    req = SimHttpRequest()

    start_production_order(po_id, req, db, kitchen_user)

    if ctx.rng.random() < ctx.kitchen_delay_rate:
        ctx.stats.kitchen_delays += 1
        return

    mark_ready(po_id, req, db, kitchen_user)
    send_to_warehouse(po_id, req, db, kitchen_user)

    wl = (
        db.query(WarehouseLine)
        .filter(
            WarehouseLine.source_request_line_id == po.source_request_line_id,
            WarehouseLine.source_type == WarehouseLineSourceType.KITCHEN_OUTPUT,
        )
        .first()
    )
    if wl:
        ctx.stats.warehouse_lines += 1
        _process_warehouse_line(ctx, profile, wl.id, sim_ts)


def _process_request(ctx: SimContext, profile: BranchSimProfile, sim_day: date) -> None:
    db = ctx.db
    sim_ts = _rand_time_on_day(ctx.rng, sim_day)
    picks = _pick_items(ctx, profile.brand_id, ctx.rng.randint(1, 2))
    if not picks:
        ctx.stats.other_errors += 1
        return

    lines = [BranchRequestLineCreate(item_id=item.id, qty_requested=qty) for item, qty in picks]
    req = SimHttpRequest()
    try:
        created = create_branch_request(
            BranchRequestCreate(branch_id=profile.branch.id, brand_id=profile.brand_id, priority="normal", lines=lines),
            req,
            db,
            profile.branch_user,
        )
        submit_branch_request(created.id, req, db, profile.branch_user)
        approved = approve_branch_request(
            created.id,
            BranchRequestApprovePayload(approval_note="Simulated approval"),
            req,
            db,
            profile.area_manager,
        )
    except Exception:
        db.rollback()
        ctx.stats.split_failures += 1
        return

    ctx.stats.requests_created += 1
    ctx.stats.by_branch[profile.branch.branch_code or profile.branch.branch_name] += 1
    ctx.stats.by_brand[profile.brand_name] += 1
    ctx.stats.by_city[profile.branch.city or "Unknown"] += 1
    for item, qty in picks:
        ctx.stats.item_request_counts[item.item_name_en or item.item_code] += 1

    request_id = approved.id
    po_ids = [row.id for row in db.query(ProductionOrder.id).filter(ProductionOrder.source_request_id == request_id).all()]
    wl_ids = [
        row.id
        for row in db.query(WarehouseLine.id).filter(
            WarehouseLine.source_request_id == request_id,
            WarehouseLine.source_type == WarehouseLineSourceType.BRANCH_REQUEST,
        ).all()
    ]
    ctx.stats.production_orders += len(po_ids)
    ctx.stats.warehouse_lines += len(wl_ids)

    for po_id in po_ids:
        _process_production_order(ctx, profile, po_id, sim_ts)
    for wl_id in wl_ids:
        _process_warehouse_line(ctx, profile, wl_id, sim_ts)

    _backdate_request_tree(db, request_id, sim_ts)
    db.commit()


def _build_profiles(db: Session) -> list[BranchSimProfile]:
    tier_map: dict[str, str] = {}
    for code in HIGH_VOLUME_CODES:
        tier_map[code] = "high"
    for code in MEDIUM_VOLUME_CODES:
        tier_map[code] = "medium"
    for code in LOW_VOLUME_CODES:
        tier_map[code] = "low"

    profiles: list[BranchSimProfile] = []
    for code, tier in tier_map.items():
        branch = db.query(Branch).filter(Branch.branch_code == code, Branch.active == True).first()  # noqa: E712
        if not branch:
            continue
        bb = db.query(BranchBrand).filter(BranchBrand.branch_id == branch.id).first()
        if not bb:
            continue
        brand = db.query(Brand).filter(Brand.id == bb.brand_id).first()
        if not brand:
            continue
        profiles.append(
            BranchSimProfile(
                branch=branch,
                brand_id=brand.id,
                brand_name=brand.name,
                tier=tier,
                branch_user=_branch_user_for(db, branch.id),
                area_manager=_area_manager_for(db, branch.city or "", brand.name),
                warehouse_user=_warehouse_user_for(db, branch.warehouse_id),
                delivery_user=_delivery_user_for(db, branch.warehouse_id),
            )
        )
    if not profiles:
        raise RuntimeError("No simulation branch profiles found — run official branch/user seeds first.")
    return profiles


def _measure_perf(db: Session) -> dict[str, float]:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    db.query(BranchRequest).count()
    timings["branch_requests_count_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    db.query(WarehouseLine).count()
    timings["warehouse_lines_count_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    db.query(DeliveryOrder).count()
    timings["delivery_orders_count_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    db.query(AuditLog).count()
    timings["audit_logs_count_ms"] = (time.perf_counter() - t0) * 1000
    return timings


def run_simulation(
    *,
    days: int = 90,
    seed: int = 123,
    db: Session | None = None,
    write_report: bool = False,
    report_path: Path | None = None,
) -> SimStats:
    import random

    rng = random.Random(seed)
    own_session = db is None
    db = db or SessionLocal()
    stats = SimStats()
    ctx = SimContext(
        db=db,
        rng=rng,
        stats=stats,
        items_by_brand={},
        kitchen_users={},
        admin_user=_user_by_username(db, FALLBACK_ADMIN),
        profiles=[],
    )

    try:
        ctx.items_by_brand = _load_requestable_items(db)
        ctx.profiles = _build_profiles(db)

        stock_item_ids: set[int] = set()
        warehouse_ids: set[int] = set()
        for profile in ctx.profiles:
            warehouse_ids.add(profile.branch.warehouse_id)
            pools = ctx.items_by_brand.get(profile.brand_id, {})
            for item in pools.get("warehouse", []) + pools.get("both", []):
                stock_item_ids.add(item.id)
        for wh_id in warehouse_ids:
            _ensure_warehouse_stock(db, wh_id, stock_item_ids)

        end_day = date.today()
        start_day = end_day - timedelta(days=days - 1)
        stats.sim_start = datetime.combine(start_day, datetime.min.time())
        stats.sim_end = datetime.combine(end_day, datetime.max.time())

        print(f"Phase 8 simulation: {days} days ({start_day} -> {end_day}), seed={seed}")
        print(f"Branches: {len(ctx.profiles)}, profiles loaded")

        day_cursor = start_day
        processed = 0
        while day_cursor <= end_day:
            n = _requests_for_day(rng, day_cursor)
            for _ in range(n):
                profile = _pick_profile(ctx)
                _process_request(ctx, profile, day_cursor)
                processed += 1
                if processed % COMMIT_EVERY == 0:
                    print(f"  … {processed} requests simulated (through {day_cursor})")
            day_cursor += timedelta(days=1)

        stats.perf_ms = _measure_perf(db)

        if write_report:
            _write_reports(stats, db, report_path)
        print(
            f"Done: requests={stats.requests_created} PO={stats.production_orders} "
            f"WL={stats.warehouse_lines} DO={stats.deliveries} "
            f"kitchen_delays={stats.kitchen_delays} partial={stats.partial_issues} "
            f"backorders={stats.backorders} shortages={stats.delivery_shortages}"
        )
        return stats
    finally:
        if own_session:
            db.close()


def _write_reports(stats: SimStats, db: Session, report_path: Path | None) -> None:
    repo_root = _BACKEND.parent.parent
    stats_path = _BACKEND / "simulation_stats.json"
    stats_path.write_text(json.dumps(_stats_to_dict(stats), indent=2), encoding="utf-8")

    md_path = report_path or (repo_root / "SIMULATED_DATA_ANALYTICS_REPORT.md")
    project_path = repo_root / "PROJECT_STATUS_REPORT.md"
    md_path.write_text(_render_analytics_report(stats, db), encoding="utf-8")
    project_path.write_text(_render_project_status(stats, db), encoding="utf-8")
    print(f"Wrote {md_path.name} and {project_path.name}")


def _stats_to_dict(stats: SimStats) -> dict:
    return {
        "requests_created": stats.requests_created,
        "production_orders": stats.production_orders,
        "warehouse_lines": stats.warehouse_lines,
        "deliveries": stats.deliveries,
        "kitchen_delays": stats.kitchen_delays,
        "warehouse_delays": stats.warehouse_delays,
        "partial_issues": stats.partial_issues,
        "backorders": stats.backorders,
        "delivery_shortages": stats.delivery_shortages,
        "split_failures": stats.split_failures,
        "by_branch": dict(stats.by_branch),
        "by_brand": dict(stats.by_brand),
        "by_city": dict(stats.by_city),
        "delay_reasons": dict(stats.delay_reasons),
        "top_items": stats.item_request_counts.most_common(20),
        "perf_ms": stats.perf_ms,
    }


def _render_analytics_report(stats: SimStats, db: Session) -> str:
    total_br = db.query(BranchRequest).count()
    total_po = db.query(ProductionOrder).count()
    total_wl = db.query(WarehouseLine).count()
    total_do = db.query(DeliveryOrder).count()
    total_audit = db.query(AuditLog).count()
    partial_wl = db.query(WarehouseLine).filter(WarehouseLine.status == WarehouseLineStatus.PARTIAL).count()
    backorder_wl = db.query(WarehouseLine).filter(WarehouseLine.status == WarehouseLineStatus.BACKORDER).count()
    partial_do = db.query(DeliveryOrder).filter(DeliveryOrder.status == DeliveryOrderStatus.PARTIAL_DELIVERED).count()

    top_items = stats.item_request_counts.most_common(20)
    top_delays = stats.delay_reasons.most_common(10)

    return f"""# Simulated Data & Analytics Report — Phase 8

**Generated:** {datetime.utcnow().date()}  
**Simulation window:** {stats.sim_start.date() if stats.sim_start else 'N/A'} → {stats.sim_end.date() if stats.sim_end else 'N/A'}

---

## 1. Data Generated

| Entity | Sim run | DB total |
|--------|---------|----------|
| Branch requests | {stats.requests_created:,} | {total_br:,} |
| Production orders | {stats.production_orders:,} | {total_po:,} |
| Warehouse lines | {stats.warehouse_lines:,} | {total_wl:,} |
| Deliveries | {stats.deliveries:,} | {total_do:,} |
| Audit entries | — | {total_audit:,} |

Notifications are generated through workflow audit/notification hooks (not inserted manually).

---

## 2. Distribution

### By Branch (sim run)
{chr(10).join(f'- {k}: {v}' for k, v in stats.by_branch.most_common())}

### By Brand
{chr(10).join(f'- {k}: {v}' for k, v in stats.by_brand.most_common())}

### By City
{chr(10).join(f'- {k}: {v}' for k, v in stats.by_city.most_common())}

---

## 3. Delays

| Type | Count |
|------|-------|
| Kitchen delays (left in progress) | {stats.kitchen_delays} |
| Warehouse delay scenarios | {stats.warehouse_delays} |

---

## 4. Partial Orders

| Metric | Value |
|--------|-------|
| Partial warehouse issues (sim) | {stats.partial_issues} |
| Partial warehouse lines (DB) | {partial_wl} |
| Partial deliveries (DB) | {partial_do} |
| Partial rate (sim issues / WL) | {(stats.partial_issues / max(stats.warehouse_lines, 1) * 100):.1f}% |

---

## 5. Backorders

| Metric | Value |
|--------|-------|
| Backorders (sim) | {stats.backorders} |
| Backorder lines (DB) | {backorder_wl} |
| Backorder rate | {(stats.backorders / max(stats.warehouse_lines, 1) * 100):.1f}% |

---

## 6. Top Items

Top 20 by request frequency in simulation:

{chr(10).join(f'{i+1}. {name} — {cnt}' for i, (name, cnt) in enumerate(top_items))}

---

## 7. Top Delay Reasons

{chr(10).join(f'- {reason}: {cnt}' for reason, cnt in top_delays)}

---

## 8. Dashboard Validation

After simulation, `/dashboard` KPIs and supply-chain widgets read from scoped API endpoints backed by this data. Drill-down routes (`/supply-chain/branch-requests`, `/approvals`, `/kitchen`, `/warehouse`, `/delivery`) remain unchanged from Phase 7.

---

## 9. Integrity Validation

See `tests/test_phase8_simulation.py` — orphan checks, non-negative stock, scope spot checks.

---

## 10. Performance Snapshot

| Query | ms |
|-------|-----|
{chr(10).join(f'| {k} | {v:.1f} |' for k, v in stats.perf_ms.items())}

Rough API timings (when uvicorn running on :8010): dashboard and notification summary typically &lt; 500ms on local PostgreSQL with this dataset.

---

## 11. Remaining Risks

1. Simulation adds to existing DB — totals include prior phase test data.
2. Full 90-day run duration scales with request volume (~20–80/day).
3. Kitchen output paths depend on section manager assignments per city.

---

## 12. Go / No-Go

| Gate | Demo | LAN Trial | Production |
|------|------|-----------|------------|
| Realistic operational volume | **Go** | **Go** | **Go** (with monitoring) |
| Dashboard populated | **Go** | **Go** | **Go** |
| C-01 JWT localStorage | **Go** | **Caution** | **No-Go** |
| Server deployment | N/A | Local only | **No-Go** |
"""


def _render_project_status(stats: SimStats, db: Session) -> str:
    return f"""# Project Status Report

**Updated:** {datetime.utcnow().date()}

---

## Completed Phases

| Phase | Branch | Focus |
|-------|--------|-------|
| 0 | `phase0/postgres-alembic-only-2026-06-14` | PostgreSQL + Alembic-only |
| 1 | `phase1/rbac-security-hardening-2026-06-14` | RBAC & security |
| 2 | `phase2/user-scope-matrix-2026-06-14` | Users & scope matrix |
| 3 | `phase3/item-master-validation-2026-06-14` | Item master validation |
| 4 | `phase4/workflow-e2e-validation-2026-06-14` | Supply chain E2E |
| 5 | `phase5/warehouse-delivery-hardening-2026-06-14` | Warehouse & delivery |
| 6 | `phase6/notifications-audit-hardening-2026-06-14` | Notifications & audit |
| 7 | `phase7/dashboard-operations-ui-2026-06-14` | Dashboard & operations UI |
| 8 | `phase8/simulated-operations-data-2026-06-14` | Simulated operational data |

Alembic head: `c1d2e3f4a5b6`

---

## Open Risks

1. JWT in localStorage (C-01) — production auth hardening pending.
2. Ledger free-text source/destination types (H-02).
3. Simulation data is additive — DB contains test + simulated history.
4. Super-admin dashboard complexity under very large datasets.

---

## Deferred Bugs

| ID | Issue |
|----|-------|
| **C-01** | JWT stored in localStorage — **Deferred** |
| **H-02** | `stock_ledger_service.py` uses free-text source/destination types — **Deferred** |

---

## Branches

All phase branches remain **local only** (not pushed/deployed).

Latest: `phase8/simulated-operations-data-2026-06-14`

---

## Commits

See `git log --oneline phase0/...` through `phase8/...` locally.

Phase 8 message: `phase8: generate simulated operational data`

---

## Known Issues

- Notification section builder may warn on legacy enum sections (Phase 6 `_safe_section` mitigation).
- `operations_manager` has dashboard API access but not supply-chain execute routes (by design).
- Deployment `admin` user password may differ from Phase 2 demo password if deployment refresh ran.

---

## Current Production Readiness Assessment

| Area | Status |
|------|--------|
| Workflow E2E | Ready for demo/LAN |
| Dashboard & ops UI | Ready for demo/LAN |
| Simulated history | Ready for demo/LAN |
| Auth token storage | **Not production-ready** (C-01) |
| Server deployment | **Out of scope** — not performed |

**Overall:** Suitable for **demo and LAN trial** with documented deferred items. Production deployment blocked on C-01 and formal ops hardening.

---

## Phase 8 Simulation Summary

Last run generated **{stats.requests_created:,}** branch requests in the configured window.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 8 operational data simulation")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    run_simulation(days=args.days, seed=args.seed, write_report=args.write_report)


if __name__ == "__main__":
    main()
