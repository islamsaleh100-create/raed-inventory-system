"""
Commit-style HTTP rollback proofs (R-1 / R-2) on a dedicated throwaway ``raed_sim_*`` database.

Isolated run (not the normal suite)::

    RAED_COMMIT_TEST_DB_URL=postgresql://…/raed_sim_… pytest tests/test_shift_ops_http_rollback.py --noconftest -p no:cacheprovider

This module is skipped during the normal ``pytest backend/tests`` collection on purpose
(``RAED_COMMIT_TEST_DB_URL`` unset or conftest already loaded).
For the isolated run, ``TEST_DATABASE_URL`` must be unset (the guard skips when it is set).
Does not use conftest db/client fixtures; does not set ``DATABASE_URL`` at import unless the skip guard passes.
"""
from __future__ import annotations

import os
import secrets
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterator
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

COMMIT_URL_ENV = "RAED_COMMIT_TEST_DB_URL"
API = "/api/v1/shift-ops"


def _parse_commit_url() -> str | None:
    return os.environ.get(COMMIT_URL_ENV)


def _validate_commit_url(url: str) -> str:
    u = make_url(url)
    host = (u.host or "").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(f"{COMMIT_URL_ENV} host must be local, got {host!r}")
    db = u.database or ""
    if not db.startswith("raed_sim_"):
        raise ValueError(f"{COMMIT_URL_ENV} database must start with raed_sim_, got {db!r}")
    forbidden = {
        "raed_inventory_test",
        "raed_sim_r2",
        "raed_sim_r3",
        "raed_sim_r4",
        "raed_sim_180",
        "raed_sim_completion_20251021",
    }
    if db in forbidden:
        raise ValueError(f"{COMMIT_URL_ENV} forbidden database {db!r}")
    return db


def _collection_skip_reason() -> str | None:
    if "app.main" in sys.modules:
        return "app already imported (conftest loaded) — commit HTTP tests NOT RUN"
    if os.environ.get("TEST_DATABASE_URL"):
        return "TEST_DATABASE_URL is set — run commit HTTP tests with --noconftest only"
    raw = _parse_commit_url()
    if not raw:
        return f"{COMMIT_URL_ENV} not set — R-1/R-2 NOT RUN"
    try:
        _validate_commit_url(raw)
    except ValueError as exc:
        return str(exc)
    return None


_skip = _collection_skip_reason()
if _skip:
    pytest.skip(_skip, allow_module_level=True)


def _mask_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.username or ''}:***@{p.hostname}:{p.port}{p.path}"


@dataclass
class CommitStack:
    commit_url: str
    expected_db: str
    run_password: str
    fresh_engine: Any
    seed_local: Any
    app: Any
    settings: Any
    app_database: Any
    get_db: Any
    get_password_hash: Any
    models: Any
    branch_shift_ops: Any
    sdv: Any
    TestClient: Any


@pytest.fixture(scope="session")
def commit_stack() -> Iterator[CommitStack]:
    commit_url = _parse_commit_url()
    assert commit_url
    expected_db = _validate_commit_url(commit_url)
    run_password = secrets.token_urlsafe(24)
    secret_key = secrets.token_urlsafe(48)
    os.environ.pop("TEST_DATABASE_URL", None)
    os.environ["DATABASE_URL"] = commit_url
    os.environ["ENVIRONMENT"] = "local"
    os.environ["SECRET_KEY"] = secret_key
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["AUDIT_LOG_ENABLED"] = "true"
    os.environ["SHIFT_CASH_ENABLED"] = "true"
    os.environ["MULTI_TENANT_ENABLED"] = "False"
    os.environ["SHIFT_DATE_VALIDATION_ENABLED"] = "true"
    os.environ.setdefault("ENV_FILE", ".env.test")

    from app.config import settings  # noqa: WPS433
    import app.database as app_database  # noqa: WPS433
    from app.core.security import get_password_hash  # noqa: WPS433
    from app.database import get_db  # noqa: WPS433
    from app.main import app  # noqa: WPS433
    from app.models import (  # noqa: WPS433
        Branch as BranchModel,
        BranchBrand as BranchBrandModel,
        Brand as BrandModel,
        BrandShiftCountItem as BrandShiftCountItemModel,
        Item as ItemModel,
        ItemBrand as ItemBrandModel,
        ItemCategory as ItemCategoryModel,
        Role as RoleModel,
        RoleName as RoleNameEnum,
        UnitOfMeasure as UnitOfMeasureModel,
        User as UserModel,
        UserRole as UserRoleModel,
        Warehouse as WarehouseModel,
    )
    from app.models import branch_shift_ops  # noqa: WPS433
    from app.models.branch_shift_ops import BranchShiftConfig as BranchShiftConfigModel  # noqa: WPS433
    from app.services import shift_ops_date_validation as sdv  # noqa: WPS433
    from fastapi.testclient import TestClient  # noqa: WPS433

    fresh_engine = create_engine(commit_url, pool_pre_ping=True)
    seed_local = sessionmaker(bind=fresh_engine)

    class _Models:
        Branch = BranchModel
        BranchBrand = BranchBrandModel
        Brand = BrandModel
        BrandShiftCountItem = BrandShiftCountItemModel
        BranchShiftConfig = BranchShiftConfigModel
        Item = ItemModel
        ItemBrand = ItemBrandModel
        ItemCategory = ItemCategoryModel
        Role = RoleModel
        RoleName = RoleNameEnum
        UnitOfMeasure = UnitOfMeasureModel
        User = UserModel
        UserRole = UserRoleModel
        Warehouse = WarehouseModel

    stack = CommitStack(
        commit_url=commit_url,
        expected_db=expected_db,
        run_password=run_password,
        fresh_engine=fresh_engine,
        seed_local=seed_local,
        app=app,
        settings=settings,
        app_database=app_database,
        get_db=get_db,
        get_password_hash=get_password_hash,
        models=_Models,
        branch_shift_ops=branch_shift_ops,
        sdv=sdv,
        TestClient=TestClient,
    )
    yield stack
    fresh_engine.dispose()


def _fresh_one(stack: CommitStack, sql: str, **params: Any):
    with stack.fresh_engine.connect() as conn:
        return conn.execute(text(sql), params).one()


def _request_path_db(stack: CommitStack) -> tuple[str, Any]:
    """Same session factory path as HTTP get_db (per-request SessionLocal)."""
    db = stack.app_database.SessionLocal()
    try:
        return db.execute(text("SELECT current_database(), inet_server_port()")).one()
    finally:
        db.close()


def assert_http_database_isolation(stack: CommitStack) -> dict[str, Any]:
    app_db = make_url(stack.settings.DATABASE_URL).database
    engine_db = stack.app_database.engine.url.database
    if app_db != stack.expected_db or engine_db != stack.expected_db:
        raise AssertionError(
            f"DATABASE mismatch: settings={app_db!r} engine={engine_db!r} expected={stack.expected_db!r}"
        )
    if stack.get_db in stack.app.dependency_overrides:
        raise AssertionError("get_db must not be overridden for HTTP isolation proof")
    req_db, req_port = _request_path_db(stack)
    with stack.fresh_engine.connect() as conn:
        port, dbname = conn.execute(
            text("SELECT inet_server_port(), current_database()")
        ).one()
    if str(dbname) != stack.expected_db or str(req_db) != stack.expected_db:
        raise AssertionError(
            f"request/fresh mismatch: request_db={req_db!r} fresh={dbname!r} expected={stack.expected_db!r}"
        )
    return {
        "commit_url_masked": _mask_url(stack.commit_url),
        "settings_db": app_db,
        "engine_db": engine_db,
        "request_path_db": req_db,
        "request_path_port": req_port,
        "fresh_read_db": dbname,
        "fresh_read_port": port,
        "get_db_overridden": False,
    }


def _suffix_row_counts(stack: CommitStack, tag: str) -> dict[str, int]:
    bp = f"HR-{tag}%"
    up = f"hr_{tag}_%"
    with stack.fresh_engine.connect() as conn:
        return {
            "users": conn.execute(
                text("SELECT COUNT(*) FROM users WHERE username LIKE :up"), {"up": up}
            ).scalar(),
            "branches": conn.execute(
                text("SELECT COUNT(*) FROM branches WHERE branch_code LIKE :bp"), {"bp": bp}
            ).scalar(),
            "branch_shifts": conn.execute(
                text(
                    "SELECT COUNT(*) FROM branch_shifts WHERE branch_id IN "
                    "(SELECT id FROM branches WHERE branch_code LIKE :bp)"
                ),
                {"bp": bp},
            ).scalar(),
        }


def _login(stack: CommitStack, client: Any, username: str) -> dict[str, str]:
    r = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": stack.run_password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_branch(stack: CommitStack, *, tag: str, shifts: tuple[int, ...] = (1, 2)) -> dict[str, Any]:
    M = stack.models
    s = stack.seed_local()
    pwd = stack.run_password
    try:
        wh = M.Warehouse(
            warehouse_code=f"HR-{tag}-WH",
            warehouse_name="WH",
            location="Riyadh",
            active=True,
        )
        s.add(wh)
        s.flush()
        branch = M.Branch(
            branch_code=f"HR-{tag}-B1",
            branch_name="HTTP Rollback Branch",
            city="Riyadh",
            area="Olaya",
            warehouse_id=wh.id,
        )
        s.add(branch)
        s.flush()
        brand = M.Brand(name=f"HR {tag}", active=True)
        s.add(brand)
        s.flush()
        s.add(M.BranchBrand(branch_id=branch.id, brand_id=brand.id))
        cat = M.ItemCategory(code=f"HR-{tag}-C", name_ar="f", name_en="c")
        unit = M.UnitOfMeasure(code=f"HR-{tag}-U", name_ar="u", name_en="u")
        s.add(cat)
        s.add(unit)
        s.flush()
        item_ids: list[int] = []
        for i in range(2):
            item = M.Item(
                item_code=f"HR-{tag}-I{i}",
                item_name_ar=f"i{i}",
                item_name_en=f"i{i}",
                category_id=cat.id,
                unit_id=unit.id,
                active=True,
                is_deleted=False,
            )
            s.add(item)
            s.flush()
            item_ids.append(item.id)
            s.add(M.ItemBrand(item_id=item.id, brand_id=brand.id))
            s.add(
                M.BrandShiftCountItem(
                    brand_id=brand.id,
                    item_id=item.id,
                    display_order=i + 1,
                    is_active=True,
                )
            )
        for n in shifts:
            s.add(
                M.BranchShiftConfig(
                    branch_id=branch.id,
                    shift_number=n,
                    shift_name_ar=f"s{n}",
                    is_active=True,
                    effective_from=date(2020, 1, 1),
                )
            )

        def role(name: M.RoleName) -> M.Role:
            row = s.query(M.Role).filter(M.Role.name == name).first()
            if not row:
                row = M.Role(name=name, display_name=name.value, description="")
                s.add(row)
                s.flush()
            return row

        def mk(u: str, rn: M.RoleName, bid: int | None = None) -> M.User:
            r = role(rn)
            user = M.User(
                username=u,
                email=f"{u}@example.com",
                full_name=u,
                hashed_password=stack.get_password_hash(pwd),
                branch_id=bid,
                status="active",
                is_deleted=False,
            )
            s.add(user)
            s.flush()
            s.add(M.UserRole(user_id=user.id, role_id=r.id))
            s.flush()
            return user

        bm = mk(f"hr_{tag}_bm", M.RoleName.branch_manager, branch.id)
        admin = mk(f"hr_{tag}_admin", M.RoleName.admin)
        s.commit()
        return {
            "tag": tag,
            "branch_id": branch.id,
            "item_ids": item_ids,
            "bm": bm.username,
            "admin": admin.username,
        }
    finally:
        s.close()


def _cleanup_seed(stack: CommitStack, tag: str) -> None:
    bp = f"HR-{tag}%"
    up = f"hr_{tag}_%"
    stmts = [
        "DELETE FROM audit_logs WHERE user_id IN (SELECT id FROM users WHERE username LIKE :up)",
        "DELETE FROM audit_logs WHERE entity_id IN (SELECT id FROM branch_shift_counts WHERE shift_id IN (SELECT id FROM branch_shifts WHERE branch_id IN (SELECT id FROM branches WHERE branch_code LIKE :bp)))",
        "DELETE FROM audit_logs WHERE entity_id IN (SELECT id FROM branch_shifts WHERE branch_id IN (SELECT id FROM branches WHERE branch_code LIKE :bp))",
        "DELETE FROM branch_shift_count_lines WHERE count_id IN (SELECT id FROM branch_shift_counts WHERE shift_id IN (SELECT id FROM branch_shifts WHERE branch_id IN (SELECT id FROM branches WHERE branch_code LIKE :bp)))",
        "DELETE FROM branch_shift_counts WHERE shift_id IN (SELECT id FROM branch_shifts WHERE branch_id IN (SELECT id FROM branches WHERE branch_code LIKE :bp))",
        "DELETE FROM branch_shift_cash WHERE shift_id IN (SELECT id FROM branch_shifts WHERE branch_id IN (SELECT id FROM branches WHERE branch_code LIKE :bp))",
        "DELETE FROM branch_shift_reopen_events WHERE shift_id IN (SELECT id FROM branch_shifts WHERE branch_id IN (SELECT id FROM branches WHERE branch_code LIKE :bp))",
        "DELETE FROM branch_shifts WHERE branch_id IN (SELECT id FROM branches WHERE branch_code LIKE :bp)",
        "DELETE FROM branch_shift_configs WHERE branch_id IN (SELECT id FROM branches WHERE branch_code LIKE :bp)",
        "DELETE FROM branch_brands WHERE branch_id IN (SELECT id FROM branches WHERE branch_code LIKE :bp)",
        "DELETE FROM brand_shift_count_items WHERE brand_id IN (SELECT id FROM brands WHERE name LIKE :bn)",
        "DELETE FROM item_brands WHERE item_id IN (SELECT id FROM items WHERE item_code LIKE :ic)",
        "DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users WHERE username LIKE :up)",
        "DELETE FROM users WHERE username LIKE :up",
        "DELETE FROM branches WHERE branch_code LIKE :bp",
        "DELETE FROM items WHERE item_code LIKE :ic",
        "DELETE FROM brands WHERE name LIKE :bn",
        "DELETE FROM warehouses WHERE warehouse_code LIKE :wp",
        "DELETE FROM item_categories WHERE code LIKE :cc",
        "DELETE FROM units WHERE code LIKE :uc",
    ]
    params = {
        "bp": bp,
        "up": up,
        "bn": f"HR {tag}%",
        "ic": f"HR-{tag}%",
        "wp": f"HR-{tag}%",
        "cc": f"HR-{tag}%",
        "uc": f"HR-{tag}%",
    }
    with stack.fresh_engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql), params)


@pytest.fixture(scope="module")
def isolation_proof(commit_stack: CommitStack) -> dict[str, Any]:
    return assert_http_database_isolation(commit_stack)


@pytest.fixture
def client(commit_stack: CommitStack, isolation_proof: dict[str, Any]) -> Iterator[Any]:
    assert isolation_proof["request_path_db"] == commit_stack.expected_db
    commit_stack.sdv.shift_open_today = lambda: date(2026, 8, 15)
    with commit_stack.TestClient(commit_stack.app, raise_server_exceptions=False) as c:
        yield c


def test_r1_open_override_rollback_after_lock_audit(
    commit_stack: CommitStack, client: Any, monkeypatch: pytest.MonkeyPatch
):
    BranchShift = commit_stack.branch_shift_ops.BranchShift
    BranchShiftStatus = commit_stack.branch_shift_ops.BranchShiftStatus
    tag = uuid.uuid4().hex[:8]
    before = _suffix_row_counts(commit_stack, tag)
    seed = _seed_branch(commit_stack, tag=tag)
    try:
        bhdr = _login(commit_stack, client, seed["bm"])
        first = client.post(
            f"{API}/shifts",
            json={"shift_date": "2026-08-14", "shift_number": 1},
            headers=bhdr,
        )
        assert first.status_code == 201, first.text
        first_id = first.json()["id"]

        _orig_flush = Session.flush

        def _flush_fail(self, objects=None):
            for obj in self.new:
                if isinstance(obj, BranchShift):
                    raise RuntimeError("forced HTTP open failure after override lock")
            return _orig_flush(self, objects)

        monkeypatch.setattr(Session, "flush", _flush_fail)
        adhdr = _login(commit_stack, client, seed["admin"])
        fail = client.post(
            f"{API}/shifts",
            json={
                "branch_id": seed["branch_id"],
                "shift_date": "2026-08-15",
                "shift_number": 2,
                "override": True,
                "override_reason": "Lock previous shift",
            },
            headers=adhdr,
        )
        assert fail.status_code >= 400

        st, audits, cnt = _fresh_one(
            commit_stack,
            "SELECT (SELECT status FROM branch_shifts WHERE id = :id), "
            "(SELECT COUNT(*) FROM audit_logs WHERE action='shift_open_override_lock_previous' AND entity_id=:id), "
            "(SELECT COUNT(*) FROM branch_shifts WHERE branch_id=:b AND shift_date='2026-08-15' AND shift_number=2)",
            id=first_id,
            b=seed["branch_id"],
        )
        assert st == BranchShiftStatus.draft.value
        assert audits == 0
        assert cnt == 0

        monkeypatch.undo()
        ok = client.post(
            f"{API}/shifts",
            json={
                "branch_id": seed["branch_id"],
                "shift_date": "2026-08-15",
                "shift_number": 2,
                "override": True,
                "override_reason": "Lock previous shift",
            },
            headers=adhdr,
        )
        assert ok.status_code == 201, ok.text
        st2, audits2, cnt2 = _fresh_one(
            commit_stack,
            "SELECT (SELECT status FROM branch_shifts WHERE id = :id), "
            "(SELECT COUNT(*) FROM audit_logs WHERE action='shift_open_override_lock_previous' AND entity_id=:id), "
            "(SELECT COUNT(*) FROM branch_shifts WHERE branch_id=:b AND shift_date='2026-08-15' AND shift_number=2)",
            id=first_id,
            b=seed["branch_id"],
        )
        assert st2 == BranchShiftStatus.exception_locked.value
        assert audits2 == 1
        assert cnt2 == 1
    finally:
        _cleanup_seed(commit_stack, tag)
        after = _suffix_row_counts(commit_stack, tag)
        assert after == before == {"users": 0, "branches": 0, "branch_shifts": 0}


def _fill_and_submit_cash(client: Any, hdr: dict, shift_id: int) -> None:
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


def _fill_and_submit_count(client: Any, hdr: dict, shift_id: int, closing: float = 10.0) -> None:
    created = client.post(f"{API}/shifts/{shift_id}/count", headers=hdr)
    assert created.status_code in (200, 201), created.text
    body = client.get(f"{API}/shifts/{shift_id}/count", headers=hdr).json()
    lines = [
        {
            "item_id": ln["item_id"],
            "received_qty": 0,
            "returned_qty": 0,
            "damaged_qty": 0,
            "closing_balance": closing,
        }
        for ln in body["lines"]
    ]
    assert client.patch(f"{API}/shifts/{shift_id}/count/lines", json={"lines": lines}, headers=hdr).status_code == 200
    assert client.post(f"{API}/shifts/{shift_id}/count/submit", headers=hdr).status_code == 200


def test_r2_submit_opening_refresh_audit_failure_and_audit_required(
    commit_stack: CommitStack, client: Any, monkeypatch: pytest.MonkeyPatch
):
    ShiftSectionStatus = commit_stack.branch_shift_ops.ShiftSectionStatus
    tag = uuid.uuid4().hex[:8]
    before = _suffix_row_counts(commit_stack, tag)
    seed = _seed_branch(commit_stack, tag=tag, shifts=(1,))
    item0 = seed["item_ids"][0]
    commit_stack.sdv.shift_open_today = lambda: date(2026, 8, 15)
    day_n, day_n1 = "2026-08-14", "2026-08-15"
    try:
        bhdr = _login(commit_stack, client, seed["bm"])
        ahdr = _login(commit_stack, client, seed["admin"])
        n_open = client.post(
            f"{API}/shifts",
            json={"shift_date": day_n, "shift_number": 1},
            headers=bhdr,
        )
        assert n_open.status_code == 201, n_open.text
        n_id = n_open.json()["id"]
        _fill_and_submit_count(client, bhdr, n_id, closing=10.0)
        _fill_and_submit_cash(client, bhdr, n_id)
        n1_resp = client.post(
            f"{API}/shifts",
            json={"shift_date": day_n1, "shift_number": 1},
            headers=bhdr,
        )
        assert n1_resp.status_code == 201
        n1_id = n1_resp.json()["id"]
        client.post(f"{API}/shifts/{n1_id}/count", headers=bhdr)
        n1_before = client.get(f"{API}/shifts/{n1_id}/count", headers=bhdr).json()
        opening_before = next(ln for ln in n1_before["lines"] if ln["item_id"] == item0)["opening_balance"]

        assert client.post(
            f"{API}/shifts/{n_id}/reopen",
            json={"target": "count", "reason": "تصحيح"},
            headers=ahdr,
        ).status_code == 200

        n_count = client.get(f"{API}/shifts/{n_id}/count", headers=bhdr).json()
        lines = []
        for ln in n_count["lines"]:
            closing = 22.0 if ln["item_id"] == item0 else float(ln["opening_balance"])
            row = {
                "item_id": ln["item_id"],
                "received_qty": 12.0 if ln["item_id"] == item0 else 0,
                "returned_qty": 0,
                "damaged_qty": 0,
                "closing_balance": closing,
            }
            lines.append(row)
        assert client.patch(f"{API}/shifts/{n_id}/count/lines", json={"lines": lines}, headers=bhdr).status_code == 200

        def _boom(*_a, **_k):
            raise RuntimeError("forced audit failure")

        monkeypatch.setattr("app.services.audit_service.log_strict", _boom)
        fail = client.post(f"{API}/shifts/{n_id}/count/submit", headers=bhdr)
        assert fail.status_code == 500
        assert fail.json()["error_code"] == "OPENING_REFRESH_AUDIT_FAILED"

        n_status, refresh_audits, n1_open = _fresh_one(
            commit_stack,
            "SELECT (SELECT status FROM branch_shift_counts WHERE shift_id=:nid), "
            "(SELECT COUNT(*) FROM audit_logs WHERE action='count_openings_refreshed' AND entity_id IN "
            "(SELECT id FROM branch_shift_counts WHERE shift_id=:n1id)), "
            "(SELECT opening_balance FROM branch_shift_count_lines WHERE item_id=:item LIMIT 1)",
            nid=n_id,
            n1id=n1_id,
            item=item0,
        )
        assert n_status == ShiftSectionStatus.draft.value
        assert refresh_audits == 0
        assert Decimal(str(n1_open)) == Decimal(str(opening_before))

        monkeypatch.undo()
        monkeypatch.setenv("AUDIT_LOG_ENABLED", "false")
        blocked = client.post(f"{API}/shifts/{n_id}/count/submit", headers=bhdr)
        assert blocked.status_code == 409
        assert blocked.json()["error_code"] == "AUDIT_REQUIRED_FOR_OPENING_REFRESH"

        monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")
        ok = client.post(f"{API}/shifts/{n_id}/count/submit", headers=bhdr)
        assert ok.status_code == 200, ok.text
        n1_after = _fresh_one(
            commit_stack,
            "SELECT opening_balance FROM branch_shift_count_lines WHERE item_id=:item "
            "AND count_id IN (SELECT id FROM branch_shift_counts WHERE shift_id=:n1id)",
            item=item0,
            n1id=n1_id,
        )
        assert Decimal(str(n1_after[0])) == Decimal("22.00")
    finally:
        _cleanup_seed(commit_stack, tag)
        after = _suffix_row_counts(commit_stack, tag)
        assert after == before == {"users": 0, "branches": 0, "branch_shifts": 0}
