from app.core.security import get_password_hash
from app.models import Branch, BranchEmployee, Role, RoleName, User, UserRole, Warehouse


def _role(db, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if row:
        return row
    row = Role(name=name, display_name=name.value, description="")
    db.add(row)
    db.flush()
    return row


def _user(db, username: str, role_name: RoleName, branch_id=None) -> User:
    role = _role(db, role_name)
    row = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash("Pass@2026"),
        branch_id=branch_id,
        status="active",
        is_deleted=False,
    )
    db.add(row)
    db.flush()
    db.add(UserRole(user_id=row.id, role_id=role.id))
    db.flush()
    return row


def _login(client, username: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "Pass@2026"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed(db):
    wh = Warehouse(warehouse_code="BE-WH-1", warehouse_name="BE WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()

    branch_one = Branch(branch_code="BE-BR-1", branch_name="Branch One", city="Riyadh", area="Olaya", warehouse_id=wh.id)
    branch_two = Branch(branch_code="BE-BR-2", branch_name="Branch Two", city="Riyadh", area="Malqa", warehouse_id=wh.id)
    db.add_all([branch_one, branch_two])
    db.flush()

    mgr_one = _user(db, "be_mgr_one", RoleName.branch_manager, branch_one.id)
    mgr_two = _user(db, "be_mgr_two", RoleName.branch_manager, branch_two.id)
    admin = _user(db, "be_admin", RoleName.admin)
    db.commit()
    return {"branch_one": branch_one.id, "branch_two": branch_two.id, "mgr_one": mgr_one.id, "mgr_two": mgr_two.id, "admin": admin.id}


def test_branch_manager_can_create_employee_in_own_branch(client, db):
    seed = _seed(db)
    token = _login(client, "be_mgr_one")

    resp = client.post(
        "/api/v1/branch-employees/",
        json={
            "full_name": "Ali Hassan",
            "job_title": "Cashier",
            "work_number": "BR1-001",
            "phone": "0500000001",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["branch_id"] == seed["branch_one"]
    assert body["full_name"] == "Ali Hassan"
    assert body["work_number"] == "BR1-001"


def test_branch_manager_cannot_create_employee_for_other_branch(client, db):
    seed = _seed(db)
    token = _login(client, "be_mgr_one")

    resp = client.post(
        "/api/v1/branch-employees/",
        json={
            "branch_id": seed["branch_two"],
            "full_name": "Cross Branch",
            "job_title": "Cook",
            "work_number": "BR2-001",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 403, resp.text


def test_branch_manager_can_edit_and_deactivate_only_own_employee(client, db):
    seed = _seed(db)
    own = BranchEmployee(branch_id=seed["branch_one"], full_name="Own User", job_title="Barista", work_number="OWN-1", active=True)
    other = BranchEmployee(branch_id=seed["branch_two"], full_name="Other User", job_title="Cook", work_number="OTH-1", active=True)
    db.add_all([own, other])
    db.commit()

    token = _login(client, "be_mgr_one")

    update_resp = client.patch(
        f"/api/v1/branch-employees/{own.id}",
        json={"job_title": "Senior Barista", "phone": "0551111111"},
        headers=_auth(token),
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["job_title"] == "Senior Barista"

    deactivate_resp = client.post(
        f"/api/v1/branch-employees/{own.id}/deactivate",
        json={"active": False},
        headers=_auth(token),
    )
    assert deactivate_resp.status_code == 200, deactivate_resp.text
    assert deactivate_resp.json()["active"] is False

    forbidden_resp = client.patch(
        f"/api/v1/branch-employees/{other.id}",
        json={"job_title": "Should Fail"},
        headers=_auth(token),
    )
    assert forbidden_resp.status_code == 403, forbidden_resp.text


def test_admin_can_transfer_employee_between_branches(client, db):
    seed = _seed(db)
    employee = BranchEmployee(branch_id=seed["branch_one"], full_name="Transfer User", job_title="Supervisor", work_number="TR-1", active=True)
    db.add(employee)
    db.commit()

    token = _login(client, "be_admin")
    resp = client.patch(
        f"/api/v1/branch-employees/{employee.id}",
        json={"branch_id": seed["branch_two"], "job_title": "Transferred Supervisor"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["branch_id"] == seed["branch_two"]
    assert body["job_title"] == "Transferred Supervisor"
