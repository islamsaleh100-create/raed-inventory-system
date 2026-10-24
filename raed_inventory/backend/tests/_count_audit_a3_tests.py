"""Count Audit A3 close-out tests."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
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
    BranchShiftReopenEvent,
    BranchShiftStatus,
    ShiftCountRowStatus,
    ShiftSectionStatus,
)
from app.routers import audit_findings as legacy_audit
from app.services import count_audit_service as svc

from tests._count_audit_a2_tests import (
    CA,
    LEAK_MARKER,
    _audit_route_paths,
    _create_shift_count_finding,
    _seed_scope_branches,
)
from tests.test_count_audit import _login, _seed_branch_with_shift, _user

QUERY_CAP = {"shifts": 12, "findings": 25, "coverage": 8, "variances": 8}

T06_CALLERS = (
    "branch_manager_in",
    "branch_manager_out",
    "branch_user",
    "area_manager_in",
    "area_manager_out",
    "operations_manager",
    "warehouse_user",
    "quality_visitor",
    "internal_auditor",
    "admin",
)


def test_T06_prefix_fails_with_old_by_entity_helper(client, db):
    ctx = _seed_scope_branches(db, "T06PF")
    db.commit()
    _create_shift_count_finding(
        client, db, branch=ctx["branch_out"], shift=ctx["shift_out"], item=ctx["item"], auditor_username="T06PF.aud"
    )
    am_out = _login(client, "T06PF.am")

    def _old_helper(db, current_user, entity_type, entity_id):
        roles = legacy_audit.get_user_roles(current_user)
        if any(role in roles for role in legacy_audit._READ_ROLES):
            return
        raise HTTPException(status_code=403, detail="Access denied for this audit finding entity")

    with patch.object(legacy_audit, "_ensure_entity_findings_read_access", _old_helper):
        resp = client.get(
            f"/api/v1/audit/findings/by-entity/shift_count/{ctx['shift_out'].id}",
            headers=am_out,
        )
        assert resp.status_code == 200
        assert LEAK_MARKER in resp.text


def test_T06_full_route_caller_grid(client, db):
    ctx = _seed_scope_branches(db, "T06G")
    _user(db, "t06g.bu", RoleName.branch_user, branch_id=ctx["branch_in"].id)
    _user(db, "t06g.wh", RoleName.warehouse_user)
    _user(db, "t06g.qv", RoleName.quality_visitor)
    _user(db, "t06g.adm", RoleName.admin)
    db.commit()
    finding, _ = _create_shift_count_finding(
        client, db, branch=ctx["branch_out"], shift=ctx["shift_out"], item=ctx["item"], auditor_username="T06G.aud"
    )
    tokens = {
        "branch_manager_in": _login(client, "T06G.bm" + str(ctx["branch_in"].id)),
        "branch_manager_out": _login(client, "T06G.bm" + str(ctx["branch_out"].id)),
        "branch_user": _login(client, "t06g.bu"),
        "area_manager_in": _login(client, "T06G.am"),
        "area_manager_out": _login(client, "T06G.am"),
        "operations_manager": _login(client, "T06G.ops"),
        "warehouse_user": _login(client, "t06g.wh"),
        "quality_visitor": _login(client, "t06g.qv"),
        "internal_auditor": _login(client, "T06G.aud"),
        "admin": _login(client, "t06g.adm"),
    }
    routes = _audit_route_paths()
    grid = 0
    for path in routes:
        for caller in T06_CALLERS:
            grid += 1
            hdr = tokens[caller]
            url = (
                path.replace("{finding_id}", str(finding["id"]))
                .replace("{entity_type}", "shift_count")
                .replace("{entity_id}", str(ctx["shift_out"].id))
            )
            if "{finding_id}" in path and "count-audit" not in path:
                url = path.replace("{finding_id}", str(finding["id"]))
            if "count-audit/coverage" in url or "count-audit/shifts" in url or "count-audit/variances" in url:
                r = client.get(url, headers=hdr, params={"date_from": "2026-06-01", "date_to": "2026-06-01"})
            elif url.endswith("/export.csv") or "/logs" in url or url.endswith("/modules") or url.endswith("/actions"):
                r = client.get(url, headers=hdr)
            elif "/events" in url:
                r = client.post(
                    url,
                    headers=hdr,
                    json={"client_request_id": f"grid-{grid:04d}", "action": "close", "note": "Grid probe note."},
                )
            elif url.endswith("/acknowledge"):
                r = client.post(url, headers=hdr, json={"response_text": "legacy ack probe"})
            elif "count-audit/findings" in url and not url.endswith("/events"):
                r = client.get(url, headers=hdr)
            else:
                r = client.get(url, headers=hdr)
            out_scope = caller in (
                "area_manager_out",
                "branch_manager_in",
                "branch_user",
                "warehouse_user",
                "quality_visitor",
            )
            if out_scope and finding["finding_no"] in r.text:
                pytest.fail(f"leak finding_no path={url} caller={caller} status={r.status_code}")
            if out_scope and LEAK_MARKER in r.text:
                pytest.fail(f"leak marker path={url} caller={caller}")
    print(f"T06_GRID_SIZE={grid}")


ROLES = (
    "internal_auditor",
    "admin",
    "super_admin",
    "operations_manager",
    "area_manager_in",
    "area_manager_out",
    "branch_manager_own",
    "branch_manager_other",
    "branch_user",
    "warehouse_user",
    "quality_visitor",
)
ACTIONS = ("create", "respond", "request_clarification", "accept", "escalate", "close", "reopen")
STATUSES = ("open", "acknowledged", "clarification_requested", "escalated", "accepted", "closed")


def _expected(action: str, role: str, status: str) -> str:
    if role in ("branch_user", "warehouse_user", "quality_visitor"):
        return "403"
    if role in ("area_manager_out", "branch_manager_other"):
        if action == "create":
            return "403"
        return "404"
    if action == "create":
        return "2xx" if role in ("internal_auditor", "admin", "super_admin") else "403"
    if role == "operations_manager":
        if action in ("close", "accept", "reopen", "escalate", "create"):
            return "403"
        if action == "respond":
            return "2xx" if status == "escalated" else "403"
    if role == "branch_manager_own":
        if action in ("request_clarification", "accept", "close", "reopen", "create", "escalate"):
            return "403"
        if action == "respond":
            if status in ("open", "clarification_requested"):
                return "2xx"
            return "403" if status == "escalated" else "409"
    if role == "area_manager_in":
        if action in ("request_clarification", "accept", "close", "reopen", "create"):
            return "403"
        if action == "respond":
            if status in ("open", "clarification_requested"):
                return "2xx"
            return "409"
        if action == "escalate":
            return "2xx" if status in ("open", "clarification_requested", "acknowledged") else "409"
    if role == "internal_auditor":
        if action == "respond":
            return "403"
    if role in ("internal_auditor", "admin", "super_admin"):
        if action == "respond":
            return "2xx" if status in ("open", "clarification_requested", "escalated") else "409"
        if action == "accept" and status != "acknowledged":
            return "409"
        if action == "request_clarification" and status not in ("acknowledged", "accepted"):
            return "409"
        if action == "close" and status == "closed":
            return "409"
        if action == "reopen" and status != "closed":
            return "409"
        if action == "escalate" and status not in ("open", "clarification_requested", "acknowledged"):
            return "409"
        return "2xx"
    return "403"


def test_T04_full_role_action_state_matrix(client, db):
    ctx = _seed_scope_branches(db, "T04M")
    _user(db, "t04m.bmown", RoleName.branch_manager, branch_id=ctx["branch_in"].id)
    _user(db, "t04m.bmother", RoleName.branch_manager, branch_id=ctx["branch_out"].id)
    _user(db, "t04m.adm", RoleName.admin)
    _user(db, "t04m.sadm", RoleName.super_admin)
    _user(db, "t04m.bu", RoleName.branch_user, branch_id=ctx["branch_in"].id)
    _user(db, "t04m.wh", RoleName.warehouse_user)
    _user(db, "t04m.qv", RoleName.quality_visitor)
    auditor = ctx["auditor"]
    db.commit()
    role_hdr = {
        "internal_auditor": _login(client, "T04M.aud"),
        "admin": _login(client, "t04m.adm"),
        "super_admin": _login(client, "t04m.sadm"),
        "operations_manager": _login(client, "T04M.ops"),
        "area_manager_in": _login(client, "T04M.am"),
        "area_manager_out": _login(client, "T04M.am"),
        "branch_manager_own": _login(client, "t04m.bmown"),
        "branch_manager_other": _login(client, "t04m.bmother"),
        "branch_user": _login(client, "t04m.bu"),
        "warehouse_user": _login(client, "t04m.wh"),
        "quality_visitor": _login(client, "t04m.qv"),
    }
    cells = 0
    for status in STATUSES:
        for role in ROLES:
            for action in ACTIONS:
                cells += 1
                exp = _expected(action, role, status)
                if role in ("area_manager_out", "branch_manager_other"):
                    branch_id = ctx["branch_out"].id
                    shift_id = ctx["shift_out"].id
                else:
                    branch_id = ctx["branch_in"].id
                    shift_id = ctx["shift_in"].id
                finding = AuditFinding(
                    finding_no=f"AF-T4-{cells:04d}",
                    entity_type="shift_count",
                    entity_id=shift_id,
                    severity="info",
                    title=f"T04 cell {cells}",
                    description="Matrix cell fixture.",
                    created_by=auditor.id,
                    status=status,
                    branch_id=branch_id,
                )
                db.add(finding)
                db.commit()
                hdr = role_hdr["branch_manager_own"] if role == "branch_manager_other" else role_hdr[role]
                if action == "create":
                    db.query(AuditFinding).filter(
                        AuditFinding.entity_type == "shift_count",
                        AuditFinding.entity_id == shift_id,
                        AuditFinding.status != "closed",
                    ).update({"status": "closed"}, synchronize_session=False)
                    db.commit()
                    r = client.post(
                        f"{CA}/findings",
                        headers=hdr,
                        json={
                            "client_request_id": f"t04c{cells:05d}"[:64],
                            "shift_id": shift_id,
                            "severity": "info",
                            "title": "create probe",
                            "description": "Matrix create cell.",
                            "item_ids": [ctx["item"].id],
                        },
                    )
                else:
                    r = client.post(
                        f"{CA}/findings/{finding.id}/events",
                        headers=hdr,
                        json={
                            "client_request_id": f"t04e{cells:05d}"[:64],
                            "action": action,
                            "note": "Matrix event probe note.",
                        },
                    )
                if exp == "2xx":
                    assert r.status_code in (200, 201), (role, action, status, r.status_code, r.text[:160])
                elif exp == "403":
                    assert r.status_code == 403, (role, action, status, r.status_code)
                elif exp == "404":
                    assert r.status_code == 404, (role, action, status, r.status_code)
                else:
                    assert r.status_code == 409, (role, action, status, r.status_code)
    print(f"T04_CELL_COUNT={cells}")


def test_T15_query_counts_page_and_branch_scaling(client, db):
    wh = Warehouse(warehouse_code="T15A-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    brand = Brand(name="T15A Brand", active=True)
    db.add(brand)
    db.flush()
    cat = ItemCategory(code="T15A-C", name_ar="c", name_en="c")
    unit = UnitOfMeasure(code="T15A-U", name_ar="u", name_en="u")
    db.add_all([cat, unit])
    db.flush()
    item = Item(
        item_code="T15A-IT",
        item_name_ar="i",
        item_name_en="i",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()
    _user(db, "t15a.aud", RoleName.internal_auditor)
    offset = {"n": 0}

    def bulk(n_branches: int, days: int = 31):
        for _ in range(n_branches):
            i = offset["n"]
            offset["n"] += 1
            b = Branch(
                branch_code=f"T15A-B{i}",
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
            opener = _user(db, f"t15a.op{i}", RoleName.branch_manager, branch_id=b.id)
            for d in range(days):
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

    bulk(20, days=31)
    ah = _login(client, "t15a.aud")
    params = {"date_from": "2026-01-01", "date_to": "2026-01-31"}

    def count_selects(fn):
        n = {"c": 0}

        def listen(conn, cursor, statement, parameters, context, executemany):
            if statement.strip().upper().startswith("SELECT"):
                n["c"] += 1

        eng = db.get_bind()
        event.listen(eng, "before_cursor_execute", listen)
        fn()
        event.remove(eng, "before_cursor_execute", listen)
        return n["c"]

    s10 = count_selects(lambda: client.get(f"{CA}/shifts", headers=ah, params={**params, "page_size": 10}))
    s100 = count_selects(lambda: client.get(f"{CA}/shifts", headers=ah, params={**params, "page_size": 100}))
    f10 = count_selects(lambda: client.get(f"{CA}/findings", headers=ah, params={"page_size": 10}))
    f100 = count_selects(lambda: client.get(f"{CA}/findings", headers=ah, params={"page_size": 100}))
    c_cov = count_selects(lambda: client.get(f"{CA}/coverage", headers=ah, params=params))
    v_var = count_selects(lambda: client.get(f"{CA}/variances", headers=ah, params=params))
    print(
        f"T15A shifts10={s10} shifts100={s100} findings10={f10} findings100={f100} "
        f"coverage={c_cov} variances={v_var}"
    )
    assert s10 == s100 <= QUERY_CAP["shifts"]
    assert f10 == f100 <= QUERY_CAP["findings"]
    assert c_cov <= QUERY_CAP["coverage"]
    assert v_var <= QUERY_CAP["variances"]

    real_list_shifts = svc.list_shifts

    def broken_list_shifts(db, user, **kwargs):
        out = real_list_shifts(db, user, **kwargs)
        for it in out["items"]:
            db.query(func.count(BranchShiftReopenEvent.id)).filter(
                BranchShiftReopenEvent.shift_id == it["shift_id"]
            ).scalar()
        return out

    with patch.object(svc, "list_shifts", broken_list_shifts):
        b10 = count_selects(lambda: client.get(f"{CA}/shifts", headers=ah, params={**params, "page_size": 10}))
        b100 = count_selects(lambda: client.get(f"{CA}/shifts", headers=ah, params={**params, "page_size": 100}))
    print(f"T15A broken shifts10={b10} shifts100={b100}")
    assert b10 != b100


def test_create_race_integrity_replay(client, db, monkeypatch):
    data = _seed_branch_with_shift(db, suffix="T4A")
    _user(db, "t04a.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "t04a.aud")
    body = {
        "client_request_id": "race-key-001",
        "shift_id": data["shift"].id,
        "severity": "info",
        "title": "Race test title",
        "description": "Concurrency idempotency test.",
        "item_ids": [data["item"].id],
    }
    real_query = db.query
    state = {"miss": True}

    class _MissFirstQuery:
        def __init__(self, q):
            self._q = q

        def filter(self, *a, **k):
            self._q = self._q.filter(*a, **k)
            return self

        def first(self):
            if state["miss"]:
                state["miss"] = False
                return None
            return self._q.first()

        def __getattr__(self, name):
            return getattr(self._q, name)

    def patched_query(*entities, **kwargs):
        q = real_query(*entities, **kwargs)
        if entities and entities[0] is AuditFinding:
            return _MissFirstQuery(q)
        return q

    monkeypatch.setattr(db, "query", patched_query)
    r1 = client.post(f"{CA}/findings", headers=ah, json=body)
    r2 = client.post(f"{CA}/findings", headers=ah, json=body)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r2.json().get("idempotent_replay") is True
    assert db.query(AuditFinding).filter(AuditFinding.client_request_id == "race-key-001").count() == 1
