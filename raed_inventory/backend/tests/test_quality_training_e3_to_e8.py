"""
Quality & Training — Phase E3→E8 coverage.

Highlights:
  * RBAC separation of duties (visitor ≠ reviewer, trainer ≠ approver).
  * Auto verdict derivation from overall score.
  * Duplicate-open prevention (can't have two drafts for same trainee+template).
  * Open-actions filters (overdue, due_within, owner).
  * Bulk resolve behavior (resolved/skipped/failed tallies).
  * Signatures on visits and assessments.
  * Section analytics + compliance trend endpoint shape.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    Branch,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
    Warehouse,
    QualityVisit,
    QualityVisitResponse,
    QualityVisitSection,
    QualityVisitItem,
    QualityVisitStatus,
    QualityResponseStatus,
    QualityItemResponseType,
    TrainingTemplate,
    TrainingTemplateSection,
    TrainingTemplateItem,
    TrainingAssessment,
    TrainingAssessmentItem,
    TrainingRoleType,
    AssessmentStatus,
    AssessmentVerdict,
)


# ═══════════════════════════════════════════════════════════════════════════
# Seeders
# ═══════════════════════════════════════════════════════════════════════════
def _ensure_role(db: Session, name: RoleName) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if role is None:
        role = Role(name=name, display_name=name.value, description="")
        db.add(role)
        db.flush()
    return role


def _seed_common(db: Session) -> dict:
    wh = Warehouse(warehouse_code="WH-QT", warehouse_name="QT WH",
                   location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(branch_code="QT-B1", branch_name="QT Branch",
                    city="الرياض", area="الرياض", warehouse_id=wh.id, active=True)
    db.add(branch)
    db.flush()

    role_visitor = _ensure_role(db, RoleName.quality_visitor)
    role_qm = _ensure_role(db, RoleName.quality_manager)
    role_bm = _ensure_role(db, RoleName.branch_manager)
    role_am = _ensure_role(db, RoleName.area_manager)
    role_om = _ensure_role(db, RoleName.operations_manager)

    visitor = User(username="qt_visitor", email="v@x.com", full_name="V",
                   hashed_password=get_password_hash("Pass@2026"),
                   status=UserStatus.active, branch_id=branch.id, is_deleted=False)
    qm = User(username="qt_qm", email="qm@x.com", full_name="QM",
              hashed_password=get_password_hash("Pass@2026"),
              status=UserStatus.active, branch_id=branch.id, is_deleted=False)
    bm = User(username="qt_bm", email="bm@x.com", full_name="BM",
              hashed_password=get_password_hash("Pass@2026"),
              status=UserStatus.active, branch_id=branch.id, is_deleted=False)
    am = User(username="qt_am", email="am@x.com", full_name="AM",
              hashed_password=get_password_hash("Pass@2026"),
              status=UserStatus.active, branch_id=branch.id, is_deleted=False)
    om = User(username="qt_om", email="om@x.com", full_name="OM",
              hashed_password=get_password_hash("Pass@2026"),
              status=UserStatus.active, branch_id=branch.id, is_deleted=False)
    trainee = User(username="qt_trainee", email="tr@x.com", full_name="TR",
                   hashed_password=get_password_hash("Pass@2026"),
                   status=UserStatus.active, branch_id=branch.id, is_deleted=False)
    db.add_all([visitor, qm, bm, am, om, trainee])
    db.flush()

    db.add_all([
        UserRole(user_id=visitor.id, role_id=role_visitor.id),
        UserRole(user_id=qm.id, role_id=role_qm.id),
        UserRole(user_id=bm.id, role_id=role_bm.id),
        UserRole(user_id=am.id, role_id=role_am.id),
        UserRole(user_id=om.id, role_id=role_om.id),
    ])

    # Quality checklist
    sec = QualityVisitSection(
        name_ar="نظافة", name_en="Hygiene", weight=100.0, order=1, is_active=True
    )
    db.add(sec)
    db.flush()
    item_yn = QualityVisitItem(
        section_id=sec.id, text_ar="بند YN", text_en="YN item",
        response_type=QualityItemResponseType.yes_no, order=1, is_active=True,
    )
    db.add(item_yn)
    db.flush()

    # Training template
    tmpl = TrainingTemplate(
        name_ar="قالب فروع", name_en="Branch tmpl",
        role_type=TrainingRoleType.branch_employee, version="v1.0", is_active=True,
    )
    db.add(tmpl)
    db.flush()
    tsec = TrainingTemplateSection(
        template_id=tmpl.id, name_ar="الأداء", name_en="Performance",
        order=1,
    )
    db.add(tsec)
    db.flush()
    titem = TrainingTemplateItem(
        section_id=tsec.id, text_ar="بند 1", text_en="Item 1", order=1,
    )
    db.add(titem)
    db.flush()

    db.commit()
    return {
        "branch_id": branch.id,
        "visitor_id": visitor.id, "qm_id": qm.id, "bm_id": bm.id,
        "am_id": am.id, "om_id": om.id, "trainee_id": trainee.id,
        "section_id": sec.id, "item_id": item_yn.id,
        "template_id": tmpl.id, "t_item_id": titem.id,
    }


def _login(client, username: str) -> str:
    r = client.post("/api/v1/auth/login",
                    json={"username": username, "password": "Pass@2026"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ═══════════════════════════════════════════════════════════════════════════
# E3/E4: Quality visit lifecycle + RBAC separation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def seeded(client, db: Session):
    return _seed_common(db)


def _create_visit(client, token, seeded, answers):
    return client.post(
        "/api/v1/quality/",
        json={
            "branch_id": seeded["branch_id"],
            "visitor_id": seeded["visitor_id"],
            "visit_date": date.today().isoformat(),
            "shift": "morning",
            "responses": answers,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def test_quality_visitor_cannot_review_own_visit(seeded, client):
    visitor_tok = _login(client, "qt_visitor")
    r = _create_visit(client, visitor_tok, seeded, [
        {"item_id": seeded["item_id"], "status": "yes"},
    ])
    assert r.status_code == 201, r.text
    visit_id = r.json()["id"]

    # submit
    r2 = client.post(f"/api/v1/quality/{visit_id}/submit",
                     headers={"Authorization": f"Bearer {visitor_tok}"})
    assert r2.status_code == 200, r2.text

    # attempt to review — visitor shouldn't have permission at all (quality_visitor not in _REVIEWER_ROLES)
    r3 = client.post(f"/api/v1/quality/{visit_id}/review", json={},
                     headers={"Authorization": f"Bearer {visitor_tok}"})
    assert r3.status_code == 403


def test_quality_manager_cannot_review_their_own_visit(seeded, client, db):
    # QM does double duty as visitor — the service must still prevent self-review
    qm_tok = _login(client, "qt_qm")
    # create a visit with visitor_id = qm user's id
    r = client.post(
        "/api/v1/quality/",
        json={
            "branch_id": seeded["branch_id"],
            "visitor_id": seeded["qm_id"],
            "visit_date": date.today().isoformat(),
            "shift": "morning",
            "responses": [{"item_id": seeded["item_id"], "status": "yes"}],
        },
        headers={"Authorization": f"Bearer {qm_tok}"},
    )
    assert r.status_code == 201
    visit_id = r.json()["id"]
    client.post(f"/api/v1/quality/{visit_id}/submit",
                headers={"Authorization": f"Bearer {qm_tok}"})

    r2 = client.post(f"/api/v1/quality/{visit_id}/review", json={},
                     headers={"Authorization": f"Bearer {qm_tok}"})
    assert r2.status_code == 403
    assert "مراجعة زيارتك" in r2.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# E7/E8: Open actions filters + bulk resolve
# ═══════════════════════════════════════════════════════════════════════════
def _make_visit_with_no_response(db, seeded, due_date=None, owner="علي"):
    visit = QualityVisit(
        branch_id=seeded["branch_id"],
        visitor_id=seeded["visitor_id"],
        visit_date=date.today(),
        status=QualityVisitStatus.reviewed,
    )
    db.add(visit)
    db.flush()
    resp = QualityVisitResponse(
        visit_id=visit.id, item_id=seeded["item_id"],
        status=QualityResponseStatus.no,
        corrective_action="fix it",
        action_owner=owner,
        due_date=due_date,
        is_resolved=False,
    )
    db.add(resp)
    db.commit()
    return visit, resp


def test_open_actions_overdue_filter(seeded, client, db):
    _make_visit_with_no_response(db, seeded, due_date=date.today() - timedelta(days=2))
    _make_visit_with_no_response(db, seeded, due_date=date.today() + timedelta(days=30))
    tok = _login(client, "qt_qm")
    r = client.get("/api/v1/quality/open-actions?overdue_only=true",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["is_overdue"] is True


def test_open_actions_owner_filter(seeded, client, db):
    _make_visit_with_no_response(db, seeded, owner="علي")
    _make_visit_with_no_response(db, seeded, owner="محمد")
    tok = _login(client, "qt_qm")
    r = client.get("/api/v1/quality/open-actions?owner=محمد",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    rows = r.json()
    assert all(row["action_owner"] == "محمد" for row in rows)
    assert len(rows) == 1


def test_list_action_owners_dedup(seeded, client, db):
    _make_visit_with_no_response(db, seeded, owner="علي")
    _make_visit_with_no_response(db, seeded, owner="علي")
    _make_visit_with_no_response(db, seeded, owner="سارة")
    tok = _login(client, "qt_qm")
    r = client.get("/api/v1/quality/open-actions/owners",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    owners = r.json()
    assert sorted(owners) == sorted(["علي", "سارة"])


def test_bulk_resolve_counts(seeded, client, db):
    _, r1 = _make_visit_with_no_response(db, seeded, owner="x")
    _, r2 = _make_visit_with_no_response(db, seeded, owner="x")
    # Pre-mark r2 as already resolved → should appear as skipped
    r2_id_skip = r2.id
    r2.is_resolved = True
    db.commit()

    tok = _login(client, "qt_qm")
    r = client.post(
        "/api/v1/quality/open-actions/bulk-resolve",
        json={"response_ids": [r1.id, r2_id_skip, 99999], "notes": "ok"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resolved"] == 1
    assert body["skipped"] == 1
    assert body["failed"] == [99999]


# ═══════════════════════════════════════════════════════════════════════════
# E8.2: Signatures on visit
# ═══════════════════════════════════════════════════════════════════════════
def test_sign_visit_visitor_and_branch_mgr(seeded, client, db):
    visitor_tok = _login(client, "qt_visitor")
    bm_tok = _login(client, "qt_bm")

    r = _create_visit(client, visitor_tok, seeded, [
        {"item_id": seeded["item_id"], "status": "yes"},
    ])
    visit_id = r.json()["id"]
    client.post(f"/api/v1/quality/{visit_id}/submit",
                headers={"Authorization": f"Bearer {visitor_tok}"})

    # visitor signs
    r2 = client.post(
        f"/api/v1/quality/{visit_id}/sign",
        json={"role": "visitor", "signature": "أحمد علي"},
        headers={"Authorization": f"Bearer {visitor_tok}"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["visitor_signature"] == "أحمد علي"

    # branch manager signs
    r3 = client.post(
        f"/api/v1/quality/{visit_id}/sign",
        json={"role": "branch_manager", "signature": "مدير الفرع"},
        headers={"Authorization": f"Bearer {bm_tok}"},
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["branch_mgr_signature"] == "مدير الفرع"


def test_sign_visit_rejects_short_signature(seeded, client, db):
    visitor_tok = _login(client, "qt_visitor")
    r = _create_visit(client, visitor_tok, seeded, [
        {"item_id": seeded["item_id"], "status": "yes"},
    ])
    visit_id = r.json()["id"]
    client.post(f"/api/v1/quality/{visit_id}/submit",
                headers={"Authorization": f"Bearer {visitor_tok}"})

    r2 = client.post(
        f"/api/v1/quality/{visit_id}/sign",
        json={"role": "visitor", "signature": "a"},
        headers={"Authorization": f"Bearer {visitor_tok}"},
    )
    assert r2.status_code == 422  # pydantic min_length


# ═══════════════════════════════════════════════════════════════════════════
# E3/E4: Training — duplicate-open prevention + auto verdict + separation
# ═══════════════════════════════════════════════════════════════════════════
def _create_assessment(client, token, seeded, trainer_id, scores):
    return client.post(
        "/api/v1/training/",
        json={
            "template_id": seeded["template_id"],
            "trainee_id": seeded["trainee_id"],
            "trainer_id": trainer_id,
            "branch_id": seeded["branch_id"],
            "assessment_date": date.today().isoformat(),
            "items": [{"item_id": seeded["t_item_id"], "score": s} for s in scores],
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def test_training_duplicate_open_prevented(seeded, client, db):
    am_tok = _login(client, "qt_am")
    r1 = _create_assessment(client, am_tok, seeded, seeded["am_id"], [4])
    assert r1.status_code == 201

    r2 = _create_assessment(client, am_tok, seeded, seeded["am_id"], [5])
    assert r2.status_code == 409
    assert "تقييم مفتوح" in r2.json()["detail"]


def test_training_approver_cannot_approve_own(seeded, client, db):
    # Make the AM user *also* an approver (quality_manager) so they can attempt to approve
    role_qm = _ensure_role(db, RoleName.quality_manager)
    db.add(UserRole(user_id=seeded["am_id"], role_id=role_qm.id))
    db.commit()

    am_tok = _login(client, "qt_am")
    r1 = _create_assessment(client, am_tok, seeded, seeded["am_id"], [5])
    assert r1.status_code == 201
    aid = r1.json()["id"]
    client.post(f"/api/v1/training/{aid}/submit",
                headers={"Authorization": f"Bearer {am_tok}"})

    # Same user (also quality_manager now) tries to approve — must be blocked
    r = client.post(
        f"/api/v1/training/{aid}/approve",
        json={"verdict": None, "re_eval_date": None, "dev_plan": None},
        headers={"Authorization": f"Bearer {am_tok}"},
    )
    assert r.status_code == 403


def test_training_verdict_auto_derivation(seeded, client, db):
    am_tok = _login(client, "qt_am")
    qm_tok = _login(client, "qt_qm")

    # score 5/5 → 100% → passed
    r = _create_assessment(client, am_tok, seeded, seeded["am_id"], [5])
    aid = r.json()["id"]
    client.post(f"/api/v1/training/{aid}/submit",
                headers={"Authorization": f"Bearer {am_tok}"})
    app = client.post(
        f"/api/v1/training/{aid}/approve",
        json={"verdict": None, "re_eval_date": None, "dev_plan": None},
        headers={"Authorization": f"Bearer {qm_tok}"},
    )
    assert app.status_code == 200, app.text
    assert app.json()["verdict"] == AssessmentVerdict.passed.value


def test_training_sign_assessment(seeded, client, db):
    am_tok = _login(client, "qt_am")
    qm_tok = _login(client, "qt_qm")
    r = _create_assessment(client, am_tok, seeded, seeded["am_id"], [4])
    aid = r.json()["id"]
    client.post(f"/api/v1/training/{aid}/submit",
                headers={"Authorization": f"Bearer {am_tok}"})

    # evaluator sign (self)
    s1 = client.post(
        f"/api/v1/training/{aid}/sign",
        json={"role": "evaluator", "signature": "AM User"},
        headers={"Authorization": f"Bearer {am_tok}"},
    )
    assert s1.status_code == 200, s1.text
    assert s1.json()["evaluator_signature"] == "AM User"

    # approver sign (different user)
    s2 = client.post(
        f"/api/v1/training/{aid}/sign",
        json={"role": "approver", "signature": "QM User"},
        headers={"Authorization": f"Bearer {qm_tok}"},
    )
    assert s2.status_code == 200, s2.text


# ═══════════════════════════════════════════════════════════════════════════
# E7: Analytics endpoint shape
# ═══════════════════════════════════════════════════════════════════════════
def test_compliance_trend_endpoint_returns_list(seeded, client, db):
    tok = _login(client, "qt_qm")
    r = client.get("/api/v1/quality/analytics/compliance-trend?months=3",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_section_compliance_endpoint_returns_list(seeded, client, db):
    tok = _login(client, "qt_qm")
    r = client.get("/api/v1/quality/analytics/section-compliance?months=3",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_verdict_distribution_endpoint_returns_list(seeded, client, db):
    tok = _login(client, "qt_qm")
    r = client.get("/api/v1/training/analytics/verdict-distribution?months=3",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
