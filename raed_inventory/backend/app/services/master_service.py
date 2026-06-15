from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased, joinedload

from app.core.errors import AppError
from app.models import (
    AreaManagerAssignment, Brand, Branch, BranchBrand, BranchItemAvailability, BranchStock, Item, ItemBrand,
    ItemCategory, ItemType, KitchenSection, StorageType, SupplySourceType, UnitOfMeasure, Warehouse, WarehouseStock,
    InventoryVarianceReason, ReceivingVarianceReason, TransactionType,
)
from app.schemas import ItemCreate, ItemUpdate
from app.services import stock_ledger_service


def _load_item_with_relations(db: Session, item_id: int) -> Item | None:
    return db.query(Item).options(
        joinedload(Item.category),
        joinedload(Item.unit),
        joinedload(Item.purchase_unit),
        joinedload(Item.supply_unit),
        joinedload(Item.kitchen_section),
    ).filter(Item.id == item_id, Item.is_deleted == False).first()


def _validate_item_references(db: Session, payload: ItemCreate | ItemUpdate):
    data = payload.model_dump(exclude_unset=True)

    if "category_id" in data and not db.query(ItemCategory).filter(ItemCategory.id == data["category_id"]).first():
        raise AppError(
            status_code=400,
            error_code="master.category_not_found",
            message="Category not found",
            detail={"category_id": data["category_id"]},
        )

    unit_fields = ["unit_id", "purchase_unit_id", "supply_unit_id"]
    for field_name in unit_fields:
        if field_name in data and data[field_name] is not None:
            if not db.query(UnitOfMeasure).filter(UnitOfMeasure.id == data[field_name]).first():
                raise AppError(
                    status_code=400,
                    error_code="master.unit_not_found",
                    message=f"{field_name} not found",
                    detail={"field": field_name, "unit_id": data[field_name]},
                )

    if "kitchen_section_id" in data and data["kitchen_section_id"] is not None:
        if not db.query(KitchenSection).filter(KitchenSection.id == data["kitchen_section_id"]).first():
            raise AppError(
                status_code=400,
                error_code="master.kitchen_section_not_found",
                message="Kitchen section not found",
                detail={"kitchen_section_id": data["kitchen_section_id"]},
            )


def list_items(
    db: Session,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    category_id: int | None = None,
    item_type: str | None = None,
    storage_type: str | None = None,
    active_only: bool = True,
    critical_only: bool = False,
    branch_id: int | None = None,
    brand_id: int | None = None,
    visible_in_branch_ui_only: bool = False,
    requestable_only: bool = False,
) -> dict:
    q = db.query(Item).options(
        joinedload(Item.category),
        joinedload(Item.unit),
        joinedload(Item.purchase_unit),
        joinedload(Item.supply_unit),
        joinedload(Item.kitchen_section),
    ).filter(Item.is_deleted == False)

    if active_only:
        q = q.filter(Item.active == True)
    if critical_only:
        q = q.filter(Item.critical_item == True)
    if category_id:
        q = q.filter(Item.category_id == category_id)
    if brand_id:
        q = q.join(ItemBrand, ItemBrand.item_id == Item.id).filter(ItemBrand.brand_id == brand_id)
    branch_item_availability = None
    if branch_id:
        branch_item_availability = aliased(BranchItemAvailability)
        q = (
            q.outerjoin(
                branch_item_availability,
                and_(
                    branch_item_availability.item_id == Item.id,
                    branch_item_availability.branch_id == branch_id,
                ),
            )
            .outerjoin(ItemBrand, ItemBrand.item_id == Item.id)
            .outerjoin(
                BranchBrand,
                and_(BranchBrand.brand_id == ItemBrand.brand_id, BranchBrand.branch_id == branch_id),
            )
            .filter(
                or_(
                    and_(branch_item_availability.id == None, BranchBrand.branch_id == branch_id),
                    branch_item_availability.active == True,
                )
            )
        )
    if visible_in_branch_ui_only:
        base_visible = and_(
            Item.visible_in_branch_ui == True,
            Item.source_type != SupplySourceType.NOT_REQUESTABLE,
            Item.item_type != ItemType.raw_material,
            Item.item_code.notlike("DEMO-%"),
        )
        q = q.filter(or_(branch_item_availability.active == True, base_visible) if branch_item_availability is not None else base_visible)
    if requestable_only:
        requestable_filter = and_(
            Item.branch_requestable == True,
            Item.source_type != SupplySourceType.NOT_REQUESTABLE,
            Item.item_type != ItemType.raw_material,
        )
        q = q.filter(
            or_(branch_item_availability.active == True, requestable_filter)
            if branch_item_availability is not None
            else requestable_filter
        )
    if item_type:
        try:
            q = q.filter(Item.item_type == ItemType(item_type))
        except ValueError:
            raise AppError(
                status_code=400,
                error_code="master.invalid_item_type",
                message="Invalid item_type value",
                detail={"item_type": item_type, "valid": [e.value for e in ItemType]},
            )
    if storage_type:
        try:
            q = q.filter(Item.storage_type == StorageType(storage_type))
        except ValueError:
            raise AppError(
                status_code=400,
                error_code="master.invalid_storage_type",
                message="Invalid storage_type value",
                detail={"storage_type": storage_type, "valid": [e.value for e in StorageType]},
            )
    if search:
        q = q.filter(
            Item.item_name_ar.ilike(f"%{search}%") |
            Item.item_name_en.ilike(f"%{search}%") |
            Item.item_code.ilike(f"%{search}%")
        )

    q = q.distinct()
    total = q.count()
    items = q.order_by(Item.category_id.asc(), Item.item_name_ar.asc(), Item.item_code.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def list_categories(db: Session):
    return db.query(ItemCategory).filter(ItemCategory.active == True).all()


def create_category(db: Session, *, code: str, name_ar: str, name_en: str, active: bool = True) -> ItemCategory:
    if db.query(ItemCategory).filter(ItemCategory.code == code).first():
        raise AppError(
            status_code=400,
            error_code="master.category_code_exists",
            message="Category code exists",
            detail={"code": code},
        )
    category = ItemCategory(code=code, name_ar=name_ar, name_en=name_en, active=active)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def list_units(db: Session):
    return db.query(UnitOfMeasure).filter(UnitOfMeasure.active == True).all()


def create_unit(db: Session, *, code: str, name_ar: str, name_en: str, active: bool = True) -> UnitOfMeasure:
    if db.query(UnitOfMeasure).filter(UnitOfMeasure.code == code).first():
        raise AppError(
            status_code=400,
            error_code="master.unit_code_exists",
            message="Unit code exists",
            detail={"code": code},
        )
    unit = UnitOfMeasure(code=code, name_ar=name_ar, name_en=name_en, active=active)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def list_warehouses(db: Session, *, active_only: bool = False):
    q = db.query(Warehouse).filter(Warehouse.is_deleted == False)
    if active_only:
        q = q.filter(Warehouse.active == True)
    return q.all()


def create_warehouse(db: Session, *, warehouse_code: str, warehouse_name: str, location: str | None = None, active: bool = True) -> Warehouse:
    if db.query(Warehouse).filter(Warehouse.warehouse_code == warehouse_code, Warehouse.is_deleted == False).first():
        raise AppError(
            status_code=400,
            error_code="master.warehouse_code_exists",
            message="Warehouse code already exists",
            detail={"warehouse_code": warehouse_code},
        )
    warehouse = Warehouse(
        warehouse_code=warehouse_code,
        warehouse_name=warehouse_name,
        location=location,
        active=active,
    )
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def update_warehouse(db: Session, wh_id: int, payload: dict) -> Warehouse:
    warehouse = db.query(Warehouse).filter(Warehouse.id == wh_id, Warehouse.is_deleted == False).first()
    if not warehouse:
        raise AppError(
            status_code=404,
            error_code="master.warehouse_not_found",
            message="Warehouse not found",
            detail={"warehouse_id": wh_id},
        )
    for k, v in payload.items():
        setattr(warehouse, k, v)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def delete_warehouse(db: Session, wh_id: int) -> dict:
    warehouse = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
    if not warehouse:
        raise AppError(
            status_code=404,
            error_code="master.warehouse_not_found",
            message="Warehouse not found",
            detail={"warehouse_id": wh_id},
        )
    warehouse.is_deleted = True
    db.commit()
    return {"message": "Deleted"}


def list_branches(db: Session, *, active_only: bool = False, warehouse_id: int | None = None):
    q = db.query(Branch).filter(Branch.is_deleted == False)
    if active_only:
        q = q.filter(Branch.active == True)
    if warehouse_id:
        q = q.filter(Branch.warehouse_id == warehouse_id)
    return q.all()


def create_branch(
    db: Session,
    *,
    branch_code: str,
    branch_name: str,
    city: str | None = None,
    area: str | None = None,
    warehouse_id: int,
    active: bool = True,
) -> Branch:
    if db.query(Branch).filter(Branch.branch_code == branch_code, Branch.is_deleted == False).first():
        raise AppError(
            status_code=400,
            error_code="master.branch_code_exists",
            message="Branch code already exists",
            detail={"branch_code": branch_code},
        )
    if not db.query(Warehouse).filter(Warehouse.id == warehouse_id).first():
        raise AppError(
            status_code=400,
            error_code="master.warehouse_not_found",
            message="Warehouse not found",
            detail={"warehouse_id": warehouse_id},
        )
    branch = Branch(
        branch_code=branch_code,
        branch_name=branch_name,
        city=city,
        area=area,
        warehouse_id=warehouse_id,
        active=active,
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


def update_branch(db: Session, br_id: int, payload: dict) -> Branch:
    branch = db.query(Branch).filter(Branch.id == br_id, Branch.is_deleted == False).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="master.branch_not_found",
            message="Branch not found",
            detail={"branch_id": br_id},
        )
    if "warehouse_id" in payload and payload["warehouse_id"] is not None:
        if not db.query(Warehouse).filter(Warehouse.id == payload["warehouse_id"]).first():
            raise AppError(
                status_code=400,
                error_code="master.warehouse_not_found",
                message="Warehouse not found",
                detail={"warehouse_id": payload["warehouse_id"]},
            )
    for k, v in payload.items():
        setattr(branch, k, v)
    db.commit()
    db.refresh(branch)
    return branch


def delete_branch(db: Session, br_id: int) -> dict:
    branch = db.query(Branch).filter(Branch.id == br_id).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="master.branch_not_found",
            message="Branch not found",
            detail={"branch_id": br_id},
        )
    branch.is_deleted = True
    db.commit()
    return {"message": "Deleted"}


def get_item(db: Session, item_id: int) -> Item:
    item = _load_item_with_relations(db, item_id)
    if not item:
        raise AppError(
            status_code=404,
            error_code="master.item_not_found",
            message="Item not found",
            detail={"item_id": item_id},
        )
    return item


def create_item(db: Session, payload: ItemCreate) -> Item:
    if db.query(Item).filter(Item.item_code == payload.item_code, Item.is_deleted == False).first():
        raise AppError(
            status_code=400,
            error_code="master.item_code_exists",
            message="Item code already exists",
            detail={"item_code": payload.item_code},
        )
    _validate_item_references(db, payload)
    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    return get_item(db, item.id)


def update_item(db: Session, item_id: int, payload: ItemUpdate) -> Item:
    item = db.query(Item).filter(Item.id == item_id, Item.is_deleted == False).first()
    if not item:
        raise AppError(
            status_code=404,
            error_code="master.item_not_found",
            message="Item not found",
            detail={"item_id": item_id},
        )
    _validate_item_references(db, payload)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    return get_item(db, item.id)


def get_item_stock_card(
    db: Session,
    *,
    item_id: int,
    limit: int = 100,
    transaction_type=None,
    source_type: str | None = None,
    destination_type: str | None = None,
    reference_no: str | None = None,
) -> dict:
    return stock_ledger_service.get_item_stock_card(
        db,
        item_id=item_id,
        limit=limit,
        transaction_type=transaction_type,
        source_type=source_type,
        destination_type=destination_type,
        reference_no=reference_no,
    )


# ─────────────────────────────────────────────
# GET SINGLE ENDPOINTS
# ─────────────────────────────────────────────

def get_warehouse(db: Session, wh_id: int) -> Warehouse:
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == wh_id, Warehouse.is_deleted == False
    ).first()
    if not warehouse:
        raise AppError(
            status_code=404,
            error_code="master.warehouse_not_found",
            message="Warehouse not found",
            detail={"warehouse_id": wh_id},
        )
    return warehouse


def get_branch(db: Session, br_id: int) -> Branch:
    branch = db.query(Branch).filter(
        Branch.id == br_id, Branch.is_deleted == False
    ).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="master.branch_not_found",
            message="Branch not found",
            detail={"branch_id": br_id},
        )
    return branch


def get_category(db: Session, cat_id: int) -> ItemCategory:
    cat = db.query(ItemCategory).filter(ItemCategory.id == cat_id).first()
    if not cat:
        raise AppError(
            status_code=404,
            error_code="master.category_not_found",
            message="Category not found",
            detail={"category_id": cat_id},
        )
    return cat


def get_unit(db: Session, unit_id: int) -> UnitOfMeasure:
    unit = db.query(UnitOfMeasure).filter(UnitOfMeasure.id == unit_id).first()
    if not unit:
        raise AppError(
            status_code=404,
            error_code="master.unit_not_found",
            message="Unit not found",
            detail={"unit_id": unit_id},
        )
    return unit


# ─────────────────────────────────────────────
# CATEGORY UPDATE / DELETE
# ─────────────────────────────────────────────

def update_category(db: Session, cat_id: int, payload: dict) -> ItemCategory:
    cat = get_category(db, cat_id)
    for k, v in payload.items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat_id: int) -> dict:
    cat = get_category(db, cat_id)
    # Guard: cannot deactivate if items reference this category
    active_items = db.query(Item).filter(
        Item.category_id == cat_id,
        Item.is_deleted == False,
        Item.active == True,
    ).count()
    if active_items:
        raise AppError(
            status_code=400,
            error_code="master.category_has_active_items",
            message="Cannot delete category with active items",
            detail={"category_id": cat_id, "active_items": active_items},
        )
    cat.active = False
    db.commit()
    return {"message": "Category deactivated"}


# ─────────────────────────────────────────────
# UNIT UPDATE / DELETE
# ─────────────────────────────────────────────

def update_unit(db: Session, unit_id: int, payload: dict) -> UnitOfMeasure:
    unit = get_unit(db, unit_id)
    for k, v in payload.items():
        setattr(unit, k, v)
    db.commit()
    db.refresh(unit)
    return unit


def delete_unit(db: Session, unit_id: int) -> dict:
    unit = get_unit(db, unit_id)
    active_items = db.query(Item).filter(
        Item.unit_id == unit_id,
        Item.is_deleted == False,
        Item.active == True,
    ).count()
    if active_items:
        raise AppError(
            status_code=400,
            error_code="master.unit_has_active_items",
            message="Cannot delete unit with active items",
            detail={"unit_id": unit_id, "active_items": active_items},
        )
    unit.active = False
    db.commit()
    return {"message": "Unit deactivated"}


# ─────────────────────────────────────────────
# INVENTORY VARIANCE REASONS CRUD
# ─────────────────────────────────────────────

def list_variance_reasons(db: Session, *, active_only: bool = True):
    q = db.query(InventoryVarianceReason)
    if active_only:
        q = q.filter(InventoryVarianceReason.active == True)
    return q.order_by(InventoryVarianceReason.id).all()


def create_variance_reason(
    db: Session, *, reason_ar: str, reason_en: str, active: bool = True
) -> InventoryVarianceReason:
    reason = InventoryVarianceReason(reason_ar=reason_ar, reason_en=reason_en, active=active)
    db.add(reason)
    db.commit()
    db.refresh(reason)
    return reason


def _get_variance_reason(db: Session, reason_id: int) -> InventoryVarianceReason:
    reason = db.query(InventoryVarianceReason).filter(
        InventoryVarianceReason.id == reason_id
    ).first()
    if not reason:
        raise AppError(
            status_code=404,
            error_code="master.variance_reason_not_found",
            message="Inventory variance reason not found",
            detail={"reason_id": reason_id},
        )
    return reason


def update_variance_reason(db: Session, reason_id: int, payload: dict) -> InventoryVarianceReason:
    reason = _get_variance_reason(db, reason_id)
    for k, v in payload.items():
        setattr(reason, k, v)
    db.commit()
    db.refresh(reason)
    return reason


def delete_variance_reason(db: Session, reason_id: int) -> dict:
    reason = _get_variance_reason(db, reason_id)
    reason.active = False
    db.commit()
    return {"message": "Variance reason deactivated"}


# ─────────────────────────────────────────────
# RECEIVING VARIANCE REASONS CRUD
# ─────────────────────────────────────────────

def list_receiving_variance_reasons(db: Session, *, active_only: bool = True):
    q = db.query(ReceivingVarianceReason)
    if active_only:
        q = q.filter(ReceivingVarianceReason.active == True)
    return q.order_by(ReceivingVarianceReason.id).all()


def create_receiving_variance_reason(
    db: Session, *, reason_ar: str, reason_en: str, active: bool = True
) -> ReceivingVarianceReason:
    reason = ReceivingVarianceReason(reason_ar=reason_ar, reason_en=reason_en, active=active)
    db.add(reason)
    db.commit()
    db.refresh(reason)
    return reason


def _get_receiving_variance_reason(db: Session, reason_id: int) -> ReceivingVarianceReason:
    reason = db.query(ReceivingVarianceReason).filter(
        ReceivingVarianceReason.id == reason_id
    ).first()
    if not reason:
        raise AppError(
            status_code=404,
            error_code="master.receiving_variance_reason_not_found",
            message="Receiving variance reason not found",
            detail={"reason_id": reason_id},
        )
    return reason


def update_receiving_variance_reason(
    db: Session, reason_id: int, payload: dict
) -> ReceivingVarianceReason:
    reason = _get_receiving_variance_reason(db, reason_id)
    for k, v in payload.items():
        setattr(reason, k, v)
    db.commit()
    db.refresh(reason)
    return reason


def delete_receiving_variance_reason(db: Session, reason_id: int) -> dict:
    reason = _get_receiving_variance_reason(db, reason_id)
    reason.active = False
    db.commit()
    return {"message": "Receiving variance reason deactivated"}


# ─────────────────────────────────────────────
# STOCK INITIALIZATION (opening balance)
# ─────────────────────────────────────────────

def initialize_branch_stock(
    db: Session,
    *,
    item_id: int,
    branch_id: int,
    opening_qty: Decimal,
    notes: str | None = None,
    created_by: int | None = None,
) -> BranchStock:
    """
    Set the opening balance for an item at a branch.
    Creates the BranchStock record if missing, then posts an
    opening_balance transaction to the ledger.
    Calling this again on an existing record REPLACES the qty
    (posts a corrective delta transaction).
    """
    item = db.query(Item).filter(Item.id == item_id, Item.is_deleted == False).first()
    if not item:
        raise AppError(
            status_code=404,
            error_code="master.item_not_found",
            message="Item not found",
            detail={"item_id": item_id},
        )
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_deleted == False).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="master.branch_not_found",
            message="Branch not found",
            detail={"branch_id": branch_id},
        )

    stock = db.query(BranchStock).filter(
        BranchStock.branch_id == branch_id,
        BranchStock.item_id == item_id,
    ).first()

    if stock is None:
        stock = BranchStock(
            branch_id=branch_id,
            item_id=item_id,
            current_qty=opening_qty,
            reserved_qty=Decimal("0"),
            in_transit_qty=Decimal("0"),
        )
        db.add(stock)
        delta = opening_qty
    else:
        delta = opening_qty - Decimal(str(stock.current_qty))
        stock.current_qty = opening_qty

    # Post ledger entry only if there's an actual quantity to record
    if delta != 0:
        stock_ledger_service.post_transaction(
            db,
            transaction_type=TransactionType.opening_balance,
            item_id=item_id,
            qty=delta,
            destination_type="branch",
            destination_id=branch_id,
            reference_no=f"OPEN-BR-{branch_id}-{item_id}",
            notes=notes or "Opening balance",
            created_by=created_by,
        )

    db.commit()
    db.refresh(stock)
    return stock


def initialize_warehouse_stock(
    db: Session,
    *,
    item_id: int,
    warehouse_id: int,
    opening_qty: Decimal,
    notes: str | None = None,
    created_by: int | None = None,
) -> WarehouseStock:
    """
    Set the opening balance for an item at a warehouse.
    Creates the WarehouseStock record if missing, then posts an
    opening_balance transaction to the ledger.
    """
    item = db.query(Item).filter(Item.id == item_id, Item.is_deleted == False).first()
    if not item:
        raise AppError(
            status_code=404,
            error_code="master.item_not_found",
            message="Item not found",
            detail={"item_id": item_id},
        )
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id, Warehouse.is_deleted == False
    ).first()
    if not warehouse:
        raise AppError(
            status_code=404,
            error_code="master.warehouse_not_found",
            message="Warehouse not found",
            detail={"warehouse_id": warehouse_id},
        )

    stock = db.query(WarehouseStock).filter(
        WarehouseStock.warehouse_id == warehouse_id,
        WarehouseStock.item_id == item_id,
    ).first()

    if stock is None:
        stock = WarehouseStock(
            warehouse_id=warehouse_id,
            item_id=item_id,
            current_qty=opening_qty,
            reserved_qty=Decimal("0"),
        )
        db.add(stock)
        delta = opening_qty
    else:
        delta = opening_qty - Decimal(str(stock.current_qty))
        stock.current_qty = opening_qty

    if delta != 0:
        stock_ledger_service.post_transaction(
            db,
            transaction_type=TransactionType.opening_balance,
            item_id=item_id,
            qty=delta,
            destination_type="warehouse",
            destination_id=warehouse_id,
            reference_no=f"OPEN-WH-{warehouse_id}-{item_id}",
            notes=notes or "Opening balance",
            created_by=created_by,
        )

    db.commit()
    db.refresh(stock)
    return stock


# ─────────────────────────────────────────────
# BRANCH / WAREHOUSE STOCK VIEWS
# ─────────────────────────────────────────────

def list_branch_stock(
    db: Session,
    *,
    branch_id: int,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
    low_stock_only: bool = False,
) -> dict:
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_deleted == False).first()
    if not branch:
        raise AppError(
            status_code=404,
            error_code="master.branch_not_found",
            message="Branch not found",
            detail={"branch_id": branch_id},
        )

    q = db.query(BranchStock).options(
        joinedload(BranchStock.item).joinedload(Item.category),
        joinedload(BranchStock.item).joinedload(Item.unit),
    ).join(BranchStock.item).filter(
        BranchStock.branch_id == branch_id,
        Item.is_deleted == False,
    )

    if search:
        q = q.filter(
            Item.item_name_ar.ilike(f"%{search}%") |
            Item.item_name_en.ilike(f"%{search}%") |
            Item.item_code.ilike(f"%{search}%")
        )
    if low_stock_only:
        # Items where current_qty <= reorder_point
        q = q.filter(BranchStock.current_qty <= Item.reorder_point)

    total = q.count()
    records = q.order_by(BranchStock.id).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": records}


def list_warehouse_stock(
    db: Session,
    *,
    warehouse_id: int,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> dict:
    warehouse = db.query(Warehouse).filter(
        Warehouse.id == warehouse_id, Warehouse.is_deleted == False
    ).first()
    if not warehouse:
        raise AppError(
            status_code=404,
            error_code="master.warehouse_not_found",
            message="Warehouse not found",
            detail={"warehouse_id": warehouse_id},
        )

    q = db.query(WarehouseStock).options(
        joinedload(WarehouseStock.item).joinedload(Item.category),
        joinedload(WarehouseStock.item).joinedload(Item.unit),
    ).join(WarehouseStock.item).filter(
        WarehouseStock.warehouse_id == warehouse_id,
        Item.is_deleted == False,
    )

    if search:
        q = q.filter(
            Item.item_name_ar.ilike(f"%{search}%") |
            Item.item_name_en.ilike(f"%{search}%") |
            Item.item_code.ilike(f"%{search}%")
        )

    total = q.count()
    records = q.order_by(WarehouseStock.id).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": records}
