"""Count Audit A4 — list_findings batching and summary."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import event, func

from app.models import (
    AreaManagerAssignment,
    AuditFinding,
    Branch,
    BranchBrand,
    Brand,
    Item,
    ItemCategory,
    RoleName,
    UnitOfMeasure,
    User,
    Warehouse,
)
from app.models.branch_shift_ops import (
    BranchShift,
    BranchShiftConfig,
    BranchShiftCount,
    BranchShiftCountLine,
    BranchShiftStatus,
    ShiftCountRowStatus,
    ShiftSectionStatus,
)
from app.models.count_audit import AuditFindingEvent, AuditFindingItem
from app.services import count_audit_service as svc
from app.services.count_audit_service import QUEUE_WAITING_AUDITOR, QUEUE_WAITING_RESPONSE

from tests.test_count_audit import CA, _login, _user

FINDINGS_QUERY_CAP = 12
STATUSES = ("open", "acknowledged", "clarification_requested", "escalated", "accepted", "closed")


def _legacy_finding_list_item(db, row: AuditFinding) -> dict:
    shift = db.query(BranchShift).filter(BranchShift.id == row.entity_id).first()
    branch_name = db.query(Branch.branch_name).filter(Branch.id == row.branch_id).scalar() if row.branch_id else None
    items_count = db.query(func.count(AuditFindingItem.id)).filter(AuditFindingItem.finding_id == row.id).scalar() or 0
    last_actor = None
    if row.last_event_at:
        ev = (
            db.query(AuditFindingEvent)
            .filter(AuditFindingEvent.finding_id == row.id)
            .order_by(AuditFindingEvent.created_at.desc())
            .first()
        )
        if ev:
            last_actor = db.query(User.full_name).filter(User.id == ev.actor_id).scalar()
    creator = db.query(User.full_name).filter(User.id == row.created_by).scalar()
    age_days = max(int((datetime.utcnow() - row.created_at).total_seconds() // 86400), 0) if row.created_at else 0
    return {
        "id": row.id,
        "finding_no": row.finding_no,
        "severity": row.severity,
        "title": row.title,
        "status": row.status,
        "queue": svc._queue_for_status(row.status),
        "branch_id": row.branch_id,
        "branch_name": branch_name,
        "shift_id": row.entity_id,
        "shift_date": shift.shift_date.isoformat() if shift else None,
        "shift_number": shift.shift_number if shift else None,
        "items_count": int(items_count),
        "created_by_name": creator,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_event_at": row.last_event_at.isoformat() if row.last_event_at else None,
        "last_actor_name": last_actor,
        "age_days": age_days,
    }


def _seed_findings_fixture(db, *, n_findings: int = 120) -> dict:
    wh = Warehouse(warehouse_code="A4-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    brand = Brand(name="A4 Brand", active=True)
    db.add(brand)
    db.flush()
    cat = ItemCategory(code="A4-C", name_ar="c", name_en="c")
    unit = UnitOfMeasure(code="A4-U", name_ar="u", name_en="u")
    db.add_all([cat, unit])
    db.flush()
    item = Item(
        item_code="A4-IT",
        item_name_ar="i",
        item_name_en="i",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()
    branches = []
    for i in range(6):
        b = Branch(
            branch_code=f"A4-B{i}",
            branch_name=f"Branch {i}",
            city="Riyadh" if i < 4 else "Dammam",
            area="T",
            warehouse_id=wh.id,
            active=True,
            is_deleted=False,
        )
        db.add(b)
        db.flush()
        db.add(BranchBrand(branch_id=b.id, brand_id=brand.id))
        db.add(
            BranchShiftConfig(
                branch_id=b.id,
                shift_number=1,
                shift_name_ar="1",
                is_active=True,
                effective_from=date(2020, 1, 1),
            )
        )
        opener = _user(db, f"a4.op{i}", RoleName.branch_manager, branch_id=b.id)
        shift = BranchShift(
            branch_id=b.id,
            shift_date=date(2026, 8, 1),
            shift_number=1,
            status=BranchShiftStatus.submitted.value,
            opened_by=opener.id,
            submitted_at=datetime.utcnow(),
        )
        db.add(shift)
        db.flush()
        count = BranchShiftCount(
            shift_id=shift.id,
            status=ShiftSectionStatus.submitted.value,
            items_frozen_at=datetime.utcnow(),
            created_by=opener.id,
            submitted_at=datetime.utcnow(),
        )
        db.add(count)
        db.flush()
        db.add(
            BranchShiftCountLine(
                count_id=count.id,
                item_id=item.id,
                item_name_snapshot="i",
                unit_snapshot="u",
                opening_balance=Decimal("10"),
                closing_balance=Decimal("8"),
                movement_diff=Decimal("1"),
                row_status=ShiftCountRowStatus.valid.value,
            )
        )
        branches.append({"branch": b, "shift": shift, "opener": opener})
    auditor = _user(db, "a4.aud", RoleName.internal_auditor)
    actor = _user(db, "a4.actor", RoleName.branch_manager, branch_id=branches[0]["branch"].id)
    am = _user(db, "a4.am", RoleName.area_manager)
    db.add(AreaManagerAssignment(user_id=am.id, city="Riyadh", brand_id=brand.id, active=True))
    db.flush()
    for n in range(n_findings):
        st = STATUSES[n % len(STATUSES)]
        br = branches[n % len(branches)]
        now = datetime.utcnow() - timedelta(days=n % 30)
        row = AuditFinding(
            finding_no=f"AF-A4-{n:04d}",
            entity_type="shift_count",
            entity_id=br["shift"].id,
            severity="info",
            title=f"Finding {n}",
            description="A4 list fixture.",
            created_by=auditor.id,
            status=st,
            branch_id=br["branch"].id,
            created_at=now,
            last_event_at=now,
        )
        db.add(row)
        db.flush()
        line = (
            db.query(BranchShiftCountLine)
            .join(BranchShiftCount, BranchShiftCount.id == BranchShiftCountLine.count_id)
            .filter(BranchShiftCount.shift_id == br["shift"].id)
            .first()
        )
        db.add(
            AuditFindingItem(
                finding_id=row.id,
                item_id=item.id,
                line_id=line.id if line else None,
                item_name_snapshot="i",
            )
        )
        db.add(
            AuditFindingEvent(
                finding_id=row.id,
                event_type="created",
                from_status=None,
                to_status=st if st != "closed" else "open",
                actor_id=actor.id,
                actor_role="branch_manager",
                note="seed event",
                created_at=now,
            )
        )
    db.commit()
    return {"auditor": auditor, "am": am, "item": item, "branches": branches}


def test_A4_findings_query_count_constant(client, db):
    _seed_findings_fixture(db, n_findings=120)
    ah = _login(client, "a4.aud")

    def count_selects(page_size: int) -> int:
        n = {"c": 0}

        def listen(conn, cursor, statement, parameters, context, executemany):
            if statement.strip().upper().startswith("SELECT"):
                n["c"] += 1

        eng = db.get_bind()
        event.listen(eng, "before_cursor_execute", listen)
        client.get(f"{CA}/findings", headers=ah, params={"page_size": page_size})
        event.remove(eng, "before_cursor_execute", listen)
        return n["c"]

    c10 = count_selects(10)
    c100 = count_selects(100)
    print(f"A4_FINDINGS_SELECT page10={c10} page100={c100} cap={FINDINGS_QUERY_CAP}")
    assert c10 == c100
    assert c10 <= FINDINGS_QUERY_CAP

    def legacy_build(db, page_rows):
        return [_legacy_finding_list_item(db, r[0]) for r in page_rows]

    with patch.object(svc, "_build_finding_list_items", legacy_build):
        b10 = count_selects(10)
        b100 = count_selects(100)
    print(f"A4_FINDINGS_SELECT broken page10={b10} page100={b100}")
    assert b10 != b100


def test_A4_findings_list_parity_with_legacy(client, db):
    ctx = _seed_findings_fixture(db, n_findings=30)
    ah = _login(client, "a4.aud")
    resp = client.get(f"{CA}/findings", headers=ah, params={"page_size": 100})
    assert resp.status_code == 200
    new_items = {i["id"]: i for i in resp.json()["items"]}
    rows = db.query(AuditFinding).filter(AuditFinding.id.in_(new_items.keys())).all()
    for row in rows:
        legacy = _legacy_finding_list_item(db, row)
        new = new_items[row.id]
        for key in legacy:
            if key == "age_days":
                assert abs(new[key] - legacy[key]) <= 1
            else:
                assert new[key] == legacy[key], (row.id, key, new[key], legacy[key])
    am = _login(client, "a4.am")
    am_resp = client.get(f"{CA}/findings", headers=am, params={"page_size": 100})
    assert am_resp.status_code == 200
    for it in am_resp.json()["items"]:
        assert it["branch_id"] in {b["branch"].id for b in ctx["branches"][:4]}


def test_A4_findings_summary_independent_of_queue_filter(client, db):
    _seed_findings_fixture(db, n_findings=120)
    ah = _login(client, "a4.aud")
    base = db.query(AuditFinding).filter(AuditFinding.entity_type == "shift_count")
    expected = {
        "waiting_response": base.filter(AuditFinding.status.in_(tuple(QUEUE_WAITING_RESPONSE))).count(),
        "waiting_auditor": base.filter(AuditFinding.status.in_(tuple(QUEUE_WAITING_AUDITOR))).count(),
        "closed": base.filter(AuditFinding.status == "closed").count(),
    }
    for params in (
        {},
        {"queue": "waiting_response"},
        {"queue": "closed"},
        {"status": "escalated"},
    ):
        resp = client.get(f"{CA}/findings", headers=ah, params={**params, "page_size": 10})
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"] == expected
    filtered = client.get(f"{CA}/findings", headers=ah, params={"queue": "waiting_response", "page_size": 100})
    assert filtered.json()["total"] == expected["waiting_response"]
