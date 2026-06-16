"""
Reporting simulation — Jan–Jun 2026 operational history for local/dev dashboards only.

Uses existing router/service workflow (no HTTP). Timestamp backdating via SQL inside this script only.

Usage (from backend/):
    python generate_reporting_simulation_data.py \\
        --start-date 2026-01-01 \\
        --end-date 2026-06-16 \\
        --seed 20260616 \\
        --i-understand-this-is-simulation \\
        --write-report

Requires PostgreSQL dev/simulation database. Refuses production / LAN trial DB names.
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
from urllib.parse import urlparse

_BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
os.chdir(str(_BACKEND))

from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal
from app.models import (
    AuditLog,
    Branch,
    BranchBrand,
    BranchRequest,
    BranchRequestLine,
    BranchRequestStatus,
    Brand,
    DeliveryOrder,
    DeliveryOrderStatus,
    Item,
    ItemBrand,
    ProductionOrder,
    ProductionOrderStatus,
    WarehouseLine,
    WarehouseLineStatus,
    WarehouseStock,
)
from app.schemas import (
    BranchRequestApprovePayload,
    BranchRequestCreate,
    BranchRequestLineCreate,
    BranchRequestRejectPayload,
    DeliveryOrderCreate,
    DeliveryOrderDeliverPayload,
    DeliveryOrderLineReceipt,
    WarehouseDelayPayload,
    WarehouseIssuePayload,
)
from app.routers.branch_requests import (
    approve_branch_request,
    create_branch_request,
    reject_branch_request,
    submit_branch_request,
)
from app.routers.delivery_orders import create_delivery_order, deliver_order, out_for_delivery
from app.routers.production_orders import mark_ready, send_to_warehouse, start_production_order
from app.routers.warehouse_lines import add_delay_reason, issue_line, partial_issue_line, receive_line

from simulation_data_generator import (
    AREA_MANAGER_BY_SCOPE,
    COMMIT_EVERY,
    DEFAULT_RIYADH_AREA,
    FALLBACK_ADMIN,
    HIGH_VOLUME_CODES,
    LOW_VOLUME_CODES,
    MEDIUM_VOLUME_CODES,
    SimContext,
    SimHttpRequest,
    SimStats,
    TIER_WEIGHT,
    BranchSimProfile,
    _area_manager_for,
    _backdate_request_tree,
    _backdate_table,
    _branch_user_for,
    _delivery_user_for,
    _ensure_warehouse_stock,
    _kitchen_user_for,
    _load_requestable_items,
    _pick_items,
    _rand_time_on_day,
    _user_by_username,
    _warehouse_user_for,
)

# ── Safety ───────────────────────────────────────────────────────────────────

FORBIDDEN_DB_FRAGMENTS = (
    "production",
    "prod_",
    "_prod",
    "lan_trial",
    "lan-trial",
    "lantrial",
    "staging",
    "railway",
)

ALLOWED_DB_HINTS = (
    "simulation",
    "sim_",
    "_sim",
    "dev",
    "local",
    "demo",
    "reporting",
    "raed_inventory",  # local dev default
)

# Arabic delay / shortage labels (reporting realism)
DELAY_REASONS_AR = (
    "تأخير مطبخ",
    "نقص مخزون",
    "تأخير مورد",
    "تأخير توصيل",
    "أخرى",
)

SHORTAGE_REASONS_AR = (
    "نقص عند الاستلام",
    "تلف أثناء النقل",
    "فرق في العد",
)

REJECTION_NOTES = (
    "كميات غير مناسبة للفرع",
    "طلب مكرر — يرجى التنسيق مع المشرف",
    "صنف غير متاح حالياً",
)

BRANCH_NAME_MAPPING = {
    "Onda 1 - ARKAN": "Onda Arkan (BR-DM-ON-ARKAN)",
    "Pizza 1 - AlKHOBAR": "Ronaldos Al Khobar (BR-DM-RN-KHOBR)",
    "ONDA DAU University": "Onda DAU University (BR-DM-ON-DAU)",
    "Ronaldos DAU University": "Ronaldos DAU University (BR-DM-RN-DAU)",
    "Onda 14 - HASSA": "Onda Hassa (BR-DM-ON-HASSA)",
    "Onda 16 - Najmah": "Onda Najmah (BR-DM-ON-NAJMA)",
    "Pizza 4 - Riyadh Takhasosy": "Ronaldos Riyadh Takhasosy (BR-RY-RN-TAKHS)",
    "Pizza 6 - Riyadh Nada": "Ronaldos Riyadh Nada (BR-RY-RN-NADA)",
    "Onda 18 - Al Midra Gym": "Onda Al Midra Gym (BR-DM-ON-MIDRA)",
    "Onda 9 - Ras Tanura": "Onda Ras Tanura (BR-DM-ON-RASTN)",
    "Pizza 15 - Ras Tanura": "Ronaldos Ras Tanura (BR-DM-RN-RASTN)",
}


@dataclass
class ReportingStats(SimStats):
    rejections: int = 0
    items_covered: set[int] = field(default_factory=set)
    by_month: Counter = field(default_factory=Counter)
    branches_touched: set[int] = field(default_factory=set)
    outcome_counts: Counter = field(default_factory=Counter)
    opening_stock_items: int = 0


def _db_name_from_url(url: str) -> str:
    parsed = urlparse(url.replace("+psycopg2", "").replace("+psycopg", ""))
    path = (parsed.path or "").lstrip("/")
    return path.split("?")[0].lower()


def assert_simulation_database(*, understood: bool, dry_run: bool) -> str:
    if not understood and not dry_run:
        raise SystemExit(
            "Refusing to run: pass --i-understand-this-is-simulation to confirm this is a dev/simulation database."
        )
    db_name = _db_name_from_url(settings.DATABASE_URL)
    if not db_name:
        raise SystemExit(f"Cannot parse database name from DATABASE_URL: {settings.DATABASE_URL!r}")
    lower = db_name.lower()
    for frag in FORBIDDEN_DB_FRAGMENTS:
        if frag in lower:
            raise SystemExit(
                f"Refusing to run on database {db_name!r} — name contains forbidden fragment {frag!r}."
            )
    if not any(h in lower for h in ALLOWED_DB_HINTS):
        raise SystemExit(
            f"Refusing to run on database {db_name!r}. "
            f"Name must suggest dev/simulation ({', '.join(ALLOWED_DB_HINTS)}) "
            "or use a dedicated reporting DB."
        )
    if not settings.DATABASE_URL.lower().startswith("postgresql"):
        raise SystemExit("Reporting simulation requires PostgreSQL.")
    return db_name


def _tier_for_code(code: str) -> str:
    if code in HIGH_VOLUME_CODES:
        return "high"
    if code in MEDIUM_VOLUME_CODES:
        return "medium"
    if code in LOW_VOLUME_CODES:
        return "low"
    return "medium"


def _build_all_official_profiles(db: Session) -> list[BranchSimProfile]:
    """Every official Phase 2 branch (seed_official_branches OFFICIAL_BRANCHES)."""
    profiles: list[BranchSimProfile] = []
    branches = (
        db.query(Branch)
        .filter(Branch.active == True, Branch.is_deleted == False)  # noqa: E712
        .filter(Branch.branch_code.like("BR-%"))
        .order_by(Branch.branch_code)
        .all()
    )
    for branch in branches:
        bb_rows = db.query(BranchBrand).filter(BranchBrand.branch_id == branch.id).all()
        if not bb_rows:
            continue
        try:
            branch_user = _branch_user_for(db, branch.id)
        except RuntimeError:
            continue
        for bb in bb_rows:
            brand = db.query(Brand).filter(Brand.id == bb.brand_id).first()
            if not brand:
                continue
            profiles.append(
                BranchSimProfile(
                    branch=branch,
                    brand_id=brand.id,
                    brand_name=brand.name,
                    tier=_tier_for_code(branch.branch_code or ""),
                    branch_user=branch_user,
                    area_manager=_area_manager_for(db, branch.city or "", brand.name),
                    warehouse_user=_warehouse_user_for(db, branch.warehouse_id),
                    delivery_user=_delivery_user_for(db, branch.warehouse_id),
                )
            )
    if not profiles:
        raise RuntimeError("No official branch profiles — run seed_official_branches.py and seed_phase2_official_users.py")
    return profiles


def _requests_for_day(rng, day: date, *, min_per_day: int, max_per_day: int) -> int:
    weekday = day.weekday()
    is_peak = weekday in (3, 4) or day.day in (1, 15)
    lo = min_per_day + (3 if is_peak else 0)
    hi = max_per_day + (5 if is_peak else 0)
    return rng.randint(lo, hi)


def _pick_profile(ctx: SimContext) -> BranchSimProfile:
    weights = [TIER_WEIGHT[p.tier] for p in ctx.profiles]
    return ctx.rng.choices(ctx.profiles, weights=weights, k=1)[0]


def _all_requestable_items(ctx: SimContext) -> list[tuple[int, Item]]:
    seen: dict[int, Item] = {}
    for brand_id, pools in ctx.items_by_brand.items():
        for key in ("warehouse", "kitchen", "both"):
            for item in pools.get(key, []):
                seen[item.id] = item
    return [(bid, seen[bid]) for bid in sorted(seen)]


def _process_warehouse_line(
    ctx: SimContext,
    profile: BranchSimProfile,
    wl_id: int,
    *,
    mode: str = "full",
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

    if mode == "receive_only":
        ctx.stats.outcome_counts["warehouse_pending"] += 1
        return

    roll = ctx.rng.random()
    if mode == "backorder" or roll < ctx.backorder_rate:
        reason = ctx.rng.choice(DELAY_REASONS_AR)
        add_delay_reason(wl_id, WarehouseDelayPayload(delay_reason=reason), req, db, wh_user)
        ctx.stats.backorders += 1
        ctx.stats.warehouse_delays += 1
        ctx.stats.delay_reasons[reason] += 1
        ctx.stats.outcome_counts["backorder"] += 1
        return

    if mode == "partial" or roll < ctx.backorder_rate + ctx.partial_rate:
        partial_qty = (pending * Decimal("0.7")).quantize(Decimal("0.001"))
        if partial_qty <= 0 or partial_qty >= pending:
            partial_qty = max(Decimal("1"), pending - Decimal("1"))
        reason = "نقص مخزون"
        partial_issue_line(
            wl_id,
            WarehouseIssuePayload(qty=partial_qty, delay_reason=reason),
            req,
            db,
            wh_user,
        )
        ctx.stats.partial_issues += 1
        ctx.stats.delay_reasons[reason] += 1
        ctx.stats.outcome_counts["partial_fulfillment"] += 1
        row = db.query(WarehouseLine).filter(WarehouseLine.id == wl_id).first()
        if mode == "partial" or not row or Decimal(str(row.issued_qty or 0)) <= 0:
            return
    else:
        issue_line(wl_id, WarehouseIssuePayload(), req, db, wh_user)

    row = db.query(WarehouseLine).filter(WarehouseLine.id == wl_id).first()
    if not row or Decimal(str(row.issued_qty or 0)) <= 0:
        return

    if mode == "issue_only":
        ctx.stats.outcome_counts["ready_to_issue"] += 1
        return

    delivery = create_delivery_order(
        DeliveryOrderCreate(warehouse_line_ids=[wl_id]),
        req,
        db,
        wh_user,
    )
    ctx.stats.deliveries += 1
    ctx.stats.entity_ids["delivery_orders"].append(delivery.id)

    if mode == "ready_dispatch":
        ctx.stats.outcome_counts["ready_for_dispatch"] += 1
        return

    out_for_delivery(delivery.id, req, db, profile.delivery_user)

    if mode == "out_for_delivery":
        ctx.stats.outcome_counts["out_for_delivery"] += 1
        return

    order = (
        db.query(DeliveryOrder)
        .options(joinedload(DeliveryOrder.lines))
        .filter(DeliveryOrder.id == delivery.id)
        .first()
    )
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
                        shortage_reason=ctx.rng.choice(SHORTAGE_REASONS_AR),
                    )
                )
        if receipts:
            lines_payload = receipts
            ctx.stats.delivery_shortages += 1
            ctx.stats.outcome_counts["delivery_shortage"] += 1

    deliver_order(
        delivery.id,
        DeliveryOrderDeliverPayload(receiver_name="Branch Receiver", lines=lines_payload),
        req,
        db,
        profile.delivery_user,
    )
    ctx.stats.outcome_counts["delivered"] += 1


def _process_production_order(
    ctx: SimContext,
    profile: BranchSimProfile,
    po_id: int,
    *,
    mode: str = "full",
) -> None:
    db = ctx.db
    po = (
        db.query(ProductionOrder)
        .options(joinedload(ProductionOrder.item))
        .filter(ProductionOrder.id == po_id)
        .first()
    )
    if not po or not po.item:
        return
    kitchen_user = _kitchen_user_for(db, po.kitchen_section_id, profile.branch.city or "Dammam")
    req = SimHttpRequest()
    start_production_order(po_id, req, db, kitchen_user)

    if mode == "in_progress" or ctx.rng.random() < ctx.kitchen_delay_rate:
        ctx.stats.kitchen_delays += 1
        ctx.stats.outcome_counts["in_production"] += 1
        return

    mark_ready(po_id, req, db, kitchen_user)
    send_to_warehouse(po_id, req, db, kitchen_user)
    ctx.stats.outcome_counts["sent_to_warehouse"] += 1

    from app.models import WarehouseLineSourceType

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
        wh_mode = "full" if mode == "full" else mode
        _process_warehouse_line(ctx, profile, wl.id, mode=wh_mode)


def _process_request(
    ctx: SimContext,
    profile: BranchSimProfile,
    sim_day: date,
    *,
    forced_items: list[tuple[Item, Decimal]] | None = None,
) -> None:
    db = ctx.db
    stats: ReportingStats = ctx.stats  # type: ignore[assignment]
    sim_ts = _rand_time_on_day(ctx.rng, sim_day)
    picks = forced_items or _pick_items(ctx, profile.brand_id, ctx.rng.randint(1, 2))
    if not picks:
        stats.other_errors += 1
        return

    lines = [BranchRequestLineCreate(item_id=item.id, qty_requested=qty) for item, qty in picks]
    req = SimHttpRequest()
    try:
        created = create_branch_request(
            BranchRequestCreate(
                branch_id=profile.branch.id,
                brand_id=profile.brand_id,
                priority="normal",
                lines=lines,
            ),
            req,
            db,
            profile.branch_user,
        )
        submit_branch_request(created.id, req, db, profile.branch_user)
    except Exception:
        db.rollback()
        stats.split_failures += 1
        return

    if ctx.rng.random() < 0.02:
        try:
            reject_branch_request(
                created.id,
                BranchRequestRejectPayload(rejection_note=ctx.rng.choice(REJECTION_NOTES)),
                req,
                db,
                profile.area_manager,
            )
            stats.rejections += 1
            stats.outcome_counts["rejected"] += 1
            stats.requests_created += 1
            stats.by_branch[profile.branch.branch_code or profile.branch.branch_name] += 1
            stats.by_brand[profile.brand_name] += 1
            stats.by_city[profile.branch.city or "Unknown"] += 1
            stats.by_month[sim_day.strftime("%Y-%m")] += 1
            stats.branches_touched.add(profile.branch.id)
            _backdate_table(db, "branch_requests", [created.id], sim_ts, {"updated_at": sim_ts + timedelta(hours=2)})
            db.commit()
            return
        except Exception:
            db.rollback()
            stats.other_errors += 1
            return

    try:
        approved = approve_branch_request(
            created.id,
            BranchRequestApprovePayload(approval_note="Simulated approval"),
            req,
            db,
            profile.area_manager,
        )
    except Exception:
        db.rollback()
        stats.split_failures += 1
        return

    stats.requests_created += 1
    stats.by_branch[profile.branch.branch_code or profile.branch.branch_name] += 1
    stats.by_brand[profile.brand_name] += 1
    stats.by_city[profile.branch.city or "Unknown"] += 1
    stats.by_month[sim_day.strftime("%Y-%m")] += 1
    stats.branches_touched.add(profile.branch.id)
    for item, qty in picks:
        stats.item_request_counts[item.item_name_en or item.item_code] += 1
        stats.items_covered.add(item.id)

    request_id = approved.id
    from app.models import WarehouseLineSourceType

    po_ids = [
        row.id
        for row in db.query(ProductionOrder.id)
        .filter(ProductionOrder.source_request_id == request_id)
        .all()
    ]
    wl_ids = [
        row.id
        for row in db.query(WarehouseLine.id)
        .filter(
            WarehouseLine.source_request_id == request_id,
            WarehouseLine.source_type == WarehouseLineSourceType.BRANCH_REQUEST,
        )
        .all()
    ]
    stats.production_orders += len(po_ids)
    stats.warehouse_lines += len(wl_ids)

    outcome_roll = ctx.rng.random()
    if outcome_roll < 0.08:
        wh_mode = "receive_only"
        po_mode = "in_progress"
    elif outcome_roll < 0.13:
        wh_mode = "issue_only"
        po_mode = "in_progress"
    elif outcome_roll < 0.18:
        wh_mode = "partial"
        po_mode = "full"
    elif outcome_roll < 0.21:
        wh_mode = "backorder"
        po_mode = "full"
    elif outcome_roll < 0.23:
        wh_mode = "out_for_delivery"
        po_mode = "full"
    else:
        wh_mode = "full"
        po_mode = "full"

    for po_id in po_ids:
        _process_production_order(ctx, profile, po_id, mode=po_mode)
    for wl_id in wl_ids:
        _process_warehouse_line(ctx, profile, wl_id, mode=wh_mode)

    _backdate_request_tree(db, request_id, sim_ts)
    db.commit()


def _profile_for_item(db: Session, ctx: SimContext, item_id: int) -> BranchSimProfile | None:
    brand_ids = {row[0] for row in db.query(ItemBrand.brand_id).filter(ItemBrand.item_id == item_id).all()}
    exact = [p for p in ctx.profiles if p.brand_id in brand_ids]
    if exact:
        return exact[0]
    branch_ids = set()
    for bid in brand_ids:
        branch_ids.update(
            row[0] for row in db.query(BranchBrand.branch_id).filter(BranchBrand.brand_id == bid).all()
        )
    for profile in ctx.profiles:
        if profile.branch.id in branch_ids:
            return profile
    return None


def _profiles_for_item(db: Session, ctx: SimContext, item_id: int) -> list[BranchSimProfile]:
    brand_ids = {row[0] for row in db.query(ItemBrand.brand_id).filter(ItemBrand.item_id == item_id).all()}
    exact = [p for p in ctx.profiles if p.brand_id in brand_ids]
    if exact:
        return exact
    branch_ids: set[int] = set()
    for bid in brand_ids:
        branch_ids.update(
            row[0] for row in db.query(BranchBrand.branch_id).filter(BranchBrand.brand_id == bid).all()
        )
    return [p for p in ctx.profiles if p.branch.id in branch_ids]


def _ensure_item_coverage_pass(
    ctx: SimContext,
    start_day: date,
    end_day: date,
    all_items: list[tuple[int, Item]],
) -> None:
    db = ctx.db
    stats: ReportingStats = ctx.stats  # type: ignore[assignment]
    missing = [(iid, item) for iid, item in all_items if iid not in stats.items_covered]
    if not missing:
        return
    total_days = (end_day - start_day).days + 1
    failed: list[str] = []
    for idx, (item_id, item) in enumerate(missing):
        profiles = _profiles_for_item(db, ctx, item_id)
        if not profiles:
            failed.append(item.item_code or str(item_id))
            continue
        day_offset = int((idx / max(len(missing), 1)) * (total_days - 1))
        sim_day = start_day + timedelta(days=day_offset)
        qty = Decimal(str(ctx.rng.randint(2, 8)))
        covered = False
        for profile in profiles:
            try:
                before = stats.items_covered.copy()
                _process_request(ctx, profile, sim_day, forced_items=[(item, qty)])
                if item_id in stats.items_covered and item_id not in before:
                    covered = True
                    break
            except Exception:
                db.rollback()
        if not covered:
            failed.append(item.item_code or str(item_id))
    if failed:
        print(f"  Item coverage: {len(failed)} still missing — {failed[:5]}{'…' if len(failed) > 5 else ''}")


def _refresh_stats_from_db(stats: ReportingStats, db: Session) -> None:
    """Populate reporting counters from DB (for --coverage-only / report refresh)."""
    from app.models import Branch

    stats.requests_created = db.query(BranchRequest).count()
    stats.items_covered = {row[0] for row in db.query(BranchRequestLine.item_id).distinct().all()}
    stats.branches_touched = {row[0] for row in db.query(BranchRequest.branch_id).distinct().all()}
    stats.by_month = Counter(
        dict(
            db.query(func.to_char(BranchRequest.created_at, "YYYY-MM"), func.count())
            .group_by(func.to_char(BranchRequest.created_at, "YYYY-MM"))
            .all()
        )
    )
    stats.by_branch = Counter()
    stats.by_brand = Counter()
    stats.by_city = Counter()
    stats.item_request_counts = Counter()
    for code, name, city, brand_name, cnt in (
        db.query(
            Branch.branch_code,
            Branch.branch_name,
            Branch.city,
            Brand.name,
            func.count(BranchRequest.id),
        )
        .join(BranchRequest, BranchRequest.branch_id == Branch.id)
        .join(Brand, Brand.id == BranchRequest.brand_id)
        .group_by(Branch.branch_code, Branch.branch_name, Branch.city, Brand.name)
        .all()
    ):
        stats.by_branch[code or name] += cnt
        stats.by_brand[brand_name] += cnt
        stats.by_city[city or "Unknown"] += cnt
    for item_name, item_code, cnt in (
        db.query(Item.item_name_en, Item.item_code, func.count(BranchRequestLine.id))
        .join(BranchRequestLine, BranchRequestLine.item_id == Item.id)
        .group_by(Item.item_name_en, Item.item_code)
        .all()
    ):
        stats.item_request_counts[item_name or item_code] += cnt
    stats.rejections = (
        db.query(BranchRequest).filter(BranchRequest.status == BranchRequestStatus.AREA_REJECTED).count()
    )


def _measure_api_perf() -> dict[str, float]:
    try:
        import httpx
    except ImportError:
        return {}
    base = os.environ.get("REPORTING_SIM_API_BASE", "http://127.0.0.1:8010").rstrip("/")
    password = os.environ.get("PHASE2_DEMO_PASSWORD", "Raed@Demo2026")
    timings: dict[str, float] = {}
    try:
        with httpx.Client(base_url=base, timeout=60.0) as client:
            login = client.post("/api/v1/auth/login", json={"username": "super.admin", "password": password})
            if login.status_code != 200:
                return {"login_failed_ms": 0}
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            for label, path in (
                ("supply_chain_dashboard_ms", "/api/v1/supply-chain/dashboard"),
                ("dashboard_global_ms", "/api/v1/dashboard/global"),
                ("warehouse_lines_ms", "/api/v1/warehouse-lines"),
                ("branch_requests_ms", "/api/v1/branch-requests?page_size=5"),
                ("delivery_orders_ms", "/api/v1/delivery-orders"),
                ("notifications_summary_ms", "/api/v1/notifications/summary"),
            ):
                t0 = time.perf_counter()
                r = client.get(path, headers=headers)
                timings[label] = (time.perf_counter() - t0) * 1000
                timings[f"{label}_status"] = float(r.status_code)
    except Exception:
        return {}
    return timings


def run_reporting_simulation(
    *,
    start_date: date,
    end_date: date,
    seed: int,
    min_per_day: int = 3,
    max_per_day: int = 10,
    dry_run: bool = False,
    coverage_only: bool = False,
    write_report: bool = False,
    report_path: Path | None = None,
    db: Session | None = None,
) -> ReportingStats:
    import random

    rng = random.Random(seed)
    own_session = db is None
    db = db or SessionLocal()
    stats = ReportingStats()
    ctx = SimContext(
        db=db,
        rng=rng,
        stats=stats,
        items_by_brand={},
        kitchen_users={},
        admin_user=_user_by_username(db, FALLBACK_ADMIN),
        profiles=[],
        kitchen_delay_rate=0.08,
        warehouse_delay_rate=0.03,
        partial_rate=0.05,
        backorder_rate=0.03,
        shortage_rate=0.02,
    )

    try:
        ctx.items_by_brand = _load_requestable_items(db)
        ctx.profiles = _build_all_official_profiles(db)
        all_items = _all_requestable_items(ctx)

        stock_item_ids: set[int] = set()
        warehouse_ids: set[int] = set()
        for profile in ctx.profiles:
            warehouse_ids.add(profile.branch.warehouse_id)
            pools = ctx.items_by_brand.get(profile.brand_id, {})
            for item in pools.get("warehouse", []) + pools.get("both", []):
                stock_item_ids.add(item.id)
        for wh_id in warehouse_ids:
            _ensure_warehouse_stock(db, wh_id, stock_item_ids, qty=Decimal("50000"))
        stats.opening_stock_items = len(stock_item_ids) * len(warehouse_ids)

        stats.sim_start = datetime.combine(start_date, datetime.min.time())
        stats.sim_end = datetime.combine(end_date, datetime.max.time())

        print(
            f"Reporting simulation: {start_date} -> {end_date}, seed={seed}, "
            f"branches={len(ctx.profiles)}, requestable_items={len(all_items)}"
        )
        if dry_run:
            total_days = (end_date - start_date).days + 1
            est = sum(_requests_for_day(rng, start_date + timedelta(days=i), min_per_day=min_per_day, max_per_day=max_per_day) for i in range(total_days))
            print(f"DRY RUN: would simulate ~{est} requests over {total_days} days (+ item coverage pass)")
            return stats

        unique_branches = len({p.branch.id for p in ctx.profiles})

        if coverage_only:
            print("Coverage-only mode: skipping daily request loop, refreshing stats from DB…")
            _refresh_stats_from_db(stats, db)
        else:
            day_cursor = start_date
            processed = 0
            while day_cursor <= end_date:
                n = _requests_for_day(rng, day_cursor, min_per_day=min_per_day, max_per_day=max_per_day)
                for _ in range(n):
                    profile = _pick_profile(ctx)
                    _process_request(ctx, profile, day_cursor)
                    processed += 1
                    if processed % COMMIT_EVERY == 0:
                        print(f"  … {processed} requests (through {day_cursor})")
                day_cursor += timedelta(days=1)

        print(f"Item coverage pass ({len(all_items) - len(stats.items_covered)} items remaining)…")
        _ensure_item_coverage_pass(ctx, start_date, end_date, all_items)
        _refresh_stats_from_db(stats, db)

        stats.perf_ms = {
            **{
                f"db_count_{k}_ms": v
                for k, v in (
                    ("branch_requests", _time_count(db, BranchRequest)),
                    ("warehouse_lines", _time_count(db, WarehouseLine)),
                    ("delivery_orders", _time_count(db, DeliveryOrder)),
                    ("audit_logs", _time_count(db, AuditLog)),
                )
            },
            **_measure_api_perf(),
        }

        if write_report:
            _write_reporting_report(
                stats,
                db,
                start_date,
                end_date,
                seed,
                report_path,
                official_profiles=unique_branches,
                profile_rows=len(ctx.profiles),
                all_items_count=len(all_items),
            )

        print(
            f"Done: requests={stats.requests_created} rejections={stats.rejections} "
            f"items_covered={len(stats.items_covered)}/{len(all_items)} "
            f"branches_touched={len(stats.branches_touched)}/{unique_branches}"
        )
        return stats
    finally:
        if own_session:
            db.close()


def _time_count(db: Session, model) -> float:
    t0 = time.perf_counter()
    db.query(model).count()
    return (time.perf_counter() - t0) * 1000


def _status_distribution(db: Session) -> dict[str, int]:
    br = dict(db.query(BranchRequest.status, func.count()).group_by(BranchRequest.status).all())
    po = dict(db.query(ProductionOrder.status, func.count()).group_by(ProductionOrder.status).all())
    wl = dict(db.query(WarehouseLine.status, func.count()).group_by(WarehouseLine.status).all())
    do = dict(db.query(DeliveryOrder.status, func.count()).group_by(DeliveryOrder.status).all())
    return {
        "branch_requests": {str(k): v for k, v in br.items()},
        "production_orders": {str(k): v for k, v in po.items()},
        "warehouse_lines": {str(k): v for k, v in wl.items()},
        "delivery_orders": {str(k): v for k, v in do.items()},
    }


def _write_reporting_report(
    stats: ReportingStats,
    db: Session,
    start_date: date,
    end_date: date,
    seed: int,
    report_path: Path | None,
    *,
    official_profiles: int,
    profile_rows: int,
    all_items_count: int,
) -> None:
    repo_root = _BACKEND.parent.parent
    path = report_path or (repo_root / "REPORTING_SIMULATION_DATA_REPORT.md")
    db_name = _db_name_from_url(settings.DATABASE_URL)
    status_dist = _status_distribution(db)
    total_br = db.query(BranchRequest).count()
    total_po = db.query(ProductionOrder).count()
    total_wl = db.query(WarehouseLine).count()
    total_do = db.query(DeliveryOrder).count()
    total_audit = db.query(AuditLog).count()
    partial_wl = db.query(WarehouseLine).filter(WarehouseLine.status == WarehouseLineStatus.PARTIAL).count()
    backorder_wl = db.query(WarehouseLine).filter(WarehouseLine.status == WarehouseLineStatus.BACKORDER).count()
    shortage_do = db.query(DeliveryOrder).filter(DeliveryOrder.status == DeliveryOrderStatus.PARTIAL_DELIVERED).count()
    rejected_br = db.query(BranchRequest).filter(BranchRequest.status == BranchRequestStatus.AREA_REJECTED).count()
    in_prog_po = db.query(ProductionOrder).filter(ProductionOrder.status == ProductionOrderStatus.IN_PROGRESS).count()

    top_items = stats.item_request_counts.most_common(20)
    branches_official = db.query(Branch).filter(
        Branch.branch_code.like("BR-%"), Branch.active == True  # noqa: E712
    ).count()
    branches_official_total = db.query(Branch).filter(Branch.branch_code.like("BR-%")).count()

    verdict = "REPORTS_READY"
    gaps: list[str] = []
    if len(stats.items_covered) < all_items_count:
        gaps.append(f"Item coverage {len(stats.items_covered)}/{all_items_count}")
        verdict = "REPORTS_READY_WITH_WARNINGS"
    if len(stats.branches_touched) < official_profiles:
        gaps.append(f"Branch activity {len(stats.branches_touched)}/{official_profiles}")
        verdict = "REPORTS_READY_WITH_WARNINGS"

    path.write_text(
        f"""# Reporting Simulation Data Report

**Generated:** {datetime.utcnow().isoformat(timespec="seconds")} UTC  
**Database:** `{db_name}` (dev/simulation only)  
**Date range:** {start_date} → {end_date}  
**Seed:** {seed}

---

## 1. Safety Checks

| Check | Result |
|-------|--------|
| `--i-understand-this-is-simulation` | Required and confirmed |
| PostgreSQL only | PASS |
| Forbidden DB names blocked | PASS |
| Service-layer workflow (no HTTP bulk) | PASS |
| Timestamp backdating | SQL in script only |

---

## 2. Date Range

```text
{start_date} to {end_date}
```

---

## 3. Seed Used

```text
{seed}
```

---

## 4. Branches Covered

Official active branches (BR-%): **{branches_official}** (total seeded: **{branches_official_total}**)  
Branch profiles with users: **{profile_rows}** (multi-brand branches may have >1 profile)  
Unique branches with activity: **{len(stats.branches_touched)}** / **{official_profiles}**

Note: Griddle-only branches (`BR-*-GRI-*`) have no dedicated branch login; Griddle items are simulated via multi-brand branch **Shawarma Olaya** (`BR-RY-SH-OLAYA`).

Name mapping (spec → DB):

{chr(10).join(f'- {k} → {v}' for k, v in BRANCH_NAME_MAPPING.items())}

---

## 5. Items Covered

Requestable items in master: **{all_items_count}**  
Items appearing in this run: **{len(stats.items_covered)}**  
Simulated opening stock rows touched: **{stats.opening_stock_items}**

---

## 6. Total Requests Generated

| Metric | This run | DB total |
|--------|----------|----------|
| Branch requests | {stats.requests_created:,} | {total_br:,} |
| Rejections | {stats.rejections:,} | {rejected_br:,} |

---

## 7. Requests By Month

{chr(10).join(f'- {m}: {c:,}' for m, c in sorted(stats.by_month.items()))}

---

## 8. Requests By Branch

{chr(10).join(f'- {k}: {c:,}' for k, c in stats.by_branch.most_common())}

---

## 9. Requests By Brand

{chr(10).join(f'- {k}: {c:,}' for k, c in stats.by_brand.most_common())}

---

## 10. Requests By City

{chr(10).join(f'- {k}: {c:,}' for k, c in stats.by_city.most_common())}

---

## 11. Status Distribution

### Branch requests
{chr(10).join(f'- {k}: {v:,}' for k, v in status_dist.get("branch_requests", {}).items())}

### Production orders
{chr(10).join(f'- {k}: {v:,}' for k, v in status_dist.get("production_orders", {}).items())}

### Warehouse lines
{chr(10).join(f'- {k}: {v:,}' for k, v in status_dist.get("warehouse_lines", {}).items())}

### Delivery orders
{chr(10).join(f'- {k}: {v:,}' for k, v in status_dist.get("delivery_orders", {}).items())}

### Sim run outcome tags
{chr(10).join(f'- {k}: {v:,}' for k, v in stats.outcome_counts.most_common())}

---

## 12. Production Orders Generated

This run: **{stats.production_orders:,}** | DB total: **{total_po:,}** | IN_PROGRESS: **{in_prog_po:,}**

---

## 13. Warehouse Lines Generated

This run: **{stats.warehouse_lines:,}** | DB total: **{total_wl:,}**

---

## 14. Deliveries Generated

This run: **{stats.deliveries:,}** | DB total: **{total_do:,}**

---

## 15. Partial Fulfillment Count

Sim partial issues: **{stats.partial_issues:,}** | DB PARTIAL lines: **{partial_wl:,}**

---

## 16. Backorder Count

Sim backorders: **{stats.backorders:,}** | DB BACKORDER lines: **{backorder_wl:,}**

---

## 17. Delivery Shortage Count

Sim shortages: **{stats.delivery_shortages:,}** | DB PARTIAL_DELIVERED orders: **{shortage_do:,}**

---

## 18. Delay Reasons Summary

{chr(10).join(f'- {reason}: {cnt:,}' for reason, cnt in stats.delay_reasons.most_common())}

---

## 19. Top 20 Items

{chr(10).join(f'{i+1}. {name} — {cnt:,}' for i, (name, cnt) in enumerate(top_items))}

---

## 20. Audit Events

DB total audit logs: **{total_audit:,}**

---

## 21. Notifications

Notifications are computed live from workflow state via `GET /api/v1/notifications/summary` (no separate notification table). Supply-chain sections populate when pending approvals, warehouse lines, and deliveries exist.

---

## 22. Integrity Validation Results

Run: `pytest tests/test_reporting_simulation_data.py -v`

---

## 23. Performance Snapshot

| Endpoint / query | ms |
|------------------|-----|
{chr(10).join(f'| {k} | {v:.1f} |' for k, v in stats.perf_ms.items() if not k.endswith("_status"))}

---

## 24. Remaining Data Gaps

{chr(10).join(f'- {g}' for g in gaps) if gaps else '- None identified for reporting review'}

---

## 25. Report Readiness Verdict

**{verdict}**

Local dev database `{db_name}` now contains Jan–Jun 2026 backdated operational history suitable for dashboard and report review. **Do not use this database for LAN trial or production.**

""",
        encoding="utf-8",
    )
    print(f"Wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reporting simulation Jan–Jun 2026 (dev DB only)")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 16))
    parser.add_argument("--seed", type=int, default=20260616)
    parser.add_argument("--min-requests-per-day", type=int, default=3)
    parser.add_argument("--max-requests-per-day", type=int, default=10)
    parser.add_argument("--i-understand-this-is-simulation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--coverage-only",
        action="store_true",
        help="Skip daily loop; refresh stats and run item coverage pass only (existing DB data).",
    )
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    db_name = assert_simulation_database(understood=args.i_understand_this_is_simulation, dry_run=args.dry_run)
    print(f"Target database: {db_name}")

    if args.start_date > args.end_date:
        raise SystemExit("start-date must be <= end-date")

    run_reporting_simulation(
        start_date=args.start_date,
        end_date=args.end_date,
        seed=args.seed,
        min_per_day=args.min_requests_per_day,
        max_per_day=args.max_requests_per_day,
        dry_run=args.dry_run,
        coverage_only=args.coverage_only,
        write_report=args.write_report,
    )


if __name__ == "__main__":
    main()
