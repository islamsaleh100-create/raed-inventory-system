"""
Shared pytest fixtures for all test suites.

Each test module may also define its own setUpClass / setUp for unittest-style
tests, but this file provides shared fixtures available to all pytest-style tests
and ensures the in-memory SQLite database is wired correctly.
"""
import os
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Force test environment before any app imports ─────────────────────────────
os.environ.setdefault("ENV_FILE", ".env.test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-minimum!!")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MULTI_TENANT_ENABLED", "False")
os.environ.setdefault("AUDIT_LOG_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.database import Base, get_db   # noqa: E402  (must come after env setup)
from app.main import app                # noqa: E402


# ── In-memory SQLite engine shared across all fixtures ────────────────────────
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once per test session."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def db(create_tables):
    """
    Yield a DB session that is rolled back after each test.
    Use this in pytest-style tests that need direct DB access.
    """
    connection = TEST_ENGINE.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(db):
    """
    FastAPI TestClient with the DB overridden to the test session.
    Use this in pytest-style tests that need HTTP access.
    """
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client_session(create_tables):
    """
    Session-scoped TestClient. Use when you need the same DB state across
    multiple tests (e.g. a seed-once / test-many pattern).
    Note: changes are NOT rolled back between tests.
    """
    session = TestingSessionLocal()
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    session.close()
    app.dependency_overrides.clear()
