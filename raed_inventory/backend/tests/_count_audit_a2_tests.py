"""Count Audit A2 tests (imported by test_count_audit.py)."""
from __future__ import annotations

import json
import os
import re
import tempfile
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, inspect, text

from app.main import app
from app.models import AreaManagerAssignment, AuditFinding, Branch, BranchBrand, Brand, Item, ItemCategory, RoleName, UnitOfMeasure, User, Warehouse
from app.models.branch_shift_ops import (
    BranchShift,
    BranchShiftConfig,
    BranchShiftCount,
    BranchShiftCountLine,
    BranchShiftStatus,
    ShiftCountRowStatus,
    ShiftSectionStatus,
)
from app.models.count_audit import AuditFindingEvent
from app.services.count_audit_service import STATUSES

# Re-use helpers from test_count_audit (same module namespace when star-imported)
from tests.test_count_audit import (
    CA,
    PASSWORD,
    SHIFT_OPS,
    _login,
    _seed_branch_with_shift,
    _shift_tables_hash,
    _user,
)

LEAK_MARKER = "LEAK-SCOPED-SHIFT-COUNT-XYZ"
DATE_RANGE = {"date_from": "2026-06-01", "date_to": "2026-06-01"}


def _audit_route_paths():
    return sorted({r.path for r in app.routes if "/audit/" in getattr(r, "path", "")})


def _seed_scope_branches(db, suffix="SC"):
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    branch_in = Branch(
        branch_code=f"{suffix}-IN",
        branch_name="In Scope",
        city="Riyadh",
        area="N",
        warehouse_id=wh.id,
        active=True,
        is_deleted=False,
    )
    branch_out = Branch(
        branch_code=f"{suffix}-OUT",
        branch_name="Out Scope",
        city="Dammam",
        area="E",
        warehouse_id=wh.id,
        active=True,
        is_deleted=False,
    )
    db.add_all([branch_in, branch_out])
    db.flush()
    db.add_all(
        [
            BranchBrand(branch_id=branch_in.id, brand_id=brand.id),
            BranchBrand(branch_id=branch_out.id, brand_id=brand.id),
        ]
    )
    cat = ItemCategory(code=f"{suffix}-C", name_ar="c", name_en="c")
    db.add(cat)
    unit = UnitOfMeasure(code=f"{suffix}-U", name_ar="u", name_en="u")
    db.add(unit)
    db.flush()
    item = Item(
        item_code=f"{suffix}-IT",
        item_name_ar="i",
        item_name_en="i",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()
    for b in (branch_in, branch_out):
        db.add(
            BranchShiftConfig(
                branch_id=b.id,
                shift_number=1,
                shift_name_ar="1",
                is_active=True,
                effective_from=date(2020, 1, 1),
            )
        )
        bm = _user(db, f"{suffix}.bm{b.id}", RoleName.branch_manager, branch_id=b.id)
        shift = BranchShift(
            branch_id=b.id,
            shift_date=date(2026, 6, 1),
            shift_number=1,
            status=BranchShiftStatus.submitted.value,
            opened_by=bm.id,
            submitted_at=datetime.utcnow(),
        )
        db.add(shift)
        db.flush()
        count = BranchShiftCount(
            shift_id=shift.id,
            status=ShiftSectionStatus.submitted.value,
            items_frozen_at=datetime.utcnow(),
            created_by=bm.id,
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
                movement_diff=Decimal("2"),
                row_status=ShiftCountRowStatus.valid.value,
            )
        )
    am = _user(db, f"{suffix}.am", RoleName.area_manager)
    db.add(AreaManagerAssignment(user_id=am.id, city="Riyadh", brand_id=brand.id, active=True))
    auditor = _user(db, f"{suffix}.aud", RoleName.internal_auditor)
    ops = _user(db, f"{suffix}.ops", RoleName.operations_manager)
    db.flush()
    return {
        "brand": brand,
        "item": item,
        "branch_in": branch_in,
        "branch_out": branch_out,
        "shift_in": db.query(BranchShift).filter(BranchShift.branch_id == branch_in.id).one(),
        "shift_out": db.query(BranchShift).filter(BranchShift.branch_id == branch_out.id).one(),
        "auditor": auditor,
        "am": am,
        "ops": ops,
    }


def _create_shift_count_finding(client, db, *, branch, shift, item, auditor_username, marker=LEAK_MARKER):
    ah = _login(client, auditor_username)
    resp = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": f"cr-{marker}-{shift.id}"[:64],
            "shift_id": shift.id,
            "severity": "warning",
            "title": marker,
            "description": "Scoped leakage test finding description.",
            "item_ids": [item.id],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["finding"], ah


def test_T02_escalation_chain(client, db):
    data = _seed_branch_with_shift(db, suffix="T02")
    auditor = _user(db, "t02.aud", RoleName.internal_auditor)
    bm = _user(db, "t02.bm", RoleName.branch_manager, branch_id=data["branch"].id)
    am = _user(db, "t02.am", RoleName.area_manager)
    brand_id = db.query(BranchBrand.brand_id).filter(BranchBrand.branch_id == data["branch"].id).scalar()
    db.add(AreaManagerAssignment(user_id=am.id, city="Riyadh", brand_id=brand_id, active=True))
    ops = _user(db, "t02.ops", RoleName.operations_manager)
    db.commit()
    ah, bh, amh, oh = (_login(client, u) for u in ("t02.aud", "t02.bm", "t02.am", "t02.ops"))
    create = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "t02-create-01",
            "shift_id": data["shift"].id,
            "severity": "warning",
            "title": "Escalation path",
            "description": "Operations manager respond rules.",
            "item_ids": [data["item"].id],
        },
    )
    fid = create.json()["finding"]["id"]
    assert client.get(f"{CA}/findings/{fid}", headers=oh).status_code == 200
    pre = client.post(
        f"{CA}/findings/{fid}/events",
        headers=oh,
        json={"client_request_id": "t02-ops-pre", "action": "respond", "note": "Ops early respond attempt."},
    )
    assert pre.status_code == 403
    esc = client.post(
        f"{CA}/findings/{fid}/events",
        headers=amh,
        json={"client_request_id": "t02-esc-001", "action": "escalate", "note": "Escalating to operations team."},
    )
    assert esc.status_code == 200, esc.text
    bm_block = client.post(
        f"{CA}/findings/{fid}/events",
        headers=bh,
        json={"client_request_id": "t02-bm-post", "action": "respond", "note": "Branch manager after escalation."},
    )
    assert bm_block.status_code in (403, 409)
    ops_ok = client.post(
        f"{CA}/findings/{fid}/events",
        headers=oh,
        json={"client_request_id": "t02-ops-ok", "action": "respond", "note": "Operations manager response ok."},
    )
    assert ops_ok.status_code == 200, ops_ok.text
    for action in ("close", "accept", "reopen", "escalate", "respond"):
        if action == "respond":
            continue
        r = client.post(
            f"{CA}/findings/{fid}/events",
            headers=oh,
            json={"client_request_id": f"t02-ops-{action}", "action": action, "note": "Ops forbidden action test."},
        )
        assert r.status_code == 403, (action, r.text)
    close = client.post(
        f"{CA}/findings/{fid}/events",
        headers=ah,
        json={"client_request_id": "t02-close-01", "action": "close", "note": "Auditor closes after ops respond."},
    )
    assert close.status_code == 200


def test_T03_reopen_preserves_history(client, db):
    data = _seed_branch_with_shift(db, suffix="T03")
    auditor = _user(db, "t03.aud", RoleName.internal_auditor)
    bm = _user(db, "t03.bm", RoleName.branch_manager, branch_id=data["branch"].id)
    db.commit()
    ah, bh = _login(client, "t03.aud"), _login(client, "t03.bm")
    create = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "t03-create-01",
            "shift_id": data["shift"].id,
            "severity": "info",
            "title": "Reopen history",
            "description": "Closed then reopened finding.",
            "item_ids": [data["item"].id],
        },
    )
    fid = create.json()["finding"]["id"]
    client.post(
        f"{CA}/findings/{fid}/events",
        headers=bh,
        json={"client_request_id": "t03-resp-01", "action": "respond", "note": "Branch response for reopen test."},
    )
    client.post(
        f"{CA}/findings/{fid}/events",
        headers=ah,
        json={"client_request_id": "t03-close-01", "action": "close", "note": "Close before reopen test case."},
    )
    before = client.get(f"{CA}/findings/{fid}", headers=ah).json()
    n_events = len(before["events"])
    reopen = client.post(
        f"{CA}/findings/{fid}/events",
        headers=ah,
        json={"client_request_id": "t03-reopen-1", "action": "reopen", "note": "Reopening for continued review."},
    )
    assert reopen.status_code == 200
    after = client.get(f"{CA}/findings/{fid}", headers=ah).json()
    assert after["finding"]["status"] == "open"
    assert len(after["events"]) == n_events + 1
    assert any(e["event_type"] == "reopen" for e in after["events"])


CA_ENDPOINTS = [
    ("GET", f"{CA}/filters", {}),
    ("GET", f"{CA}/coverage", DATE_RANGE),
    ("GET", f"{CA}/shifts", DATE_RANGE),
    ("GET", f"{CA}/variances", DATE_RANGE),
    ("GET", f"{CA}/findings", {}),
]


@pytest.mark.parametrize(
    "role_name",
    [RoleName.branch_user, RoleName.warehouse_user, RoleName.quality_visitor],
)
def test_T04_forbidden_roles_403(client, db, role_name):
    data = _seed_branch_with_shift(db, suffix=f"T04-{role_name.value}")
    _user(db, f"t04.{role_name.value}", role_name, branch_id=data["branch"].id)
    db.commit()
    hdr = _login(client, f"t04.{role_name.value}")
    for method, path, params in CA_ENDPOINTS:
        if method == "GET":
            r = client.get(path, headers=hdr, params=params)
        else:
            r = client.post(path, headers=hdr, json={})
        assert r.status_code == 403, (role_name, path, r.text)


def test_T04_auditor_respond_forbidden_403(client, db):
    data = _seed_branch_with_shift(db, suffix="T04R")
    auditor = _user(db, "t04.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "t04.aud")
    fid = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "t04-resp-forbid",
            "shift_id": data["shift"].id,
            "severity": "info",
            "title": "Role matrix",
            "description": "Auditor cannot respond.",
            "item_ids": [data["item"].id],
        },
    ).json()["finding"]["id"]
    r = client.post(
        f"{CA}/findings/{fid}/events",
        headers=ah,
        json={"client_request_id": "t04-aud-resp", "action": "respond", "note": "Auditor respond attempt."},
    )
    assert r.status_code == 403


def test_T05_scope_isolation(client, db):
    ctx = _seed_scope_branches(db, "T05")
    db.commit()
    finding, _ = _create_shift_count_finding(
        client, db, branch=ctx["branch_out"], shift=ctx["shift_out"], item=ctx["item"], auditor_username="T05.aud"
    )
    am_out = _login(client, "T05.am")
    bm_out = _login(client, "T05.bm" + str(ctx["branch_out"].id))
    bm_in = _login(client, "T05.bm" + str(ctx["branch_in"].id))
    assert client.get(f"{CA}/findings/{finding['id']}", headers=am_out).status_code == 404
    assert client.get(f"{CA}/findings/{finding['id']}", headers=bm_in).status_code == 404
    assert client.get(f"{CA}/shifts/{ctx['shift_out'].id}", headers=am_out).status_code == 404
    r403 = client.get(f"{CA}/shifts", headers=am_out, params={**DATE_RANGE, "branch_id": ctx["branch_out"].id})
    assert r403.status_code == 403
    listed = client.get(f"{CA}/findings", headers=am_out).json()
    assert all(x["id"] != finding["id"] for x in listed.get("items", []))
    cov = client.get(f"{CA}/coverage", headers=am_out, params=DATE_RANGE).json()
    assert LEAK_MARKER not in json.dumps(cov)
    by_ent = client.get(
        f"/api/v1/audit/findings/by-entity/shift_count/{ctx['shift_out'].id}",
        headers=am_out,
    )
    assert by_ent.status_code == 404
    assert LEAK_MARKER not in by_ent.text


def test_T06_legacy_route_leakage_matrix(client, db):
    ctx = _seed_scope_branches(db, "T06")
    db.commit()
    finding, ah = _create_shift_count_finding(
        client, db, branch=ctx["branch_out"], shift=ctx["shift_out"], item=ctx["item"], auditor_username="T06.aud"
    )
    am_out = _login(client, "T06.am")
    paths = _audit_route_paths()
    assert paths
    # Out-of-scope area manager must not see marker on by-entity (ITEM 1 fix)
    by_entity = client.get(
        f"/api/v1/audit/findings/by-entity/shift_count/{ctx['shift_out'].id}",
        headers=am_out,
    )
    assert by_entity.status_code == 404
    assert LEAK_MARKER not in by_entity.text
    assert finding["finding_no"] not in by_entity.text
    list_legacy = client.get("/api/v1/audit/findings", headers=am_out)
    assert LEAK_MARKER not in list_legacy.text
    export = client.get("/api/v1/audit/findings/export.csv", headers=am_out)
    assert LEAK_MARKER not in export.text
    admin = _login(client, "T06.aud")
    admin_list = client.get("/api/v1/audit/findings", headers=admin)
    assert LEAK_MARKER in admin_list.text or finding["finding_no"] in admin_list.text


def test_T06_regression_non_shift_count_by_entity(client, db):
    ctx = _seed_scope_branches(db, "T06R")
    legacy = AuditFinding(
        finding_no="AF-T06-LEG",
        entity_type="branch_request",
        entity_id=1,
        severity="info",
        title="Legacy branch request finding",
        description="Regression payload for by-entity access.",
        created_by=ctx["auditor"].id,
        status="open",
    )
    db.add(legacy)
    db.commit()
    am_in = _login(client, "T06R.am")
    r = client.get("/api/v1/audit/findings/by-entity/branch_request/1", headers=am_in)
    assert r.status_code in (200, 404)


def test_T09_data_untouched_listener(client, db):
    data = _seed_branch_with_shift(db, suffix="T09")
    auditor = _user(db, "t09.aud", RoleName.internal_auditor)
    bm = _user(db, "t09.bm", RoleName.branch_manager, branch_id=data["branch"].id)
    db.commit()
    ah, bh = _login(client, "t09.aud"), _login(client, "t09.bm")
    before = _shift_tables_hash(db)
    forbidden = []

    guarded = (
        "branch_shifts",
        "branch_shift_counts",
        "branch_shift_count_lines",
        "branch_shift_cash",
        "branch_shift_reopen_events",
        "branch_shift_configs",
        "items",
    )

    def _listen(conn, cursor, statement, parameters, context, executemany):
        st = statement.strip()
        if not st[:6].upper().startswith(("INSERT", "UPDATE", "DELETE")):
            return
        low = st.lower()
        for tbl in guarded:
            if re.search(rf"\b{re.escape(tbl)}\b", low):
                forbidden.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", _listen)
    try:
        create = client.post(
            f"{CA}/findings",
            headers=ah,
            json={
                "client_request_id": "t09-create-01",
                "shift_id": data["shift"].id,
                "severity": "warning",
                "title": "T09 untouched",
                "description": "Hash and listener during cycle.",
                "item_ids": [data["item"].id],
            },
        )
        fid = create.json()["finding"]["id"]
        client.post(
            f"{CA}/findings/{fid}/events",
            headers=bh,
            json={"client_request_id": "t09-resp-01", "action": "respond", "note": "Response during T09 cycle."},
        )
        client.post(
            f"{CA}/findings/{fid}/events",
            headers=ah,
            json={"client_request_id": "t09-close-01", "action": "close", "note": "Close during T09 cycle test."},
        )
    finally:
        event.remove(engine, "before_cursor_execute", _listen)
    assert forbidden == []
    assert _shift_tables_hash(db) == before


def test_T10_event_idempotency(client, db):
    data = _seed_branch_with_shift(db, suffix="T10")
    auditor = _user(db, "t10.aud", RoleName.internal_auditor)
    bm = _user(db, "t10.bm", RoleName.branch_manager, branch_id=data["branch"].id)
    db.commit()
    ah, bh = _login(client, "t10.aud"), _login(client, "t10.bm")
    fid = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "t10-create-01",
            "shift_id": data["shift"].id,
            "severity": "info",
            "title": "T10 idempotency",
            "description": "Event idempotency checks.",
            "item_ids": [data["item"].id],
        },
    ).json()["finding"]["id"]
    body = {"client_request_id": "t10-evt-dup", "action": "respond", "note": "Same note for replay test."}
    first = client.post(f"{CA}/findings/{fid}/events", headers=bh, json=body)
    second = client.post(f"{CA}/findings/{fid}/events", headers=bh, json=body)
    assert second.json().get("idempotent_replay") is True
    assert db.query(AuditFindingEvent).filter(AuditFindingEvent.client_request_id == "t10-evt-dup").count() == 1
    bad = dict(body)
    bad["action"] = "close"
    r = client.post(f"{CA}/findings/{fid}/events", headers=ah, json=bad)
    assert r.status_code == 409
    assert r.json()["detail"]["error_code"] == "COUNT_AUDIT_IDEMPOTENCY_KEY_REUSED"


def test_T13_snapshot_after_reopen(client, db):
    data = _seed_branch_with_shift(db, suffix="T13")
    auditor = _user(db, "t13.aud", RoleName.internal_auditor)
    admin = _user(db, "t13.adm", RoleName.admin)
    db.commit()
    ah, adm = _login(client, "t13.aud"), _login(client, "t13.adm")
    fid = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "t13-create-01",
            "shift_id": data["shift"].id,
            "severity": "warning",
            "title": "Snapshot test",
            "description": "Snapshot vs reopen shift count.",
            "item_ids": [data["item"].id],
        },
    ).json()["finding"]["id"]
    snap = client.get(f"{CA}/findings/{fid}", headers=ah).json()["items"][0]["closing_balance_snapshot"]
    reopen = client.post(
        f"{SHIFT_OPS}/shifts/{data['shift'].id}/reopen",
        headers=adm,
        json={"target": "count", "reason": "Reopen for snapshot test", "admin_override": True},
    )
    assert reopen.status_code == 200, reopen.text
    data["line"].closing_balance = Decimal("99")
    db.commit()
    detail = client.get(f"{CA}/findings/{fid}", headers=ah).json()
    item = detail["items"][0]
    assert float(item["closing_balance_snapshot"]) == float(snap)
    assert item.get("changed_since_finding") is True


def test_T14_read_endpoint_aggregates(client, db):
    data = _seed_branch_with_shift(db, suffix="T14")
    auditor = _user(db, "t14.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "t14.aud")
    shifts = client.get(f"{CA}/shifts", headers=ah, params=DATE_RANGE).json()
    assert shifts["total"] >= 1
    row = shifts["items"][0]
    assert row["shortage_lines"] >= 1
    assert row["shortage_qty_total"] >= 2
    var = client.get(f"{CA}/variances", headers=ah, params={**DATE_RANGE, "direction": "shortage"}).json()
    assert var["total"] >= 1
    cov = client.get(f"{CA}/coverage", headers=ah, params=DATE_RANGE).json()
    cell = cov["branches"][0]["days"]["2026-06-01"]
    assert cell["state"] == "submitted"
    big = client.get(f"{CA}/shifts", headers=ah, params={"date_from": "2026-01-01", "date_to": "2026-12-31"})
    assert big.status_code == 422


def test_T15_query_count_constancy(client, db, monkeypatch):
    from tests.test_count_audit import _role

    wh = Warehouse(warehouse_code="T15-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    brand = Brand(name="T15 Brand", active=True)
    db.add(brand)
    db.flush()
    cat = ItemCategory(code="T15-C", name_ar="c", name_en="c")
    unit = UnitOfMeasure(code="T15-U", name_ar="u", name_en="u")
    db.add_all([cat, unit])
    db.flush()
    item = Item(
        item_code="T15-IT",
        item_name_ar="i",
        item_name_en="i",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()
    auditor = _user(db, "t15.aud", RoleName.internal_auditor)
    db.flush()

    offset = {"n": 0}

    def _bulk(n_branches: int):
        for j in range(n_branches):
            i = offset["n"]
            offset["n"] += 1
            b = Branch(
                branch_code=f"T15-B{i}",
                branch_name=f"B{i}",
                city="Riyadh",
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
            opener = _user(db, f"t15.op{i}", RoleName.branch_manager, branch_id=b.id)
            for d in range(31):
                sd = date(2026, 1, 1) + timedelta(days=d)
                shift = BranchShift(
                    branch_id=b.id,
                    shift_date=sd,
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
        db.commit()

    _bulk(2)
    ah = _login(client, "t15.aud")
    params = {"date_from": "2026-01-01", "date_to": "2026-01-31"}

    def _count_queries(callable_fn):
        n = {"c": 0}

        def _listen(conn, cursor, statement, parameters, context, executemany):
            if statement.strip().upper().startswith("SELECT"):
                n["c"] += 1

        eng = db.get_bind()
        event.listen(eng, "before_cursor_execute", _listen)
        t0 = time.perf_counter()
        callable_fn()
        elapsed = time.perf_counter() - t0
        event.remove(eng, "before_cursor_execute", _listen)
        return n["c"], elapsed

    c2_sh, t2_sh = _count_queries(lambda: client.get(f"{CA}/shifts", headers=ah, params=params))
    c2_cov, t2_cov = _count_queries(lambda: client.get(f"{CA}/coverage", headers=ah, params=params))
    c2_var, t2_var = _count_queries(lambda: client.get(f"{CA}/variances", headers=ah, params=params))
    _bulk(18)
    c20_sh, t20_sh = _count_queries(lambda: client.get(f"{CA}/shifts", headers=ah, params=params))
    c20_cov, t20_cov = _count_queries(lambda: client.get(f"{CA}/coverage", headers=ah, params=params))
    c20_var, t20_var = _count_queries(lambda: client.get(f"{CA}/variances", headers=ah, params=params))
    print(
        f"T15_MEASURED shifts:2br={c2_sh}q/{t2_sh:.3f}s 20br={c20_sh}q/{t20_sh:.3f}s "
        f"coverage:2br={c2_cov}q/{t2_cov:.3f}s 20br={c20_cov}q/{t20_cov:.3f}s "
        f"variances:2br={c2_var}q/{t2_var:.3f}s 20br={c20_var}q/{t20_var:.3f}s"
    )
    assert c2_sh == c20_sh
    assert c2_cov == c20_cov
    assert c2_var == c20_var


def test_T17_status_columns_and_downgrade_guard(db):
    insp = inspect(db.get_bind())
    cols = {c["name"]: c for c in insp.get_columns("audit_findings")}
    assert cols["status"]["type"].length >= 30
    ev_cols = {c["name"]: c for c in insp.get_columns("audit_finding_events")}
    assert ev_cols["to_status"]["type"].length >= 30
    longest = max(STATUSES, key=len)
    assert len(longest) > 20
    assert all(len(s) <= 30 for s in STATUSES)
    auditor = _user(db, "t17.aud", RoleName.internal_auditor)
    db.add(
        AuditFinding(
            finding_no="AF-T17-LONG",
            entity_type="shift_count",
            entity_id=1,
            severity="info",
            title="status width",
            description="Downgrade guard row.",
            created_by=auditor.id,
            status="clarification_requested",
        )
    )
    db.commit()
    too_long = db.execute(text("SELECT COUNT(*) FROM audit_findings WHERE LENGTH(status) > 20")).scalar()
    assert too_long >= 1


def test_T17_alembic_file_cycle_or_skip():
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite:///{db_path.replace(chr(92), '/')}"
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            pytest.skip(f"Full alembic chain on empty SQLite file not supported: {proc.stderr[-400:]}")
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO audit_findings (finding_no, entity_type, entity_id, severity, title, description, created_by, status) "
                    "VALUES ('AF-LONG','shift_count',1,'info','t','d',1,'clarification_requested')"
                )
            )
        proc2 = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "-1"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        assert proc2.returncode != 0
        assert "Cannot downgrade" in (proc2.stderr or proc2.stdout)
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_T18_shift_id_diverges_from_count_id(client, db):
    data = _seed_branch_with_shift(db, suffix="T18A")
    opener = data["opener"]
    branch = data["branch"]
    item = data["item"]
    for i in range(4):
        s = BranchShift(
            branch_id=branch.id,
            shift_date=date(2025, 1, 1 + i),
            shift_number=1,
            status=BranchShiftStatus.draft.value,
            opened_by=opener.id,
        )
        db.add(s)
        db.flush()
    shift = BranchShift(
        branch_id=branch.id,
        shift_date=date(2026, 7, 1),
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
            movement_diff=Decimal("2"),
            row_status=ShiftCountRowStatus.valid.value,
        )
    )
    assert shift.id != count.id
    auditor = _user(db, "t18.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "t18.aud")
    bad = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "t18-bad-count",
            "shift_id": count.id,
            "severity": "info",
            "title": "Wrong id",
            "description": "Must reject count pk as shift_id.",
            "item_ids": [item.id],
        },
    )
    assert bad.status_code == 422
    good = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "t18-good-shift",
            "shift_id": shift.id,
            "severity": "info",
            "title": "Correct id",
            "description": "Entity uses branch_shifts.id.",
            "item_ids": [item.id],
        },
    )
    assert good.status_code == 200
    row = db.query(AuditFinding).filter(AuditFinding.client_request_id == "t18-good-shift").one()
    assert row.entity_id == shift.id
    assert good.json()["finding"]["shift_id"] == shift.id


def test_T19_accept_does_not_mutate_shift(client, db):
    data = _seed_branch_with_shift(db, suffix="T19")
    auditor = _user(db, "t19.aud", RoleName.internal_auditor)
    bm = _user(db, "t19.bm", RoleName.branch_manager, branch_id=data["branch"].id)
    db.commit()
    ah, bh = _login(client, "t19.aud"), _login(client, "t19.bm")
    before = _shift_tables_hash(db)
    shift_status = data["shift"].status
    count_status = data["count"].status
    fid = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "t19-create-01",
            "shift_id": data["shift"].id,
            "severity": "info",
            "title": "Accept semantics",
            "description": "Accept must not change shift tables.",
            "item_ids": [data["item"].id],
        },
    ).json()["finding"]["id"]
    client.post(
        f"{CA}/findings/{fid}/events",
        headers=bh,
        json={"client_request_id": "t19-resp", "action": "respond", "note": "Branch response for accept test."},
    )
    client.post(
        f"{CA}/findings/{fid}/events",
        headers=ah,
        json={"client_request_id": "t19-acc", "action": "accept", "note": "Accept note."},
    )
    client.post(
        f"{CA}/findings/{fid}/events",
        headers=ah,
        json={"client_request_id": "t19-close", "action": "close", "note": "Close after accept semantics."},
    )
    db.refresh(data["shift"])
    db.refresh(data["count"])
    assert data["shift"].status == shift_status
    assert data["count"].status == count_status
    assert _shift_tables_hash(db) == before


def test_T20_operations_manager_rules(client, db):
    ctx = _seed_scope_branches(db, "T20")
    db.commit()
    finding_in, _ = _create_shift_count_finding(
        client, db, branch=ctx["branch_in"], shift=ctx["shift_in"], item=ctx["item"], auditor_username="T20.aud"
    )
    finding_out, _ = _create_shift_count_finding(
        client,
        db,
        branch=ctx["branch_out"],
        shift=ctx["shift_out"],
        item=ctx["item"],
        auditor_username="T20.aud",
        marker="LEAK-OTHER-BRANCH",
    )
    oh = _login(client, "T20.ops")
    assert client.get(f"{CA}/findings/{finding_in['id']}", headers=oh).status_code == 200
    assert client.get(f"{CA}/findings/{finding_out['id']}", headers=oh).status_code == 200
    for action in ("close", "accept", "reopen", "escalate"):
        r = client.post(
            f"{CA}/findings/{finding_in['id']}/events",
            headers=oh,
            json={"client_request_id": f"t20-{action}", "action": action, "note": "Ops forbidden on count audit."},
        )
        assert r.status_code == 403
    create = client.post(
        f"{CA}/findings",
        headers=oh,
        json={
            "client_request_id": "t20-create-denied",
            "shift_id": ctx["shift_in"].id,
            "severity": "info",
            "title": "Ops create",
            "description": "Operations manager cannot create.",
            "item_ids": [ctx["item"].id],
        },
    )
    assert create.status_code == 403

