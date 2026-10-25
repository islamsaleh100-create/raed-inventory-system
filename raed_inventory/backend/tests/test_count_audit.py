"""Count Audit backend tests (plan T01–T20)."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, text

from app.config import settings
from app.core.security import get_password_hash
from app.main import app
from app.models import AuditFinding, AuditLog, Branch, BranchBrand, Brand, Item, ItemBrand, ItemCategory, Role, RoleName, UnitOfMeasure, User, UserRole, Warehouse
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
from app.services.count_audit_service import STATUSES

CA = "/api/v1/audit/findings/count-audit"
SHIFT_OPS = "/api/v1/shift-ops"
PASSWORD = "Aa1!" + secrets.token_urlsafe(12)


@pytest.fixture(autouse=True)
def _audit_log_on(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")


def _role(db, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if not row:
        row = Role(name=name, display_name=name.value, description="")
        db.add(row)
        db.flush()
    return row


def _user(db, username: str, role_name: RoleName, *, branch_id=None) -> User:
    role = _role(db, role_name)
    row = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash(PASSWORD),
        branch_id=branch_id,
        status="active",
        is_deleted=False,
    )
    db.add(row)
    db.flush()
    db.add(UserRole(user_id=row.id, role_id=role.id))
    db.flush()
    return row


def _login(client, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _add_prior_opening_shift(
    db,
    *,
    branch_id: int,
    opener_id: int,
    item_id: int,
    shift_date: date = date(2026, 5, 31),
) -> BranchShift:
    prior = BranchShift(
        branch_id=branch_id,
        shift_date=shift_date,
        shift_number=1,
        status=BranchShiftStatus.submitted.value,
        opened_by=opener_id,
        submitted_at=datetime.utcnow(),
    )
    db.add(prior)
    db.flush()
    prior_count = BranchShiftCount(
        shift_id=prior.id,
        status=ShiftSectionStatus.submitted.value,
        items_frozen_at=datetime.utcnow(),
        created_by=opener_id,
        submitted_at=datetime.utcnow(),
    )
    db.add(prior_count)
    db.flush()
    db.add(
        BranchShiftCountLine(
            count_id=prior_count.id,
            item_id=item_id,
            item_name_snapshot="item",
            unit_snapshot="u",
            opening_balance=Decimal("0"),
            closing_balance=Decimal("10"),
            movement_diff=Decimal("-10"),
            row_status=ShiftCountRowStatus.valid.value,
        )
    )
    db.flush()
    return prior


def _seed_branch_with_shift(db, suffix: str = "CA", *, movement_diff=Decimal("2.00"), submitted=True) -> dict:
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-BR",
        branch_name=f"Branch {suffix}",
        city="Riyadh",
        area="Test",
        warehouse_id=wh.id,
        active=True,
        is_deleted=False,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"{suffix}-C", name_ar="c", name_en="c")
    db.add(cat)
    unit = UnitOfMeasure(code=f"{suffix}-U", name_ar="u", name_en="u")
    db.add(unit)
    db.flush()
    item = Item(
        item_code=f"{suffix}-IT",
        item_name_ar="item",
        item_name_en="item",
        category_id=cat.id,
        unit_id=unit.id,
        active=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()
    db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
    db.add(
        BranchShiftConfig(
            branch_id=branch.id,
            shift_number=1,
            shift_name_ar="1",
            is_active=True,
            effective_from=date(2020, 1, 1),
        )
    )
    opener = _user(db, f"{suffix}.opener", RoleName.branch_manager, branch_id=branch.id)
    _add_prior_opening_shift(db, branch_id=branch.id, opener_id=opener.id, item_id=item.id)
    shift = BranchShift(
        branch_id=branch.id,
        shift_date=date(2026, 6, 1),
        shift_number=1,
        status=BranchShiftStatus.submitted.value if submitted else BranchShiftStatus.draft.value,
        opened_by=opener.id,
        submitted_at=datetime.utcnow() if submitted else None,
    )
    db.add(shift)
    db.flush()
    count = BranchShiftCount(
        shift_id=shift.id,
        status=ShiftSectionStatus.submitted.value if submitted else ShiftSectionStatus.draft.value,
        items_frozen_at=datetime.utcnow(),
        created_by=opener.id,
        submitted_at=datetime.utcnow() if submitted else None,
    )
    db.add(count)
    db.flush()
    line = BranchShiftCountLine(
        count_id=count.id,
        item_id=item.id,
        item_name_snapshot="item",
        unit_snapshot="u",
        opening_balance=Decimal("10"),
        closing_balance=Decimal("8"),
        movement_diff=movement_diff,
        row_status=ShiftCountRowStatus.valid.value,
    )
    db.add(line)
    db.flush()
    return {"branch": branch, "shift": shift, "count": count, "line": line, "item": item, "opener": opener}


def _shift_tables_hash(db) -> str:
    parts = []
    for table in (
        "branch_shifts",
        "branch_shift_counts",
        "branch_shift_count_lines",
        "branch_shift_cash",
        "branch_shift_reopen_events",
        "branch_shift_configs",
        "items",
    ):
        rows = db.execute(text(f"SELECT * FROM {table} ORDER BY id")).fetchall()
        parts.append(json.dumps([list(r) for r in rows], default=str))
    return hashlib.sha256("".join(parts).encode()).hexdigest()


def test_T01_full_cycle(client, db):
    data = _seed_branch_with_shift(db)
    auditor = _user(db, "ca.auditor", RoleName.internal_auditor)
    bm = _user(db, "ca.bm", RoleName.branch_manager, branch_id=data["branch"].id)
    db.commit()
    ah = _login(client, "ca.auditor")
    bh = _login(client, "ca.bm")
    before_hash = _shift_tables_hash(db)
    create = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "req-create-001",
            "shift_id": data["shift"].id,
            "severity": "warning",
            "title": "Shortage noted",
            "description": "Closing balance lower than expected movement.",
            "item_ids": [data["item"].id],
        },
    )
    assert create.status_code == 200, create.text
    fid = create.json()["finding"]["id"]
    r1 = client.post(
        f"{CA}/findings/{fid}/events",
        headers=bh,
        json={"client_request_id": "evt-resp-001", "action": "respond", "note": "First branch manager response text."},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["finding"]["status"] == "acknowledged"
    r2 = client.post(
        f"{CA}/findings/{fid}/events",
        headers=ah,
        json={"client_request_id": "evt-clar-001", "action": "request_clarification", "note": "Need more detail please."},
    )
    assert r2.status_code == 200, r2.text
    r3 = client.post(
        f"{CA}/findings/{fid}/events",
        headers=bh,
        json={"client_request_id": "evt-resp-002", "action": "respond", "note": "Second branch manager response text."},
    )
    assert r3.status_code == 200, r3.text
    acc = client.post(
        f"{CA}/findings/{fid}/events",
        headers=ah,
        json={"client_request_id": "evt-acc-001", "action": "accept", "note": "Accepted."},
    )
    assert acc.status_code == 200, acc.text
    close = client.post(
        f"{CA}/findings/{fid}/events",
        headers=ah,
        json={"client_request_id": "evt-close-01", "action": "close", "note": "Closing finding after review."},
    )
    assert close.status_code == 200, close.text
    detail = client.get(f"{CA}/findings/{fid}", headers=ah)
    assert detail.status_code == 200
    body = detail.json()
    assert body["finding"]["status"] == "closed"
    assert body["finding"]["closed_at"] is not None
    assert body["finding"]["response_text"] == "Second branch manager response text."
    respond_events = [e for e in body["events"] if e["event_type"] == "respond"]
    assert len(respond_events) == 2
    assert respond_events[0]["note"] != respond_events[1]["note"]
    assert db.query(AuditLog).filter(AuditLog.action == "count_audit_create").count() >= 1
    assert _shift_tables_hash(db) == before_hash


def test_T07_legacy_guards(client, db):
    data = _seed_branch_with_shift(db)
    auditor = _user(db, "ca.aud2", RoleName.internal_auditor)
    db.commit()
    legacy = AuditFinding(
        finding_no="AF-LEG-001",
        entity_type="branch_request",
        entity_id=99,
        severity="info",
        title="Legacy title here",
        description="Legacy finding for acknowledge test.",
        created_by=auditor.id,
        status="open",
    )
    shift_f = AuditFinding(
        finding_no="AF-LEG-002",
        entity_type="shift_count",
        entity_id=data["shift"].id,
        severity="warning",
        title="Shift count legacy",
        description="Should block legacy acknowledge.",
        created_by=auditor.id,
        status="open",
        branch_id=data["branch"].id,
    )
    db.add_all([legacy, shift_f])
    db.commit()
    ops = _user(db, "ca.ops", RoleName.operations_manager)
    db.commit()
    token = _login(client, "ca.ops")
    ack = client.post(
        f"/api/v1/audit/findings/{shift_f.id}/acknowledge",
        headers=token,
        json={"response_text": "Should not work on shift_count"},
    )
    assert ack.status_code == 409
    assert ack.json()["detail"]["error_code"] == "COUNT_AUDIT_USE_EVENTS"
    patch = client.patch(
        f"/api/v1/audit/findings/{shift_f.id}",
        headers=token,
        json={"title": "Changed title value"},
    )
    assert patch.status_code == 409
    ack2 = client.post(
        f"/api/v1/audit/findings/{legacy.id}/acknowledge",
        headers=token,
        json={"response_text": "Legacy acknowledge still works."},
    )
    assert ack2.status_code == 200, ack2.text


def test_T08_middleware_internal_auditor(client, db):
    data = _seed_branch_with_shift(db)
    auditor = _user(db, "ca.aud3", RoleName.internal_auditor)
    db.commit()
    token = _login(client, "ca.aud3")
    ah = _login(client, "ca.aud3")
    create = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "req-mw-001",
            "shift_id": data["shift"].id,
            "severity": "info",
            "title": "Middleware test",
            "description": "Ensure auditor can write count audit.",
            "item_ids": [data["item"].id],
        },
    )
    assert create.status_code == 200, create.text
    blocked = client.post(
        "/api/v1/master/kitchens",
        headers=ah,
        json={"name": "Blocked Kitchen", "city": "Riyadh", "active": True, "section_ids": []},
    )
    assert blocked.status_code == 403


def test_T11_duplicate_and_idempotency(client, db):
    data = _seed_branch_with_shift(db)
    auditor = _user(db, "ca.aud4", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "ca.aud4")
    body = {
        "client_request_id": "dup-key-001",
        "shift_id": data["shift"].id,
        "severity": "warning",
        "title": "Dup test title",
        "description": "Duplicate open finding rule test.",
        "item_ids": [data["item"].id],
    }
    first = client.post(f"{CA}/findings", headers=ah, json=body)
    assert first.status_code == 200
    second = client.post(f"{CA}/findings", headers=ah, json=body)
    assert second.status_code == 200
    assert second.json().get("idempotent_replay") is True
    body2 = dict(body)
    body2["title"] = "Different title text"
    third = client.post(f"{CA}/findings", headers=ah, json=body2)
    assert third.status_code == 409
    assert third.json()["detail"]["error_code"] == "COUNT_AUDIT_IDEMPOTENCY_KEY_REUSED"


def test_T12_validation_not_submitted(client, db):
    data = _seed_branch_with_shift(db, submitted=False)
    auditor = _user(db, "ca.aud5", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "ca.aud5")
    resp = client.post(
        f"{CA}/findings",
        headers=ah,
        json={
            "client_request_id": "val-0010",
            "shift_id": data["shift"].id,
            "severity": "info",
            "title": "Should fail",
            "description": "Count not submitted should 422.",
            "item_ids": [data["item"].id],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "COUNT_AUDIT_COUNT_NOT_SUBMITTED"


def test_T16_route_collision(client, db):
    data = _seed_branch_with_shift(db)
    auditor = _user(db, "ca.aud6", RoleName.internal_auditor)
    legacy = AuditFinding(
        finding_no="AF-999999",
        entity_type="branch_request",
        entity_id=1,
        severity="info",
        title="Legacy numeric route",
        description="Legacy finding for route collision.",
        created_by=auditor.id,
        status="open",
    )
    db.add(legacy)
    db.commit()
    token = _login(client, "ca.aud6")
    legacy_get = client.get(f"/api/v1/audit/findings/{legacy.id}", headers=token)
    assert legacy_get.status_code == 200
    filters = client.get(f"{CA}/filters", headers=token)
    assert filters.status_code == 200


def test_T06_audit_routes_enumeration():
    routes = sorted({r.path for r in app.routes if "/audit/" in getattr(r, "path", "")})
    assert any("/count-audit/filters" in p for p in routes)
    assert "/api/v1/audit/findings/{finding_id}" in routes or any("{finding_id}" in p for p in routes)


from tests._count_audit_a4_tests import (  # noqa: E402
    test_A4_findings_list_parity_with_legacy,
    test_A4_findings_query_count_constant,
    test_A4_findings_summary_independent_of_queue_filter,
)
from tests._count_audit_a3_tests import (  # noqa: E402
    test_T04_full_role_action_state_matrix,
    test_T06_full_route_caller_grid,
    test_T06_prefix_fails_with_old_by_entity_helper,
    test_T15_query_counts_page_and_branch_scaling,
    test_create_race_integrity_replay,
)
from tests._count_audit_a5_tests import (  # noqa: E402
    test_A5_get_router_smoke,
    test_A5_orm_attribute_guard,
    test_A5_same_key_create_race,
    test_A5_shift_detail_success,
)
from tests._count_audit_a2_tests import (  # noqa: E402
    test_T02_escalation_chain,
    test_T03_reopen_preserves_history,
    test_T04_auditor_respond_forbidden_403,
    test_T04_forbidden_roles_403,
    test_T05_scope_isolation,
    test_T06_legacy_route_leakage_matrix,
    test_T06_regression_non_shift_count_by_entity,
    test_T09_data_untouched_listener,
    test_T10_event_idempotency,
    test_T13_snapshot_after_reopen,
    test_T14_read_endpoint_aggregates,
    test_T17_alembic_file_cycle_or_skip,
    test_T17_status_columns_and_downgrade_guard,
    test_T18_shift_id_diverges_from_count_id,
    test_T19_accept_does_not_mutate_shift,
    test_T20_operations_manager_rules,
)

