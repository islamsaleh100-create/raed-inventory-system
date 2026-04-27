"""L1 — probe 5 API endpoints via TestClient (JWT for user id=1 admin)."""
import os
import sys
import traceback

os.environ.setdefault("ENV_FILE", ".env")
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.security import create_access_token  # noqa: E402

client = TestClient(app)

# Local DB admin password may differ from seed; issue token like auth would.
tok = create_access_token({"sub": "1"})
h = {"Authorization": f"Bearer {tok}"}
print("using JWT for user_id=1")

paths = [
    "GET /api/v1/quality/",
    "GET /api/v1/quality/open-actions",
    "GET /api/v1/training/",
    "GET /api/v1/training/analytics/verdict-distribution",
    "GET /api/v1/dashboard/order-delay-analytics?days=30",
]
urls = [
    "/api/v1/quality/",
    "/api/v1/quality/open-actions",
    "/api/v1/training/",
    "/api/v1/training/analytics/verdict-distribution",
    "/api/v1/dashboard/order-delay-analytics?days=30",
]
for label, url in zip(paths, urls):
    try:
        resp = client.get(url, headers=h)
        print(f"\n{label} -> {resp.status_code}")
        if resp.status_code >= 400:
            print(resp.text[:800])
    except Exception as e:
        print(f"\n{label} -> EXCEPTION {e}")
        traceback.print_exc()
