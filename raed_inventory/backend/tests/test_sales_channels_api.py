from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import Branch, Role, RoleName, User, UserRole, UserStatus, Warehouse
from app.models.sales_channels import BranchDailySale, ChannelType, ClosureScopeType, SalesChannel
from app.services import sales_channels_service as svc


def _mk_role(db: Session, role_name: RoleName, display_name: str) -> Role:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role:
        return role
    role = Role(name=role_name, display_name=display_name, description="test role")
    db.add(role)
    db.flush()
    return role


def _mk_user(
    db: Session,
    *,
    username: str,
    password: str,
    full_name: str,
    role_name: RoleName,
    branch_id: int | None = None,
) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=full_name,
        hashed_password=get_password_hash(password),
        status=UserStatus.active,
        branch_id=branch_id,
        is_deleted=False,
    )
    db.add(user)
    db.flush()
    role = _mk_role(db, role_name, role_name.value)
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()
    return user


def _seed_graph(db: Session) -> dict:
    wh = Warehouse(
        warehouse_code="SCAPI-WH",
        warehouse_name="Sales Channels WH",
        location="Riyadh",
        active=True,
        is_deleted=False,
    )
    db.add(wh)
    db.flush()

    branch_a = Branch(
        branch_code="SCAPI-BR1",
        branch_name="Branch One",
        city="Riyadh",
        area="Central",
        warehouse_id=wh.id,
        active=True,
        is_deleted=False,
    )
    branch_b = Branch(
        branch_code="SCAPI-BR2",
        branch_name="Branch Two",
        city="Riyadh",
        area="Central",
        warehouse_id=wh.id,
        active=True,
        is_deleted=False,
    )
    branch_c = Branch(
        branch_code="SCAPI-BR3",
        branch_name="Branch East",
        city="Dammam",
        area="Eastern",
        warehouse_id=wh.id,
        active=True,
        is_deleted=False,
    )
    db.add_all([branch_a, branch_b, branch_c])
    db.flush()

    jahez = SalesChannel(
        code="jahez",
        name_ar="جاهز",
        name_en="Jahez",
        type=ChannelType.delivery_app.value,
        commission_rate=Decimal("15.00"),
        is_active=True,
        sort_order=1,
    )
    hunger = SalesChannel(
        code="hungerstation",
        name_ar="هنجرستيشن",
        name_en="HungerStation",
        type=ChannelType.delivery_app.value,
        commission_rate=Decimal("18.00"),
        is_active=True,
        sort_order=2,
    )
    cash = SalesChannel(
        code="cash",
        name_ar="كاش",
        name_en="Cash",
        type=ChannelType.payment_method.value,
        commission_rate=None,
        is_active=True,
        sort_order=20,
    )
    db.add_all([jahez, hunger, cash])
    db.flush()

    branch_manager = _mk_user(
        db,
        username="sales_branch_mgr",
        password="Branch@2026",
        full_name="Branch Manager",
        role_name=RoleName.branch_manager,
        branch_id=branch_a.id,
    )
    area_manager = _mk_user(
        db,
        username="sales_area_mgr",
        password="Area@2026",
        full_name="Area Manager",
        role_name=RoleName.area_manager,
        branch_id=branch_a.id,
    )
    sales_manager = _mk_user(
        db,
        username="sales_mgr",
        password="Sales@2026",
        full_name="Sales Manager",
        role_name=RoleName.sales_manager,
    )
    operations_manager = _mk_user(
        db,
        username="ops_mgr",
        password="Ops@2026",
        full_name="Operations Manager",
        role_name=RoleName.operations_manager,
    )
    db.commit()

    return {
        "branch_a": branch_a,
        "branch_b": branch_b,
        "branch_c": branch_c,
        "jahez": jahez,
        "hunger": hunger,
        "cash": cash,
        "branch_manager": branch_manager,
        "area_manager": area_manager,
        "sales_manager": sales_manager,
        "operations_manager": operations_manager,
        "passwords": {
            "branch_manager": "Branch@2026",
            "area_manager": "Area@2026",
            "sales_manager": "Sales@2026",
            "operations_manager": "Ops@2026",
        },
    }


@pytest.fixture
def seeded(client, db: Session):
    return _seed_graph(db)


def _auth_headers(client, username: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_channels_for_branch_manager(client, seeded):
    headers = _auth_headers(client, "sales_branch_mgr", seeded["passwords"]["branch_manager"])
    response = client.get("/api/v1/sales-channels/channels", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 3
    assert {row["code"] for row in data} == {"jahez", "hungerstation", "cash"}


def test_patch_commission_rate_forbidden_for_branch_manager(client, seeded):
    headers = _auth_headers(client, "sales_branch_mgr", seeded["passwords"]["branch_manager"])
    response = client.patch(
        f"/api/v1/sales-channels/channels/{seeded['jahez'].id}/commission-rate",
        json={"commission_rate": "20"},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_patch_commission_rate_success_for_sales_manager(client, seeded):
    headers = _auth_headers(client, "sales_mgr", seeded["passwords"]["sales_manager"])
    response = client.patch(
        f"/api/v1/sales-channels/channels/{seeded['jahez'].id}/commission-rate",
        json={"commission_rate": "20"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["commission_rate"] == "20.00"


def test_daily_sales_batch_success_for_own_branch(client, seeded):
    headers = _auth_headers(client, "sales_branch_mgr", seeded["passwords"]["branch_manager"])
    response = client.post(
        "/api/v1/sales-channels/daily-sales/batch",
        json={
            "branch_id": seeded["branch_a"].id,
            "sales_date": "2026-04-10",
            "lines": [
                {"channel_id": seeded["jahez"].id, "amount": "400.00", "orders_count": 8},
                {"channel_id": seeded["hunger"].id, "amount": "220.00", "orders_count": 4},
                {"channel_id": seeded["cash"].id, "amount": "150.00", "orders_count": None},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert len(response.json()) == 3


def test_daily_sales_batch_rejects_other_branch_for_branch_manager(client, seeded):
    headers = _auth_headers(client, "sales_branch_mgr", seeded["passwords"]["branch_manager"])
    response = client.post(
        "/api/v1/sales-channels/daily-sales/batch",
        json={
            "branch_id": seeded["branch_b"].id,
            "sales_date": "2026-04-10",
            "lines": [
                {"channel_id": seeded["jahez"].id, "amount": "400.00", "orders_count": 8},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_daily_sales_batch_maps_orders_count_rule_error(client, seeded):
    headers = _auth_headers(client, "sales_branch_mgr", seeded["passwords"]["branch_manager"])
    response = client.post(
        "/api/v1/sales-channels/daily-sales/batch",
        json={
            "branch_id": seeded["branch_a"].id,
            "sales_date": "2026-04-11",
            "lines": [
                {"channel_id": seeded["cash"].id, "amount": "100.00", "orders_count": 1},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "payment_method" in response.json()["detail"]


def test_list_daily_sales_scoped_to_branch_manager_branch(client, seeded):
    headers = _auth_headers(client, "sales_branch_mgr", seeded["passwords"]["branch_manager"])
    client.post(
        "/api/v1/sales-channels/daily-sales/batch",
        json={
            "branch_id": seeded["branch_a"].id,
            "sales_date": "2026-04-12",
            "lines": [{"channel_id": seeded["jahez"].id, "amount": "300.00", "orders_count": 6}],
        },
        headers=headers,
    )

    sales_headers = _auth_headers(client, "sales_mgr", seeded["passwords"]["sales_manager"])
    client.post(
        "/api/v1/sales-channels/daily-sales/batch",
        json={
            "branch_id": seeded["branch_b"].id,
            "sales_date": "2026-04-12",
            "lines": [{"channel_id": seeded["jahez"].id, "amount": "500.00", "orders_count": 9}],
        },
        headers=sales_headers,
    )

    response = client.get(
        "/api/v1/sales-channels/daily-sales",
        params={"month": "2026-04"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    branch_ids = {row["branch_id"] for row in response.json()}
    assert branch_ids == {seeded["branch_a"].id}


def test_patch_daily_sale_edit_window_maps_to_403(client, seeded, db: Session):
    row = svc.create_daily_sale(
        db,
        branch_id=seeded["branch_a"].id,
        sales_date=date(2026, 4, 13),
        channel_id=seeded["jahez"].id,
        amount=Decimal("450"),
        orders_count=9,
        submitted_by=seeded["branch_manager"].id,
    )
    row.submitted_at = row.submitted_at - timedelta(days=2)
    db.commit()

    headers = _auth_headers(client, "sales_branch_mgr", seeded["passwords"]["branch_manager"])
    response = client.patch(
        f"/api/v1/sales-channels/daily-sales/{row.id}",
        json={"amount": "470.00", "orders_count": 10, "edit_reason": "late correction"},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_patch_daily_sale_locked_month_maps_to_423(client, seeded, db: Session):
    row = svc.create_daily_sale(
        db,
        branch_id=seeded["branch_a"].id,
        sales_date=date(2026, 4, 14),
        channel_id=seeded["jahez"].id,
        amount=Decimal("600"),
        orders_count=12,
        submitted_by=seeded["branch_manager"].id,
    )
    svc.close_month(
        db,
        month="2026-04",
        scope_type=ClosureScopeType.branch.value,
        branch_id=seeded["branch_a"].id,
        closed_by=seeded["sales_manager"].id,
    )
    db.commit()

    headers = _auth_headers(client, "sales_mgr", seeded["passwords"]["sales_manager"])
    response = client.patch(
        f"/api/v1/sales-channels/daily-sales/{row.id}",
        json={"amount": "610.00", "orders_count": 13, "edit_reason": "post lock check"},
        headers=headers,
    )
    assert response.status_code == 423, response.text


def test_create_statement_success(client, seeded):
    headers = _auth_headers(client, "sales_mgr", seeded["passwords"]["sales_manager"])
    response = client.post(
        "/api/v1/sales-channels/statements",
        json={
            "channel_id": seeded["jahez"].id,
            "branch_id": seeded["branch_a"].id,
            "statement_month": "2026-04",
            "app_reported_amount": "1000.00",
            "app_reported_count": 20,
            "commission_rate": "15",
            "import_source": "manual",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["net_amount"] == "850.00"


def test_reconciliation_zero_app_total_returns_major_with_null_percent(client, seeded, db: Session):
    svc.create_daily_sale(
        db,
        branch_id=seeded["branch_a"].id,
        sales_date=date(2026, 4, 15),
        channel_id=seeded["jahez"].id,
        amount=Decimal("500"),
        orders_count=10,
        submitted_by=seeded["branch_manager"].id,
    )
    db.commit()

    headers = _auth_headers(client, "sales_mgr", seeded["passwords"]["sales_manager"])
    response = client.get(
        "/api/v1/sales-channels/reconciliation",
        params={"month": "2026-04", "branch_id": seeded["branch_a"].id, "channel_id": seeded["jahez"].id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    line = response.json()["lines"][0]
    assert line["app_total"] == "0"
    assert line["variance_percent"] is None
    assert line["status"] == "major"


def test_create_closure_duplicate_maps_to_409(client, seeded):
    headers = _auth_headers(client, "sales_mgr", seeded["passwords"]["sales_manager"])
    first = client.post(
        "/api/v1/sales-channels/closures",
        json={"month": "2026-04", "scope_type": "branch", "branch_id": seeded["branch_a"].id},
        headers=headers,
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/sales-channels/closures",
        json={"month": "2026-04", "scope_type": "branch", "branch_id": seeded["branch_a"].id},
        headers=headers,
    )
    assert second.status_code == 409, second.text


def test_reopen_closure_success(client, seeded):
    headers = _auth_headers(client, "sales_mgr", seeded["passwords"]["sales_manager"])
    closure = client.post(
        "/api/v1/sales-channels/closures",
        json={"month": "2026-05", "scope_type": "branch", "branch_id": seeded["branch_a"].id},
        headers=headers,
    )
    assert closure.status_code == 201, closure.text
    closure_id = closure.json()["id"]

    response = client.post(
        f"/api/v1/sales-channels/closures/{closure_id}/reopen",
        json={"reopen_reason": "statement typo fixed"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["reopen_reason"] == "statement typo fixed"


def test_daily_sales_batch_allowed_for_area_manager(client, seeded):
    """Model C (2026-04-24): area_manager CAN enter daily data as substitute
    for an absent branch in their region."""
    headers = _auth_headers(client, "sales_area_mgr", seeded["passwords"]["area_manager"])
    response = client.post(
        "/api/v1/sales-channels/daily-sales/batch",
        json={
            "branch_id": seeded["branch_a"].id,
            "sales_date": "2026-04-16",
            "lines": [
                {"channel_id": seeded["jahez"].id, "amount": "300.00", "orders_count": 6},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload[0]["entered_by_role"] == "area_manager"
    assert payload[0]["on_behalf_of"] is False


def test_daily_sales_batch_forbidden_for_sales_manager(client, seeded):
    """Model C: sales_manager is the Delivery Accounts Manager, NOT an
    operational entry role. Must be blocked from daily-sales writes."""
    headers = _auth_headers(client, "sales_mgr", seeded["passwords"]["sales_manager"])
    response = client.post(
        "/api/v1/sales-channels/daily-sales/batch",
        json={
            "branch_id": seeded["branch_a"].id,
            "sales_date": "2026-04-18",
            "lines": [
                {"channel_id": seeded["jahez"].id, "amount": "400.00", "orders_count": 8},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_channels_list_forbidden_for_warehouse_manager(client, seeded, db: Session):
    """Policy 2026-04-23: warehouse_manager is OUT of the Delivery/sales_channels module."""
    wh_mgr = _mk_user(
        db,
        username="wh_mgr_sc",
        password="Wh@2026",
        full_name="Warehouse Manager",
        role_name=RoleName.warehouse_manager,
    )
    db.commit()
    headers = _auth_headers(client, "wh_mgr_sc", "Wh@2026")
    response = client.get("/api/v1/sales-channels/channels", headers=headers)
    assert response.status_code == 403, response.text


def test_reconciliation_read_allowed_for_area_manager(client, seeded, db: Session):
    """area_manager keeps read access to reconciliation (reviewer role)."""
    svc.create_daily_sale(
        db,
        branch_id=seeded["branch_a"].id,
        sales_date=date(2026, 4, 17),
        channel_id=seeded["jahez"].id,
        amount=Decimal("250"),
        orders_count=5,
        submitted_by=seeded["branch_manager"].id,
    )
    db.commit()
    headers = _auth_headers(client, "sales_area_mgr", seeded["passwords"]["area_manager"])
    response = client.get(
        "/api/v1/sales-channels/reconciliation",
        params={"month": "2026-04", "branch_id": seeded["branch_a"].id},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def test_compliance_scoped_for_branch_manager(client, seeded, db: Session):
    svc.create_daily_sale(
        db,
        branch_id=seeded["branch_a"].id,
        sales_date=date(2026, 4, 1),
        channel_id=seeded["jahez"].id,
        amount=Decimal("100"),
        orders_count=2,
        submitted_by=seeded["branch_manager"].id,
    )
    svc.create_daily_sale(
        db,
        branch_id=seeded["branch_b"].id,
        sales_date=date(2026, 4, 1),
        channel_id=seeded["jahez"].id,
        amount=Decimal("120"),
        orders_count=3,
        submitted_by=seeded["sales_manager"].id,
    )
    db.commit()

    headers = _auth_headers(client, "sales_branch_mgr", seeded["passwords"]["branch_manager"])
    response = client.get(
        "/api/v1/sales-channels/compliance",
        params={"month": "2026-04"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["branch_id"] == seeded["branch_a"].id
