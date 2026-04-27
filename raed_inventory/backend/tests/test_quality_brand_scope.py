from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    Branch,
    QualityItemResponseType,
    QualityVisit,
    QualityVisitItem,
    QualityVisitSection,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)


def _ensure_role(db: Session, name: RoleName) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if role is None:
        role = Role(name=name, display_name=name.value, description="")
        db.add(role)
        db.flush()
    return role


def _login(client, username: str) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "Pass@2026"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def quality_brand_seed(db: Session):
    wh = Warehouse(warehouse_code="WH-QB", warehouse_name="Quality WH", location="Riyadh", active=True)
    db.add(wh)
    db.flush()
    branch = Branch(
        branch_code="QB-PIZZA-15",
        branch_name="Pizza 15 - Ras Tanura",
        city="Ras Tanura",
        area="Ras Tanura",
        warehouse_id=wh.id,
        active=True,
    )
    db.add(branch)
    db.flush()

    visitor_role = _ensure_role(db, RoleName.quality_visitor)
    visitor = User(
        username="qb_visitor",
        email="qb_visitor@example.com",
        full_name="Quality Visitor",
        hashed_password=get_password_hash("Pass@2026"),
        status=UserStatus.active,
        branch_id=branch.id,
        is_deleted=False,
    )
    db.add(visitor)
    db.flush()
    db.add(UserRole(user_id=visitor.id, role_id=visitor_role.id))

    onda_sec = QualityVisitSection(
        brand_key="onda",
        name_ar="نظافة القهوة",
        name_en="Coffee Hygiene",
        order=1,
        weight=100,
        is_active=True,
    )
    ron_sec = QualityVisitSection(
        brand_key="ronaldos",
        name_ar="جودة البيتزا",
        name_en="Pizza Quality",
        order=1,
        weight=100,
        is_active=True,
    )
    db.add_all([onda_sec, ron_sec])
    db.flush()

    onda_item = QualityVisitItem(
        section_id=onda_sec.id,
        text_ar="نظافة منطقة تحضير القهوة",
        text_en="Coffee prep area cleanliness",
        response_type=QualityItemResponseType.yes_no,
        order=1,
        is_active=True,
    )
    ron_item = QualityVisitItem(
        section_id=ron_sec.id,
        text_ar="جاهزية الفرن قبل التشغيل",
        text_en="Oven readiness before operation",
        response_type=QualityItemResponseType.yes_no,
        order=1,
        is_active=True,
    )
    db.add_all([onda_item, ron_item])
    db.commit()
    return {"branch": branch.id, "visitor": visitor.id, "onda_item": onda_item.id, "ron_item": ron_item.id}


def test_checklist_filters_by_brand_key(client, quality_brand_seed):
    token = _login(client, "qb_visitor")
    r = client.get(
        "/api/v1/quality/checklist",
        params={"branch_id": quality_brand_seed["branch"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["brand_key"] == "ronaldos"
    assert body[0]["items"][0]["text_en"] == "Oven readiness before operation"


def test_create_visit_infers_branch_brand_key(client, db: Session, quality_brand_seed):
    token = _login(client, "qb_visitor")
    create = client.post(
        "/api/v1/quality/",
        json={
            "branch_id": quality_brand_seed["branch"],
            "visitor_id": quality_brand_seed["visitor"],
            "visit_date": date.today().isoformat(),
            "shift": "morning",
            "responses": [{"item_id": quality_brand_seed["ron_item"], "status": "yes"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create.status_code == 201, create.text
    visit = db.query(QualityVisit).filter(QualityVisit.id == create.json()["id"]).first()
    assert visit is not None
    assert visit.brand_key == "ronaldos"


def test_create_visit_rejects_mismatched_brand_items(client, quality_brand_seed):
    token = _login(client, "qb_visitor")
    create = client.post(
        "/api/v1/quality/",
        json={
            "branch_id": quality_brand_seed["branch"],
            "brand_key": "ronaldos",
            "visitor_id": quality_brand_seed["visitor"],
            "visit_date": date.today().isoformat(),
            "shift": "morning",
            "responses": [{"item_id": quality_brand_seed["onda_item"], "status": "yes"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create.status_code == 400, create.text
    assert "البراند المختار" in create.json()["detail"]
