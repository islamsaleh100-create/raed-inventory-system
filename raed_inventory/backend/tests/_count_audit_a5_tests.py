"""Count Audit A5 — shift detail + idempotency after lock (imported by test_count_audit.py)."""
from __future__ import annotations

import ast
import importlib
import inspect
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import inspect as sa_inspect

from app.main import app
from app.models import (
    AreaManagerAssignment,
    AuditFinding,
    Branch,
    BranchBrand,
    Brand,
    Item,
    ItemBrand,
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
from app.models.count_audit import AuditFindingEvent, AuditFindingItem

from tests.test_count_audit import CA, PASSWORD, _login, _seed_branch_with_shift, _user

DATE_RANGE = {"date_from": "2026-06-01", "date_to": "2026-06-01"}
CA_PREFIX = "/api/v1/audit/findings/count-audit"


def _seed_a5_detail(db, suffix: str = "A5") -> dict:
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    branch_in = Branch(
        branch_code=f"{suffix}-IN",
        branch_name="In",
        city="Riyadh",
        area="N",
        warehouse_id=wh.id,
        active=True,
        is_deleted=False,
    )
    branch_out = Branch(
        branch_code=f"{suffix}-OUT",
        branch_name="Out",
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
    items = []
    for i in range(3):
        it = Item(
            item_code=f"{suffix}-IT{i}",
            item_name_ar=f"i{i}",
            item_name_en=f"i{i}",
            category_id=cat.id,
            unit_id=unit.id,
            active=True,
            is_deleted=False,
        )
        db.add(it)
        db.flush()
        db.add(ItemBrand(item_id=it.id, brand_id=brand.id))
        items.append(it)
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
        _user(db, f"{suffix}.bm{b.id}", RoleName.branch_manager, branch_id=b.id)
    opener = db.query(User).filter(User.username == f"{suffix}.bm{branch_in.id}").one()
    shift_in = BranchShift(
        branch_id=branch_in.id,
        shift_date=date(2026, 6, 1),
        shift_number=1,
        status=BranchShiftStatus.submitted.value,
        opened_by=opener.id,
        submitted_at=datetime.utcnow(),
    )
    shift_out = BranchShift(
        branch_id=branch_out.id,
        shift_date=date(2026, 6, 1),
        shift_number=1,
        status=BranchShiftStatus.submitted.value,
        opened_by=opener.id,
        submitted_at=datetime.utcnow(),
    )
    db.add_all([shift_in, shift_out])
    db.flush()
    count_in = BranchShiftCount(
        shift_id=shift_in.id,
        status=ShiftSectionStatus.submitted.value,
        items_frozen_at=datetime.utcnow(),
        created_by=opener.id,
        submitted_at=datetime.utcnow(),
    )
    db.add(count_in)
    db.flush()
    for idx, it in enumerate(items):
        db.add(
            BranchShiftCountLine(
                count_id=count_in.id,
                item_id=it.id,
                item_name_snapshot=f"item{idx}",
                unit_snapshot="u",
                opening_balance=Decimal("10"),
                closing_balance=Decimal("8"),
                movement_diff=Decimal(str(idx + 1)),
                row_status=ShiftCountRowStatus.valid.value,
            )
        )
    db.add(
        BranchShiftReopenEvent(
            shift_id=shift_in.id,
            target="count",
            reason="A5 detail reopen event reason",
            reopened_by=opener.id,
            reopened_at=datetime.utcnow(),
        )
    )
    auditor = _user(db, f"{suffix}.aud", RoleName.internal_auditor)
    _user(db, f"{suffix}.admin", RoleName.admin)
    _user(db, f"{suffix}.super", RoleName.super_admin)
    _user(db, f"{suffix}.ops", RoleName.operations_manager)
    am = _user(db, f"{suffix}.am", RoleName.area_manager)
    db.add(AreaManagerAssignment(user_id=am.id, city="Riyadh", brand_id=brand.id, active=True))
    am_out = _user(db, f"{suffix}.amout", RoleName.area_manager)
    db.add(AreaManagerAssignment(user_id=am_out.id, city="Dammam", brand_id=brand.id, active=True))
    _user(db, f"{suffix}.bu", RoleName.branch_user, branch_id=branch_in.id)
    _user(db, f"{suffix}.wu", RoleName.warehouse_user)
    db.flush()
    finding = AuditFinding(
        finding_no="AF-PENDING",
        entity_type="shift_count",
        entity_id=shift_in.id,
        severity="info",
        title="A5 linked finding",
        description="Linked finding for shift detail test.",
        created_by=auditor.id,
        status="open",
        branch_id=branch_in.id,
        client_request_id=f"{suffix}-find-001",
        last_event_at=datetime.utcnow(),
    )
    db.add(finding)
    db.flush()
    finding.finding_no = f"AF-{finding.id:06d}"
    db.add(
        AuditFindingItem(
            finding_id=finding.id,
            item_id=items[0].id,
            line_id=db.query(BranchShiftCountLine).filter(BranchShiftCountLine.count_id == count_in.id).first().id,
            item_name_snapshot="item0",
            closing_balance_snapshot=Decimal("8"),
            movement_diff_snapshot=Decimal("1"),
        )
    )
    db.add(
        AuditFindingEvent(
            finding_id=finding.id,
            event_type="created",
            from_status=None,
            to_status="open",
            actor_id=auditor.id,
            actor_role="internal_auditor",
            note="created",
            client_request_id=f"create-{suffix}-find-001",
        )
    )
    db.flush()
    line_count = db.query(BranchShiftCountLine).filter(BranchShiftCountLine.count_id == count_in.id).count()
    return {
        "branch_in": branch_in,
        "branch_out": branch_out,
        "shift_in": shift_in,
        "shift_out": shift_out,
        "count_in": count_in,
        "items": items,
        "finding": finding,
        "line_count": line_count,
        "reopen_id": db.query(BranchShiftReopenEvent).filter(BranchShiftReopenEvent.shift_id == shift_in.id).one().id,
    }


def test_A5_shift_detail_success(client, db):
    ctx = _seed_a5_detail(db, "A5D")
    db.commit()
    shift_id = ctx["shift_in"].id
    in_scope = [
        (f"A5D.aud", RoleName.internal_auditor),
        (f"A5D.admin", RoleName.admin),
        (f"A5D.super", RoleName.super_admin),
        (f"A5D.ops", RoleName.operations_manager),
        (f"A5D.am", RoleName.area_manager),
        (f"A5D.bm{ctx['branch_in'].id}", RoleName.branch_manager),
    ]
    for username, _role in in_scope:
        hdr = _login(client, username)
        r = client.get(f"{CA}/shifts/{shift_id}", headers=hdr)
        assert r.status_code == 200, (username, r.text)
        body = r.json()
        assert body["count_id"] == ctx["count_in"].id
        assert len(body["count"]["lines"]) == ctx["line_count"]
        assert any(ev["id"] == ctx["reopen_id"] and ev.get("created_at") for ev in body["reopen_events"])
        assert any(f["id"] == ctx["finding"].id for f in body["findings"])
    am_out = _login(client, "A5D.amout")
    bm_out = _login(client, f"A5D.bm{ctx['branch_out'].id}")
    assert client.get(f"{CA}/shifts/{shift_id}", headers=am_out).status_code == 404
    assert client.get(f"{CA}/shifts/{shift_id}", headers=bm_out).status_code == 404
    for uname in (f"A5D.bu", f"A5D.wu"):
        hdr = _login(client, uname)
        assert client.get(f"{CA}/shifts/{shift_id}", headers=hdr).status_code == 403


def _count_audit_get_route_paths():
    out = []
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "") or ""
        if "GET" in methods and path.startswith(CA_PREFIX):
            out.append(path)
    return sorted(set(out))


def _fill_get_path(path: str, ctx: dict) -> tuple[str, dict]:
    params: dict = {}
    p = path
    if "{shift_id}" in p:
        p = p.replace("{shift_id}", str(ctx["shift_in"].id))
    if "{finding_id}" in p:
        p = p.replace("{finding_id}", str(ctx["finding"].id))
    if "date_from" in path or path.endswith("/coverage") or path.endswith("/shifts") or path.endswith("/variances"):
        params.update(DATE_RANGE)
    return p, params


def test_A5_get_router_smoke(client, db):
    ctx = _seed_a5_detail(db, "A5S")
    _user(db, "A5S.aud2", RoleName.internal_auditor)
    db.commit()
    hdr = _login(client, "A5S.aud")
    routes = _count_audit_get_route_paths()
    print(f"A5 router GET routes covered: {len(routes)}")
    for path in routes:
        url, params = _fill_get_path(path, ctx)
        r = client.get(url, headers=hdr, params=params)
        assert r.status_code == 200, (path, r.status_code, r.text[:500])
        assert "Traceback" not in r.text
    assert len(routes) >= 6


def _model_classes_from_imports(module_name: str) -> dict[str, type]:
    mod = importlib.import_module(module_name)
    tree = ast.parse(Path(inspect.getfile(mod)).read_text(encoding="utf-8"))
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for alias in node.names:
                local = alias.asname or alias.name
                if base.startswith("app.models"):
                    names[local] = f"{base}.{alias.name}" if base else alias.name
    classes: dict[str, type] = {}
    for local, qual in names.items():
        try:
            if hasattr(mod, local):
                obj = getattr(mod, local)
                try:
                    if inspect.isclass(obj) and sa_inspect(obj, raiseerr=False) is not None:
                        classes[local] = obj
                except Exception:
                    pass
        except Exception:
            pass
        if local not in classes and qual:
            parts = qual.rsplit(".", 1)
            if len(parts) == 2:
                pkg, cls_name = parts
                try:
                    m = importlib.import_module(pkg)
                    obj = getattr(m, cls_name, None)
                    try:
                        if inspect.isclass(obj) and sa_inspect(obj, raiseerr=False) is not None:
                            classes[local] = obj
                    except Exception:
                        pass
                except Exception:
                    pass
    return classes


def _collect_orm_attribute_refs(source: str, model_names: set[str]) -> list[tuple[str, str]]:
    tree = ast.parse(source)
    refs: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in model_names:
                refs.append((node.value.id, node.attr))
    return refs


def test_A5_orm_attribute_guard():
    modules = (
        "app.services.count_audit_service",
        "app.routers.count_audit",
        "app.schemas.count_audit",
    )
    checked = 0
    missing: list[str] = []
    for module_name in modules:
        path = Path(importlib.import_module(module_name).__file__)
        source = path.read_text(encoding="utf-8")
        models = _model_classes_from_imports(module_name)
        if not models:
            continue
        for cls_name, attr in _collect_orm_attribute_refs(source, set(models.keys())):
            checked += 1
            model = models[cls_name]
            mapper = sa_inspect(model)
            ok = attr in mapper.columns or attr in mapper.relationships
            if not ok and hasattr(model, attr):
                ok = True
            if not ok:
                missing.append(f"{cls_name}.{attr}")
    print(f"A5 ORM attribute references checked: {checked}")
    assert checked > 0
    assert not missing, f"Missing ORM attributes: {missing}"


def test_A5_same_key_create_race(client, db, monkeypatch):
    data = _seed_branch_with_shift(db, suffix="A5R")
    _user(db, "a5r.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "a5r.aud")
    body = {
        "client_request_id": "a5-race-same-key",
        "shift_id": data["shift"].id,
        "severity": "info",
        "title": "A5 race title",
        "description": "Same key create race test.",
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
    state["miss"] = True
    r2 = client.post(f"{CA}/findings", headers=ah, json=body)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r2.json().get("idempotent_replay") is True
    assert db.query(AuditFinding).filter(AuditFinding.client_request_id == body["client_request_id"]).count() == 1

    cat = ItemCategory(code="A5R-C2", name_ar="c", name_en="c")
    db.add(cat)
    unit = UnitOfMeasure(code="A5R-U2", name_ar="u", name_en="u")
    db.add(unit)
    db.flush()
    item2 = Item(
        item_code="A5R-IT2",
        item_name_ar="i2",
        item_name_en="i2",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item2)
    db.flush()
    db.add(
        BranchShiftCountLine(
            count_id=data["count"].id,
            item_id=item2.id,
            item_name_snapshot="item2",
            unit_snapshot="u",
            opening_balance=Decimal("10"),
            closing_balance=Decimal("8"),
            movement_diff=Decimal("2"),
            row_status=ShiftCountRowStatus.valid.value,
        )
    )
    item3 = Item(
        item_code="A5R-IT3",
        item_name_ar="i3",
        item_name_en="i3",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item3)
    db.flush()
    db.add(
        BranchShiftCountLine(
            count_id=data["count"].id,
            item_id=item3.id,
            item_name_snapshot="item3",
            unit_snapshot="u",
            opening_balance=Decimal("10"),
            closing_balance=Decimal("8"),
            movement_diff=Decimal("3"),
            row_status=ShiftCountRowStatus.valid.value,
        )
    )
    db.commit()

    bad = {
        **body,
        "client_request_id": "a5-race-reuse-key",
        "title": "Different title here",
        "item_ids": [item2.id],
    }
    state["miss"] = True
    assert client.post(f"{CA}/findings", headers=ah, json=bad).status_code == 200
    assert db.query(AuditFinding).filter(AuditFinding.client_request_id == bad["client_request_id"]).count() == 1
    state["miss"] = True
    r_reuse = client.post(
        f"{CA}/findings",
        headers=ah,
        json={**bad, "title": "Another title change"},
    )
    assert r_reuse.status_code == 409
    detail = r_reuse.json().get("detail")
    err = detail.get("error_code") if isinstance(detail, dict) else None
    assert err == "COUNT_AUDIT_IDEMPOTENCY_KEY_REUSED"
    assert db.query(AuditFinding).filter(AuditFinding.client_request_id == bad["client_request_id"]).count() == 1

    dup_body = {
        **body,
        "client_request_id": "a5-race-diff-key-01",
        "item_ids": [item3.id],
    }
    state["miss"] = True
    assert client.post(f"{CA}/findings", headers=ah, json=dup_body).status_code == 200
    assert db.query(AuditFinding).filter(AuditFinding.client_request_id == dup_body["client_request_id"]).count() == 1
    dup_body["client_request_id"] = "a5-race-diff-key-02"
    state["miss"] = True
    r_dup = client.post(f"{CA}/findings", headers=ah, json=dup_body)
    assert r_dup.status_code == 409
    assert r_dup.json().get("detail", {}).get("error_code") == "COUNT_AUDIT_DUPLICATE_OPEN_FINDING"
