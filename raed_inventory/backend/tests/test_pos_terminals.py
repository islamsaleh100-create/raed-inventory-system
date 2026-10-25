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


def test_create_without_branch_and_list(client, db):
    _user(db, "pos9.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos9.aud")
    create = client.post(
        API,
        headers=ah,
        json={
            "provider": "nami",
            "terminal_number": "NO-BR-1",
            "branch_label": "Sheet Branch Name",
            "status": "active",
            "notes": "import note",
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["branch_id"] is None
    assert body["branch_name"] is None
    assert body["branch_label"] == "Sheet Branch Name"
    listed = client.get(API, headers=ah)
    assert listed.status_code == 200
    ids = {x["id"] for x in listed.json()["items"]}
    assert body["id"] in ids
    by_label = client.get(f"{API}?search=Sheet Branch", headers=ah)
    assert by_label.json()["total"] >= 1
    by_notes = client.get(f"{API}?search=import note", headers=ah)
    assert by_notes.json()["total"] >= 1


def test_patch_unlink_and_relink_branch(client, db):
    b1, b2 = _seed_branches(db, "POS9B")
    _user(db, "pos9b.aud", RoleName.internal_auditor)
    db.commit()
    ah = _login(client, "pos9b.aud")
    tid = client.post(
        API,
        headers=ah,
        json={"provider": "hala", "terminal_number": "LINK-1", "branch_id": b1.id},
    ).json()["id"]
    unlinked = client.patch(f"{API}/{tid}", headers=ah, json={"branch_id": None, "branch_label": "Unlinked label"})
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["branch_id"] is None
    assert unlinked.json()["branch_label"] == "Unlinked label"
    relink = client.patch(f"{API}/{tid}", headers=ah, json={"branch_id": b2.id})
    assert relink.status_code == 200
    assert relink.json()["branch_id"] == b2.id
    assert relink.json()["branch_name"] == b2.branch_name


NAMI_IMPORT_BRANCHES = [
    "Onda 1 - ARKAN",
    "Onda 13 - Al Malqa",
    "Onda 14 - HASSA",
    "Onda 16 - Namjah",
    "Onda 4 - SEFARAT",
    "Onda 5 - MUOWASAT",
    "Pizza 4 - Riyadh Takhasosy",
    "Pizza 9 - Al Azizia",
    "SHAWERMA - 1 - Khobar",
    "SHAWERMA - 4 - ARKAN",
    "SHAWERMA - OLAYA",
]


def _seed_nami_import_branches(db) -> None:
    wh = db.query(Warehouse).first()
    if not wh:
        wh = Warehouse(warehouse_code="NAMI-IMP-WH", warehouse_name="WH", location="Riyadh", active=True)
        db.add(wh)
        db.flush()
    for i, name in enumerate(NAMI_IMPORT_BRANCHES):
        exists = (
            db.query(Branch)
            .filter(Branch.is_deleted == False, Branch.branch_name == name)  # noqa: E712
            .first()
        )
        if exists:
            continue
        db.add(
            Branch(
                branch_code=f"NAMI-IMP-{i+1:02d}",
                branch_name=name,
                city="Riyadh",
                area="T",
                warehouse_id=wh.id,
                active=True,
                is_deleted=False,
            )
        )
    db.flush()


def _ensure_audit_officer(db) -> User:
    row = db.query(User).filter(User.username == "audit.officer").first()
    if row:
        return row
    role = _role(db, RoleName.internal_auditor)
    row = User(
        username="audit.officer",
        email="audit@example.com",
        full_name="Internal Auditor",
        hashed_password=get_password_hash(PASSWORD),
        status="active",
        is_deleted=False,
    )
    db.add(row)
    db.flush()
    db.add(UserRole(user_id=row.id, role_id=role.id))
    db.flush()
    return row


def test_import_nami_script_dry_run_apply_and_idempotent(db):
    wb = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".ai-workflow", "POS_Nami_import_v2.xlsx")
    wb = os.path.normpath(wb)
    if not os.path.isfile(wb):
        pytest.skip("POS_Nami_import_v2.xlsx not present")
    env = {**os.environ}
    if not env.get("DATABASE_URL") and env.get("TEST_DATABASE_URL"):
        env["DATABASE_URL"] = env["TEST_DATABASE_URL"]
    backend = os.path.join(os.path.dirname(__file__), "..")
    seed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, sys; sys.path.insert(0, '.'); "
            "from sqlalchemy import create_engine; from sqlalchemy.orm import sessionmaker; "
            "from tests.test_pos_terminals import _seed_nami_import_branches, _ensure_audit_officer; "
            "from app.models.pos_terminal import PosTerminal; "
            "e=create_engine(os.environ['DATABASE_URL']); S=sessionmaker(bind=e); db=S(); "
            "_seed_nami_import_branches(db); _ensure_audit_officer(db); "
            "db.query(PosTerminal).filter(PosTerminal.provider=='nami').delete(); "
            "db.commit(); db.close(); e.dispose()",
        ],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
    )
    assert seed.returncode == 0, seed.stderr + seed.stdout
    script = os.path.join(backend, "scripts", "import_pos_terminals_nami.py")
    dry = subprocess.run(
        [sys.executable, script, wb],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env=env,
        capture_output=True,
        text=True,
    )
    assert dry.returncode == 0, dry.stderr + dry.stdout
    assert "would_create=37" in dry.stdout
    assert "rejected=0" in dry.stdout
    assert "with_branch=11" in dry.stdout
    assert "without_branch=26" in dry.stdout
    apply = subprocess.run(
        [sys.executable, script, wb, "--apply"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env=env,
        capture_output=True,
        text=True,
    )
    assert apply.returncode == 0, apply.stderr + apply.stdout
    assert "created=37" in apply.stdout
    verify = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, sys; sys.path.insert(0, '.'); "
            "from sqlalchemy import create_engine; from sqlalchemy.orm import sessionmaker; "
            "from app.models.pos_terminal import PosTerminal; "
            "e=create_engine(os.environ['DATABASE_URL']); S=sessionmaker(bind=e); db=S(); "
            "total=db.query(PosTerminal).filter(PosTerminal.provider=='nami').count(); "
            "linked=db.query(PosTerminal).filter(PosTerminal.provider=='nami', PosTerminal.branch_id.isnot(None)).count(); "
            "unlinked=db.query(PosTerminal).filter(PosTerminal.provider=='nami', PosTerminal.branch_id.is_(None)).count(); "
            "print(f'total={total} linked={linked} unlinked={unlinked}'); "
            "db.close(); e.dispose(); "
            "assert total==37 and linked==11 and unlinked==26",
        ],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
    )
    assert verify.returncode == 0, verify.stderr + verify.stdout
    again = subprocess.run(
        [sys.executable, script, wb, "--apply"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env=env,
        capture_output=True,
        text=True,
    )
    assert again.returncode == 2
    assert "rejected=37" in again.stdout


def test_migration_upgrade_downgrade_cycle():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required")
    env = {**os.environ, "DATABASE_URL": url}
    cwd = os.path.join(os.path.dirname(__file__), "..")
    preclean = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; from sqlalchemy import create_engine, text; "
            "e=create_engine(os.environ['DATABASE_URL']); "
            "c=e.connect(); t=c.begin(); "
            "c.execute(text('DELETE FROM pos_terminals WHERE branch_id IS NULL')); "
            "t.commit(); c.close(); e.dispose()",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert preclean.returncode == 0, preclean.stderr
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
            "tbl=c.execute(text(\"SELECT to_regclass('public.pos_terminals')\")).scalar(); "
            "col=c.execute(text(\"SELECT count(*) FROM information_schema.columns "
            "WHERE table_name='pos_terminals' AND column_name='branch_label'\")).scalar(); "
            "print(tbl, col); c.close(); e.dispose(); "
            "assert tbl and int(col)==0",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr + check.stdout
    up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert up.returncode == 0, up.stderr
