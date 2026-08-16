"""Coverage for the acceptance areas flagged as missing in FINAL_DECISION.md.

Written against the gate's acceptance list, not against the implementation:
  - isolation: no ledger movement, no branch request
  - available_shift_numbers (1 shift / 2 shifts / expired config)
  - reopen limit + admin bypass
  - reopen target=cash must not touch the count
  - chain_gap returns the five details, not a boolean
  - POST /count idempotency including the submitted case
  - effective_from/to overlap: containment and open-ended range
  - is_partial across all four states + partial_only filter
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.security import get_password_hash
from app.models import (
    Branch,
    BranchBrand,
    BranchRequest,
    Brand,
    Item,
    ItemBrand,
    ItemCategory,
    Role,
    RoleName,
    StockTransaction,
    UnitOfMeasure,
    User,
    UserRole,
    Warehouse,
)
from app.models.branch_shift_ops import BranchShiftConfig, BrandShiftCountItem

API = "/api/v1/shift-ops"
PASSWORD = "Pass@2026"


# ─────────────────────────── helpers ───────────────────────────

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


def _seed(db, *, shifts: int = 1, items: int = 1, suffix: str = "G"):
    """Branch + brand + items + shift configs + users. `shifts` drives how many
    BranchShiftConfig rows are created (1 or 2)."""
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-B1", branch_name="Gap Branch", city="Riyadh",
        area="Olaya", warehouse_id=wh.id,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"{suffix}-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    unit = UnitOfMeasure(code=f"{suffix}-PCS", name_ar="قطعة", name_en="pcs")
    db.add(unit)
    db.flush()

    item_ids = []
    for i in range(items):
        item = Item(
            item_code=f"{suffix}-ITEM-{i}", item_name_ar=f"صنف {i}", item_name_en=f"Item {i}",
            category_id=cat.id, unit_id=unit.id, active=True, is_deleted=False,
        )
        db.add(item)
        db.flush()
        db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
        db.add(BrandShiftCountItem(brand_id=brand.id, item_id=item.id, display_order=i + 1, is_active=True))
        item_ids.append(item.id)

    for n in range(1, shifts + 1):
        db.add(BranchShiftConfig(
            branch_id=branch.id, shift_number=n, shift_name_ar=f"الشفت {n}",
            is_active=True, effective_from=date(2020, 1, 1), effective_to=None,
        ))

    users = {
        "branch": _user(db, f"{suffix}_bu".lower(), RoleName.branch_user, branch.id),
        "admin": _user(db, f"{suffix}_admin".lower(), RoleName.admin),
        "ops": _user(db, f"{suffix}_ops".lower(), RoleName.operations_manager),
    }
    db.commit()
    return {
        "branch_id": branch.id, "brand_id": brand.id, "item_ids": item_ids,
        "usernames": {k: v.username for k, v in users.items()},
    }


def _open_shift(client, hdr, day="2026-08-01", number=1, branch_id=None):
    payload = {"shift_date": day, "shift_number": number}
    if branch_id:
        payload["branch_id"] = branch_id
    resp = client.post(f"{API}/shifts", json=payload, headers=hdr)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _fill_and_submit_count(client, hdr, shift_id):
    created = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    assert created.status_code in (200, 201), created.text
    lines = created.json()["lines"]
    payload = {"lines": [
        {
            "item_id": ln["item_id"], "received_qty": 0, "returned_qty": 0,
            "damaged_qty": 0, "closing_balance": float(ln["opening_balance"]),
        } for ln in lines
    ]}
    assert client.patch(f"{API}/shifts/{shift_id}/count/lines", json=payload, headers=hdr).status_code == 200
    resp = client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr)
    assert resp.status_code == 200, resp.text
    return resp


def _fill_and_submit_cash(client, hdr, shift_id):
    body = {
        "total_sale": 100, "bill_count": 2, "mada_sales": 60, "cash_sales": 40,
        "app_sales": 0, "refund_bill": 0, "exchange_amount": 0, "expiry_amount": 0,
        "cash_expense": 0, "cash_float_carried_forward": 0, "cash_deposited": 40,
    }
    assert client.put(f"{API}/shifts/{shift_id}/cash", json=body, headers=hdr).status_code == 200
    resp = client.post(f"{API}/shifts/{shift_id}/cash/submit", headers=hdr)
    assert resp.status_code == 200, resp.text
    return resp


# ─────────────────────── 1. isolation (the two missing) ───────────────────────

def test_submit_creates_no_ledger_movement(db, client):
    seed = _seed(db, suffix="LG")
    hdr = _login(client, seed["usernames"]["branch"])
    before = db.query(StockTransaction).count()
    shift_id = _open_shift(client, hdr)
    _fill_and_submit_count(client, hdr, shift_id)
    _fill_and_submit_cash(client, hdr, shift_id)
    assert db.query(StockTransaction).count() == before == 0


def test_submit_creates_no_branch_request(db, client):
    seed = _seed(db, suffix="BR")
    hdr = _login(client, seed["usernames"]["branch"])
    before = db.query(BranchRequest).count()
    shift_id = _open_shift(client, hdr)
    _fill_and_submit_count(client, hdr, shift_id)
    _fill_and_submit_cash(client, hdr, shift_id)
    assert db.query(BranchRequest).count() == before == 0


# ───────────────────── 2. available_shift_numbers ─────────────────────

def test_available_shift_numbers_two_shift_branch(db, client):
    seed = _seed(db, shifts=2, suffix="A2")
    hdr = _login(client, seed["usernames"]["branch"])
    shift_id = _open_shift(client, hdr)
    body = client.get(f"{API}/shifts/{shift_id}", headers=hdr).json()
    assert body["available_shift_numbers"] == [1, 2]


def test_available_shift_numbers_single_shift_branch(db, client):
    seed = _seed(db, shifts=1, suffix="A1")
    hdr = _login(client, seed["usernames"]["branch"])
    shift_id = _open_shift(client, hdr)
    body = client.get(f"{API}/shifts/{shift_id}", headers=hdr).json()
    assert body["available_shift_numbers"] == [1]


def test_available_shift_numbers_hides_expired_config(db, client):
    seed = _seed(db, shifts=1, suffix="AX")
    # a second shift that stopped being valid before the shift date
    db.add(BranchShiftConfig(
        branch_id=seed["branch_id"], shift_number=2, shift_name_ar="الشفت 2",
        is_active=True, effective_from=date(2020, 1, 1), effective_to=date(2026, 1, 1),
    ))
    db.commit()
    hdr = _login(client, seed["usernames"]["branch"])
    shift_id = _open_shift(client, hdr, day="2026-08-01")
    body = client.get(f"{API}/shifts/{shift_id}", headers=hdr).json()
    assert body["available_shift_numbers"] == [1], "expired config must not be offered"


def test_available_shift_numbers_present_in_list(db, client):
    seed = _seed(db, shifts=2, suffix="AL")
    hdr = _login(client, seed["usernames"]["branch"])
    _open_shift(client, hdr)
    rows = client.get(f"{API}/shifts", headers=hdr).json()["items"]
    assert rows and rows[0]["available_shift_numbers"] == [1, 2]


def test_list_shifts_exposes_config_with_zero_shifts(db, client):
    """Branch with shift config but no opened shifts must still get numbers at response level."""
    seed = _seed(db, shifts=1, suffix="Z0")
    hdr = _login(client, seed["usernames"]["branch"])
    body = client.get(f"{API}/shifts", headers=hdr).json()
    assert body["items"] == []
    assert body["available_shift_numbers"] == [1]


def test_list_shifts_empty_config_returns_empty_array(db, client):
    """Branch with no BranchShiftConfig rows must get [], not null and no error."""
    wh = Warehouse(warehouse_code="NC-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code="NC-B1", branch_name="No Config Branch", city="Riyadh",
        area="Olaya", warehouse_id=wh.id,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name="NC Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    user = _user(db, "nc_bu", RoleName.branch_user, branch.id)
    db.commit()
    hdr = _login(client, user.username)
    body = client.get(f"{API}/shifts", headers=hdr).json()
    assert body["items"] == []
    assert body["available_shift_numbers"] == []


def test_list_shifts_admin_scope_uses_requested_branch(db, client):
    """Admin listing branch A must not inherit shift numbers from branch B's open shift."""
    seed_one = _seed(db, shifts=1, suffix="S1")
    seed_two = _seed(db, shifts=2, suffix="S2")
    admin_hdr = _login(client, seed_one["usernames"]["admin"])
    branch_hdr = _login(client, seed_two["usernames"]["branch"])
    _open_shift(client, branch_hdr, day="2026-08-01")
    body = client.get(
        f"{API}/shifts",
        params={"branch_id": seed_one["branch_id"]},
        headers=admin_hdr,
    ).json()
    assert body["available_shift_numbers"] == [1]
    assert body["available_shift_numbers"] != [1, 2]


# ───────────────────── 3. reopen limit + admin bypass ─────────────────────

def _reopen(client, hdr, shift_id, target="both", reason="تصحيح رقم", admin_override=False):
    body = {"target": target, "reason": reason}
    if admin_override:
        body["admin_override"] = True
    return client.post(f"{API}/shifts/{shift_id}/reopen", json=body, headers=hdr)


def test_third_reopen_is_rejected_and_admin_can_override(db, client):
    seed = _seed(db, suffix="RL")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr)

    for attempt in range(2):
        _fill_and_submit_count(client, bhdr, shift_id)
        _fill_and_submit_cash(client, bhdr, shift_id)
        assert _reopen(client, ahdr, shift_id).status_code == 200, f"reopen #{attempt + 1} should pass"

    _fill_and_submit_count(client, bhdr, shift_id)
    _fill_and_submit_cash(client, bhdr, shift_id)

    blocked = _reopen(client, ahdr, shift_id)
    assert blocked.status_code == 409
    assert "REOPEN_LIMIT_REACHED" in blocked.text

    bypass = _reopen(client, ahdr, shift_id, admin_override=True)
    assert bypass.status_code == 200, "admin must be able to override the cap"


def test_reopen_target_cash_does_not_touch_count(db, client):
    seed = _seed(db, suffix="RT")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr)
    _fill_and_submit_count(client, bhdr, shift_id)
    _fill_and_submit_cash(client, bhdr, shift_id)

    assert _reopen(client, ahdr, shift_id, target="cash").status_code == 200

    body = client.get(f"{API}/shifts/{shift_id}", headers=bhdr).json()
    assert body["cash_status"] == "draft"
    assert body["count_status"] == "submitted", "count must be untouched when target=cash"


def test_reopen_requires_reason(db, client):
    seed = _seed(db, suffix="RR")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr)
    _fill_and_submit_count(client, bhdr, shift_id)
    _fill_and_submit_cash(client, bhdr, shift_id)
    assert _reopen(client, ahdr, shift_id, reason="abc").status_code == 422


def test_branch_user_cannot_reopen(db, client):
    seed = _seed(db, suffix="RB")
    bhdr = _login(client, seed["usernames"]["branch"])
    shift_id = _open_shift(client, bhdr)
    _fill_and_submit_count(client, bhdr, shift_id)
    _fill_and_submit_cash(client, bhdr, shift_id)
    assert _reopen(client, bhdr, shift_id).status_code == 403


# ───────────────────── 4. chain_gap with five details ─────────────────────

def test_chain_gap_returns_five_details_not_boolean(db, client):
    seed = _seed(db, suffix="CG")
    bhdr = _login(client, seed["usernames"]["branch"])
    ohdr = _login(client, seed["usernames"]["ops"])

    stuck = _open_shift(client, bhdr, day="2026-08-01")
    resp = client.post(
        f"{API}/shifts/{stuck}/close-no-activity",
        json={"exception_type": "branch_closed", "reason": "الفرع كان مغلق"},
        headers=ohdr,
    )
    assert resp.status_code == 200, resp.text

    later = _open_shift(client, bhdr, day="2026-08-02")
    _fill_and_submit_count(client, bhdr, later)
    _fill_and_submit_cash(client, bhdr, later)

    report = client.get(f"{API}/reports/shift-operations", headers=ohdr)
    assert report.status_code == 200, report.text
    rows = [r for r in report.json()["items"] if r.get("chain_gap")]
    assert rows, "a skipped exception-locked shift must surface a chain_gap"
    gap = rows[0]["chain_gap"]
    for key in (
        "skipped_shift_id", "skipped_shift_date", "skipped_shift_number",
        "skipped_reason", "skipped_exception_type",
    ):
        assert key in gap, f"chain_gap missing {key}"
    assert gap["skipped_shift_id"] == stuck
    assert gap["skipped_exception_type"] == "branch_closed"


# ───────────────────── 5. idempotency incl. submitted ─────────────────────

def test_post_count_idempotent_while_draft(db, client):
    seed = _seed(db, suffix="ID")
    hdr = _login(client, seed["usernames"]["branch"])
    shift_id = _open_shift(client, hdr)
    first = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    second = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["items_frozen_at"] == second.json()["items_frozen_at"]
    assert len(first.json()["lines"]) == len(second.json()["lines"])


def test_post_count_idempotent_after_submit(db, client):
    seed = _seed(db, suffix="IS")
    hdr = _login(client, seed["usernames"]["branch"])
    shift_id = _open_shift(client, hdr)
    created = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    _fill_and_submit_count(client, hdr, shift_id)
    again = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    assert again.status_code == 200, "re-opening the page on a submitted count must not 409"
    assert again.json()["id"] == created.json()["id"]
    assert again.json()["items_frozen_at"] == created.json()["items_frozen_at"]


def test_frozen_list_survives_reopen(db, client):
    seed = _seed(db, suffix="FZ")
    bhdr = _login(client, seed["usernames"]["branch"])
    ahdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, bhdr)
    created = client.post(f"{API}/shifts/{shift_id}/count", headers=bhdr)
    original = len(created.json()["lines"])
    _fill_and_submit_count(client, bhdr, shift_id)
    _fill_and_submit_cash(client, bhdr, shift_id)

    # a brand item added after freezing must never appear, even after reopen
    new_item = Item(
        item_code="FZ-LATE", item_name_ar="متأخر", item_name_en="Late",
        category_id=db.query(ItemCategory).first().id,
        unit_id=db.query(UnitOfMeasure).first().id, active=True, is_deleted=False,
    )
    db.add(new_item)
    db.flush()
    db.add(BrandShiftCountItem(brand_id=seed["brand_id"], item_id=new_item.id, display_order=99, is_active=True))
    db.commit()

    assert _reopen(client, ahdr, shift_id, target="count").status_code == 200
    after = client.get(f"{API}/shifts/{shift_id}/count", headers=bhdr).json()
    assert len(after["lines"]) == original, "frozen list must not absorb items added later"


# ───────────────────── 6. effective range overlap ─────────────────────

@pytest.mark.parametrize(
    "new_from,new_to,label",
    [
        (date(2026, 3, 1), date(2026, 5, 1), "containment"),
        (date(2026, 1, 1), None, "open-ended"),
        (date(2025, 1, 1), date(2026, 3, 1), "overlap from the left"),
        (date(2026, 5, 1), date(2027, 1, 1), "overlap from the right"),
    ],
)
def test_config_overlap_rejected_in_all_shapes(db, new_from, new_to, label):
    from app.services import shift_ops_service as svc

    seed = _seed(db, shifts=0, suffix=f"OV{abs(hash(label)) % 997}")
    existing = BranchShiftConfig(
        branch_id=seed["branch_id"], shift_number=1, shift_name_ar="الشفت 1",
        is_active=True, effective_from=date(2026, 2, 1), effective_to=date(2026, 6, 1),
    )
    db.add(existing)
    db.commit()

    from app.core.errors import AppError

    with pytest.raises(AppError) as err:
        svc.validate_config_no_overlap(
            db, branch_id=seed["branch_id"], shift_number=1,
            effective_from=new_from, effective_to=new_to,
        )
    # Assert the specific code: a bare `raises(Exception)` would also pass on a
    # NameError or an unrelated AppError, i.e. pass for the wrong reason.
    assert err.value.error_code == "shift_ops.config_overlap", (
        f"{label} must be rejected as an overlap, got {err.value.error_code}"
    )


def test_config_non_overlapping_range_is_accepted(db):
    from app.services import shift_ops_service as svc

    seed = _seed(db, shifts=0, suffix="OK")
    db.add(BranchShiftConfig(
        branch_id=seed["branch_id"], shift_number=1, shift_name_ar="الشفت 1",
        is_active=True, effective_from=date(2026, 2, 1), effective_to=date(2026, 6, 1),
    ))
    db.commit()
    svc.validate_config_no_overlap(
        db, branch_id=seed["branch_id"], shift_number=1,
        effective_from=date(2026, 6, 2), effective_to=None,
    )


# ───────────────────── 7. is_partial across four states ─────────────────────

def test_is_partial_four_states_and_filter(db, client):
    seed = _seed(db, suffix="PT")
    hdr = _login(client, seed["usernames"]["branch"])
    shift_id = _open_shift(client, hdr)

    def state():
        return client.get(f"{API}/shifts/{shift_id}", headers=hdr).json()

    # 1) neither submitted
    assert state()["is_partial"] is False

    # 2) count only
    _fill_and_submit_count(client, hdr, shift_id)
    body = state()
    assert body["is_partial"] is True
    assert body["count_status"] == "submitted" and body["cash_status"] != "submitted"

    # 3) both submitted
    _fill_and_submit_cash(client, hdr, shift_id)
    body = state()
    assert body["is_partial"] is False
    assert body["status"] == "submitted"

    # 4) cash only — reached by reopening the count
    ahdr = _login(client, seed["usernames"]["admin"])
    assert _reopen(client, ahdr, shift_id, target="count").status_code == 200
    body = state()
    assert body["is_partial"] is True
    assert body["cash_status"] == "submitted" and body["count_status"] == "draft"

    partial = client.get(f"{API}/shifts", params={"partial_only": "true"}, headers=hdr).json()["items"]
    assert any(r["id"] == shift_id for r in partial)


def test_partial_only_filter_finds_forgotten_shifts(db, client):
    seed = _seed(db, suffix="PF")
    hdr = _login(client, seed["usernames"]["branch"])
    forgotten = _open_shift(client, hdr, day="2026-08-01")
    _fill_and_submit_count(client, hdr, forgotten)  # cash never submitted

    rows = client.get(
        f"{API}/shifts",
        params={"partial_only": "true", "date_to": "2026-08-02"},
        headers=hdr,
    ).json()["items"]
    assert [r["id"] for r in rows] == [forgotten]


# ───────────────────── 8. branch without count items (deploy assumption) ─────────────────────

def _seed_no_count_items(db, *, suffix: str = "NC"):
    """Branch + brand link, shift config, but zero BrandShiftCountItem rows."""
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"{suffix}-B1", branch_name="No Count Items Branch", city="Riyadh",
        area="Olaya", warehouse_id=wh.id,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"{suffix}-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    unit = UnitOfMeasure(code=f"{suffix}-PCS", name_ar="قطعة", name_en="pcs")
    db.add(unit)
    db.flush()
    item = Item(
        item_code=f"{suffix}-ITEM-0", item_name_ar="صنف", item_name_en="Item",
        category_id=cat.id, unit_id=unit.id, active=True, is_deleted=False,
    )
    db.add(item)
    db.flush()
    db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
    db.add(BranchShiftConfig(
        branch_id=branch.id, shift_number=1, shift_name_ar="الشفت 1",
        is_active=True, effective_from=date(2020, 1, 1), effective_to=None,
    ))
    users = {
        "branch": _user(db, f"{suffix}_bu".lower(), RoleName.branch_user, branch.id),
        "admin": _user(db, f"{suffix}_admin".lower(), RoleName.admin),
    }
    db.commit()
    return {"branch_id": branch.id, "usernames": {k: v.username for k, v in users.items()}}


def test_branch_without_count_items_empty_count_submits(db, client):
    """فرع بلا brand_shift_count_items: جرد فارغ يُرحَّل، الكاش يُرحَّل، التقرير 0/0."""
    seed = _seed_no_count_items(db, suffix="NC")
    hdr = _login(client, seed["usernames"]["branch"])
    admin_hdr = _login(client, seed["usernames"]["admin"])
    shift_id = _open_shift(client, hdr)

    created = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    assert created.status_code in (200, 201), created.text
    assert created.json()["lines"] == []

    assert client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr).status_code == 200
    _fill_and_submit_cash(client, hdr, shift_id)

    body = client.get(f"{API}/shifts/{shift_id}", headers=hdr).json()
    assert body["status"] == "submitted"

    report = client.get(f"{API}/reports/shift-operations", headers=admin_hdr).json()
    row = next(i for i in report["items"] if i["id"] == shift_id)
    assert row["count_lines_total"] == 0
    assert row["count_lines_filled"] == 0
