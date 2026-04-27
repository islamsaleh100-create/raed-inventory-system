from pathlib import Path

import openpyxl
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    Branch,
    BranchBrand,
    Brand,
    Item,
    KitchenSection,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
    Warehouse,
)
from app.services.supply_item_master_import_service import import_supply_item_master


HEADERS = [
    "Original Row",
    "Brand",
    "POS Category",
    "Item Name",
    "Price",
    "Item Type",
    "Source Type",
    "Default Source",
    "Kitchen Section",
    "Can Branch Request",
    "Visible in Branch UI",
    "Confidence",
    "Notes",
]


def _workbook(path: Path, rows: list[list[object]]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Classified_Items"
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    for name in ("Summary", "Review_Needed", "Rules"):
        wb.create_sheet(name)
    wb.save(path)
    return path


def _role(db: Session, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if row:
        return row
    row = Role(name=name, display_name=name.value, description="")
    db.add(row)
    db.flush()
    return row


def _user(db: Session, username: str, role_name: RoleName, *, branch_id: int | None = None) -> User:
    role = _role(db, role_name)
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
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()
    return user


def _login(client, username: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "Pass@2026"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_import_supply_item_master_imports_rows_and_logs_invalid(db: Session, tmp_path: Path):
    workbook = _workbook(
        tmp_path / "classified_supply_items.xlsx",
        [
            [1, "Onda", "drinks", "Cola", None, None, "WAREHOUSE", "WAREHOUSE", None, "Yes", "Yes", "High", ""],
            [2, "Ronaldos", "pizza", "Pizza Dough", None, None, "KITCHEN", "KITCHEN", "Pizza", "Yes", "Yes", "High", ""],
            [3, "Onda", "fees", "Delivery Fee", None, None, "NOT_REQUESTABLE", None, None, "No", "No", "High", ""],
            [4, "Ronaldos", "pizza", "Broken Kitchen", None, None, "KITCHEN", "KITCHEN", None, "Yes", "Yes", "High", ""],
            [5, "Onda", "drinks", "Cola", None, None, "WAREHOUSE", "WAREHOUSE", None, "Yes", "Yes", "High", ""],
        ],
    )

    result = import_supply_item_master(db, workbook, invalid_log_dir=tmp_path)

    assert result.imported_items == 3
    assert result.created_items == 3
    assert len(result.rejected_rows) == 2
    assert Path(result.invalid_log_path).exists()

    kitchen_item = db.query(Item).filter(Item.item_name_ar == "Pizza Dough").first()
    assert kitchen_item is not None
    assert kitchen_item.kitchen_section is not None
    assert kitchen_item.kitchen_section.name == "Pizza"

    not_requestable = db.query(Item).filter(Item.item_name_ar == "Delivery Fee").first()
    assert not_requestable is not None
    assert not_requestable.source_type.value == "NOT_REQUESTABLE"
    assert not not_requestable.branch_requestable
    assert not not_requestable.visible_in_branch_ui


def test_allowed_items_hides_not_requestable_and_hidden_items(client, db: Session, tmp_path: Path):
    warehouse = Warehouse(warehouse_code="WH-IMP", warehouse_name="Import WH", location="Riyadh", active=True)
    db.add(warehouse)
    db.flush()
    branch = Branch(branch_code="BR-IMP", branch_name="Import Branch", city="Riyadh", area="", warehouse_id=warehouse.id)
    db.add(branch)
    db.flush()
    branch_user = _user(db, "import_branch_user", RoleName.branch_user, branch_id=branch.id)
    assert branch_user.id

    workbook = _workbook(
        tmp_path / "classified_supply_items_ui.xlsx",
        [
            [1, "Onda", "drinks", "Visible Cola", None, None, "WAREHOUSE", "WAREHOUSE", None, "Yes", "Yes", "High", ""],
            [2, "Onda", "drinks", "Hidden Syrup", None, None, "WAREHOUSE", "WAREHOUSE", None, "Yes", "No", "High", ""],
            [3, "Onda", "fees", "Service Fee", None, None, "NOT_REQUESTABLE", None, None, "No", "No", "High", ""],
        ],
    )
    import_supply_item_master(db, workbook, invalid_log_dir=tmp_path)

    onda = db.query(Brand).filter(Brand.name == "Onda").first()
    assert onda is not None
    db.add(BranchBrand(branch_id=branch.id, brand_id=onda.id))
    db.commit()

    token = _login(client, "import_branch_user")
    response = client.get(
        f"/api/v1/branch-requests/allowed-items?branch_id={branch.id}&brand_id={onda.id}",
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    names = {row["item_name_ar"] for row in response.json()}
    assert names == {"Visible Cola"}


def test_import_maps_general_and_shared_rows_to_expected_brands(db: Session, tmp_path: Path):
    workbook = _workbook(
        tmp_path / "classified_supply_items_shared.xlsx",
        [
            [1, "General", "drinks", "Pepsi", None, None, "WAREHOUSE", "WAREHOUSE", None, "Yes", "Yes", "High", ""],
            [2, "Shared", "snack", "Shared Sauce", None, None, "KITCHEN", "KITCHEN", "Meat & Chicken", "Yes", "Yes", "High", ""],
        ],
    )
    import_supply_item_master(db, workbook, invalid_log_dir=tmp_path)

    pepsi = db.query(Item).filter(Item.item_name_ar == "Pepsi").first()
    shared = db.query(Item).filter(Item.item_name_ar == "Shared Sauce").first()
    assert pepsi is not None and shared is not None

    pepsi_brands = sorted(link.brand.name for link in pepsi.item_brands)
    shared_brands = sorted(link.brand.name for link in shared.item_brands)
    assert pepsi_brands == ["Griddle", "Onda", "Ronaldos", "Shawarma"]
    assert shared_brands == ["Griddle", "Ronaldos", "Shawarma"]

    section = db.query(KitchenSection).filter(KitchenSection.name == "Meat & Chicken").first()
    assert section is not None
