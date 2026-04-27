from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    AreaManagerAssignment,
    Brand,
    Branch,
    BranchBrand,
    Evaluation,
    EvaluationFinalRating,
    EvaluationStatus,
    EvaluationTargetMode,
    EvaluationTemplate,
    EvaluationTemplateVersion,
    EvaluationTemplateVersionStatus,
    EvaluationType,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)
from app.services.evaluation_seed_service import seed_evaluation_templates


def _role(db: Session, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if row:
        return row
    row = Role(name=name, display_name=name.value, description="")
    db.add(row)
    db.flush()
    return row


def _user(db: Session, username: str, role: RoleName, branch_id: int | None = None) -> User:
    r = _role(db, role)
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash("Pass@2026"),
        status=UserStatus.active,
        branch_id=branch_id,
        is_deleted=False,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=r.id))
    db.flush()
    return user


@pytest.fixture
def eval_seed(db: Session):
    wh = Warehouse(warehouse_code="EV-WH", warehouse_name="Eval WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(branch_code="EV-BR", branch_name="Eval Branch", city="Riyadh", area="", warehouse_id=wh.id)
    other_branch = Branch(branch_code="EV-OT", branch_name="Other Branch", city="Dammam", area="", warehouse_id=wh.id)
    db.add_all([branch, other_branch])
    db.flush()
    brand = Brand(name="Eval Brand", active=True)
    db.add(brand)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    admin = _user(db, "ev_admin", RoleName.admin)
    quality = _user(db, "ev_quality", RoleName.quality_manager)
    evaluator = _user(db, "ev_evaluator", RoleName.evaluator)
    branch_manager = _user(db, "ev_branch_manager", RoleName.branch_manager, branch.id)
    area_manager = _user(db, "ev_area_manager", RoleName.area_manager, branch.id)
    employee = _user(db, "ev_employee", RoleName.branch_user, branch.id)
    hr = _user(db, "ev_hr", RoleName.hr_manager)
    db.add(AreaManagerAssignment(user_id=area_manager.id, city="Riyadh", brand_id=brand.id, active=True))
    db.commit()
    return {
        "brand": brand.id,
        "branch": branch.id,
        "other_branch": other_branch.id,
        "admin": admin.id,
        "quality": quality.id,
        "evaluator": evaluator.id,
        "branch_manager": branch_manager.id,
        "area_manager": area_manager.id,
        "employee": employee.id,
        "hr": hr.id,
    }


def _login(client, username: str) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "Pass@2026"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _template(client, seed, name="Evaluation Template", target_mode="BRANCH", evaluation_type="BRANCH") -> dict:
    token = _login(client, "ev_quality")
    r = client.post(
        "/api/evaluations/templates",
        json={"name": name, "brand_id": seed["brand"], "evaluation_type": evaluation_type, "target_mode": target_mode},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _version_payload(weights=True, low_note=False, allow_na=True) -> dict:
    return {
        "notes": "v1",
        "sections": [
            {
                "name": "Service",
                "weight_percent": "50" if weights else None,
                "display_order": 1,
                "active": True,
                "questions": [
                    {
                        "question_text_ar": "Service question",
                        "question_text_en": "Service question",
                        "max_score": "5",
                        "allow_na": allow_na,
                        "requires_note_if_low_score": low_note,
                        "low_score_threshold": "2",
                        "requires_photo": False,
                        "display_order": 1,
                        "active": True,
                    }
                ],
            },
            {
                "name": "Quality",
                "weight_percent": "50" if weights else None,
                "display_order": 2,
                "active": True,
                "questions": [
                    {
                        "question_text_ar": "Quality question",
                        "question_text_en": "Quality question",
                        "max_score": "5",
                        "allow_na": allow_na,
                        "requires_note_if_low_score": False,
                        "low_score_threshold": "2",
                        "requires_photo": False,
                        "display_order": 1,
                        "active": True,
                    }
                ],
            },
        ],
    }


def _version(client, template_id: int, payload: dict | None = None, publish=True) -> dict:
    token = _login(client, "ev_quality")
    r = client.post(f"/api/evaluations/templates/{template_id}/versions", json=payload or _version_payload(), headers=_auth(token))
    assert r.status_code == 201, r.text
    version = r.json()
    if publish:
        p = client.post(f"/api/evaluations/template-versions/{version['id']}/publish", headers=_auth(token))
        assert p.status_code == 200, p.text
        version = p.json()
    return version


def _published_version(client, seed, **kwargs) -> dict:
    template = _template(client, seed, **kwargs)
    return _version(client, template["id"])


def _evaluation(client, seed, version_id: int, branch_id=None, employee_id=None, username="ev_evaluator") -> dict:
    token = _login(client, username)
    r = client.post(
        "/api/evaluations",
        json={
            "template_version_id": version_id,
            "brand_id": seed["brand"],
            "branch_id": seed["branch"] if branch_id is None else branch_id,
            "employee_id": employee_id,
            "evaluation_date": date.today().isoformat(),
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _answer_all(client, evaluation: dict, scores, username="ev_evaluator"):
    token = _login(client, username)
    answers = []
    for answer, value in zip(evaluation["answers"], scores):
        if value == "NA":
            answers.append({"answer_id": answer["id"], "is_na": True, "score": None})
        else:
            answers.append({"answer_id": answer["id"], "is_na": False, "score": str(value), "note": "note" if Decimal(str(value)) <= 2 else None})
    r = client.put(f"/api/evaluations/{evaluation['id']}", json={"answers": answers}, headers=_auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_template_can_be_created(eval_seed, client):
    row = _template(client, eval_seed)
    assert row["name"] == "Evaluation Template"
    assert row["brand_id"] == eval_seed["brand"]


def test_template_version_can_be_created(eval_seed, client):
    template = _template(client, eval_seed)
    version = _version(client, template["id"], publish=False)
    assert version["status"] == EvaluationTemplateVersionStatus.DRAFT.value
    assert len(version["sections"]) == 2


def test_version_publish_fails_if_no_sections(eval_seed, client):
    template = _template(client, eval_seed)
    version = _version(client, template["id"], {"notes": "empty", "sections": []}, publish=False)
    r = client.post(f"/api/evaluations/template-versions/{version['id']}/publish", headers=_auth(_login(client, "ev_quality")))
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.publish_no_sections"


def test_version_publish_fails_if_section_has_no_questions(eval_seed, client):
    template = _template(client, eval_seed)
    version = _version(client, template["id"], {"sections": [{"name": "Empty", "weight_percent": None, "display_order": 1, "active": True, "questions": []}]}, publish=False)
    r = client.post(f"/api/evaluations/template-versions/{version['id']}/publish", headers=_auth(_login(client, "ev_quality")))
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.publish_section_without_questions"


def test_version_publish_fails_if_weights_not_100(eval_seed, client):
    template = _template(client, eval_seed)
    payload = _version_payload()
    payload["sections"][0]["weight_percent"] = "60"
    payload["sections"][1]["weight_percent"] = "20"
    version = _version(client, template["id"], payload, publish=False)
    r = client.post(f"/api/evaluations/template-versions/{version['id']}/publish", headers=_auth(_login(client, "ev_quality")))
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.publish_weights_invalid"


def test_version_publish_succeeds_with_valid_structure(eval_seed, client):
    version = _published_version(client, eval_seed)
    assert version["status"] == EvaluationTemplateVersionStatus.PUBLISHED.value
    assert version["published_at"] is not None


def test_duplicate_template_copies_sections_questions(eval_seed, client):
    version = _published_version(client, eval_seed)
    token = _login(client, "ev_quality")
    dup = client.post(f"/api/evaluations/templates/{version['template_id']}/duplicate", headers=_auth(token))
    assert dup.status_code == 201, dup.text
    versions = client.get(f"/api/evaluations/templates/{dup.json()['id']}/versions", headers=_auth(token))
    assert len(versions.json()[0]["sections"]) == 2
    assert len(versions.json()[0]["sections"][0]["questions"]) == 1


def test_activate_deactivate_works(eval_seed, client):
    template = _template(client, eval_seed)
    token = _login(client, "ev_quality")
    off = client.post(f"/api/evaluations/templates/{template['id']}/deactivate", headers=_auth(token))
    on = client.post(f"/api/evaluations/templates/{template['id']}/activate", headers=_auth(token))
    assert off.json()["active"] is False
    assert on.json()["active"] is True


def test_unauthorized_role_cannot_manage_templates(eval_seed, client):
    r = client.post(
        "/api/evaluations/templates",
        json={"name": "No", "brand_id": eval_seed["brand"], "evaluation_type": "BRANCH", "target_mode": "BRANCH"},
        headers=_auth(_login(client, "ev_branch_manager")),
    )
    assert r.status_code == 403


def test_seeded_templates_exist(db: Session):
    created = seed_evaluation_templates(db)
    assert created >= 9
    names = {row.name for row in db.query(EvaluationTemplate).all()}
    assert "Ronaldos Branch Evaluation" in names
    assert "Onda Barista Placeholder" in names


def test_evaluation_can_be_created_from_published_version(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    assert ev["status"] == EvaluationStatus.DRAFT.value
    assert len(ev["answers"]) == 2


def test_evaluation_creation_fails_from_non_published_version(eval_seed, client):
    template = _template(client, eval_seed)
    version = _version(client, template["id"], publish=False)
    r = client.post(
        "/api/evaluations",
        json={"template_version_id": version["id"], "brand_id": eval_seed["brand"], "branch_id": eval_seed["branch"], "evaluation_date": date.today().isoformat()},
        headers=_auth(_login(client, "ev_evaluator")),
    )
    assert r.status_code == 400


def test_target_mode_branch_validation_works(eval_seed, client):
    version = _published_version(client, eval_seed)
    r = client.post(
        "/api/evaluations",
        json={"template_version_id": version["id"], "brand_id": eval_seed["brand"], "employee_id": eval_seed["employee"], "evaluation_date": date.today().isoformat()},
        headers=_auth(_login(client, "ev_evaluator")),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.invalid_branch_target"


def test_target_mode_employee_validation_works(eval_seed, client):
    version = _published_version(client, eval_seed, name="Employee T", target_mode="EMPLOYEE", evaluation_type="EMPLOYEE")
    ok = _evaluation(client, eval_seed, version["id"], employee_id=eval_seed["employee"])
    assert ok["employee_id"] == eval_seed["employee"]
    r = client.post(
        "/api/evaluations",
        json={"template_version_id": version["id"], "brand_id": eval_seed["brand"], "branch_id": eval_seed["branch"], "evaluation_date": date.today().isoformat()},
        headers=_auth(_login(client, "ev_evaluator")),
    )
    assert r.status_code == 400


def test_target_mode_none_validation_works(eval_seed, client):
    version = _published_version(client, eval_seed, name="None T", target_mode="NONE", evaluation_type="STORE_VISIT")
    token = _login(client, "ev_evaluator")
    ok = client.post("/api/evaluations", json={"template_version_id": version["id"], "brand_id": eval_seed["brand"], "evaluation_date": date.today().isoformat()}, headers=_auth(token))
    bad = client.post("/api/evaluations", json={"template_version_id": version["id"], "brand_id": eval_seed["brand"], "employee_id": eval_seed["employee"], "evaluation_date": date.today().isoformat()}, headers=_auth(token))
    assert ok.status_code == 201, ok.text
    assert bad.status_code == 400


def test_evaluation_creation_fails_if_branch_not_linked_to_brand(eval_seed, client):
    version = _published_version(client, eval_seed)
    r = client.post(
        "/api/evaluations",
        json={
            "template_version_id": version["id"],
            "brand_id": eval_seed["brand"],
            "branch_id": eval_seed["other_branch"],
            "evaluation_date": date.today().isoformat(),
        },
        headers=_auth(_login(client, "ev_evaluator")),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.branch_brand_mismatch"


def test_employee_evaluation_fails_if_employee_not_in_selected_branch(eval_seed, client, db: Session):
    db.add(BranchBrand(branch_id=eval_seed["other_branch"], brand_id=eval_seed["brand"]))
    db.commit()
    version = _published_version(client, eval_seed, name="Employee Scope", target_mode="EMPLOYEE", evaluation_type="EMPLOYEE")
    r = client.post(
        "/api/evaluations",
        json={
            "template_version_id": version["id"],
            "brand_id": eval_seed["brand"],
            "branch_id": eval_seed["other_branch"],
            "employee_id": eval_seed["employee"],
            "evaluation_date": date.today().isoformat(),
        },
        headers=_auth(_login(client, "ev_evaluator")),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.employee_branch_mismatch"


def test_normal_evaluator_cannot_override_evaluator_id(eval_seed, client):
    version = _published_version(client, eval_seed)
    r = client.post(
        "/api/evaluations",
        json={
            "template_version_id": version["id"],
            "brand_id": eval_seed["brand"],
            "branch_id": eval_seed["branch"],
            "evaluation_date": date.today().isoformat(),
            "evaluator_id": eval_seed["quality"],
        },
        headers=_auth(_login(client, "ev_evaluator")),
    )
    assert r.status_code == 403
    assert r.json()["error_code"] == "evaluations.evaluator_override_denied"


def test_quality_manager_can_create_on_behalf_of_another_evaluator(eval_seed, client):
    version = _published_version(client, eval_seed)
    r = client.post(
        "/api/evaluations",
        json={
            "template_version_id": version["id"],
            "brand_id": eval_seed["brand"],
            "branch_id": eval_seed["branch"],
            "evaluation_date": date.today().isoformat(),
            "evaluator_id": eval_seed["evaluator"],
        },
        headers=_auth(_login(client, "ev_quality")),
    )
    assert r.status_code == 201, r.text
    assert r.json()["evaluator_id"] == eval_seed["evaluator"]


def test_answer_score_validation_works(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    r = client.put(
        f"/api/evaluations/{ev['id']}",
        json={"answers": [{"answer_id": ev["answers"][0]["id"], "score": "6", "is_na": False}]},
        headers=_auth(_login(client, "ev_evaluator")),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.score_invalid"


def test_na_exclusion_works_in_scoring(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    _answer_all(client, ev, [5, "NA"])
    submitted = client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    assert submitted.status_code == 200, submitted.text
    assert Decimal(submitted.json()["total_percentage"]) == Decimal("100.00")


def test_weighted_scoring_works(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    _answer_all(client, ev, [5, 3])
    submitted = client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    assert Decimal(submitted.json()["total_percentage"]) == Decimal("80.00")
    assert submitted.json()["final_rating"] == EvaluationFinalRating.GOOD.value


def test_non_weighted_scoring_works(eval_seed, client):
    template = _template(client, eval_seed, name="No Weight")
    version = _version(client, template["id"], _version_payload(weights=False))
    ev = _evaluation(client, eval_seed, version["id"])
    _answer_all(client, ev, [5, 3])
    submitted = client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    assert Decimal(submitted.json()["total_percentage"]) == Decimal("80.00")


def test_low_score_note_requirement_works(eval_seed, client):
    template = _template(client, eval_seed, name="Low Note")
    version = _version(client, template["id"], _version_payload(low_note=True))
    ev = _evaluation(client, eval_seed, version["id"])
    r = client.put(
        f"/api/evaluations/{ev['id']}",
        json={"answers": [{"answer_id": ev["answers"][0]["id"], "score": "1", "is_na": False}]},
        headers=_auth(_login(client, "ev_evaluator")),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.low_score_note_required"


def test_submit_evaluation_works(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    _answer_all(client, ev, [5, 4])
    submitted = client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    assert submitted.status_code == 200
    assert submitted.json()["status"] == EvaluationStatus.SUBMITTED.value


def test_submit_empty_evaluation_fails(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    r = client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.empty"


def test_submitted_evaluation_cannot_be_edited_by_normal_evaluator(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    _answer_all(client, ev, [5, 4])
    client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    r = client.put(f"/api/evaluations/{ev['id']}", json={"general_notes": "late edit"}, headers=_auth(_login(client, "ev_evaluator")))
    assert r.status_code == 400


def test_review_and_close_work(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    _answer_all(client, ev, [5, 4])
    client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    review = client.post(f"/api/evaluations/{ev['id']}/review", json={"notes": "ok"}, headers=_auth(_login(client, "ev_quality")))
    close = client.post(f"/api/evaluations/{ev['id']}/close", json={}, headers=_auth(_login(client, "ev_quality")))
    assert review.status_code == 200, review.text
    assert review.json()["status"] == EvaluationStatus.REVIEWED.value
    assert close.status_code == 200, close.text
    assert close.json()["status"] == EvaluationStatus.CLOSED.value


def test_cancel_transition_works(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    r = client.post(f"/api/evaluations/{ev['id']}/cancel", json={"notes": "cancelled"}, headers=_auth(_login(client, "ev_quality")))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == EvaluationStatus.CANCELLED.value


def test_branch_history_endpoint_returns_scoped_data(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    r = client.get(f"/api/evaluations/reports/branch?branch_id={eval_seed['branch']}", headers=_auth(_login(client, "ev_branch_manager")))
    assert r.status_code == 200, r.text
    assert ev["id"] in {row["id"] for row in r.json()}


def test_employee_history_endpoint_returns_correct_data(eval_seed, client):
    version = _published_version(client, eval_seed, name="Employee Hist", target_mode="EMPLOYEE", evaluation_type="EMPLOYEE")
    ev = _evaluation(client, eval_seed, version["id"], employee_id=eval_seed["employee"])
    r = client.get(f"/api/evaluations/reports/employee?employee_id={eval_seed['employee']}", headers=_auth(_login(client, "ev_hr")))
    assert r.status_code == 200, r.text
    assert ev["id"] in {row["id"] for row in r.json()}


def test_admin_bypass_works(eval_seed, client):
    template = _template(client, eval_seed)
    r = client.post(f"/api/evaluations/templates/{template['id']}/deactivate", headers=_auth(_login(client, "ev_admin")))
    assert r.status_code == 200, r.text
