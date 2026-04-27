"""
تحويل بين الفروع تحت area_manager: نفس المدينة → 200، مدينة مختلفة → 403.
يعتمد على can_access_branch(..., db) و _same_region في app.core.auth.
"""
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    Branch,
    BranchStock,
    Item,
    ItemCategory,
    Role,
    RoleName,
    UnitOfMeasure,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)


def _seed_minimal_graph(db: Session):
    wh = Warehouse(
        warehouse_code="WH-T",
        warehouse_name="Test WH",
        location="Riyadh",
        active=True,
    )
    db.add(wh)
    db.flush()

    b_riyadh_a = Branch(
        branch_code="BR-RY-A",
        branch_name="فرع الرياض أ",
        city="الرياض",
        area="",
        warehouse_id=wh.id,
        active=True,
    )
    b_riyadh_b = Branch(
        branch_code="BR-RY-B",
        branch_name="فرع الرياض ب",
        city="الرياض",
        area="",
        warehouse_id=wh.id,
        active=True,
    )
    b_eastern = Branch(
        branch_code="BR-EAST-1",
        branch_name="فرع الشرقية",
        city="الخبر",
        area="الشرقية",
        warehouse_id=wh.id,
        active=True,
    )
    db.add_all([b_riyadh_a, b_riyadh_b, b_eastern])
    db.flush()

    role = Role(
        name=RoleName.area_manager,
        display_name="مدير منطقة",
        description="test",
    )
    db.add(role)
    db.flush()

    am_user = User(
        username="area_mgr_test",
        email="area_mgr_test@example.com",
        full_name="Area Manager Test",
        hashed_password=get_password_hash("AreaMgr@2026"),
        status=UserStatus.active,
        branch_id=b_riyadh_a.id,
        warehouse_id=None,
        is_deleted=False,
    )
    db.add(am_user)
    db.flush()
    db.add(UserRole(user_id=am_user.id, role_id=role.id))

    cat = ItemCategory(code="CAT-T", name_ar="تصنيف", name_en="Cat")
    db.add(cat)
    db.flush()
    uom = UnitOfMeasure(code="U-T", name_ar="كجم", name_en="kg")
    db.add(uom)
    db.flush()
    item = Item(
        item_code="IT-T-001",
        item_name_ar="صنف تجريبي",
        item_name_en="Test item",
        category_id=cat.id,
        unit_id=uom.id,
    )
    db.add(item)
    db.flush()

    # مخزون كافٍ في فرعَي الرياض فقط للاختبار
    db.add(
        BranchStock(
            branch_id=b_riyadh_a.id,
            item_id=item.id,
            current_qty=Decimal("100"),
            reserved_qty=Decimal("0"),
        )
    )
    db.add(
        BranchStock(
            branch_id=b_riyadh_b.id,
            item_id=item.id,
            current_qty=Decimal("10"),
            reserved_qty=Decimal("0"),
        )
    )
    db.add(
        BranchStock(
            branch_id=b_eastern.id,
            item_id=item.id,
            current_qty=Decimal("50"),
            reserved_qty=Decimal("0"),
        )
    )
    db.commit()

    return {
        "token_user": am_user,
        "password": "AreaMgr@2026",
        "item_id": item.id,
        "b_riyadh_a": b_riyadh_a.id,
        "b_riyadh_b": b_riyadh_b.id,
        "b_eastern": b_eastern.id,
    }


@pytest.fixture
def seeded(client, db: Session):
    return _seed_minimal_graph(db)


def test_area_manager_same_city_transfer_200(seeded, client):
    """فرعان في الرياض → 200."""
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "area_mgr_test", "password": seeded["password"]},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    body = {
        "source_branch_id": seeded["b_riyadh_a"],
        "destination_branch_id": seeded["b_riyadh_b"],
        "item_id": seeded["item_id"],
        "qty": "5",
        "reason": "اختبار نفس المدينة",
    }
    resp = client.post(
        "/api/v1/stock/transfer/branch-to-branch",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source_branch_id"] == seeded["b_riyadh_a"]
    assert data["destination_branch_id"] == seeded["b_riyadh_b"]
    assert data["qty_transferred"] == 5.0


def test_area_manager_cross_region_transfer_403(seeded, client):
    """الرياض ↔ الشرقية → 403 على المصدر أو الوجهة."""
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "area_mgr_test", "password": seeded["password"]},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    body = {
        "source_branch_id": seeded["b_riyadh_a"],
        "destination_branch_id": seeded["b_eastern"],
        "item_id": seeded["item_id"],
        "qty": "3",
        "reason": "اختبار عبر المنطقة",
    }
    resp = client.post(
        "/api/v1/stock/transfer/branch-to-branch",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, resp.text
    err = resp.json()
    assert err.get("error_code") == "stock.branch_access_denied"
