"""Opening-balance refresh on count submit + reopen guards (TG opening refresh)."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from app.core.security import get_password_hash
from app.models import (
    AuditLog,
    Branch,
    BranchBrand,
    Brand,
    BrandShiftCountItem,
    Item,
    ItemBrand,
    ItemCategory,
    Role,
    RoleName,
    UnitOfMeasure,
    User,
    UserRole,
    Warehouse,
)
from app.models.branch_shift_ops import (
    BranchShift,
    BranchShiftConfig,
    BranchShiftStatus,
    ShiftCountRowStatus,
    ShiftSectionStatus,
)

API = "/api/v1/shift-ops"
PASSWORD = "Pass@2026"


@pytest.fixture(autouse=True)
def _opening_refresh_env(monkeypatch):
    monkeypatch.setattr("app.config.settings.SHIFT_CASH_ENABLED", True)
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")


def _role(db, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if not row:
        row = Role(name=name, display_name=name.value, description="")
        db.add(row)
        db.flush()
    return row


def _user(db, username: str, role_name: RoleName, branch_id=None) -> User:
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


def _seed(db, *, items: int = 2, shifts: int = 2, suffix: str = "OR") -> dict:
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-B1",
        branch_name="Opening Refresh Branch",
        city="Riyadh",
        area="Olaya",
        warehouse_id=wh.id,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"{suffix}-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    unit = UnitOfMeasure(code=f"{suffix}-PCS", name_ar="pcs", name_en="pcs")
    db.add(unit)
    db.flush()

    item_ids = []
    for i in range(items):
        item = Item(
            item_code=f"{suffix}-ITEM-{i}",
            item_name_ar=f"صنف {i}",
            item_name_en=f"Item {i}",
            category_id=cat.id,
            unit_id=unit.id,
            active=True,
            is_deleted=False,
        )
        db.add(item)
        db.flush()
        db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
        db.add(
            BrandShiftCountItem(
                brand_id=brand.id,
                item_id=item.id,
                display_order=i + 1,
                is_active=True,
            )
        )
        item_ids.append(item.id)

    for n in range(1, shifts + 1):
        db.add(
            BranchShiftConfig(
                branch_id=branch.id,
                shift_number=n,
                shift_name_ar=f"وردية {n}",
                is_active=True,
                effective_from=date(2020, 1, 1),
                effective_to=None,
            )
        )

    users = {
        "branch": _user(db, f"{suffix}_bm".lower(), RoleName.branch_manager, branch.id),
        "admin": _user(db, f"{suffix}_admin".lower(), RoleName.admin),
    }
    db.commit()
    return {"branch_id": branch.id, "brand_id": brand.id, "item_ids": item_ids, "usernames": {k: v.username for k, v in users.items()}}


def _open_shift(client, hdr, day="2026-08-01", number=1, branch_id=None):
    payload = {"shift_date": day, "shift_number": number}
    if branch_id:
        payload["branch_id"] = branch_id
    resp = client.post(f"{API}/shifts", json=payload, headers=hdr)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_count(client, hdr, shift_id):
    resp = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def _patch_lines(client, hdr, shift_id, lines_payload):
    resp = client.patch(f"{API}/shifts/{shift_id}/count/lines", json={"lines": lines_payload}, headers=hdr)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _lines_from_count(count_json, *, closing_fn=None, extra=None):
    out = []
    for ln in count_json["lines"]:
        closing = closing_fn(ln) if closing_fn else float(ln["opening_balance"])
        row = {
            "item_id": ln["item_id"],
            "received_qty": 0,
            "returned_qty": 0,
            "damaged_qty": 0,
            "closing_balance": closing,
        }
        if extra:
            patch = extra(ln)
            if patch:
                row.update(patch)
        out.append(row)
    return out


def _submit_count(client, hdr, shift_id):
    return client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr)


def _fill_and_submit_count(client, hdr, shift_id, *, closing_fn=None):
    created = _create_count(client, hdr, shift_id)
    _patch_lines(client, hdr, shift_id, _lines_from_count(created, closing_fn=closing_fn))
    return _submit_count(client, hdr, shift_id)


def _fill_and_submit_cash(client, hdr, shift_id):
    body = {
        "total_sale": 100,
        "bill_count": 2,
        "mada_sales": 60,
        "cash_sales": 40,
        "app_sales": 0,
        "refund_bill": 0,
        "exchange_amount": 0,
        "expiry_amount": 0,
        "cash_expense": 0,
        "cash_float_carried_forward": 0,
        "cash_deposited": 40,
    }
    assert client.put(f"{API}/shifts/{shift_id}/cash", json=body, headers=hdr).status_code == 200
    assert client.post(f"{API}/shifts/{shift_id}/cash/submit", headers=hdr).status_code == 200


def _reopen(client, hdr, shift_id, *, target="count", reason="تصحيح بعد المراجعة"):
    return client.post(
        f"{API}/shifts/{shift_id}/reopen",
        json={"target": target, "reason": reason},
        headers=hdr,
    )


def _refresh_audit_rows(db, entity_id: int) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.module == "shift_ops",
            AuditLog.action == "count_openings_refreshed",
            AuditLog.entity_id == entity_id,
        )
        .all()
    )


def test_t1_reopen_resubmit_refreshes_later_draft(db, client):
    seed = _seed(db, suffix="T1")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    n_count = _create_count(client, bhdr, n_id)
    _patch_lines(client, bhdr, n_id, _lines_from_count(n_count, closing_fn=lambda ln: 10.0))
    assert _submit_count(client, bhdr, n_id).status_code == 200
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-01", number=2)
    n1_count = _create_count(client, bhdr, n1_id)
    item0 = seed["item_ids"][0]
    lines = _lines_from_count(n1_count, closing_fn=lambda ln: 10.0)
    for row in lines:
        if row["item_id"] == item0:
            row["received_qty"] = 3
            row["closing_balance"] = 8.0
    _patch_lines(client, bhdr, n1_id, lines)
    snap_before = client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()

    assert _reopen(client, ahdr, n_id).status_code == 200
    n_reopened = client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()
    patched = _lines_from_count(n_reopened, closing_fn=lambda ln: 17.0 if ln["item_id"] == item0 else 10.0)
    _patch_lines(client, bhdr, n_id, patched)
    submit = _submit_count(client, bhdr, n_id)
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["opening_refresh_summary"]["items_changed"]
    assert body["opening_refresh_summary"]["source_shift_id"] == n_id

    n1_after = client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()
    line0 = next(ln for ln in n1_after["lines"] if ln["item_id"] == item0)
    assert Decimal(line0["opening_balance"]) == Decimal("17.00")
    snap_line0 = next(ln for ln in snap_before["lines"] if ln["item_id"] == item0)
    assert line0["received_qty"] == snap_line0["received_qty"]
    assert line0["closing_balance"] == snap_line0["closing_balance"]

    audits = _refresh_audit_rows(db, n1_after["id"])
    assert len(audits) == 1
    old = json.loads(audits[0].old_values)
    new = json.loads(audits[0].new_values)
    assert str(item0) in old["openings"]
    assert new["source_shift_id"] == n_id


def test_t2_reopen_blocked_when_later_submitted(db, client):
    seed = _seed(db, suffix="T2")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id)
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-01", number=2)
    _fill_and_submit_count(client, bhdr, n1_id)
    _fill_and_submit_cash(client, bhdr, n1_id)

    before = db.query(BranchShift).filter(BranchShift.id == n_id).one().count.status
    resp = _reopen(client, ahdr, n_id)
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "REOPEN_BLOCKED_LATER_COUNT_SUBMITTED"
    after = db.query(BranchShift).filter(BranchShift.id == n_id).one().count.status
    assert before == after == ShiftSectionStatus.submitted.value


def test_t3_no_later_count_empty_summary(db, client):
    seed = _seed(db, suffix="T3")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id)
    _fill_and_submit_cash(client, bhdr, n_id)

    assert _reopen(client, ahdr, n_id).status_code == 200
    n_count = _create_count(client, bhdr, n_id)
    _patch_lines(client, bhdr, n_id, _lines_from_count(n_count, closing_fn=lambda ln: 12.0))
    submit = _submit_count(client, bhdr, n_id)
    assert submit.status_code == 200
    assert submit.json()["opening_refresh_summary"]["items_changed"] == []


def test_t4_exception_locked_chain(db, client):
    seed = _seed(db, suffix="T4")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    item0 = seed["item_ids"][0]

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id, closing_fn=lambda ln: 20.0 if ln["item_id"] == item0 else 5.0)
    _fill_and_submit_cash(client, bhdr, n_id)

    locked_id = _open_shift(client, bhdr, day="2026-08-02", number=1)
    locked_count = _create_count(client, bhdr, locked_id)
    locked_lines = _lines_from_count(
        locked_count,
        closing_fn=lambda ln: 999.0 if ln["item_id"] == item0 else float(ln["opening_balance"]),
        extra=lambda ln: (
            {"received_qty": 979.0}
            if ln["item_id"] == item0
            else None
        ),
    )
    _patch_lines(client, bhdr, locked_id, locked_lines)
    assert _submit_count(client, bhdr, locked_id).status_code == 200
    _fill_and_submit_cash(client, bhdr, locked_id)
    locked = db.query(BranchShift).filter(BranchShift.id == locked_id).one()
    locked.status = BranchShiftStatus.exception_locked.value
    db.commit()

    n1_id = _open_shift(client, bhdr, day="2026-08-03", number=1)
    n1 = _create_count(client, bhdr, n1_id)
    line0 = next(ln for ln in n1["lines"] if ln["item_id"] == item0)
    assert Decimal(line0["opening_balance"]) == Decimal("20.00")

    resp = _reopen(client, ahdr, n_id)
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "REOPEN_BLOCKED_LATER_COUNT_SUBMITTED"


def test_t5_three_shift_reopen_and_refresh(db, client):
    seed = _seed(db, suffix="T5")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    item0 = seed["item_ids"][0]

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id, closing_fn=lambda ln: 10.0)
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-02", number=1)
    _fill_and_submit_count(client, bhdr, n1_id, closing_fn=lambda ln: 10.0)
    _fill_and_submit_cash(client, bhdr, n1_id)

    n2_id = _open_shift(client, bhdr, day="2026-08-03", number=1)
    n2 = _create_count(client, bhdr, n2_id)
    _patch_lines(client, bhdr, n2_id, _lines_from_count(n2, closing_fn=lambda ln: 10.0))

    assert _reopen(client, ahdr, n_id).status_code == 409

    assert _reopen(client, ahdr, n1_id).status_code == 200
    n1_count = client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()
    _patch_lines(
        client,
        bhdr,
        n1_id,
        _lines_from_count(
            n1_count,
            closing_fn=lambda ln: 25.0 if ln["item_id"] == item0 else 10.0,
            extra=lambda ln: (
                {"received_qty": 15.0}
                if ln["item_id"] == item0
                else None
            ),
        ),
    )
    submit = _submit_count(client, bhdr, n1_id)
    assert submit.status_code == 200
    n2_after = client.get(f"{API}/shifts/{n2_id}/count", headers=bhdr).json()
    line0 = next(ln for ln in n2_after["lines"] if ln["item_id"] == item0)
    assert Decimal(line0["opening_balance"]) == Decimal("25.00")


def test_t6_first_count_branch_reason_incomplete(db, client):
    seed = _seed(db, suffix="T6", items=1)
    bhdr = _login(client, seed["usernames"]["branch"])
    item0 = seed["item_ids"][0]

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    n_count = _create_count(client, bhdr, n_id)
    _patch_lines(client, bhdr, n_id, _lines_from_count(n_count, closing_fn=lambda ln: 10.0))
    assert _submit_count(client, bhdr, n_id).status_code == 200
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-01", number=2)
    n1 = _create_count(client, bhdr, n1_id)
    lines = _lines_from_count(n1, closing_fn=lambda ln: float(ln["opening_balance"]))
    _patch_lines(client, bhdr, n1_id, lines)

    assert _reopen(client, _login(client, seed["usernames"]["admin"]), n_id).status_code == 200
    n_again = client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()
    _patch_lines(
        client,
        bhdr,
        n_id,
        _lines_from_count(n_again, closing_fn=lambda ln: 5.0),
    )
    resubmit = _submit_count(client, bhdr, n_id)
    assert resubmit.status_code == 200, resubmit.text
    assert resubmit.json()["opening_refresh_summary"]["items_changed"]

    n1_mid = client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()
    line0_mid = next(ln for ln in n1_mid["lines"] if ln["item_id"] == item0)
    assert Decimal(line0_mid["opening_balance"]) == Decimal("5.00")
    assert line0_mid["row_status"] != ShiftCountRowStatus.valid.value

    blocked = _submit_count(client, bhdr, n1_id)
    assert blocked.status_code == 409
    assert blocked.json()["error_code"] == "SHIFT_COUNT_INCOMPLETE"


def test_t7_previous_count_not_submitted_hole(db, client):
    seed = _seed(db, suffix="T7")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id)
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-01", number=2)
    n1 = _create_count(client, bhdr, n1_id)
    _patch_lines(client, bhdr, n1_id, _lines_from_count(n1, closing_fn=lambda ln: float(ln["opening_balance"])))

    assert _reopen(client, ahdr, n_id).status_code == 200
    hole = _submit_count(client, bhdr, n1_id)
    assert hole.status_code == 409
    assert hole.json()["error_code"] == "PREVIOUS_COUNT_NOT_SUBMITTED"

    n_reopened = client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()
    _patch_lines(
        client,
        bhdr,
        n_id,
        _lines_from_count(n_reopened, closing_fn=lambda ln: float(ln["opening_balance"])),
    )
    assert _submit_count(client, bhdr, n_id).status_code == 200
    ok = _submit_count(client, bhdr, n1_id)
    assert ok.status_code == 200


def test_t8_cash_only_reopen_not_blocked(db, client):
    seed = _seed(db, suffix="T8")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id)
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-02", number=1)
    _fill_and_submit_count(client, bhdr, n1_id)
    _fill_and_submit_cash(client, bhdr, n1_id)

    resp = _reopen(client, ahdr, n_id, target="cash")
    assert resp.status_code == 200


def test_t9_audit_strictness(db, client, monkeypatch):
    seed = _seed(db, suffix="T9")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    item0 = seed["item_ids"][0]

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id, closing_fn=lambda ln: 10.0)
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-02", number=1)
    n1 = _create_count(client, bhdr, n1_id)
    _patch_lines(client, bhdr, n1_id, _lines_from_count(n1, closing_fn=lambda ln: 10.0))
    opening_before = next(ln for ln in n1["lines"] if ln["item_id"] == item0)["opening_balance"]

    assert _reopen(client, ahdr, n_id).status_code == 200
    n_count = client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()
    _patch_lines(
        client,
        bhdr,
        n_id,
        _lines_from_count(
            n_count,
            closing_fn=lambda ln: 22.0 if ln["item_id"] == item0 else 10.0,
            extra=lambda ln: (
                {"received_qty": 12.0}
                if ln["item_id"] == item0
                else None
            ),
        ),
    )

    def _boom(*_a, **_k):
        raise RuntimeError("forced audit failure")

    monkeypatch.setattr("app.services.audit_service.log_strict", _boom)
    fail = _submit_count(client, bhdr, n_id)
    assert fail.status_code >= 400
    db.expire_all()
    n_status = client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()["status"]
    assert n_status == ShiftSectionStatus.draft.value
    n1_line = client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()
    line0 = next(ln for ln in n1_line["lines"] if ln["item_id"] == item0)
    assert line0["opening_balance"] == opening_before

    monkeypatch.undo()
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "false")
    blocked = _submit_count(client, bhdr, n_id)
    assert blocked.status_code == 409
    assert blocked.json()["error_code"] == "AUDIT_REQUIRED_FOR_OPENING_REFRESH"
    db.expire_all()
    assert client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()["status"] == ShiftSectionStatus.draft.value

    seed_solo = _seed(db, suffix="T9S")
    bhdr_solo = _login(client, seed_solo["usernames"]["branch"])
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "false")
    solo_id = _open_shift(client, bhdr_solo, day="2026-08-10", number=1)
    solo = _create_count(client, bhdr_solo, solo_id)
    _patch_lines(client, bhdr_solo, solo_id, _lines_from_count(solo, closing_fn=lambda ln: 7.0))
    ok = _submit_count(client, bhdr_solo, solo_id)
    assert ok.status_code == 200


def test_t9iv_audit_off_resubmit_no_opening_change_succeeds(db, client, monkeypatch):
    seed = _seed(db, suffix="T9IV")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id, closing_fn=lambda ln: 10.0)
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-01", number=2)
    n1 = _create_count(client, bhdr, n1_id)
    _patch_lines(client, bhdr, n1_id, _lines_from_count(n1, closing_fn=lambda ln: float(ln["opening_balance"])))

    assert _reopen(client, ahdr, n_id).status_code == 200
    n_reopened = client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()
    _patch_lines(
        client,
        bhdr,
        n_id,
        _lines_from_count(n_reopened, closing_fn=lambda ln: float(ln["closing_balance"])),
    )

    monkeypatch.setenv("AUDIT_LOG_ENABLED", "false")
    resubmit = _submit_count(client, bhdr, n_id)
    assert resubmit.status_code == 200, resubmit.text
    assert resubmit.json()["opening_refresh_summary"]["items_changed"] == []


def test_t9v_audit_off_closing_change_blocked_n_stays_draft(db, client, monkeypatch):
    seed = _seed(db, suffix="T9V")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    item0 = seed["item_ids"][0]

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id, closing_fn=lambda ln: 10.0)
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-02", number=1)
    n1 = _create_count(client, bhdr, n1_id)
    _patch_lines(client, bhdr, n1_id, _lines_from_count(n1, closing_fn=lambda ln: float(ln["opening_balance"])))
    openings_before = {
        ln["item_id"]: ln["opening_balance"]
        for ln in client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()["lines"]
    }

    assert _reopen(client, ahdr, n_id).status_code == 200
    n_count = client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()
    _patch_lines(
        client,
        bhdr,
        n_id,
        _lines_from_count(
            n_count,
            closing_fn=lambda ln: 18.0 if ln["item_id"] == item0 else float(ln["opening_balance"]),
            extra=lambda ln: (
                {"received_qty": 8.0}
                if ln["item_id"] == item0
                else None
            ),
        ),
    )

    monkeypatch.setenv("AUDIT_LOG_ENABLED", "false")
    blocked = _submit_count(client, bhdr, n_id)
    assert blocked.status_code == 409
    assert blocked.json()["error_code"] == "AUDIT_REQUIRED_FOR_OPENING_REFRESH"
    db.expire_all()
    assert client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()["status"] == ShiftSectionStatus.draft.value
    openings_after = {
        ln["item_id"]: ln["opening_balance"]
        for ln in client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()["lines"]
    }
    assert openings_after == openings_before


def test_t9vi_summary_matches_db_opening_diff(db, client):
    seed = _seed(db, suffix="T9VI")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    item0 = seed["item_ids"][0]

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id, closing_fn=lambda ln: 10.0)
    _fill_and_submit_cash(client, bhdr, n_id)

    n1_id = _open_shift(client, bhdr, day="2026-08-02", number=1)
    n1 = _create_count(client, bhdr, n1_id)
    _patch_lines(client, bhdr, n1_id, _lines_from_count(n1, closing_fn=lambda ln: float(ln["opening_balance"])))
    before = {
        ln["item_id"]: ln["opening_balance"]
        for ln in client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()["lines"]
    }

    assert _reopen(client, ahdr, n_id).status_code == 200
    n_count = client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()
    _patch_lines(
        client,
        bhdr,
        n_id,
        _lines_from_count(
            n_count,
            closing_fn=lambda ln: 15.0 if ln["item_id"] == item0 else 10.0,
            extra=lambda ln: (
                {"received_qty": 5.0}
                if ln["item_id"] == item0
                else None
            ),
        ),
    )
    submit = _submit_count(client, bhdr, n_id)
    assert submit.status_code == 200, submit.text
    after = {
        ln["item_id"]: ln["opening_balance"]
        for ln in client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()["lines"]
    }
    expected_items = {
        item_id
        for item_id, old in before.items()
        if Decimal(after[item_id]) != Decimal(old)
    }
    summary_ids = {row["item_id"] for row in submit.json()["opening_refresh_summary"]["items_changed"]}
    assert summary_ids == expected_items
    for row in submit.json()["opening_refresh_summary"]["items_changed"]:
        assert row["old_opening"] == f"{Decimal(before[row['item_id']]):.2f}"
        assert row["new_opening"] == f"{Decimal(after[row['item_id']]):.2f}"


def test_t10_resubmit_empty_summary_no_audit(db, client):
    seed = _seed(db, suffix="T10")
    bhdr = _login(client, seed["usernames"]["branch"])

    n_id = _open_shift(client, bhdr, day="2026-08-01", number=1)
    _fill_and_submit_count(client, bhdr, n_id)
    before_audits = db.query(AuditLog).filter(AuditLog.action == "count_openings_refreshed").count()

    again = _submit_count(client, bhdr, n_id)
    assert again.status_code == 200
    assert again.json()["opening_refresh_summary"]["items_changed"] == []
    assert db.query(AuditLog).filter(AuditLog.action == "count_openings_refreshed").count() == before_audits
