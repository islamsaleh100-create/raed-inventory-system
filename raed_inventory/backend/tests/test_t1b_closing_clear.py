"""
T1-b — closing balance clear behavior (TG-T1B-CLOSING-CLEAR).

PostgreSQL test DB only. All scenarios via TestClient; value checks via raw SQL on the
test transaction connection after session.expire_all().
"""
from __future__ import annotations

import os
import secrets
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Branch,
    BranchBrand,
    Brand,
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
from app.models.branch_shift_ops import BranchShiftConfig, BrandShiftCountItem  # noqa: E402
from conftest import (  # noqa: E402
    EXPECTED_ALEMBIC,
    EXPECTED_DB,
    EXPECTED_USER,
    TEST_ENGINE,
    USE_POSTGRES,
    _run_postgres_guard,
)
from fastapi.testclient import TestClient  # noqa: E402

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not USE_POSTGRES, reason="T1-b requires PostgreSQL test database"),
]

API = "/api/v1/shift-ops"
PASSWORD = secrets.token_urlsafe(32)


@pytest.fixture(autouse=True)
def _enable_shift_cash(monkeypatch):
    monkeypatch.setattr("app.config.settings.SHIFT_CASH_ENABLED", True)


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


def _seed_opening_branch(db, *, suffix: str) -> dict:
    """Minimal branch + one count item + shift config; first shift will be opening count."""
    wh = Warehouse(
        warehouse_code=f"T1B-{suffix}-WH",
        warehouse_name="WH",
        location="Riyadh",
        active=True,
    )
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code=f"T1B-{suffix}-B",
        branch_name="T1b Branch",
        city="Riyadh",
        area="Test",
        warehouse_id=wh.id,
    )
    db.add(branch)
    db.flush()
    brand = Brand(name=f"T1B {suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    cat = ItemCategory(code=f"T1B-{suffix}-CAT", name_ar="فئة", name_en="Cat")
    db.add(cat)
    unit = UnitOfMeasure(code=f"T1B-{suffix}-PCS", name_ar="قطعة", name_en="pcs")
    db.add(unit)
    db.flush()
    item = Item(
        item_code=f"T1B-{suffix}-ITEM",
        item_name_ar="صنف",
        item_name_en="Item",
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
            display_order=1,
            is_active=True,
        )
    )
    db.add(
        BranchShiftConfig(
            branch_id=branch.id,
            shift_number=1,
            shift_name_ar="الشفت 1",
            is_active=True,
            effective_from=date(2020, 1, 1),
            effective_to=None,
        )
    )
    bm = _user(db, f"t1b_{suffix}_bm", RoleName.branch_manager, branch.id)
    db.commit()
    return {
        "branch_code": branch.branch_code,
        "branch_id": branch.id,
        "item_id": item.id,
        "username": bm.username,
    }


def _login(client: TestClient, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _open_first_shift(client: TestClient, hdr: dict, branch_id: int) -> int:
    resp = client.post(
        f"{API}/shifts",
        json={"shift_date": "2026-09-01", "shift_number": 1, "branch_id": branch_id},
        headers=hdr,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_opening_count(client: TestClient, hdr: dict, shift_id: int) -> dict:
    resp = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["is_opening_count"] is True, "must use first opening count on new branch"
    assert body["status"] == "draft"
    return body


def _patch_line(
    client: TestClient,
    hdr: dict,
    shift_id: int,
    item_id: int,
    *,
    closing: float | None = None,
    omit_closing_key: bool = False,
) -> dict:
    line: dict = {
        "item_id": item_id,
        "received_qty": 0,
        "returned_qty": 0,
        "damaged_qty": 0,
    }
    if not omit_closing_key:
        line["closing_balance"] = closing
    resp = client.patch(
        f"{API}/shifts/{shift_id}/count/lines",
        json={"lines": [line]},
        headers=hdr,
    )
    if resp.status_code == 422:
        pytest.fail(
            f"PATCH returned 422 (check opening-count setup): {resp.json().get('error_code')} — {resp.text}"
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _raw_line(db, count_id: int, item_id: int) -> tuple[Decimal | None, str]:
    db.expire_all()
    row = (
        db.connection()
        .execute(
            text(
                "SELECT closing_balance, row_status FROM branch_shift_count_lines "
                "WHERE count_id = :cid AND item_id = :iid"
            ),
            {"cid": count_id, "iid": item_id},
        )
        .one()
    )
    closing = row[0]
    if closing is not None:
        closing = Decimal(str(closing))
    return closing, str(row[1])


def _raw_count_status(db, count_id: int) -> str:
    db.expire_all()
    return (
        db.connection()
        .execute(
            text("SELECT status FROM branch_shift_counts WHERE id = :cid"),
            {"cid": count_id},
        )
        .scalar()
    )


def _external_lines_for_count(count_id: int) -> int:
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT COUNT(*) FROM branch_shift_count_lines WHERE count_id = :cid"
                ),
                {"cid": count_id},
            ).scalar()
    finally:
        engine.dispose()


def _external_branch_shifts(branch_code: str) -> int:
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT COUNT(*) FROM branch_shifts bs "
                    "JOIN branches b ON b.id = bs.branch_id "
                    "WHERE b.branch_code = :code"
                ),
                {"code": branch_code},
            ).scalar()
    finally:
        engine.dispose()


def _assert_session_override_is_test_db(db):
    override = app.dependency_overrides[get_db]
    assert override() is db, "dependency_overrides[get_db] must return the test session object"


# ── G1–G8 + identity line ───────────────────────────────────────────────────


def test_t1b_guard_g1_g8_identity():
    _run_postgres_guard(TEST_ENGINE)
    with TEST_ENGINE.connect() as conn:
        db_name, user, rev = conn.execute(
            text(
                "SELECT current_database(), current_user, "
                "(SELECT version_num FROM alembic_version)"
            )
        ).one()
    assert db_name == EXPECTED_DB
    assert user == EXPECTED_USER
    assert rev == EXPECTED_ALEMBIC


# ── Pre-flight: TestClient transaction sharing (§2-1) ─────────────────────────


def test_t1b_preflight_testclient_transaction_sharing(db, client):
    suffix = uuid.uuid4().hex[:10]
    seed = _seed_opening_branch(db, suffix=suffix)
    hdr = _login(client, seed["username"])
    _assert_session_override_is_test_db(db)

    shift_id = _open_first_shift(client, hdr, seed["branch_id"])
    count_body = _create_opening_count(client, hdr, shift_id)
    count_id = count_body["id"]
    item_id = seed["item_id"]

    _patch_line(client, hdr, shift_id, item_id, closing=50.0)

    closing, status = _raw_line(db, count_id, item_id)
    assert closing == Decimal("50.00")
    assert status == "valid"

    internal_rows = (
        db.connection()
        .execute(
            text("SELECT COUNT(*) FROM branch_shift_count_lines WHERE count_id = :cid"),
            {"cid": count_id},
        )
        .scalar()
    )
    assert internal_rows >= 1, "(A) internal connection must see API-written rows"

    assert _external_lines_for_count(count_id) == 0, "(B) external connection must see zero rows"


# ── T1-b scenarios (independent data per test) ──────────────────────────────


def test_t1b_1_clear_saved_closing_becomes_null(db, client):
    suffix = uuid.uuid4().hex[:10]
    seed = _seed_opening_branch(db, suffix=suffix)
    hdr = _login(client, seed["username"])
    shift_id = _open_first_shift(client, hdr, seed["branch_id"])
    count_body = _create_opening_count(client, hdr, shift_id)
    count_id = count_body["id"]
    item_id = seed["item_id"]

    _patch_line(client, hdr, shift_id, item_id, closing=50.0)
    closing, status = _raw_line(db, count_id, item_id)
    assert closing == Decimal("50.00")
    assert status == "valid"

    _patch_line(client, hdr, shift_id, item_id, omit_closing_key=True)
    closing2, status2 = _raw_line(db, count_id, item_id)
    assert closing2 is None, f"expected NULL closing_balance, got {closing2!r}"
    assert status2 == "incomplete"
    assert _raw_count_status(db, count_id) == "draft"


def test_t1b_2_explicit_zero_stays_valid(db, client):
    suffix = uuid.uuid4().hex[:10]
    seed = _seed_opening_branch(db, suffix=suffix)
    hdr = _login(client, seed["username"])
    shift_id = _open_first_shift(client, hdr, seed["branch_id"])
    count_body = _create_opening_count(client, hdr, shift_id)
    count_id = count_body["id"]
    item_id = seed["item_id"]

    _patch_line(client, hdr, shift_id, item_id, closing=0.0)
    closing, status = _raw_line(db, count_id, item_id)
    assert closing == Decimal("0.00")
    assert status == "valid"


def test_t1b_3_submit_rejects_incomplete_after_clear(db, client):
    suffix = uuid.uuid4().hex[:10]
    seed = _seed_opening_branch(db, suffix=suffix)
    hdr = _login(client, seed["username"])
    shift_id = _open_first_shift(client, hdr, seed["branch_id"])
    count_body = _create_opening_count(client, hdr, shift_id)
    count_id = count_body["id"]
    item_id = seed["item_id"]

    _patch_line(client, hdr, shift_id, item_id, closing=50.0)
    _patch_line(client, hdr, shift_id, item_id, omit_closing_key=True)
    closing, status = _raw_line(db, count_id, item_id)
    assert closing is None
    assert status == "incomplete"

    submit = client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr)
    assert submit.status_code == 409, submit.text
    assert submit.json()["error_code"] == "SHIFT_COUNT_INCOMPLETE"
    assert _raw_count_status(db, count_id) == "draft"


def test_t1b_rollback_removes_data_externally(db, client):
    suffix = uuid.uuid4().hex[:10]
    branch_code = None
    with conftest._pg_test_session_scope() as (session, _conn, _trans, _state):
        seed = _seed_opening_branch(session, suffix=suffix)
        branch_code = seed["branch_code"]
        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app) as scoped_client:
            hdr = _login(scoped_client, seed["username"])
            shift_id = _open_first_shift(scoped_client, hdr, seed["branch_id"])
            _create_opening_count(scoped_client, hdr, shift_id)
            _patch_line(scoped_client, hdr, shift_id, seed["item_id"], closing=50.0)
        app.dependency_overrides.clear()

    assert branch_code is not None
    assert _external_branch_shifts(branch_code) == 0
