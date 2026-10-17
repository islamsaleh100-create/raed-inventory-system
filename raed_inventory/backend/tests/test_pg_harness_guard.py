"""
PostgreSQL test harness guard proofs (GF) and rollback isolation (R1/R2).

Collected via pytest tests/ (python_files = test_*.py).
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: E402
from app.database import Base
from conftest import (  # noqa: E402
    EXPECTED_ALEMBIC,
    EXPECTED_DB,
    EXPECTED_USER,
    PostgresTestGuardError,
    USE_POSTGRES,
    _assert_test_database,
    _external_warehouse_count,
    _pg_test_session_scope,
    _prepare_schema,
    _run_postgres_guard,
)

_PG_TEST_URL = (
    "postgresql://raed_inventory_test_runner:pw@127.0.0.1:5432/raed_inventory_test"
)


def _gf_ok_kwargs(**overrides):
    base = dict(
        db_name=EXPECTED_DB,
        current_user=EXPECTED_USER,
        server_addr="127.0.0.1",
        url_host="127.0.0.1",
        alembic_rev=EXPECTED_ALEMBIC,
        test_url="postgresql://u:p@127.0.0.1:5432/raed_inventory_test",
        settings_url="postgresql://u:p@127.0.0.1:5432/raed_inventory_test",
        app_engine_url="postgresql://u:p@127.0.0.1:5432/raed_inventory_test",
        postgres_path_requested=True,
    )
    base.update(overrides)
    return base


# ── GF1–GF10 (pure guard) ───────────────────────────────────────────────────


def test_gf1_rejects_wrong_db():
    with pytest.raises(PostgresTestGuardError):
        _assert_test_database(**_gf_ok_kwargs(db_name="raed_inventory"))


def test_gf2_rejects_similar_db_name():
    with pytest.raises(PostgresTestGuardError):
        _assert_test_database(**_gf_ok_kwargs(db_name="raed_inventory_test2"))


def test_gf3_rejects_railway_host():
    with pytest.raises(PostgresTestGuardError):
        _assert_test_database(**_gf_ok_kwargs(url_host="foo.railway.app"))


def test_gf4_rejects_remote_server_addr():
    with pytest.raises(PostgresTestGuardError):
        _assert_test_database(**_gf_ok_kwargs(server_addr="10.0.0.5"))


def test_gf5_rejects_wrong_alembic():
    with pytest.raises(PostgresTestGuardError):
        _assert_test_database(**_gf_ok_kwargs(alembic_rev="deadbeef"))


def test_gf6_rejects_missing_test_url_when_postgres():
    with pytest.raises(PostgresTestGuardError):
        _assert_test_database(**_gf_ok_kwargs(test_url=None))


def test_gf7_accepts_all_valid():
    _assert_test_database(**_gf_ok_kwargs())


def test_gf8_rejects_wrong_user():
    with pytest.raises(PostgresTestGuardError):
        _assert_test_database(**_gf_ok_kwargs(current_user="raed_user"))


def test_gf9_rejects_url_mismatch():
    with pytest.raises(PostgresTestGuardError):
        _assert_test_database(
            **_gf_ok_kwargs(settings_url="postgresql://u:p@127.0.0.1:5432/other")
        )


def test_gf10_rejects_engine_mismatch():
    with pytest.raises(PostgresTestGuardError):
        _assert_test_database(
            **_gf_ok_kwargs(app_engine_url="postgresql://u:p@127.0.0.1:5432/wrong")
        )


# ── 2-α · _run_postgres_guard with stub engine ──────────────────────────────


def _make_stub_engine(
    *,
    db_name: str = EXPECTED_DB,
    current_user: str = EXPECTED_USER,
    server_addr: str = "127.0.0.1",
    alembic_rev: str = EXPECTED_ALEMBIC,
    branch_shift_lines_reg: Optional[str] = "public.branch_shift_count_lines",
) -> MagicMock:
    class _RowResult:
        def __init__(self, value):
            self._value = value

        def one(self):
            return self._value

        def scalar(self):
            return self._value

    class _StubConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if "current_database()" in sql:
                return _RowResult((db_name, current_user, server_addr, 5432))
            if "alembic_version" in sql:
                return _RowResult(alembic_rev)
            if "branch_shift_count_lines" in sql:
                return _RowResult(branch_shift_lines_reg)
            raise AssertionError(f"unexpected SQL in stub: {sql}")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    engine = MagicMock()
    engine.connect.return_value = _StubConn()
    return engine


@pytest.mark.parametrize(
    "stub_kwargs",
    [
        {"db_name": "raed_inventory"},
        {"current_user": "postgres"},
        {"alembic_rev": "deadbeef"},
        {"server_addr": "10.0.0.5"},
        {"branch_shift_lines_reg": None},
    ],
    ids=["wrong_db", "wrong_user", "wrong_alembic", "remote_addr", "missing_table"],
)
def test_run_postgres_guard_rejects(stub_kwargs, monkeypatch):
    create_all = MagicMock()
    drop_all = MagicMock()
    monkeypatch.setattr(Base.metadata, "create_all", create_all)
    monkeypatch.setattr(Base.metadata, "drop_all", drop_all)
    monkeypatch.setattr(conftest, "TEST_DATABASE_URL", _PG_TEST_URL)
    monkeypatch.setattr(conftest.settings, "DATABASE_URL", _PG_TEST_URL)
    monkeypatch.setattr(conftest.app_database.engine, "url", _PG_TEST_URL)

    stub = _make_stub_engine(**stub_kwargs)
    with pytest.raises(PostgresTestGuardError):
        _run_postgres_guard(stub)

    create_all.assert_not_called()
    drop_all.assert_not_called()


# ── 2-β · _prepare_schema wiring (no real DB) ───────────────────────────────


def test_prepare_schema_postgres_invokes_guard(monkeypatch):
    guard = MagicMock()
    monkeypatch.setattr(conftest, "_run_postgres_guard", guard)
    stub_engine = MagicMock()
    _prepare_schema(stub_engine, use_postgres=True)
    guard.assert_called_once_with(stub_engine)


def test_prepare_schema_sqlite_calls_create_all(monkeypatch):
    guard = MagicMock()
    create_all = MagicMock()
    monkeypatch.setattr(conftest, "_run_postgres_guard", guard)
    monkeypatch.setattr(Base.metadata, "create_all", create_all)
    stub_engine = MagicMock()
    _prepare_schema(stub_engine, use_postgres=False)
    guard.assert_not_called()
    create_all.assert_called_once_with(bind=stub_engine)


# ── R1 / R2 (PostgreSQL integration) ────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.skipif(not USE_POSTGRES, reason="PostgreSQL test path only")
def test_r1_service_commit_not_visible_externally():
    from app.models import Warehouse

    code = f"PG-R1-{uuid.uuid4().hex[:12]}"
    with _pg_test_session_scope() as (session, _connection, _transaction, _scope_state):
        wh = Warehouse(
            warehouse_code=code,
            warehouse_name="R1 isolation",
            location="test",
            active=True,
        )
        session.add(wh)
        session.commit()
        assert session.query(Warehouse).filter(Warehouse.warehouse_code == code).count() == 1
        assert _external_warehouse_count(code) == 0

    assert _external_warehouse_count(code) == 0


@pytest.mark.integration
@pytest.mark.skipif(not USE_POSTGRES, reason="PostgreSQL test path only")
def test_r2_two_scopes_same_unique_code_succeeds():
    from app.models import Warehouse

    code = f"PG-R2-{uuid.uuid4().hex[:12]}"
    xact_ids: list[Any] = []

    with _pg_test_session_scope() as (session, connection, _transaction, scope_state):
        xact_ids.append(connection.execute(text("SELECT pg_current_xact_id()")).scalar())
        session.add(
            Warehouse(
                warehouse_code=code,
                warehouse_name="R2 first",
                location="test",
                active=True,
            )
        )
        session.commit()

    assert scope_state["transaction_active_after_teardown"] is False
    assert _external_warehouse_count(code) == 0

    with _pg_test_session_scope() as (session, connection, _transaction, scope_state2):
        xact_ids.append(connection.execute(text("SELECT pg_current_xact_id()")).scalar())
        session.add(
            Warehouse(
                warehouse_code=code,
                warehouse_name="R2 second",
                location="test",
                active=True,
            )
        )
        session.commit()

    assert scope_state2["transaction_active_after_teardown"] is False
    assert len(xact_ids) == 2
    assert xact_ids[0] != xact_ids[1]
