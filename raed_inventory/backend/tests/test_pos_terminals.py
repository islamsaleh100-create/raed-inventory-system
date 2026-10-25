"""POS terminals registry — PostgreSQL."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys

import pytest
from sqlalchemy import text

from app.core.security import get_password_hash
from app.models import AuditLog, Branch, BranchBrand, Brand, Role, RoleName, User, UserRole, Warehouse
from app.services import audit_service
from app.models.pos_terminal import PosTerminal
from app.services import pos_terminal_service as pos_svc
from app.services.pos_terminal_utils import normalize_terminal_text

API = "/api/v1/audit/pos-terminals"
PASSWORD = "Aa1!" + secrets.token_urlsafe(12)


@pytest.fixture(autouse=True)
def _pg_only(db):
    from app.config import settings

    if settings.DATABASE_URL.startswith("sqlite"):
        pytest.skip("PostgreSQL only")


@pytest.fixture(autouse=True)
def _audit_log_on(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")


def _role(db, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if not row:
        row = Role(name=name, display_name=name.value, description="")
        db.add(row)
        db.flush()
    return row


def _user(db, username: str, role_name: RoleName, *, branch_id=None) -> User:
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


def _seed_branches(db, suffix: str) -> tuple[Branch, Branch]:
    wh = Warehouse(warehouse_code=f"{suffix}-WH", warehouse_name="WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    brand = Brand(name=f"{suffix} Brand", active=True)
    db.add(brand)
    db.flush()
    b1 = Branch(
        branch_code=f"{suffix}-B1",
        branch_name=f"Branch One {suffix}",
        city="Riyadh",
        area="T",
        warehouse_id=wh.id,
        active=True,
        is_deleted=False,
    )
    b2 = Branch(
        branch_code=f"{suffix}-B2",
        branch_name=f"Branch Two {suffix}",
        city="Dammam",
        area="T",
        warehouse_id=wh.id,
        active=True,
        is_deleted=False,
    )
    db.add_all([b1, b2])
    db.flush()
    for b in (b1, b2):
        db.add(BranchBrand(branch_id=b.id, brand_id=brand.id))
    db.flush()
    return b1, b2


def test_normalize_arabic_digits():
    assert normalize_terminal_text("٠١٢٣") == "0123"
    assert normalize_terminal_text("  123  ") == "123"


def test_create_search_arabic_and_update(client, db):
    b1, b2 = _seed_branches(db, "POS1")
    _user(db, "pos1.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos1.aud")
    create = client.post(
        API,
        headers=ah,
        json={
            "provider": "hala",
            "terminal_number": "٠١٢٣",
            "serial_number": "SN-١٠",
            "branch_id": b1.id,
            "status": "active",
            "notes": "note",
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["terminal_number"] == "0123"
    assert body["branch_id"] == b1.id
    assert body["brand_names"]
    search = client.get(f"{API}?search=0123", headers=ah)
    assert search.status_code == 200
    assert search.json()["total"] == 1
    tid = body["id"]
    upd = client.patch(
        f"{API}/{tid}",
        headers=ah,
        json={"branch_id": b2.id, "status": "withdrawn"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["branch_id"] == b2.id
    assert upd.json()["status"] == "withdrawn"


def test_duplicate_same_provider_409_different_provider_ok(client, db):
    b1, _ = _seed_branches(db, "POS2")
    _user(db, "pos2.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos2.aud")
    first = client.post(
        API,
        headers=ah,
        json={"provider": "nami", "terminal_number": "T-100", "branch_id": b1.id},
    )
    assert first.status_code == 201
    dup = client.post(
        API,
        headers=ah,
        json={"provider": "nami", "terminal_number": "T-100", "branch_id": b1.id},
    )
    assert dup.status_code == 409
    payload = dup.json()
    assert payload["error_code"] == "POS_TERMINAL_DUPLICATE_NUMBER"
    assert payload["detail"]["existing_branch_name"]
    other = client.post(
        API,
        headers=ah,
        json={"provider": "hala", "terminal_number": "T-100", "branch_id": b1.id},
    )
    assert other.status_code == 201


def test_forbidden_for_branch_manager(client, db):
    b1, _ = _seed_branches(db, "POS3")
    _user(db, "pos3.bm", RoleName.branch_manager, branch_id=b1.id)
    db.commit()
    bh = _login(client, "pos3.bm")
    r = client.get(API, headers=bh)
    assert r.status_code == 403


def test_audit_log_on_create_and_update(client, db):
    b1, b2 = _seed_branches(db, "POS4")
    auditor = _user(db, "pos4.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos4.aud")
    create = client.post(
        API,
        headers=ah,
        json={"provider": "riyad_bank", "terminal_number": "RB-1", "branch_id": b1.id},
    )
    assert create.status_code == 201
    tid = create.json()["id"]
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "pos_terminal", AuditLog.entity_id == tid)
        .order_by(AuditLog.id)
        .all()
    )
    assert len(logs) >= 1
    assert logs[0].action == "pos_terminal_create"
    assert json.loads(logs[0].new_values or "{}")["branch_id"] == b1.id
    client.patch(f"{API}/{tid}", headers=ah, json={"branch_id": b2.id, "status": "disabled"})
    logs2 = audit_service.get_logs(db, entity_type="pos_terminal", entity_id=tid, page_size=10)
    actions = [x["action"] for x in logs2["items"]]
    assert "pos_terminal_update" in actions
    update_row = next(x for x in logs2["items"] if x["action"] == "pos_terminal_update")
    old = update_row["old_values"]
    new = update_row["new_values"]
    assert old["branch_id"] == b1.id and new["branch_id"] == b2.id
    assert old["status"] == "active" and new["status"] == "disabled"


def test_search_by_serial_number(client, db):
    b1, _ = _seed_branches(db, "POS5")
    _user(db, "pos5.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos5.aud")
    client.post(
        API,
        headers=ah,
        json={
            "provider": "hala",
            "terminal_number": "H-55",
            "serial_number": "SER-٩٩٠",
            "branch_id": b1.id,
        },
    )
    r = client.get(f"{API}?search=990", headers=ah)
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["serial_number"] == "SER-990"


def test_create_unknown_branch_422(client, db):
    _user(db, "pos6.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos6.aud")
    r = client.post(
        API,
        headers=ah,
        json={"provider": "hala", "terminal_number": "X-1", "branch_id": 9_999_999},
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "POS_TERMINAL_BRANCH_NOT_FOUND"


def test_patch_null_provider_and_status_422(client, db):
    b1, _ = _seed_branches(db, "POS7")
    _user(db, "pos7.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos7.aud")
    tid = client.post(
        API,
        headers=ah,
        json={"provider": "nami", "terminal_number": "N-1", "branch_id": b1.id},
    ).json()["id"]
    r1 = client.patch(f"{API}/{tid}", headers=ah, json={"provider": None})
    assert r1.status_code == 422
    assert r1.json()["error_code"] == "POS_TERMINAL_NULL_PROVIDER"
    r2 = client.patch(f"{API}/{tid}", headers=ah, json={"status": None})
    assert r2.status_code == 422
    assert r2.json()["error_code"] == "POS_TERMINAL_NULL_STATUS"


def test_integrity_error_on_create_returns_409(client, db, monkeypatch):
    b1, _ = _seed_branches(db, "POS8")
    _user(db, "pos8.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos8.aud")
    body = {"provider": "hala", "terminal_number": "RACE-1", "branch_id": b1.id}
    assert client.post(API, headers=ah, json=body).status_code == 201

    monkeypatch.setattr(pos_svc, "_assert_unique", lambda *args, **kwargs: None)
    dup = client.post(API, headers=ah, json=body)
    assert dup.status_code == 409
    assert dup.json()["error_code"] == "POS_TERMINAL_DUPLICATE_NUMBER"

    after = client.get(f"{API}?search=RACE-1&provider=hala", headers=ah)
    assert after.status_code == 200, after.text
    assert after.json()["total"] == 1
    assert (
        db.query(PosTerminal)
        .filter(PosTerminal.provider == "hala", PosTerminal.terminal_number == "RACE-1")
        .count()
        == 1
    )


def test_integrity_error_on_patch_returns_409_preserves_row(client, db, monkeypatch):
    b1, _ = _seed_branches(db, "POS8B")
    _user(db, "pos8b.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos8b.aud")
    first = client.post(
        API,
        headers=ah,
        json={"provider": "nami", "terminal_number": "IE-P1", "branch_id": b1.id, "status": "active"},
    )
    second = client.post(
        API,
        headers=ah,
        json={"provider": "nami", "terminal_number": "IE-P2", "branch_id": b1.id, "status": "disabled"},
    )
    assert first.status_code == 201 and second.status_code == 201
    second_id = second.json()["id"]
    second_before = second.json()["terminal_number"]

    monkeypatch.setattr(pos_svc, "_assert_unique", lambda *args, **kwargs: None)
    conflict = client.patch(
        f"{API}/{second_id}",
        headers=ah,
        json={"terminal_number": "IE-P1"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error_code"] == "POS_TERMINAL_DUPLICATE_NUMBER"

    row = db.query(PosTerminal).filter(PosTerminal.id == second_id).one()
    assert row.terminal_number == second_before
    assert row.status == "disabled"
    listed = client.get(f"{API}?search={second_before}", headers=ah)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == second_id


def test_migration_upgrade_downgrade_cycle():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required")
    env = {**os.environ, "DATABASE_URL": url}
    cwd = os.path.join(os.path.dirname(__file__), "..")
    down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "-1"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert down.returncode == 0, down.stderr
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; from sqlalchemy import create_engine, text; "
            "e=create_engine(os.environ['DATABASE_URL']); "
            "c=e.connect(); "
            "print(c.execute(text(\"SELECT to_regclass('public.pos_terminals')\")).scalar()); "
            "c.close(); e.dispose()",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0
    assert check.stdout.strip() in ("None", "null", "")
    up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert up.returncode == 0, up.stderr
