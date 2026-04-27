from app.core.security import get_password_hash
from app.models import AuditFinding, Role, RoleName, User, UserRole, UserStatus


def _role(db, name: RoleName, display_name: str | None = None):
    row = db.query(Role).filter(Role.name == name).first()
    if row:
        return row
    row = Role(name=name, display_name=display_name or name.value, description="")
    db.add(row)
    db.flush()
    return row


def _user(db, username: str, roles: list[RoleName]):
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash("Raed@2025"),
        status=UserStatus.active,
        is_deleted=False,
    )
    db.add(user)
    db.flush()
    for role_name in roles:
        role = _role(db, role_name)
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()
    return user


def _login(client, username: str, password: str = "Raed@2025") -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_internal_auditor_can_create_and_view_findings(client, db):
    _user(db, "audit.officer", [RoleName.internal_auditor])
    db.commit()
    token = _login(client, "audit.officer")

    create_res = client.post(
        "/api/v1/audit/findings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "entity_type": "branch_request",
            "entity_id": 101,
            "severity": "warning",
            "title": "Approval looked too fast",
            "description": "The approval time appears unusually short and should be reviewed.",
        },
    )
    assert create_res.status_code == 200, create_res.text
    finding_id = create_res.json()["id"]

    list_res = client.get("/api/v1/audit/findings", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 200, list_res.text
    assert list_res.json()["total"] >= 1

    detail_res = client.get(f"/api/v1/audit/findings/{finding_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail_res.status_code == 200, detail_res.text
    assert detail_res.json()["finding_no"].startswith("AF-")


def test_internal_auditor_is_blocked_from_operational_writes(client, db):
    _user(db, "audit.blocked", [RoleName.internal_auditor])
    db.commit()
    token = _login(client, "audit.blocked")

    res = client.post(
        "/api/v1/master/kitchens",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Forbidden Kitchen", "city": "Riyadh", "active": True, "section_ids": []},
    )
    assert res.status_code == 403, res.text
    assert "read-only" in res.json()["detail"].lower()


def test_manager_can_acknowledge_auditor_finding(client, db):
    auditor = _user(db, "audit.owner", [RoleName.internal_auditor])
    manager = _user(db, "ops.manager", [RoleName.operations_manager])
    row = AuditFinding(
        finding_no="AF-900001",
        entity_type="warehouse_line",
        entity_id=77,
        severity="violation",
        title="Missing delay reason",
        description="Partial issue without delay reason.",
        created_by=auditor.id,
        status="open",
    )
    db.add(row)
    db.commit()

    token = _login(client, "ops.manager")
    res = client.post(
        f"/api/v1/audit/findings/{row.id}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"response_text": "Acknowledged and team retrained on the policy."},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "acknowledged"


def test_internal_auditor_can_read_audit_logs(client, db):
    _user(db, "audit.reader", [RoleName.internal_auditor])
    db.commit()
    token = _login(client, "audit.reader")
    res = client.get("/api/v1/audit/logs", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert "items" in res.json()


def test_internal_auditor_exports_and_dashboard_shape(client, db):
    auditor = _user(db, "audit.exporter", [RoleName.internal_auditor])
    db.add(
        AuditFinding(
            finding_no="AF-900002",
            entity_type="quality_visit",
            entity_id=12,
            severity="warning",
            title="Export shape check",
            description="Ensure exports and dashboard include richer audit fields.",
            created_by=auditor.id,
            status="open",
        )
    )
    db.commit()
    token = _login(client, "audit.exporter")

    export_res = client.get("/api/v1/audit/findings/export.csv", headers={"Authorization": f"Bearer {token}"})
    assert export_res.status_code == 200, export_res.text
    assert "created_by_name" in export_res.text
    assert "response_text" in export_res.text

    dashboard_res = client.get("/api/v1/audit/findings/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert dashboard_res.status_code == 200, dashboard_res.text
    payload = dashboard_res.json()
    assert "findings_created_last_7_days" in payload
    assert "unacknowledged_findings_older_than_7_days" in payload
    assert "average_approval_time_seconds" in payload
    assert "findings_by_entity_type" in payload
    assert "oldest_open_findings" in payload


def test_internal_auditor_can_update_own_finding_but_not_others(client, db):
    owner = _user(db, "audit.editor", [RoleName.internal_auditor])
    other = _user(db, "audit.other", [RoleName.internal_auditor])
    own_row = AuditFinding(
        finding_no="AF-900010",
        entity_type="branch_request",
        entity_id=1,
        severity="warning",
        title="Original title",
        description="Original description for own finding.",
        created_by=owner.id,
        status="open",
    )
    other_row = AuditFinding(
        finding_no="AF-900011",
        entity_type="delivery_order",
        entity_id=2,
        severity="info",
        title="Other title",
        description="Original description for another user's finding.",
        created_by=other.id,
        status="open",
    )
    db.add_all([own_row, other_row])
    db.commit()

    token = _login(client, "audit.editor")
    own_res = client.patch(
        f"/api/v1/audit/findings/{own_row.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Updated title"},
    )
    assert own_res.status_code == 200, own_res.text
    assert own_res.json()["title"] == "Updated title"

    blocked_res = client.patch(
        f"/api/v1/audit/findings/{other_row.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Should not work"},
    )
    assert blocked_res.status_code == 403, blocked_res.text


def test_internal_auditor_cannot_acknowledge_findings(client, db):
    auditor = _user(db, "audit.noack", [RoleName.internal_auditor])
    row = AuditFinding(
        finding_no="AF-900012",
        entity_type="warehouse_line",
        entity_id=33,
        severity="violation",
        title="No self acknowledge",
        description="Auditor should not acknowledge findings.",
        created_by=auditor.id,
        status="open",
    )
    db.add(row)
    db.commit()

    token = _login(client, "audit.noack")
    res = client.post(
        f"/api/v1/audit/findings/{row.id}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"response_text": "Should be blocked."},
    )
    assert res.status_code == 403, res.text
