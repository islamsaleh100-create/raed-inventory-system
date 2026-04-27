import os
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.main import app
from app.models import Base, IdempotencyRequest
from app.services.idempotency_service import (
    cleanup_expired_idempotency_requests,
    complete_idempotency_request,
    get_idempotency_request,
    register_idempotency_request,
)


SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


class Epic1FoundationTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        self.client_manager = TestClient(app, raise_server_exceptions=False)
        self.client = self.client_manager.__enter__()

    def tearDown(self):
        self.client_manager.__exit__(None, None, None)
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_v1_health_endpoint_exposes_environment_metadata(self):
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "healthy")
        self.assertIn("app", payload)
        self.assertIn("version", payload)
        self.assertIn("environment", payload)
        self.assertIn("timestamp", payload)

    def test_v1_meta_endpoint_exposes_docs_urls(self):
        response = self.client.get("/api/v1/meta")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        # يطابق app.main:app_meta — روابط التوثيق ثابتة على /api/docs وليست داخل JSON
        self.assertIn("app", payload)
        self.assertIn("version", payload)
        self.assertIn("environment", payload)

    def test_startup_registers_idempotency_cleanup_task(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            self.assertEqual(client.get("/api/v1/health").status_code, 200)
            task = getattr(app.state, "idempotency_cleanup_task", None)
            self.assertIsNotNone(task)
            self.assertFalse(task.done())

    def test_idempotency_key_is_unique_per_tenant_request_and_operation(self):
        register_idempotency_request(
            self.db,
            tenant_id=1,
            client_request_id="req-001",
            operation_name="inventory.submit",
            user_id=9,
        )

        with self.assertRaises(IntegrityError):
            register_idempotency_request(
                self.db,
                tenant_id=1,
                client_request_id="req-001",
                operation_name="inventory.submit",
                user_id=9,
            )

    def test_idempotency_record_can_be_completed_and_reloaded(self):
        record = register_idempotency_request(
            self.db,
            tenant_id=1,
            client_request_id="req-002",
            operation_name="orders.dispatch",
            user_id=7,
            request_hash="debug-hash",
        )

        completed = complete_idempotency_request(
            self.db,
            record=record,
            response_reference_type="order",
            response_reference_id=123,
        )
        loaded = get_idempotency_request(
            self.db,
            tenant_id=1,
            client_request_id="req-002",
            operation_name="orders.dispatch",
        )

        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.response_reference_type, "order")
        self.assertEqual(completed.response_reference_id, "123")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.request_hash, "debug-hash")

    def test_cleanup_removes_expired_idempotency_records_only(self):
        expired = IdempotencyRequest(
            tenant_id=1,
            client_request_id="expired-1",
            operation_name="inventory.submit",
            status="completed",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        active = IdempotencyRequest(
            tenant_id=1,
            client_request_id="active-1",
            operation_name="inventory.submit",
            status="completed",
            expires_at=datetime.utcnow() + timedelta(hours=2),
        )
        self.db.add_all([expired, active])
        self.db.commit()

        deleted_count = cleanup_expired_idempotency_requests(self.db)

        self.assertEqual(deleted_count, 1)
        remaining = self.db.query(IdempotencyRequest).all()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].client_request_id, "active-1")

    def test_settings_can_load_from_explicit_env_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env.test"
            env_path.write_text(
                "\n".join(
                    [
                        "ENVIRONMENT=staging",
                        "DATABASE_URL=sqlite:///tmp/test.db",
                        "SECRET_KEY=test-secret-key",
                        "DEBUG=false",
                        "ALLOWED_ORIGINS=https://staging.example.com",
                    ]
                ),
                encoding="utf-8",
            )

            # متغيرات pytest/conftest لها أسبقية على ملف الـ env — نزيلها مؤقتاً لهذا الاستدعاء
            _pop_keys = (
                "ENVIRONMENT",
                "DATABASE_URL",
                "SECRET_KEY",
                "DEBUG",
                "ALLOWED_ORIGINS",
                "ENV_FILE",
            )
            _saved = {k: os.environ.pop(k, None) for k in _pop_keys}
            try:
                loaded = Settings(_env_file=str(env_path))
            finally:
                for _k, _v in _saved.items():
                    if _v is not None:
                        os.environ[_k] = _v

        self.assertEqual(loaded.ENVIRONMENT, "staging")
        self.assertEqual(loaded.DATABASE_URL, "sqlite:///tmp/test.db")
        self.assertFalse(loaded.DEBUG)
        self.assertEqual(loaded.allowed_origins_list, ["https://staging.example.com"])


if __name__ == "__main__":
    unittest.main()
