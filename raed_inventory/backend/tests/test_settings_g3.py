"""
G3-Fix — System Settings endpoint coverage.

Covers:
  * GET  /settings returns all rows (admin only).
  * GET  /settings/{key} single lookup + 404 for unknown.
  * PUT  /settings/{key} updates value + records updated_by.
  * PUT  /settings bulk update is atomic (rolls back on any invalid key).
  * Validation: numeric, percentage, boolean, enum, time HH:MM.
  * RBAC: non-admin users (branch_user/manager/warehouse_user) are blocked.
"""
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    Branch,
    Role,
    RoleName,
    SystemSetting,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)


# ═══════════════════════════════════════════════════════════════════════════
# Seed helpers
# ═══════════════════════════════════════════════════════════════════════════
def _ensure_role(db: Session, name: RoleName) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if role is None:
        role = Role(name=name, display_name=name.value, description="")
        db.add(role)
        db.flush()
    return role


def _seed(db: Session) -> dict:
    wh = Warehouse(warehouse_code="WH-SET", warehouse_name="Set WH",
                   location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    br = Branch(branch_code="SET-1", branch_name="B1", city="الرياض",
                area="الرياض", warehouse_id=wh.id, active=True)
    db.add(br)
    db.flush()

    role_admin = _ensure_role(db, RoleName.admin)
    role_bu = _ensure_role(db, RoleName.branch_user)
    role_bm = _ensure_role(db, RoleName.branch_manager)

    admin = User(username="set_admin", email="set_admin@x.com", full_name="Admin",
                 hashed_password=get_password_hash("Pass@2026"),
                 status=UserStatus.active, is_deleted=False)
    staff = User(username="set_staff", email="set_staff@x.com", full_name="Staff",
                 hashed_password=get_password_hash("Pass@2026"),
                 status=UserStatus.active, branch_id=br.id, is_deleted=False)
    mgr = User(username="set_mgr", email="set_mgr@x.com", full_name="Mgr",
               hashed_password=get_password_hash("Pass@2026"),
               status=UserStatus.active, branch_id=br.id, is_deleted=False)
    db.add_all([admin, staff, mgr])
    db.flush()
    db.add_all([
        UserRole(user_id=admin.id, role_id=role_admin.id),
        UserRole(user_id=staff.id, role_id=role_bu.id),
        UserRole(user_id=mgr.id, role_id=role_bm.id),
    ])

    # Seed a representative slice of the settings the router validates.
    db.add_all([
        SystemSetting(key="days_of_cover_target", value="3",
                      description="Target days of stock coverage"),
        SystemSetting(key="variance_warning_threshold_pct", value="10",
                      description="Variance % that triggers warning"),
        SystemSetting(key="variance_critical_threshold_pct", value="25",
                      description="Variance % that triggers critical"),
        SystemSetting(key="auto_generate_order_on_approval", value="true",
                      description="Auto generate order on approval"),
        SystemSetting(key="require_variance_reason", value="true",
                      description="Require reason for critical variance"),
        SystemSetting(key="avg_consumption_mode", value="last_7_days",
                      description="Consumption window"),
        SystemSetting(key="inventory_reminder_time", value="08:00",
                      description="Daily inventory reminder"),
        SystemSetting(key="max_exceptional_order_per_day", value="3",
                      description="Max exceptional orders/day"),
    ])
    db.commit()

    return {"admin_id": admin.id, "staff_id": staff.id, "mgr_id": mgr.id}


@pytest.fixture
def seeded(client, db: Session):
    return _seed(db)


def _login(client, username: str) -> str:
    r = client.post("/api/v1/auth/login",
                    json={"username": username, "password": "Pass@2026"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ═══════════════════════════════════════════════════════════════════════════
# Tests — happy paths
# ═══════════════════════════════════════════════════════════════════════════
def test_admin_can_list_all_settings(client, seeded):
    tok = _login(client, "set_admin")
    r = client.get("/api/v1/settings", headers=_auth(tok))
    assert r.status_code == 200
    rows = r.json()
    keys = {row["key"] for row in rows}
    # Rows seeded above must all come back
    assert "days_of_cover_target" in keys
    assert "variance_warning_threshold_pct" in keys
    assert "avg_consumption_mode" in keys


def test_admin_can_get_single_setting(client, seeded):
    tok = _login(client, "set_admin")
    r = client.get("/api/v1/settings/days_of_cover_target", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["value"] == "3"


def test_get_unknown_setting_returns_404(client, seeded):
    tok = _login(client, "set_admin")
    r = client.get("/api/v1/settings/does_not_exist", headers=_auth(tok))
    assert r.status_code == 404


def test_update_single_setting_persists_and_records_user(client, seeded, db):
    tok = _login(client, "set_admin")
    r = client.put("/api/v1/settings/days_of_cover_target",
                   json={"value": "5"}, headers=_auth(tok))
    assert r.status_code == 200, r.text
    assert r.json()["value"] == "5"
    assert r.json()["updated_by"] == seeded["admin_id"]

    # Verify persisted
    row = db.query(SystemSetting).filter(
        SystemSetting.key == "days_of_cover_target").first()
    assert row.value == "5"
    assert row.updated_by == seeded["admin_id"]


def test_bulk_update_atomic_on_success(client, seeded, db):
    tok = _login(client, "set_admin")
    r = client.put("/api/v1/settings",
                   json={"settings": {
                       "days_of_cover_target": "4",
                       "variance_warning_threshold_pct": "12.5",
                       "auto_generate_order_on_approval": "false",
                   }}, headers=_auth(tok))
    assert r.status_code == 200, r.text
    returned = {row["key"]: row["value"] for row in r.json()}
    assert returned["days_of_cover_target"] == "4"
    assert returned["variance_warning_threshold_pct"] == "12.5"
    assert returned["auto_generate_order_on_approval"] == "false"


# ═══════════════════════════════════════════════════════════════════════════
# Tests — validation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("key,bad_value", [
    ("days_of_cover_target", "abc"),           # not int
    ("days_of_cover_target", "-1"),            # negative
    ("days_of_cover_target", "0"),             # must be > 0
    ("variance_warning_threshold_pct", "-5"),  # below 0
    ("variance_warning_threshold_pct", "150"), # above 100
    ("auto_generate_order_on_approval", "maybe"),  # not bool
    ("avg_consumption_mode", "last_90_days"),  # not in enum
    ("inventory_reminder_time", "25:00"),      # invalid hour
    ("inventory_reminder_time", "8am"),        # not HH:MM
])
def test_invalid_values_rejected(client, seeded, key, bad_value):
    tok = _login(client, "set_admin")
    r = client.put(f"/api/v1/settings/{key}",
                   json={"value": bad_value}, headers=_auth(tok))
    assert r.status_code == 400, f"expected 400 for {key}={bad_value}, got {r.status_code}: {r.text}"


def test_bulk_update_rolls_back_on_any_invalid_key(client, seeded, db):
    """If one key fails validation, NONE of the others should be saved."""
    tok = _login(client, "set_admin")
    original = db.query(SystemSetting).filter(
        SystemSetting.key == "days_of_cover_target").first().value

    r = client.put("/api/v1/settings",
                   json={"settings": {
                       "days_of_cover_target": "7",           # valid
                       "variance_warning_threshold_pct": "999",  # invalid
                   }}, headers=_auth(tok))
    assert r.status_code == 400
    # Original must be unchanged — the valid key from the same payload must NOT be persisted.
    db.expire_all()
    still = db.query(SystemSetting).filter(
        SystemSetting.key == "days_of_cover_target").first().value
    assert still == original, f"expected {original}, got {still} — bulk update was not atomic"


def test_bool_accepts_aliases(client, seeded):
    tok = _login(client, "set_admin")
    for v_in, v_out in [("1", "true"), ("0", "false"),
                        ("yes", "true"), ("no", "false"),
                        ("TRUE", "true"), ("False", "false")]:
        r = client.put("/api/v1/settings/auto_generate_order_on_approval",
                       json={"value": v_in}, headers=_auth(tok))
        assert r.status_code == 200, f"{v_in}: {r.text}"
        assert r.json()["value"] == v_out


# ═══════════════════════════════════════════════════════════════════════════
# Tests — RBAC
# ═══════════════════════════════════════════════════════════════════════════
def test_branch_user_cannot_list(client, seeded):
    tok = _login(client, "set_staff")
    r = client.get("/api/v1/settings", headers=_auth(tok))
    assert r.status_code == 403


def test_branch_manager_cannot_update(client, seeded):
    tok = _login(client, "set_mgr")
    r = client.put("/api/v1/settings/days_of_cover_target",
                   json={"value": "5"}, headers=_auth(tok))
    assert r.status_code == 403


def test_unauthenticated_blocked(client, seeded):
    r = client.get("/api/v1/settings")
    assert r.status_code in (401, 403)


def test_bulk_update_rejects_null_value_with_422(client, seeded):
    tok = _login(client, "set_admin")
    r = client.put(
        "/api/v1/settings",
        json={"settings": {"days_of_cover_target": None}},
        headers=_auth(tok),
    )
    assert r.status_code == 422


def test_bulk_update_accepts_integer_json_coerced_to_string(client, seeded, db):
    """JSON numbers are coerced to str before per-key validation (days_of_cover_target)."""
    tok = _login(client, "set_admin")
    r = client.put(
        "/api/v1/settings",
        json={"settings": {"days_of_cover_target": 12}},
        headers=_auth(tok),
    )
    assert r.status_code == 200, r.text
    vals = {row["key"]: row["value"] for row in r.json()}
    assert vals["days_of_cover_target"] == "12"
    row = db.query(SystemSetting).filter(SystemSetting.key == "days_of_cover_target").first()
    assert row.value == "12"


def test_bulk_then_single_put_latest_value_wins(client, seeded, db):
    tok = _login(client, "set_admin")
    r1 = client.put(
        "/api/v1/settings",
        json={"settings": {"days_of_cover_target": "2"}},
        headers=_auth(tok),
    )
    assert r1.status_code == 200
    r2 = client.put(
        "/api/v1/settings/days_of_cover_target",
        json={"value": "8"},
        headers=_auth(tok),
    )
    assert r2.status_code == 200
    assert r2.json()["value"] == "8"
    assert r2.json()["updated_by"] == seeded["admin_id"]
    row = db.query(SystemSetting).filter(SystemSetting.key == "days_of_cover_target").first()
    assert row.value == "8"
    assert row.updated_by == seeded["admin_id"]
