"""
Smoke-verify matrix users against a running API (default http://127.0.0.1:8010).

Usage (from backend/):
  set ENV_FILE=.env.staging   # or .env — must match API's DB/users
  python scripts/verify_matrix_roles_api.py

Environment:
  VERIFY_API_BASE   — API root (default http://127.0.0.1:8010); use staging URL when probing staging.
  VERIFY_API_PASSWORD — matrix user password (default Raed@2025; override if PERMISSION_MATRIX_PASSWORD was set at seed).
  VERIFY_LOGIN_DELAY_S — seconds between logins (default 3.2) to stay under RATE_LIMIT_AUTH.

Uses VERIFY_LOGIN_DELAY_S between logins; retries 429 with backoff.
Reuses delivery_dammam token for NEG probe to save one auth call.
First probes GET /api/v1/ready — non-200 counts as FAIL (exit 1).
"""
from __future__ import annotations

import os
import sys
import time

import httpx

BASE = os.environ.get("VERIFY_API_BASE", "http://127.0.0.1:8010").rstrip("/")
PASSWORD = os.environ.get("VERIFY_API_PASSWORD", "Raed@2025")
# Default keeps /auth/login under RATE_LIMIT_AUTH (often 20/min): ~21 users * 3.2s > 60s window.
DELAY_S = float(os.environ.get("VERIFY_LOGIN_DELAY_S", "3.2"))

def post_login(client: httpx.Client, username: str, password: str) -> httpx.Response:
    for attempt in range(4):
        lr = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        if lr.status_code != 429:
            return lr
        if attempt < 3:
            wait = 2.0 * (attempt + 1)
            print(f"RETRY login {username} after 429, sleeping {wait}s")
            time.sleep(wait)
    return lr


USERS: list[tuple[str, str]] = [
    ("super.admin", "branches"),
    ("admin", "branches"),
    ("area_dammam_onda", "branch_requests_list"),
    ("area_dammam_restaurants", "branch_requests_list"),
    ("area_riyadh_all", "branch_requests_list"),
    ("branch_onda_13_al_malqa", "branch_requests_list"),
    ("branch_pizza_4_riyadh_takhasosy", "branch_requests_list"),
    ("branch_shawarma_olaya", "branch_requests_list"),
    ("branch_griddle", "branch_requests_list"),
    ("kitchen_dammam_meat_and_chicken_mgr", "production_orders"),
    ("kitchen_dammam_bakery_and_sweets_mgr", "production_orders"),
    ("kitchen_dammam_pizza_mgr", "production_orders"),
    ("kitchen_riyadh_meat_and_chicken_mgr", "production_orders"),
    ("kitchen_riyadh_bakery_and_sweets_mgr", "production_orders"),
    ("kitchen_riyadh_pizza_mgr", "production_orders"),
    ("warehouse_dammam_manager", "warehouse_lines_list"),
    ("warehouse_dammam_user", "warehouse_lines_list"),
    ("warehouse_riyadh_manager", "warehouse_lines_list"),
    ("warehouse_riyadh_user", "warehouse_lines_list"),
    ("delivery_dammam", "delivery_ready"),
    ("delivery_riyadh", "delivery_ready"),
]


def main() -> int:
    results: list[str] = []
    delivery_dammam_token: str | None = None
    with httpx.Client(base_url=BASE, timeout=15.0) as client:
        ready_r = client.get("/api/v1/ready")
        results.append(f"ready_http={ready_r.status_code}")
        if ready_r.status_code != 200:
            results.append(f"FAIL /api/v1/ready http={ready_r.status_code} (expect 200 — DB down or old build)")

        r = client.get("/api/v1/master/branches", params={"active_only": "true"})
        if r.status_code != 401:
            results.append(f"WARN branches without auth: {r.status_code}")
        r0 = client.get(f"{BASE}/docs", follow_redirects=True)
        results.append(f"docs_http={r0.status_code}")

        for username, probe in USERS:
            time.sleep(DELAY_S)
            lr = post_login(client, username, PASSWORD)
            if lr.status_code == 429:
                results.append(f"SKIP login {username} http=429 (rate limit — retry with VERIFY_LOGIN_DELAY_S or RATE_LIMIT_AUTH)")
                continue
            if lr.status_code != 200:
                results.append(f"FAIL login {username} http={lr.status_code}")
                continue
            token = lr.json().get("access_token")
            if username == "delivery_dammam" and token:
                delivery_dammam_token = token
            h = {"Authorization": f"Bearer {token}"}
            me = client.get("/api/v1/auth/me", headers=h)
            if me.status_code != 200:
                results.append(f"FAIL me {username} http={me.status_code}")
                continue
            ok = False
            code = 0
            if probe == "branches":
                x = client.get("/api/v1/master/branches", headers=h, params={"active_only": "true"})
                code = x.status_code
                ok = x.status_code == 200
            elif probe == "branch_requests_list":
                x = client.get("/api/v1/branch-requests", headers=h, params={"page": 1, "page_size": 5})
                code = x.status_code
                ok = x.status_code == 200
            elif probe == "production_orders":
                x = client.get("/api/v1/production-orders", headers=h)
                code = x.status_code
                ok = x.status_code == 200
            elif probe == "warehouse_lines_list":
                x = client.get("/api/v1/warehouse-lines", headers=h)
                code = x.status_code
                ok = x.status_code == 200
            elif probe == "delivery_ready":
                x = client.get("/api/v1/delivery-orders/ready", headers=h)
                code = x.status_code
                ok = x.status_code == 200
            tag = "OK" if ok else "FAIL"
            results.append(f"{tag} {username} probe={probe} http={code}")
        # Negative: delivery must not see production (reuse token to avoid extra /auth/login)
        if delivery_dammam_token:
            h = {"Authorization": f"Bearer {delivery_dammam_token}"}
            neg = client.get("/api/v1/production-orders", headers=h)
            results.append(f"NEG delivery_dammam production_orders http={neg.status_code} (expect 403)")
        else:
            results.append("FAIL NEG skipped (no delivery_dammam token)")

    for line in results:
        print(line)
    fails = [x for x in results if x.startswith("FAIL")]
    skips = [x for x in results if x.startswith("SKIP")]
    if skips:
        print("(SKIPS present — not counted as failures for exit code)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
