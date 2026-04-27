from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models import EvaluationActionPlanStatus, EvaluationStatus
from tests.test_evaluation_core_phase1 import (
    _answer_all,
    _auth,
    _evaluation,
    _login,
    _published_version,
    _template,
    _version,
    _version_payload,
    eval_seed,
)


def _submitted_eval(client, seed, scores=(5, 4), **kwargs):
    version = _published_version(client, seed, **kwargs)
    ev = _evaluation(client, seed, version["id"], employee_id=kwargs.get("employee_id"))
    _answer_all(client, ev, scores)
    submitted = client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    assert submitted.status_code == 200, submitted.text
    return submitted.json()


def _create_plan(client, evaluation_id: int, seed, due_date=None, username="ev_quality"):
    r = client.post(
        f"/api/evaluations/{evaluation_id}/action-plans",
        json={
            "branch_id": seed["branch"],
            "issue": "Low score",
            "corrective_action": "Train team",
            "responsible_user_id": seed["quality"],
            "due_date": (due_date or (date.today() + timedelta(days=7))).isoformat(),
        },
        headers=_auth(_login(client, username)),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _file(name="evidence.txt", content=b"evidence"):
    return {"file": (name, content, "text/plain")}


def test_action_plan_can_be_created_from_evaluation(eval_seed, client):
    ev = _submitted_eval(client, eval_seed)
    plan = _create_plan(client, ev["id"], eval_seed)
    assert plan["evaluation_id"] == ev["id"]
    assert plan["status"] == EvaluationActionPlanStatus.OPEN.value


def test_action_plan_validation_works(eval_seed, client):
    ev = _submitted_eval(client, eval_seed)
    r = client.post(
        f"/api/evaluations/{ev['id']}/action-plans",
        json={"issue": "", "corrective_action": "", "responsible_user_id": eval_seed["quality"]},
        headers=_auth(_login(client, "ev_quality")),
    )
    assert r.status_code == 422


def test_action_plan_branch_must_match_evaluation_branch(eval_seed, client):
    ev = _submitted_eval(client, eval_seed)
    r = client.post(
        f"/api/evaluations/{ev['id']}/action-plans",
        json={
            "branch_id": eval_seed["other_branch"],
            "issue": "Wrong branch",
            "corrective_action": "Fix assignment",
            "responsible_user_id": eval_seed["quality"],
            "due_date": (date.today() + timedelta(days=3)).isoformat(),
        },
        headers=_auth(_login(client, "ev_quality")),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.action_plan_branch_mismatch"


def test_action_plan_update_and_close_work(eval_seed, client):
    ev = _submitted_eval(client, eval_seed)
    plan = _create_plan(client, ev["id"], eval_seed)
    token = _login(client, "ev_quality")
    updated = client.put(
        f"/api/evaluations/action-plans/{plan['id']}",
        json={"corrective_action": "Updated action"},
        headers=_auth(token),
    )
    closed = client.post(f"/api/evaluations/action-plans/{plan['id']}/close", headers=_auth(token))
    assert updated.status_code == 200, updated.text
    assert updated.json()["corrective_action"] == "Updated action"
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == EvaluationActionPlanStatus.CLOSED.value
    assert closed.json()["closed_by"] == eval_seed["quality"]


def test_action_plan_status_cannot_be_updated_directly(eval_seed, client):
    ev = _submitted_eval(client, eval_seed)
    plan = _create_plan(client, ev["id"], eval_seed)
    r = client.put(
        f"/api/evaluations/action-plans/{plan['id']}",
        json={"status": EvaluationActionPlanStatus.CLOSED.value},
        headers=_auth(_login(client, "ev_quality")),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.action_plan_status_not_editable"


def test_overdue_filter_works(eval_seed, client):
    ev = _submitted_eval(client, eval_seed)
    plan = _create_plan(client, ev["id"], eval_seed, due_date=date.today() - timedelta(days=1))
    r = client.get("/api/evaluations/action-plans?overdue_only=true", headers=_auth(_login(client, "ev_quality")))
    assert r.status_code == 200, r.text
    assert plan["id"] in {row["id"] for row in r.json()}


def test_unauthorized_role_cannot_manage_action_plans(eval_seed, client):
    ev = _submitted_eval(client, eval_seed)
    r = client.post(
        f"/api/evaluations/{ev['id']}/action-plans",
        json={"branch_id": eval_seed["branch"], "issue": "x", "corrective_action": "y", "responsible_user_id": eval_seed["quality"], "due_date": date.today().isoformat()},
        headers=_auth(_login(client, "ev_branch_manager")),
    )
    assert r.status_code == 403


def test_evaluation_and_answer_attachment_upload_and_delete(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    token = _login(client, "ev_evaluator")
    whole = client.post(f"/api/evaluations/{ev['id']}/attachments", files=_file(), headers=_auth(token))
    answer = client.post(
        f"/api/evaluations/{ev['id']}/attachments",
        data={"answer_id": str(ev["answers"][0]["id"])},
        files=_file("answer.txt", b"answer"),
        headers=_auth(token),
    )
    deleted = client.delete(f"/api/evaluations/attachments/{answer.json()['id']}", headers=_auth(token))
    assert whole.status_code == 201, whole.text
    assert whole.json()["answer_id"] is None
    assert answer.status_code == 201, answer.text
    assert answer.json()["answer_id"] == ev["answers"][0]["id"]
    assert deleted.status_code == 204


def test_answer_attachment_must_belong_to_same_evaluation(eval_seed, client):
    version = _published_version(client, eval_seed)
    ev1 = _evaluation(client, eval_seed, version["id"])
    ev2 = _evaluation(client, eval_seed, version["id"])
    r = client.post(
        f"/api/evaluations/{ev1['id']}/attachments",
        data={"answer_id": str(ev2["answers"][0]["id"])},
        files=_file(),
        headers=_auth(_login(client, "ev_evaluator")),
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.answer_not_in_evaluation"


def _photo_version(client, seed):
    template = _template(client, seed, name="Photo Required")
    payload = _version_payload()
    payload["sections"][0]["questions"][0]["requires_photo"] = True
    return _version(client, template["id"], payload)


def test_required_photo_blocks_submit_without_attachment(eval_seed, client):
    version = _photo_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    _answer_all(client, ev, [5, 4])
    r = client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    assert r.status_code == 400
    assert r.json()["error_code"] == "evaluations.required_photo_missing"


def test_required_photo_submit_succeeds_with_attachment(eval_seed, client):
    version = _photo_version(client, eval_seed)
    ev = _evaluation(client, eval_seed, version["id"])
    _answer_all(client, ev, [5, 4])
    token = _login(client, "ev_evaluator")
    upload = client.post(
        f"/api/evaluations/{ev['id']}/attachments",
        data={"answer_id": str(ev["answers"][0]["id"])},
        files=_file(),
        headers=_auth(token),
    )
    assert upload.status_code == 201, upload.text
    r = client.post(f"/api/evaluations/{ev['id']}/submit", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == EvaluationStatus.SUBMITTED.value


def test_dashboard_flags_and_reports_exports(eval_seed, client):
    low_branch = _submitted_eval(client, eval_seed, scores=(1, 1))
    emp_version = _published_version(client, eval_seed, name="Employee Phase2", target_mode="EMPLOYEE", evaluation_type="EMPLOYEE")
    emp = _evaluation(client, eval_seed, emp_version["id"], employee_id=eval_seed["employee"])
    _answer_all(client, emp, [3, 3])
    emp_submitted = client.post(f"/api/evaluations/{emp['id']}/submit", headers=_auth(_login(client, "ev_evaluator")))
    assert emp_submitted.status_code == 200, emp_submitted.text
    for _ in range(2):
        e = _submitted_eval(client, eval_seed, scores=(1, 5))
        assert e["id"]
    plan = _create_plan(client, low_branch["id"], eval_seed, due_date=date.today() - timedelta(days=1))
    token = _login(client, "ev_quality")
    dashboard = client.get("/api/evaluations/reports/dashboard", headers=_auth(token))
    branch_report = client.get(f"/api/evaluations/reports/branch?branch_id={eval_seed['branch']}", headers=_auth(token))
    employee_report = client.get(f"/api/evaluations/reports/employee?employee_id={eval_seed['employee']}", headers=_auth(token))
    plan_report = client.get("/api/evaluations/reports/action-plans?overdue_only=true", headers=_auth(token))
    pdf = client.get(f"/api/evaluations/{low_branch['id']}/export/pdf", headers=_auth(token))
    excel = client.get("/api/evaluations/reports/export/excel", headers=_auth(token))
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert {"average_score_by_brand", "repeated_weak_points", "flags", "overdue_action_plans"}.issubset(body.keys())
    assert body["flags"]["branch_below_60"]
    assert body["flags"]["employee_below_70"]
    assert body["flags"]["repeated_low_score"]
    assert any(p["id"] == plan["id"] for p in body["flags"]["overdue_action_plan"])
    assert "hygiene_below_threshold" in body["flags"]
    assert "food_safety_below_threshold" in body["flags"]
    assert branch_report.status_code == 200
    assert employee_report.status_code == 200
    assert plan_report.status_code == 200
    assert pdf.status_code == 200
    assert "text/html" in pdf.headers["content-type"]
    assert excel.status_code == 200
    assert "spreadsheetml" in excel.headers["content-type"]


def test_branch_manager_cannot_access_out_of_scope_data(eval_seed, client):
    _submitted_eval(client, eval_seed)
    r = client.get(f"/api/evaluations/reports/branch?branch_id={eval_seed['other_branch']}", headers=_auth(_login(client, "ev_branch_manager")))
    assert r.status_code == 200
    assert r.json() == []


def test_area_manager_scope_and_admin_bypass_still_work(eval_seed, client):
    ev = _submitted_eval(client, eval_seed)
    area = client.get(f"/api/evaluations/reports/branch?branch_id={eval_seed['branch']}", headers=_auth(_login(client, "ev_area_manager")))
    admin = client.get(f"/api/evaluations/{ev['id']}", headers=_auth(_login(client, "ev_admin")))
    assert area.status_code == 200
    assert ev["id"] in {row["id"] for row in area.json()}
    assert admin.status_code == 200


def test_phase1_core_lifecycle_still_works(eval_seed, client):
    ev = _submitted_eval(client, eval_seed, scores=(5, 5))
    review = client.post(f"/api/evaluations/{ev['id']}/review", json={}, headers=_auth(_login(client, "ev_quality")))
    close = client.post(f"/api/evaluations/{ev['id']}/close", json={}, headers=_auth(_login(client, "ev_quality")))
    assert review.status_code == 200
    assert close.status_code == 200
    assert close.json()["status"] == EvaluationStatus.CLOSED.value
