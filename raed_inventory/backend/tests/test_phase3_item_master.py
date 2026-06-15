"""Phase 3 — item master import, visibility, and split validation (PostgreSQL)."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import get_password_hash
from app.database import SessionLocal, engine, get_db
from app.main import app
from app.models import (
    Branch,
    BranchBrand,
    BranchRequest,
    BranchRequestLine,
    BranchRequestLineStatus,
    BranchRequestStatus,
    Brand,
    Item,
    ItemBrand,
    ItemCategory,
    ItemType,
    KitchenSection,
    ProductionOrder,
    Role,
    RoleName,
    SupplyDefaultSource,
    SupplySourceType,
    UnitOfMeasure,
    User,
    UserRole,
    UserStatus,
    Warehouse,
    WarehouseLine,
)
from app.services.branch_request_split_service import split_branch_request
from app.services.supply_item_master_import_service import import_supply_item_master

pytestmark = pytest.mark.skipif(
    not engine.url.drivername.startswith("postgresql"),
    reason="Phase 3 item master tests require PostgreSQL",
)

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


@pytest.fixture
def pg_db():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def pg_client(pg_db: Session):
    def _override():
        yield pg_db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _ensure_kitchen_sections(db: Session) -> None:
    for name in ("Meat & Chicken", "Bakery & Sweets", "Pizza"):
        if not db.query(KitchenSection).filter(KitchenSection.name == name).first():
            db.add(KitchenSection(name=name, active=True))
    db.flush()


def _role(db: Session, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if row:
        return row
    row = Role(name=name, display_name=name.value, description="")
    db.add(row)
    db.flush()
    return row


def _branch_user(db: Session, username: str, branch_id: int) -> User:
    role = _role(db, RoleName.branch_user)
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


def _seed_brand_branch(db: Session, brand_name: str, branch_code: str) -> tuple[Branch, Brand]:
    wh = db.query(Warehouse).filter(Warehouse.warehouse_code == "PH3-WH").first()
    if not wh:
        wh = Warehouse(warehouse_code="PH3-WH", warehouse_name="Phase3 WH", location="Riyadh", active=True)
        db.add(wh)
        db.flush()
    branch = db.query(Branch).filter(Branch.branch_code == branch_code).first()
    if not branch:
        branch = Branch(
            branch_code=branch_code,
            branch_name=f"{brand_name} Branch",
            city="Riyadh",
            area="",
            warehouse_id=wh.id,
            active=True,
        )
        db.add(branch)
        db.flush()
    brand = db.query(Brand).filter(Brand.name == brand_name).first()
    if not brand:
        brand = Brand(name=brand_name, active=True)
        db.add(brand)
        db.flush()
    if not db.query(BranchBrand).filter(
        BranchBrand.branch_id == branch.id,
        BranchBrand.brand_id == brand.id,
    ).first():
        db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
        db.flush()
    return branch, brand


def _login(client: TestClient, username: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "Pass@2026"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_import_valid_kitchen_item(pg_db: Session, tmp_path: Path):
    _ensure_kitchen_sections(pg_db)
    workbook = _workbook(
        tmp_path / "kitchen_ok.xlsx",
        [[1, "Onda", "pizza", "Pizza Dough", None, "FINISHED", "KITCHEN", "KITCHEN", "Pizza", "Yes", "Yes", "High", ""]],
    )
    result = import_supply_item_master(pg_db, workbook, invalid_log_dir=tmp_path)
    assert result.imported_items == 1
    item = pg_db.query(Item).filter(Item.item_name_ar == "Pizza Dough").first()
    assert item is not None
    assert item.kitchen_section_id is not None
    assert item.default_source == SupplyDefaultSource.KITCHEN


def test_import_rejects_kitchen_without_section(pg_db: Session, tmp_path: Path):
    _ensure_kitchen_sections(pg_db)
    workbook = _workbook(
        tmp_path / "kitchen_bad.xlsx",
        [[1, "Onda", "pizza", "Broken Dough", None, "FINISHED", "KITCHEN", "KITCHEN", None, "Yes", "Yes", "High", ""]],
    )
    result = import_supply_item_master(pg_db, workbook, invalid_log_dir=tmp_path)
    assert result.imported_items == 0
    assert any("kitchen" in row["reason"].lower() for row in result.rejected_rows)


def test_import_rejects_raw_requestable(pg_db: Session, tmp_path: Path):
    _ensure_kitchen_sections(pg_db)
    workbook = _workbook(
        tmp_path / "raw_bad.xlsx",
        [[1, "Onda", "raw", "Flour", None, "RAW", "WAREHOUSE", "WAREHOUSE", None, "Yes", "Yes", "High", ""]],
    )
    result = import_supply_item_master(pg_db, workbook, invalid_log_dir=tmp_path)
    assert result.imported_items == 0
    assert any("RAW" in row["reason"] for row in result.rejected_rows)


def test_import_duplicate_upserts(pg_db: Session, tmp_path: Path):
    _ensure_kitchen_sections(pg_db)
    workbook = _workbook(
        tmp_path / "dup.xlsx",
        [[1, "Onda", "drinks", "Cola", None, "FINISHED", "WAREHOUSE", "WAREHOUSE", None, "Yes", "Yes", "High", ""]],
    )
    first = import_supply_item_master(pg_db, workbook, invalid_log_dir=tmp_path)
    second = import_supply_item_master(pg_db, workbook, invalid_log_dir=tmp_path)
    assert first.created_items == 1
    assert second.updated_items == 1
    assert pg_db.query(Item).filter(Item.item_name_ar == "Cola").count() == 1


def test_branch_visibility_hides_raw_and_not_requestable(pg_db: Session, pg_client: TestClient, tmp_path: Path):
    _ensure_kitchen_sections(pg_db)
    branch, brand = _seed_brand_branch(pg_db, "Onda", "PH3-ONDA")
    _branch_user(pg_db, "ph3_branch_onda", branch.id)
    pg_db.commit()

    workbook = _workbook(
        tmp_path / "visibility.xlsx",
        [
            [1, "Onda", "drinks", "Visible Cola", None, "FINISHED", "WAREHOUSE", "WAREHOUSE", None, "Yes", "Yes", "High", ""],
            [2, "Onda", "raw", "Hidden Flour", None, "RAW", "WAREHOUSE", "WAREHOUSE", None, "No", "No", "High", ""],
            [3, "Onda", "fees", "Service Fee", None, "FINISHED", "NOT_REQUESTABLE", None, None, "No", "No", "High", ""],
        ],
    )
    import_supply_item_master(pg_db, workbook, invalid_log_dir=tmp_path)
    pg_db.commit()

    token = _login(pg_client, "ph3_branch_onda")
    response = pg_client.get(
        f"/api/v1/branch-requests/allowed-items?branch_id={branch.id}&brand_id={brand.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    names = {row["item_name_ar"] for row in response.json()}
    assert names == {"Visible Cola"}


@pytest.mark.parametrize(
    "brand_name,branch_code,username,visible_item",
    [
        ("Onda", "PH3-ONDA-V", "ph3_onda_v", "Onda Visible"),
        ("Ronaldos", "PH3-RON-V", "ph3_ron_v", "Ronaldos Visible"),
        ("Shawarma", "PH3-SH-V", "ph3_sh_v", "Shawarma Visible"),
    ],
)
def test_branch_visibility_by_brand_id(
    pg_db: Session,
    pg_client: TestClient,
    tmp_path: Path,
    brand_name: str,
    branch_code: str,
    username: str,
    visible_item: str,
):
    _ensure_kitchen_sections(pg_db)
    branch, brand = _seed_brand_branch(pg_db, brand_name, branch_code)
    _branch_user(pg_db, username, branch.id)
    pg_db.commit()

    workbook = _workbook(
        tmp_path / f"{branch_code}.xlsx",
        [[1, brand_name, "cat", visible_item, None, "FINISHED", "WAREHOUSE", "WAREHOUSE", None, "Yes", "Yes", "High", ""]],
    )
    import_supply_item_master(pg_db, workbook, invalid_log_dir=tmp_path)
    pg_db.commit()

    token = _login(pg_client, username)
    response = pg_client.get(
        f"/api/v1/branch-requests/allowed-items?branch_id={branch.id}&brand_id={brand.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert visible_item in {row["item_name_ar"] for row in response.json()}


def _split_fixture(
    db: Session,
    *,
    source_type: SupplySourceType,
    default_source: SupplyDefaultSource,
    resolved: SupplyDefaultSource | None,
    kitchen_section_id: int | None = None,
) -> BranchRequest:
    wh = db.query(Warehouse).filter(Warehouse.warehouse_code == "PH3-SPLIT").first()
    if not wh:
        wh = Warehouse(warehouse_code="PH3-SPLIT", warehouse_name="Split WH", location="Riyadh", active=True)
        db.add(wh)
        db.flush()
    branch = db.query(Branch).filter(Branch.branch_code == "PH3-SPL-BR").first()
    if not branch:
        branch = Branch(branch_code="PH3-SPL-BR", branch_name="Split Branch", city="Riyadh", area="", warehouse_id=wh.id)
        db.add(branch)
        db.flush()
    brand = db.query(Brand).filter(Brand.name == "Onda").first()
    if not brand:
        brand = Brand(name="Onda", active=True)
        db.add(brand)
        db.flush()
    cat = db.query(ItemCategory).filter(ItemCategory.code == "PH3-CAT").first()
    if not cat:
        cat = ItemCategory(code="PH3-CAT", name_ar="Cat", name_en="Cat", active=True)
        db.add(cat)
        db.flush()
    unit = db.query(UnitOfMeasure).filter(UnitOfMeasure.code == "PCS").first()
    if not unit:
        unit = UnitOfMeasure(code="PCS", name_ar="Pcs", name_en="Pcs", active=True)
        db.add(unit)
        db.flush()
    if not db.query(BranchBrand).filter(
        BranchBrand.branch_id == branch.id,
        BranchBrand.brand_id == brand.id,
    ).first():
        db.add(BranchBrand(branch_id=branch.id, brand_id=brand.id))
        db.flush()
    item = db.query(Item).filter(Item.item_code == "PH3-SPLIT-ITEM").first()
    if not item:
        item = Item(
            item_code="PH3-SPLIT-ITEM",
            item_name_ar="Split Item",
            item_name_en="Split Item",
            category_id=cat.id,
            unit_id=unit.id,
            item_type=ItemType.finished_good,
            source_type=source_type,
            default_source=default_source,
            kitchen_section_id=kitchen_section_id,
            branch_requestable=True,
            visible_in_branch_ui=True,
            active=True,
        )
        db.add(item)
        db.flush()
    else:
        item.source_type = source_type
        item.default_source = default_source
        item.kitchen_section_id = kitchen_section_id
        db.flush()
    if not db.query(ItemBrand).filter(ItemBrand.item_id == item.id, ItemBrand.brand_id == brand.id).first():
        db.add(ItemBrand(item_id=item.id, brand_id=brand.id))
        db.flush()
    creator = _branch_user(db, f"ph3_split_{item.id}_{resolved}", branch.id)
    request = BranchRequest(
        request_no=f"BR-PH3-{source_type.value}",
        branch_id=branch.id,
        brand_id=brand.id,
        status=BranchRequestStatus.AREA_APPROVED,
        created_by=creator.id,
    )
    db.add(request)
    db.flush()
    line = BranchRequestLine(
        request_id=request.id,
        item_id=item.id,
        qty_requested=Decimal("5"),
        qty_approved=Decimal("5"),
        source_type=source_type,
        resolved_source_type=resolved,
        status=BranchRequestLineStatus.APPROVED,
    )
    db.add(line)
    db.flush()
    request.lines = [line]
    return request


def test_split_kitchen_creates_production_order(pg_db: Session):
    section = pg_db.query(KitchenSection).filter(KitchenSection.name == "Pizza").first()
    if not section:
        section = KitchenSection(name="Pizza", active=True)
        pg_db.add(section)
        pg_db.flush()
    request = _split_fixture(
        pg_db,
        source_type=SupplySourceType.KITCHEN,
        default_source=SupplyDefaultSource.KITCHEN,
        resolved=SupplyDefaultSource.KITCHEN,
        kitchen_section_id=section.id,
    )
    split_branch_request(pg_db, request)
    assert pg_db.query(ProductionOrder).filter(ProductionOrder.source_request_line_id == request.lines[0].id).count() == 1


def test_split_warehouse_creates_warehouse_line(pg_db: Session):
    request = _split_fixture(
        pg_db,
        source_type=SupplySourceType.WAREHOUSE,
        default_source=SupplyDefaultSource.WAREHOUSE,
        resolved=SupplyDefaultSource.WAREHOUSE,
    )
    split_branch_request(pg_db, request)
    assert pg_db.query(WarehouseLine).filter(WarehouseLine.source_request_line_id == request.lines[0].id).count() == 1


def test_split_both_resolves_to_default(pg_db: Session):
    section = pg_db.query(KitchenSection).filter(KitchenSection.name == "Pizza").first()
    if not section:
        section = KitchenSection(name="Pizza", active=True)
        pg_db.add(section)
        pg_db.flush()
    request = _split_fixture(
        pg_db,
        source_type=SupplySourceType.BOTH,
        default_source=SupplyDefaultSource.KITCHEN,
        resolved=SupplyDefaultSource.KITCHEN,
        kitchen_section_id=section.id,
    )
    split_branch_request(pg_db, request)
    assert pg_db.query(ProductionOrder).filter(ProductionOrder.source_request_line_id == request.lines[0].id).count() == 1


def test_split_unresolvable_source_raises(pg_db: Session):
    request = _split_fixture(
        pg_db,
        source_type=SupplySourceType.WAREHOUSE,
        default_source=SupplyDefaultSource.WAREHOUSE,
        resolved=SupplyDefaultSource.WAREHOUSE,
    )
    request.lines[0].resolved_source_type = None
    pg_db.flush()
    with pytest.raises(AppError) as exc:
        split_branch_request(pg_db, request)
    assert exc.value.error_code == "split.unresolvable_source_type"
