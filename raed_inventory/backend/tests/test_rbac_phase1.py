"""Phase 1 RBAC hardening tests."""
from app.core.area_manager_scope import branch_in_area_manager_scope, get_area_manager_branch_ids
from app.core.auth import can_access_branch, is_platform_admin
from app.core.security import get_password_hash
from app.models import (
    AreaManagerAssignment,
    Branch,
    BranchBrand,
    Brand,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)


def _role(db, name: RoleName):
    row = db.query(Role).filter(Role.name == name).first()
    if row:
        return row
    row = Role(name=name, display_name=name.value, description=name.value)
    db.add(row)
    db.flush()
    return row


def _user(db, username: str, roles: list[RoleName], **kwargs) -> User:
    row = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("Raed@2025"),
        full_name=username,
        status=UserStatus.active,
        is_deleted=False,
        **kwargs,
    )
    db.add(row)
    db.flush()
    for role_name in roles:
        db.add(UserRole(user_id=row.id, role_id=_role(db, role_name).id))
    db.flush()
    return row


def _login(client, username: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": "Raed@2025"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _seed_branch(db, code: str, city: str, brand: Brand, warehouse: Warehouse) -> Branch:
    branch = Branch(
        branch_code=code,
        branch_name=code,
        city=city,
        area=city,
        warehouse_id=warehouse.id,
        active=True,
        is_deleted=False,
    )
    db.add(branch)
    db.flush()
    db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
    db.flush()
    return branch


def test_delivery_user_without_warehouse_gets_403(client, db):
    wh = Warehouse(warehouse_code="WH-RBAC", warehouse_name="RBAC WH", location="Riyadh", active=True, is_deleted=False)
    db.add(wh)
    db.flush()
    brand = Brand(name="RBAC Brand", active=True)
    db.add(brand)
    db.flush()
    _seed_branch(db, "BR-RBAC-1", "Riyadh", brand, wh)
    _user(db, "delivery.no.wh", [RoleName.delivery_user], warehouse_id=None)
    db.commit()

    token = _login(client, "delivery.no.wh")
    res = client.get("/api/v1/delivery-orders", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_area_manager_scope_uses_assignment_not_home_branch(client, db):
    wh = Warehouse(warehouse_code="WH-RBAC2", warehouse_name="RBAC WH2", location="Riyadh", active=True, is_deleted=False)
    db.add(wh)
    db.flush()
    brand = Brand(name="RBAC Brand 2", active=True)
    db.add(brand)
    db.flush()

    branch_riyadh = _seed_branch(db, "RBAC-RY-1", "Riyadh", brand, wh)
    branch_dammam = _seed_branch(db, "RBAC-DM-1", "Dammam", brand, wh)

    manager = _user(
        db,
        "am.rbac",
        [RoleName.area_manager],
        branch_id=branch_dammam.id,
    )
    db.add(
        AreaManagerAssignment(
            user_id=manager.id,
            city="Riyadh",
            brand_id=brand.id,
            active=True,
        )
    )
    db.commit()

    assert branch_in_area_manager_scope(manager, db, branch_riyadh.id) is True
    assert branch_in_area_manager_scope(manager, db, branch_dammam.id) is False
    assert can_access_branch(manager, branch_riyadh.id, db) is True
    assert can_access_branch(manager, branch_dammam.id, db) is False
    scoped = get_area_manager_branch_ids(manager, db)
    assert branch_riyadh.id in scoped
    assert branch_dammam.id not in scoped


def test_internal_auditor_not_platform_admin(db):
    auditor = _user(db, "audit.rbac", [RoleName.internal_auditor])
    db.commit()
    assert is_platform_admin(auditor) is False
