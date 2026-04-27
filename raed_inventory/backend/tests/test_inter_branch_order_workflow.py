"""
Inter-branch order workflow (OrderType.inter_branch) — area_manager approval flow.

Coverage:
    1. branch_manager ينشئ طلب → status = area_manager_review، المخزون لم يتحرّك.
    2. area_manager (نفس المنطقة) يوافق → المخزون يتحرّك، status = closed.
    3. area_manager (منطقة مختلفة) محجوب عن الموافقة → 403.
    4. الموافقة مع مخزون غير كافٍ → 400 ولا تتحرّك أي كميّة.
    5. الرفض → status = rejected + rejection_reason محفوظ.
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
    OrderStatus,
    OrderType,
    ReplenishmentOrder,
    Role,
    RoleName,
    UnitOfMeasure,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)


def _seed(db: Session) -> dict:
    wh = Warehouse(
        warehouse_code="WH-IB",
        warehouse_name="IB WH",
        location="Riyadh",
        active=True,
    )
    db.add(wh)
    db.flush()

    b_src = Branch(
        branch_code="IB-SRC", branch_name="مصدر رياض",
        city="الرياض", area="", warehouse_id=wh.id, active=True,
    )
    b_dst_same = Branch(
        branch_code="IB-DST", branch_name="هدف رياض",
        city="الرياض", area="", warehouse_id=wh.id, active=True,
    )
    b_other_region = Branch(
        branch_code="IB-EAST", branch_name="فرع شرقية",
        city="الخبر", area="الشرقية", warehouse_id=wh.id, active=True,
    )
    db.add_all([b_src, b_dst_same, b_other_region])
    db.flush()

    # Roles
    role_bm = Role(name=RoleName.branch_manager, display_name="BM", description="")
    role_am = Role(name=RoleName.area_manager, display_name="AM", description="")
    db.add_all([role_bm, role_am])
    db.flush()

    # Branch manager at source branch
    bm_user = User(
        username="ib_bm", email="ib_bm@example.com", full_name="BM",
        hashed_password=get_password_hash("BmPass@2026"),
        status=UserStatus.active, branch_id=b_src.id, is_deleted=False,
    )
    # Area manager — same region as source (الرياض)
    am_user_same = User(
        username="ib_am_same", email="ib_am_same@example.com", full_name="AM-Same",
        hashed_password=get_password_hash("AmPass@2026"),
        status=UserStatus.active, branch_id=b_src.id, is_deleted=False,
    )
    # Area manager — different region (الشرقية)
    am_user_other = User(
        username="ib_am_other", email="ib_am_other@example.com", full_name="AM-Other",
        hashed_password=get_password_hash("AmPass@2026"),
        status=UserStatus.active, branch_id=b_other_region.id, is_deleted=False,
    )
    db.add_all([bm_user, am_user_same, am_user_other])
    db.flush()
    db.add_all([
        UserRole(user_id=bm_user.id, role_id=role_bm.id),
        UserRole(user_id=am_user_same.id, role_id=role_am.id),
        UserRole(user_id=am_user_other.id, role_id=role_am.id),
    ])

    cat = ItemCategory(code="IB-CAT", name_ar="تصنيف", name_en="Cat")
    db.add(cat)
    db.flush()
    uom = UnitOfMeasure(code="IB-U", name_ar="كجم", name_en="kg")
    db.add(uom)
    db.flush()
    item = Item(
        item_code="IB-IT-001",
        item_name_ar="صنف تجريبي للتحويل",
        item_name_en="Test transfer item",
        category_id=cat.id,
        unit_id=uom.id,
    )
    db.add(item)
    db.flush()

    db.add(BranchStock(
        branch_id=b_src.id, item_id=item.id,
        current_qty=Decimal("100"), reserved_qty=Decimal("0"),
    ))
    db.add(BranchStock(
        branch_id=b_dst_same.id, item_id=item.id,
        current_qty=Decimal("10"), reserved_qty=Decimal("0"),
    ))
    db.commit()

    return {
        "item_id": item.id,
        "b_src": b_src.id,
        "b_dst": b_dst_same.id,
        "b_other": b_other_region.id,
    }


def _login(client, username: str, password: str) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def seeded(client, db: Session):
    return _seed(db)


def test_create_order_status_pending_stock_unchanged(seeded, client, db):
    token = _login(client, "ib_bm", "BmPass@2026")

    r = client.post(
        "/api/v1/orders/inter-branch",
        json={
            "destination_branch_id": seeded["b_dst"],
            "items": [{"item_id": seeded["item_id"], "qty": "5"}],
            "reason": "نقل اختباري",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == OrderStatus.area_manager_review.value
    assert body["source_branch_id"] == seeded["b_src"]
    assert body["destination_branch_id"] == seeded["b_dst"]

    # Stock unchanged — no movement until approval
    src = db.query(BranchStock).filter(
        BranchStock.branch_id == seeded["b_src"],
        BranchStock.item_id == seeded["item_id"],
    ).first()
    dst = db.query(BranchStock).filter(
        BranchStock.branch_id == seeded["b_dst"],
        BranchStock.item_id == seeded["item_id"],
    ).first()
    assert src.current_qty == Decimal("100")
    assert dst.current_qty == Decimal("10")


def test_approve_moves_stock_and_closes_order(seeded, client, db):
    bm_token = _login(client, "ib_bm", "BmPass@2026")
    create = client.post(
        "/api/v1/orders/inter-branch",
        json={
            "destination_branch_id": seeded["b_dst"],
            "items": [{"item_id": seeded["item_id"], "qty": "7"}],
            "reason": "لتغذية الفرع الآخر",
        },
        headers={"Authorization": f"Bearer {bm_token}"},
    ).json()
    order_id = create["id"]

    am_token = _login(client, "ib_am_same", "AmPass@2026")
    r = client.post(
        f"/api/v1/orders/{order_id}/inter-branch-approve",
        json={},
        headers={"Authorization": f"Bearer {am_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == OrderStatus.closed.value

    src = db.query(BranchStock).filter(
        BranchStock.branch_id == seeded["b_src"],
        BranchStock.item_id == seeded["item_id"],
    ).first()
    dst = db.query(BranchStock).filter(
        BranchStock.branch_id == seeded["b_dst"],
        BranchStock.item_id == seeded["item_id"],
    ).first()
    assert src.current_qty == Decimal("93")
    assert dst.current_qty == Decimal("17")


def test_approve_out_of_region_area_manager_blocked(seeded, client, db):
    bm_token = _login(client, "ib_bm", "BmPass@2026")
    create = client.post(
        "/api/v1/orders/inter-branch",
        json={
            "destination_branch_id": seeded["b_dst"],
            "items": [{"item_id": seeded["item_id"], "qty": "3"}],
            "reason": "اختبار خارج المنطقة",
        },
        headers={"Authorization": f"Bearer {bm_token}"},
    ).json()
    order_id = create["id"]

    am_other_token = _login(client, "ib_am_other", "AmPass@2026")
    r = client.post(
        f"/api/v1/orders/{order_id}/inter-branch-approve",
        json={},
        headers={"Authorization": f"Bearer {am_other_token}"},
    )
    assert r.status_code == 403, r.text
    err = r.json()
    assert err.get("error_code") == "inter_branch.approval_access_denied"

    # Order still pending
    order = db.query(ReplenishmentOrder).filter(ReplenishmentOrder.id == order_id).first()
    assert order.status == OrderStatus.area_manager_review


def test_approve_insufficient_stock_fails(seeded, client, db):
    bm_token = _login(client, "ib_bm", "BmPass@2026")
    create = client.post(
        "/api/v1/orders/inter-branch",
        json={
            "destination_branch_id": seeded["b_dst"],
            # Source has only 100 — requesting 500
            "items": [{"item_id": seeded["item_id"], "qty": "500"}],
            "reason": "مخزون غير كافٍ",
        },
        headers={"Authorization": f"Bearer {bm_token}"},
    ).json()
    order_id = create["id"]

    am_token = _login(client, "ib_am_same", "AmPass@2026")
    r = client.post(
        f"/api/v1/orders/{order_id}/inter-branch-approve",
        json={},
        headers={"Authorization": f"Bearer {am_token}"},
    )
    assert r.status_code == 400
    err = r.json()
    assert err.get("error_code") == "inter_branch.insufficient_stock"

    # Stock unchanged
    src = db.query(BranchStock).filter(
        BranchStock.branch_id == seeded["b_src"],
        BranchStock.item_id == seeded["item_id"],
    ).first()
    assert src.current_qty == Decimal("100")


def test_reject_marks_status_and_reason(seeded, client, db):
    bm_token = _login(client, "ib_bm", "BmPass@2026")
    create = client.post(
        "/api/v1/orders/inter-branch",
        json={
            "destination_branch_id": seeded["b_dst"],
            "items": [{"item_id": seeded["item_id"], "qty": "2"}],
            "reason": "للرفض",
        },
        headers={"Authorization": f"Bearer {bm_token}"},
    ).json()
    order_id = create["id"]

    am_token = _login(client, "ib_am_same", "AmPass@2026")
    r = client.post(
        f"/api/v1/orders/{order_id}/inter-branch-reject",
        json={"reason": "غير مبرر"},
        headers={"Authorization": f"Bearer {am_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == OrderStatus.rejected.value

    order = db.query(ReplenishmentOrder).filter(ReplenishmentOrder.id == order_id).first()
    assert order.status == OrderStatus.rejected
    assert order.rejection_reason == "غير مبرر"


def test_pending_list_excludes_out_of_region(seeded, client, db):
    bm_token = _login(client, "ib_bm", "BmPass@2026")
    client.post(
        "/api/v1/orders/inter-branch",
        json={
            "destination_branch_id": seeded["b_dst"],
            "items": [{"item_id": seeded["item_id"], "qty": "1"}],
            "reason": "قائمة منتظرة",
        },
        headers={"Authorization": f"Bearer {bm_token}"},
    )

    # In-region AM sees it
    am_token = _login(client, "ib_am_same", "AmPass@2026")
    r = client.get(
        "/api/v1/orders/inter-branch/pending",
        headers={"Authorization": f"Bearer {am_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # Out-of-region AM sees nothing
    am_other_token = _login(client, "ib_am_other", "AmPass@2026")
    r = client.get(
        "/api/v1/orders/inter-branch/pending",
        headers={"Authorization": f"Bearer {am_other_token}"},
    )
    assert r.status_code == 200
    assert r.json() == []
