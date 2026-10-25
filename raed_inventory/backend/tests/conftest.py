"""
Shared pytest fixtures for all test suites.

PostgreSQL path: set TEST_DATABASE_URL (and DATABASE_URL to the same value) before pytest.
SQLite path: default in-memory behavior unchanged when TEST_DATABASE_URL is unset.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# ── Environment before app imports ───────────────────────────────────────────
os.environ.setdefault("ENV_FILE", ".env.test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-minimum!!")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MULTI_TENANT_ENABLED", "False")
os.environ.setdefault("AUDIT_LOG_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
USE_POSTGRES = bool(TEST_DATABASE_URL)

if USE_POSTGRES:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
else:
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.config import settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
import app.database as app_database  # noqa: E402
from app.main import app  # noqa: E402

EXPECTED_ALEMBIC = "a1b2c3d4e5f7"
EXPECTED_DB = "raed_inventory_test"
EXPECTED_USER = "raed_inventory_test_runner"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class PostgresTestGuardError(Exception):
    """Raised when PostgreSQL test guard rejects the environment."""


def _mask_url(url: str) -> str:
    p = urlparse(url)
    host = p.hostname or ""
    user = p.username or ""
    return f"{p.scheme}://{user}:***@{host}:{p.port or ''}{p.path or ''}"


def _urls_equivalent(a: str, b: str) -> bool:
    from sqlalchemy.engine import make_url

    ua = make_url(a)
    ub = make_url(b)
    return (
        ua.drivername == ub.drivername
        and ua.username == ub.username
        and (ua.host or "") == (ub.host or "")
        and ua.port == ub.port
        and (ua.database or "") == (ub.database or "")
    )


def _assert_test_database(
    *,
    db_name: str,
    current_user: str,
    server_addr: Optional[str],
    url_host: str,
    alembic_rev: Optional[str],
    test_url: Optional[str],
    settings_url: str,
    app_engine_url: str,
    postgres_path_requested: bool,
) -> None:
    """Pure guard (G1–G8). Raises PostgresTestGuardError — no DB side effects."""
    if db_name != EXPECTED_DB:
        raise PostgresTestGuardError(f"G1 database name {db_name!r}")
    if url_host not in LOCAL_HOSTS:
        raise PostgresTestGuardError(f"G2 host {url_host!r}")
    low = url_host.lower()
    if any(x in low for x in ("railway", "rlwy", "proxy.")):
        raise PostgresTestGuardError("G2 remote host pattern")
    if server_addr is not None and str(server_addr) != "":
        addr_norm = str(server_addr).split("/")[0]
        if addr_norm not in LOCAL_HOSTS:
            raise PostgresTestGuardError(f"G2 server_addr {server_addr!r}")
    if postgres_path_requested and not test_url:
        raise PostgresTestGuardError("G3 TEST_DATABASE_URL missing")
    if alembic_rev != EXPECTED_ALEMBIC:
        raise PostgresTestGuardError(f"G4 alembic {alembic_rev!r}")
    if current_user != EXPECTED_USER:
        raise PostgresTestGuardError(f"G6 user {current_user!r}")
    if test_url and not _urls_equivalent(test_url, settings_url):
        raise PostgresTestGuardError("G7 TEST_DATABASE_URL != settings.DATABASE_URL")
    if test_url and not _urls_equivalent(app_engine_url, test_url):
        raise PostgresTestGuardError("G8 engine url mismatch")


def _run_postgres_guard(engine) -> None:
    with engine.connect() as conn:
        db_name, user, addr, port = conn.execute(
            text(
                "SELECT current_database(), current_user, "
                "inet_server_addr()::text, inet_server_port()"
            )
        ).one()
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        reg = conn.execute(text("SELECT to_regclass('public.branch_shift_count_lines')")).scalar()
        if reg is None:
            raise PostgresTestGuardError("branch_shift_count_lines missing")
    host = urlparse(TEST_DATABASE_URL or "").hostname or ""
    _assert_test_database(
        db_name=db_name,
        current_user=user,
        server_addr=addr,
        url_host=host,
        alembic_rev=rev,
        test_url=TEST_DATABASE_URL,
        settings_url=settings.DATABASE_URL,
        app_engine_url=str(app_database.engine.url),
        postgres_path_requested=True,
    )


def _prepare_schema(engine, use_postgres: bool) -> None:
    """Session schema setup: PostgreSQL guard only, or SQLite create_all."""
    if use_postgres:
        _run_postgres_guard(engine)
    else:
        Base.metadata.create_all(bind=engine)


def _external_warehouse_count(code: str) -> int:
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT COUNT(*) FROM warehouses WHERE warehouse_code = :c"),
                {"c": code},
            ).scalar()
    finally:
        engine.dispose()


@contextmanager
def _pg_test_session_scope() -> Iterator[tuple[Session, Any, Any, dict[str, bool]]]:
    """PostgreSQL: outer transaction + SAVEPOINT + SessionLocal patch; rollback on exit."""
    connection = TEST_ENGINE.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    orig_session_local = app_database.SessionLocal

    def _session_factory():
        return session

    app_database.SessionLocal = _session_factory  # type: ignore[assignment]
    scope_state: dict[str, bool] = {"transaction_active_after_teardown": True}
    try:
        yield session, connection, transaction, scope_state
    finally:
        app_database.SessionLocal = orig_session_local
        session.close()
        if transaction.is_active:
            transaction.rollback()
        scope_state["transaction_active_after_teardown"] = transaction.is_active
        connection.close()


if USE_POSTGRES:
    TEST_ENGINE = create_engine(TEST_DATABASE_URL)
    app_database.engine.dispose()
    app_database.engine = TEST_ENGINE
    app_database.SessionLocal.configure(bind=TEST_ENGINE)
else:
    TEST_ENGINE = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """SQLite: create/drop schema. PostgreSQL: guard + verify Alembic schema only."""
    _prepare_schema(TEST_ENGINE, USE_POSTGRES)
    yield
    if not USE_POSTGRES:
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def db(create_tables):
    """DB session; PostgreSQL uses outer transaction + SAVEPOINT for service commits."""
    if not USE_POSTGRES:
        connection = TEST_ENGINE.connect()
        transaction = connection.begin()
        session = TestingSessionLocal(bind=connection)
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
            connection.close()
        return

    with _pg_test_session_scope() as (session, _connection, _transaction, _scope_state):
        yield session


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient with DB bound to the test transaction."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client_session(create_tables):
    """Session-scoped client — SQLite only (PostgreSQL uses function-scoped isolation)."""
    if USE_POSTGRES:
        pytest.skip("client_session not supported on PostgreSQL test path")
    session = TestingSessionLocal()
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    session.close()
    app.dependency_overrides.clear()


_LEGACY_SHIFT_DATE_TEST_MODULE_SUFFIXES = (
    ".test_shift_ops_api",
    ".test_shift_ops_sequencing",
    ".test_shift_ops_gaps",
    ".test_shift_ops_opening_refresh",
    ".test_shift_ops_defer_cash",
    ".test_shift_ops_reopen_audit_fix",
    ".test_shift_ops_read_roles",
    ".test_shift_ops_isolation",
    ".test_shift_ops_list_scope",
    ".test_brand_count_items_admin",
    ".test_t1b_closing_clear",
)


@pytest.fixture(autouse=True)
def _legacy_shift_date_validation_opt_out(request, monkeypatch):
    """Disable D1/D2/D3 only for legacy modules with fixed historic shift_date values."""
    mod = getattr(request.node, "module", None)
    name = getattr(mod, "__name__", "")
    if not name.endswith(_LEGACY_SHIFT_DATE_TEST_MODULE_SUFFIXES):
        return

    prior_enabled = settings.SHIFT_DATE_VALIDATION_ENABLED
    settings.SHIFT_DATE_VALIDATION_ENABLED = False

    def _restore_shift_date_validation_flag() -> None:
        settings.SHIFT_DATE_VALIDATION_ENABLED = prior_enabled

    request.addfinalizer(_restore_shift_date_validation_flag)

    original_undo = monkeypatch.undo

    def undo_preserve_legacy_shift_date_opt_out() -> None:
        original_undo()
        settings.SHIFT_DATE_VALIDATION_ENABLED = False

    monkeypatch.undo = undo_preserve_legacy_shift_date_opt_out
