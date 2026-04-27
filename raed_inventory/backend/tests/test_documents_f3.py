"""
Documents module — Phase F3 coverage.

Covers:
  * Service-layer CRUD + validation (branch/user exclusivity).
  * Status derivation: valid | due_soon | expired | archived.
  * Renewal: new doc created, old archived with link via renewed_from_id.
  * Reminder helpers: due_for_reminder + mark_reminder_sent idempotency.
  * HTTP RBAC: branch_manager scoped to own branch; non-privileged roles blocked.
  * File upload + download round-trip.
  * Expiry summary aggregation.
"""
from datetime import date, timedelta, datetime
from io import BytesIO

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    Branch,
    Document,
    DocumentOwnerType,
    DocumentType,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)
from app.services import document_service


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
    wh = Warehouse(warehouse_code="WH-DOC", warehouse_name="Docs WH",
                   location="Riyadh", active=True)
    db.add(wh)
    db.flush()

    branch_a = Branch(branch_code="DOC-A", branch_name="Branch A",
                      city="الرياض", area="الرياض", warehouse_id=wh.id, active=True)
    branch_b = Branch(branch_code="DOC-B", branch_name="Branch B",
                      city="الرياض", area="الرياض", warehouse_id=wh.id, active=True)
    db.add_all([branch_a, branch_b])
    db.flush()

    role_admin = _ensure_role(db, RoleName.admin)
    role_am = _ensure_role(db, RoleName.area_manager)
    role_bm = _ensure_role(db, RoleName.branch_manager)
    role_wm = _ensure_role(db, RoleName.warehouse_manager)
    role_bu = _ensure_role(db, RoleName.branch_user)

    admin = User(username="doc_admin", email="doc_admin@x.com", full_name="Admin",
                 hashed_password=get_password_hash("Pass@2026"),
                 status=UserStatus.active, is_deleted=False)
    area_mgr = User(username="doc_am", email="doc_am@x.com", full_name="AM",
                    hashed_password=get_password_hash("Pass@2026"),
                    status=UserStatus.active, is_deleted=False)
    bm_a = User(username="doc_bm_a", email="bm_a@x.com", full_name="BM A",
                hashed_password=get_password_hash("Pass@2026"),
                status=UserStatus.active, branch_id=branch_a.id, is_deleted=False)
    bm_b = User(username="doc_bm_b", email="bm_b@x.com", full_name="BM B",
                hashed_password=get_password_hash("Pass@2026"),
                status=UserStatus.active, branch_id=branch_b.id, is_deleted=False)
    wh_mgr = User(username="doc_wm", email="wm@x.com", full_name="WM",
                  hashed_password=get_password_hash("Pass@2026"),
                  status=UserStatus.active, is_deleted=False)
    staff_a = User(username="doc_staff_a", email="staff_a@x.com", full_name="Staff A",
                   hashed_password=get_password_hash("Pass@2026"),
                   status=UserStatus.active, branch_id=branch_a.id, is_deleted=False)
    staff_b = User(username="doc_staff_b", email="staff_b@x.com", full_name="Staff B",
                   hashed_password=get_password_hash("Pass@2026"),
                   status=UserStatus.active, branch_id=branch_b.id, is_deleted=False)
    outsider = User(username="doc_outsider", email="out@x.com", full_name="Outsider",
                    hashed_password=get_password_hash("Pass@2026"),
                    status=UserStatus.active, branch_id=branch_a.id, is_deleted=False)
    db.add_all([admin, area_mgr, bm_a, bm_b, wh_mgr, staff_a, staff_b, outsider])
    db.flush()

    db.add_all([
        UserRole(user_id=admin.id, role_id=role_admin.id),
        UserRole(user_id=area_mgr.id, role_id=role_am.id),
        UserRole(user_id=bm_a.id, role_id=role_bm.id),
        UserRole(user_id=bm_b.id, role_id=role_bm.id),
        UserRole(user_id=wh_mgr.id, role_id=role_wm.id),
        UserRole(user_id=outsider.id, role_id=role_bu.id),
    ])
    db.commit()

    return {
        "branch_a": branch_a.id,
        "branch_b": branch_b.id,
        "admin_id": admin.id,
        "am_id": area_mgr.id,
        "bm_a_id": bm_a.id,
        "bm_b_id": bm_b.id,
        "wh_id": wh_mgr.id,
        "staff_a_id": staff_a.id,
        "staff_b_id": staff_b.id,
        "outsider_id": outsider.id,
    }


@pytest.fixture
def seeded(client, db: Session):
    return _seed(db)


def _login(client, username: str) -> str:
    r = client.post("/api/v1/auth/login",
                    json={"username": username, "password": "Pass@2026"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════
# Service-level tests
# ═══════════════════════════════════════════════════════════════════════════

def test_create_branch_document_service(seeded, db):
    doc = document_service.create_document(
        db,
        owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.municipality_license,
        title="رخصة بلدية — الفرع A",
        branch_id=seeded["branch_a"],
        expiry_date=date.today() + timedelta(days=200),
        reminder_days=30,
        uploaded_by=seeded["admin_id"],
    )
    assert doc.id is not None
    assert doc.owner_type == DocumentOwnerType.branch
    assert doc.branch_id == seeded["branch_a"]
    assert doc.user_id is None
    assert doc.is_archived is False


def test_create_employee_document_service(seeded, db):
    doc = document_service.create_document(
        db,
        owner_type=DocumentOwnerType.employee,
        doc_type=DocumentType.health_certificate,
        title="شهادة صحية — Staff A",
        user_id=seeded["staff_a_id"],
        expiry_date=date.today() + timedelta(days=90),
        reminder_days=30,
        uploaded_by=seeded["admin_id"],
    )
    assert doc.user_id == seeded["staff_a_id"]
    assert doc.branch_id is None


def test_create_rejects_mismatched_owner_refs(seeded, db):
    # branch doc with a user_id set → 400
    with pytest.raises(Exception):
        document_service.create_document(
            db,
            owner_type=DocumentOwnerType.branch,
            doc_type=DocumentType.municipality_license,
            title="bad",
            branch_id=seeded["branch_a"],
            user_id=seeded["staff_a_id"],
            expiry_date=date.today() + timedelta(days=10),
        )


def test_status_computation_valid_due_soon_expired(seeded, db):
    today = date.today()

    # valid (100d, reminder=30)
    d_valid = document_service.create_document(
        db,
        owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.commercial_registration,
        title="valid",
        branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=100),
        reminder_days=30,
    )
    # due_soon (15d left, reminder=30)
    d_due = document_service.create_document(
        db,
        owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.civil_defense_license,
        title="due",
        branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=15),
        reminder_days=30,
    )
    # expired (-5d)
    d_exp = document_service.create_document(
        db,
        owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.food_safety_permit,
        title="exp",
        branch_id=seeded["branch_a"],
        expiry_date=today - timedelta(days=5),
        reminder_days=30,
    )

    assert document_service._compute_status(d_valid) == "valid"
    assert document_service._compute_status(d_due) == "due_soon"
    assert document_service._compute_status(d_exp) == "expired"


def test_renew_archives_old_and_creates_new(seeded, db):
    old = document_service.create_document(
        db,
        owner_type=DocumentOwnerType.employee,
        doc_type=DocumentType.health_certificate,
        title="health cert",
        user_id=seeded["staff_a_id"],
        expiry_date=date.today() + timedelta(days=5),
        reminder_days=30,
        doc_number="OLD-001",
    )
    new_doc = document_service.renew_document(
        db, old.id,
        new_expiry_date=date.today() + timedelta(days=365),
        new_doc_number="NEW-002",
        uploaded_by=seeded["admin_id"],
    )
    db.refresh(old)
    assert old.is_archived is True
    assert new_doc.id != old.id
    assert new_doc.renewed_from_id == old.id
    assert new_doc.doc_number == "NEW-002"
    # Inherits title/type/owner from old
    assert new_doc.doc_type == old.doc_type
    assert new_doc.user_id == old.user_id


def test_renew_blocks_already_archived(seeded, db):
    d = document_service.create_document(
        db,
        owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.municipality_license,
        title="arc test",
        branch_id=seeded["branch_a"],
        expiry_date=date.today() + timedelta(days=30),
    )
    document_service.renew_document(
        db, d.id, new_expiry_date=date.today() + timedelta(days=400)
    )
    with pytest.raises(Exception):
        document_service.renew_document(
            db, d.id, new_expiry_date=date.today() + timedelta(days=500)
        )


def test_due_for_reminder_captures_due_and_expired(seeded, db):
    today = date.today()
    # in window (10d ≤ 30d)
    d1 = document_service.create_document(
        db, owner_type=DocumentOwnerType.branch, doc_type=DocumentType.municipality_license,
        title="d1", branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=10), reminder_days=30,
    )
    # expired
    d2 = document_service.create_document(
        db, owner_type=DocumentOwnerType.branch, doc_type=DocumentType.civil_defense_license,
        title="d2", branch_id=seeded["branch_a"],
        expiry_date=today - timedelta(days=2), reminder_days=30,
    )
    # out of window — shouldn't surface
    d3 = document_service.create_document(
        db, owner_type=DocumentOwnerType.branch, doc_type=DocumentType.commercial_registration,
        title="d3", branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=120), reminder_days=30,
    )
    ids = {d.id for d in document_service.due_for_reminder(db)}
    assert d1.id in ids
    assert d2.id in ids
    assert d3.id not in ids


def test_mark_reminder_sent_prevents_same_day_repeat(seeded, db):
    today = date.today()
    d = document_service.create_document(
        db, owner_type=DocumentOwnerType.branch, doc_type=DocumentType.municipality_license,
        title="d", branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=5), reminder_days=30,
    )
    assert any(x.id == d.id for x in document_service.due_for_reminder(db))
    document_service.mark_reminder_sent(db, [d.id])
    # After marking, same-day call should NOT return it
    remaining = document_service.due_for_reminder(db)
    assert all(x.id != d.id for x in remaining)


def test_expiry_summary_counts(seeded, db):
    today = date.today()
    # valid
    document_service.create_document(
        db, owner_type=DocumentOwnerType.branch, doc_type=DocumentType.municipality_license,
        title="v1", branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=200), reminder_days=30,
    )
    # due_soon
    document_service.create_document(
        db, owner_type=DocumentOwnerType.branch, doc_type=DocumentType.civil_defense_license,
        title="d1", branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=20), reminder_days=30,
    )
    # expired
    document_service.create_document(
        db, owner_type=DocumentOwnerType.branch, doc_type=DocumentType.commercial_registration,
        title="e1", branch_id=seeded["branch_a"],
        expiry_date=today - timedelta(days=1), reminder_days=30,
    )
    s = document_service.expiry_summary(db)
    assert s["valid"] >= 1
    assert s["due_soon"] >= 1
    assert s["expired"] >= 1
    assert s["total"] == s["valid"] + s["due_soon"] + s["expired"]


# ═══════════════════════════════════════════════════════════════════════════
# HTTP + RBAC tests
# ═══════════════════════════════════════════════════════════════════════════

def test_admin_can_create_branch_document(seeded, client):
    tok = _login(client, "doc_admin")
    r = client.post("/api/v1/documents/", json={
        "owner_type": "branch",
        "doc_type": "municipality_license",
        "branch_id": seeded["branch_a"],
        "title": "رخصة — الفرع A",
        "expiry_date": (date.today() + timedelta(days=200)).isoformat(),
        "reminder_days": 30,
    }, headers=_auth(tok))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["owner_type"] == "branch"
    assert body["status"] == "valid"


def test_branch_manager_restricted_to_own_branch(seeded, client):
    """BM of branch A cannot create a doc for branch B."""
    tok = _login(client, "doc_bm_a")
    r = client.post("/api/v1/documents/", json={
        "owner_type": "branch",
        "doc_type": "municipality_license",
        "branch_id": seeded["branch_b"],
        "title": "trying cross-branch",
        "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
    }, headers=_auth(tok))
    assert r.status_code == 403


def test_branch_manager_cannot_view_other_branch_doc(seeded, client, db):
    doc = document_service.create_document(
        db, owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.municipality_license,
        title="B's doc", branch_id=seeded["branch_b"],
        expiry_date=date.today() + timedelta(days=60),
    )
    tok = _login(client, "doc_bm_a")
    r = client.get(f"/api/v1/documents/{doc.id}", headers=_auth(tok))
    assert r.status_code == 403


def test_non_privileged_user_blocked_from_documents(seeded, client):
    # branch_user (outsider) has no view role
    tok = _login(client, "doc_outsider")
    r = client.get("/api/v1/documents/", headers=_auth(tok))
    assert r.status_code == 403


def test_expiring_endpoint_filters_by_days(seeded, client, db):
    today = date.today()
    document_service.create_document(
        db, owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.municipality_license,
        title="in 5d", branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=5), reminder_days=30,
    )
    document_service.create_document(
        db, owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.civil_defense_license,
        title="in 120d", branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=120), reminder_days=30,
    )
    tok = _login(client, "doc_admin")
    r = client.get("/api/v1/documents/expiring?days=30", headers=_auth(tok))
    assert r.status_code == 200, r.text
    titles = {d["title"] for d in r.json()}
    assert "in 5d" in titles
    assert "in 120d" not in titles


def test_summary_endpoint_returns_counts(seeded, client, db):
    today = date.today()
    document_service.create_document(
        db, owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.municipality_license,
        title="v", branch_id=seeded["branch_a"],
        expiry_date=today + timedelta(days=200),
    )
    document_service.create_document(
        db, owner_type=DocumentOwnerType.branch,
        doc_type=DocumentType.civil_defense_license,
        title="e", branch_id=seeded["branch_a"],
        expiry_date=today - timedelta(days=3),
    )
    tok = _login(client, "doc_admin")
    r = client.get("/api/v1/documents/summary", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["expired"] >= 1
    assert body["valid"] >= 1


def test_upload_and_download_file_round_trip(seeded, client, db, tmp_path, monkeypatch):
    # Redirect upload dir to pytest tmp
    from app.config import settings as cfg
    monkeypatch.setattr(cfg, "DOCUMENTS_UPLOAD_DIR", str(tmp_path))

    tok = _login(client, "doc_admin")
    r = client.post("/api/v1/documents/", json={
        "owner_type": "branch",
        "doc_type": "municipality_license",
        "branch_id": seeded["branch_a"],
        "title": "for file",
        "expiry_date": (date.today() + timedelta(days=200)).isoformat(),
    }, headers=_auth(tok))
    assert r.status_code == 201
    doc_id = r.json()["id"]

    # Upload — pretend PDF (FastAPI infers content-type from tuple)
    files = {"file": ("sample.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r2 = client.post(f"/api/v1/documents/{doc_id}/file",
                     files=files, headers=_auth(tok))
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["file_name"] == "sample.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["size_bytes"] == len(b"%PDF-1.4 fake")

    # Download
    r3 = client.get(f"/api/v1/documents/{doc_id}/file", headers=_auth(tok))
    assert r3.status_code == 200
    assert r3.content == b"%PDF-1.4 fake"


def test_upload_rejects_disallowed_mime(seeded, client, db, tmp_path, monkeypatch):
    from app.config import settings as cfg
    monkeypatch.setattr(cfg, "DOCUMENTS_UPLOAD_DIR", str(tmp_path))
    tok = _login(client, "doc_admin")
    r = client.post("/api/v1/documents/", json={
        "owner_type": "branch",
        "doc_type": "municipality_license",
        "branch_id": seeded["branch_a"],
        "title": "t",
        "expiry_date": (date.today() + timedelta(days=90)).isoformat(),
    }, headers=_auth(tok))
    doc_id = r.json()["id"]

    bad = {"file": ("a.exe", BytesIO(b"MZ\x90\x00"), "application/x-msdownload")}
    r2 = client.post(f"/api/v1/documents/{doc_id}/file",
                     files=bad, headers=_auth(tok))
    assert r2.status_code == 415


def test_renew_endpoint_archives_and_returns_new_doc(seeded, client, db):
    doc = document_service.create_document(
        db, owner_type=DocumentOwnerType.employee,
        doc_type=DocumentType.health_certificate,
        title="health", user_id=seeded["staff_a_id"],
        expiry_date=date.today() + timedelta(days=3), reminder_days=30,
    )
    tok = _login(client, "doc_admin")
    r = client.post(f"/api/v1/documents/{doc.id}/renew", json={
        "new_expiry_date": (date.today() + timedelta(days=400)).isoformat(),
        "new_doc_number": "HC-2027",
    }, headers=_auth(tok))
    assert r.status_code == 201, r.text
    new_body = r.json()
    assert new_body["renewed_from_id"] == doc.id
    assert new_body["doc_number"] == "HC-2027"

    db.refresh(doc)
    assert doc.is_archived is True
