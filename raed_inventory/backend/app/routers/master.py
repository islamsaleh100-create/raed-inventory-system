"""
Master Data Router — /api/v1/master
Covers: warehouses, branches, items, categories, units,
        variance reasons, stock initialization, stock views.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_current_active_user, get_user_roles, require_roles
from app.core.errors import AppError
from app.database import get_db
from app.models import (
    AreaManagerAssignment, Brand, Branch, BranchBrand, Item, ItemBrand,
    Kitchen, KitchenSection, KitchenSectionAssignment, TransactionType, User,
)
from app.schemas import (
    # Warehouse
    WarehouseCreate, WarehouseUpdate, WarehouseOut,
    # Branch
    BranchCreate, BranchUpdate, BranchOut,
    # Category
    CategoryCreate, CategoryUpdate, CategoryOut,
    # Unit
    UnitCreate, UnitUpdate, UnitOut,
    # Supply chain master data
    AreaManagerAssignmentCreate, BrandCreate, BrandOut, BranchBrandCreate,
    ItemBrandCreate, KitchenSectionAssignmentCreate, KitchenSectionAssignmentOut,
    KitchenSectionCreate, KitchenSectionOut, KitchenCreate, KitchenOut,
    # Item
    ItemCreate, ItemUpdate, ItemOut, ItemListResponse, StockCardResponse,
    # Variance reasons
    VarianceReasonCreate, VarianceReasonUpdate, VarianceReasonOut,
    # Stock init / views
    StockInitRequest, StockInitResponse,
    BranchStockOut, BranchStockListResponse,
    WarehouseStockOut, WarehouseStockListResponse,
)
from app.services import master_service

router = APIRouter(prefix="/api/v1/master", tags=["Master Data"])

admin_roles = ["admin", "super_admin"]


def _ensure_exists(db: Session, model, obj_id: int, label: str):
    obj = db.query(model).filter(model.id == obj_id).first()
    if not obj:
        raise AppError(
            status_code=404,
            error_code=f"master.{label}_not_found",
            message=f"{label} not found",
            detail={f"{label}_id": obj_id},
        )
    return obj


# ──────────────────────────────────────────────────────────────────────────
# WAREHOUSES
# ──────────────────────────────────────────────────────────────────────────

@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(
    active_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.list_warehouses(db, active_only=active_only)


@router.get("/warehouses/{wh_id}", response_model=WarehouseOut)
def get_warehouse(
    wh_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.get_warehouse(db, wh_id)


@router.post("/warehouses", response_model=WarehouseOut, status_code=201)
def create_warehouse(
    payload: WarehouseCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.create_warehouse(db, **payload.model_dump())


@router.put("/warehouses/{wh_id}", response_model=WarehouseOut)
def update_warehouse(
    wh_id: int,
    payload: WarehouseUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.update_warehouse(db, wh_id, payload.model_dump(exclude_unset=True))


@router.delete("/warehouses/{wh_id}")
def delete_warehouse(
    wh_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.delete_warehouse(db, wh_id)


# Warehouse stock view
@router.get("/warehouses/{wh_id}/stock", response_model=WarehouseStockListResponse)
def list_warehouse_stock(
    wh_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.list_warehouse_stock(
        db, warehouse_id=wh_id, page=page, page_size=page_size, search=search
    )


# ──────────────────────────────────────────────────────────────────────────
# BRANCHES
# ──────────────────────────────────────────────────────────────────────────

@router.get("/branches", response_model=list[BranchOut])
def list_branches(
    active_only: bool = False,
    warehouse_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.list_branches(db, active_only=active_only, warehouse_id=warehouse_id)


@router.get("/branches/{br_id}", response_model=BranchOut)
def get_branch(
    br_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.get_branch(db, br_id)


@router.post("/branches", response_model=BranchOut, status_code=201)
def create_branch(
    payload: BranchCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.create_branch(db, **payload.model_dump())


@router.put("/branches/{br_id}", response_model=BranchOut)
def update_branch(
    br_id: int,
    payload: BranchUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.update_branch(db, br_id, payload.model_dump(exclude_unset=True))


@router.delete("/branches/{br_id}")
def delete_branch(
    br_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.delete_branch(db, br_id)


# Branch stock view
@router.get("/branches/{br_id}/stock", response_model=BranchStockListResponse)
def list_branch_stock(
    br_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    low_stock_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.list_branch_stock(
        db,
        branch_id=br_id,
        page=page,
        page_size=page_size,
        search=search,
        low_stock_only=low_stock_only,
    )


# ──────────────────────────────────────────────────────────────────────────
# ITEM CATEGORIES
# ──────────────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    if active_only:
        return master_service.list_categories(db)
    from app.models import ItemCategory
    return db.query(ItemCategory).order_by(ItemCategory.id).all()


@router.get("/categories/{cat_id}", response_model=CategoryOut)
def get_category(
    cat_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.get_category(db, cat_id)


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.create_category(db, **payload.model_dump())


@router.put("/categories/{cat_id}", response_model=CategoryOut)
def update_category(
    cat_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.update_category(db, cat_id, payload.model_dump(exclude_unset=True))


@router.delete("/categories/{cat_id}")
def delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.delete_category(db, cat_id)


# ──────────────────────────────────────────────────────────────────────────
# UNITS OF MEASURE
# ──────────────────────────────────────────────────────────────────────────

@router.get("/units", response_model=list[UnitOut])
def list_units(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    if active_only:
        return master_service.list_units(db)
    from app.models import UnitOfMeasure
    return db.query(UnitOfMeasure).order_by(UnitOfMeasure.id).all()


@router.get("/units/{unit_id}", response_model=UnitOut)
def get_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.get_unit(db, unit_id)


@router.post("/units", response_model=UnitOut, status_code=201)
def create_unit(
    payload: UnitCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.create_unit(db, **payload.model_dump())


@router.put("/units/{unit_id}", response_model=UnitOut)
def update_unit(
    unit_id: int,
    payload: UnitUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.update_unit(db, unit_id, payload.model_dump(exclude_unset=True))


@router.delete("/units/{unit_id}")
def delete_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.delete_unit(db, unit_id)


# ──────────────────────────────────────────────────────────────────────────
# SUPPLY CHAIN MASTER DATA (Phase 1)
# ──────────────────────────────────────────────────────────────────────────

@router.get("/brands", response_model=list[BrandOut])
def list_brands(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    q = db.query(Brand)
    if active_only:
        q = q.filter(Brand.active == True)
    return q.order_by(Brand.name).all()


@router.post("/brands", response_model=BrandOut, status_code=201)
def create_brand(
    payload: BrandCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    exists = db.query(Brand).filter(Brand.name == payload.name).first()
    if exists:
        raise AppError(
            status_code=400,
            error_code="master.brand_exists",
            message="Brand already exists",
            detail={"name": payload.name},
        )
    brand = Brand(**payload.model_dump())
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


@router.get("/kitchens", response_model=list[KitchenOut])
def list_kitchens(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    q = db.query(Kitchen).options(joinedload(Kitchen.sections))
    if active_only:
        q = q.filter(Kitchen.active == True)
    return q.order_by(Kitchen.city, Kitchen.name).all()


@router.post("/kitchens", response_model=KitchenOut, status_code=201)
def create_kitchen(
    payload: KitchenCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    dup = (
        db.query(Kitchen)
        .filter(
            func.lower(func.trim(Kitchen.name)) == func.lower(func.trim(payload.name)),
            func.lower(func.trim(Kitchen.city)) == func.lower(func.trim(payload.city)),
        )
        .first()
    )
    if dup:
        raise AppError(
            status_code=400,
            error_code="master.kitchen_exists",
            message="Kitchen with this name and city already exists",
            detail={"name": payload.name, "city": payload.city},
        )
    row = Kitchen(name=payload.name.strip(), city=payload.city.strip(), active=payload.active)
    db.add(row)
    db.flush()
    for sid in payload.section_ids:
        sec = db.query(KitchenSection).filter(KitchenSection.id == sid).first()
        if sec and sec not in row.sections:
            row.sections.append(sec)
    db.commit()
    db.refresh(row)
    return db.query(Kitchen).options(joinedload(Kitchen.sections)).filter(Kitchen.id == row.id).first()


@router.get("/kitchen-sections", response_model=list[KitchenSectionOut])
def list_kitchen_sections(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    q = db.query(KitchenSection).options(joinedload(KitchenSection.kitchens))
    if active_only:
        q = q.filter(KitchenSection.active == True)
    return q.order_by(KitchenSection.name).all()


@router.post("/kitchen-sections", response_model=KitchenSectionOut, status_code=201)
def create_kitchen_section(
    payload: KitchenSectionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    exists = db.query(KitchenSection).filter(KitchenSection.name == payload.name).first()
    if exists:
        raise AppError(
            status_code=400,
            error_code="master.kitchen_section_exists",
            message="Kitchen section already exists",
            detail={"name": payload.name},
        )
    section = KitchenSection(**payload.model_dump())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.post("/branch-brands", status_code=201)
def assign_branch_brand(
    payload: BranchBrandCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    _ensure_exists(db, Branch, payload.branch_id, "branch")
    _ensure_exists(db, Brand, payload.brand_id, "brand")
    row = db.query(BranchBrand).filter(
        BranchBrand.branch_id == payload.branch_id,
        BranchBrand.brand_id == payload.brand_id,
    ).first()
    if not row:
        row = BranchBrand(branch_id=payload.branch_id, brand_id=payload.brand_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return {"id": row.id, "branch_id": row.branch_id, "brand_id": row.brand_id}


@router.post("/item-brands", status_code=201)
def assign_item_brand(
    payload: ItemBrandCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    _ensure_exists(db, Item, payload.item_id, "item")
    _ensure_exists(db, Brand, payload.brand_id, "brand")
    row = db.query(ItemBrand).filter(
        ItemBrand.item_id == payload.item_id,
        ItemBrand.brand_id == payload.brand_id,
    ).first()
    if not row:
        row = ItemBrand(item_id=payload.item_id, brand_id=payload.brand_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return {"id": row.id, "item_id": row.item_id, "brand_id": row.brand_id}


@router.post("/area-manager-assignments", status_code=201)
def assign_area_manager(
    payload: AreaManagerAssignmentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    user = _ensure_exists(db, User, payload.user_id, "user")
    _ensure_exists(db, Brand, payload.brand_id, "brand")
    if "area_manager" not in get_user_roles(user):
        raise AppError(
            status_code=400,
            error_code="master.user_not_area_manager",
            message="Assigned user must have area_manager role",
            detail={"user_id": payload.user_id},
        )
    duplicate = db.query(AreaManagerAssignment).filter(
        AreaManagerAssignment.user_id == payload.user_id,
        func.lower(AreaManagerAssignment.city) == payload.city.lower(),
        AreaManagerAssignment.brand_id == payload.brand_id,
        AreaManagerAssignment.active == True,
    ).first()
    if duplicate:
        raise AppError(
            status_code=400,
            error_code="master.duplicate_area_manager_assignment",
            message="Active area-manager assignment already exists",
            detail={"user_id": payload.user_id, "city": payload.city, "brand_id": payload.brand_id},
        )
    row = AreaManagerAssignment(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "user_id": row.user_id,
        "city": row.city,
        "brand_id": row.brand_id,
        "active": row.active,
    }


@router.get("/kitchen-section-assignments", response_model=list[KitchenSectionAssignmentOut])
def list_kitchen_section_assignments(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    q = db.query(KitchenSectionAssignment)
    if active_only:
        q = q.filter(KitchenSectionAssignment.active == True)
    return q.order_by(KitchenSectionAssignment.id).all()


@router.post("/kitchen-section-assignments", response_model=KitchenSectionAssignmentOut, status_code=201)
def assign_kitchen_section(
    payload: KitchenSectionAssignmentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    user = _ensure_exists(db, User, payload.user_id, "user")
    section = _ensure_exists(db, KitchenSection, payload.kitchen_section_id, "kitchen_section")
    if not section.active:
        raise AppError(
            status_code=400,
            error_code="master.kitchen_section_inactive",
            message="Kitchen section is inactive",
            detail={"kitchen_section_id": payload.kitchen_section_id},
        )
    if "kitchen_section_manager" not in get_user_roles(user):
        raise AppError(
            status_code=400,
            error_code="master.user_not_kitchen_section_manager",
            message="Assigned user must have kitchen_section_manager role",
            detail={"user_id": payload.user_id},
        )
    duplicate = db.query(KitchenSectionAssignment).filter(
        KitchenSectionAssignment.user_id == payload.user_id,
        KitchenSectionAssignment.kitchen_section_id == payload.kitchen_section_id,
        KitchenSectionAssignment.active == True,
    ).first()
    if duplicate:
        raise AppError(
            status_code=400,
            error_code="master.duplicate_kitchen_section_assignment",
            message="Active kitchen section assignment already exists",
            detail={"user_id": payload.user_id, "kitchen_section_id": payload.kitchen_section_id},
        )
    row = KitchenSectionAssignment(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/kitchen-section-assignments/{assignment_id}/deactivate", response_model=KitchenSectionAssignmentOut)
def deactivate_kitchen_section_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    row = _ensure_exists(db, KitchenSectionAssignment, assignment_id, "kitchen_section_assignment")
    row.active = False
    row.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


# ──────────────────────────────────────────────────────────────────────────
# ITEMS
# ──────────────────────────────────────────────────────────────────────────

@router.get("/items", response_model=ItemListResponse)
def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    item_type: Optional[str] = None,
    storage_type: Optional[str] = None,
    active_only: bool = True,
    critical_only: bool = False,
    branch_id: Optional[int] = None,
    brand_id: Optional[int] = None,
    visible_in_branch_ui_only: bool = False,
    requestable_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.list_items(
        db,
        page=page,
        page_size=page_size,
        search=search,
        category_id=category_id,
        item_type=item_type,
        storage_type=storage_type,
        active_only=active_only,
        critical_only=critical_only,
        branch_id=branch_id,
        brand_id=brand_id,
        visible_in_branch_ui_only=visible_in_branch_ui_only,
        requestable_only=requestable_only,
    )


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.get_item(db, item_id)


@router.get("/items/{item_id}/stock-card", response_model=StockCardResponse)
def get_item_stock_card(
    item_id: int,
    limit: int = Query(100, ge=1, le=500),
    transaction_type: Optional[str] = None,
    source_type: Optional[str] = None,
    destination_type: Optional[str] = None,
    reference_no: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    parsed_transaction_type = None
    if transaction_type:
        try:
            parsed_transaction_type = TransactionType(transaction_type)
        except ValueError:
            raise AppError(
                status_code=400,
                error_code="ledger.invalid_transaction_type_filter",
                message="Invalid transaction_type filter",
                detail={"transaction_type": transaction_type},
            )

    return master_service.get_item_stock_card(
        db,
        item_id=item_id,
        limit=limit,
        transaction_type=parsed_transaction_type,
        source_type=source_type,
        destination_type=destination_type,
        reference_no=reference_no,
    )


@router.post("/items", response_model=ItemOut, status_code=201)
def create_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.create_item(db, payload)


@router.put("/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    payload: ItemUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.update_item(db, item_id, payload)


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    # Soft-delete via service (consistent AppError on not-found)
    master_service.get_item(db, item_id)          # raises 404 if missing
    from app.models import Item
    item = db.query(Item).filter(Item.id == item_id).first()
    item.is_deleted = True
    db.commit()
    return {"message": "Item deleted"}


# Stock initialization for an item at a branch
@router.post("/items/{item_id}/stock/branch/{branch_id}", response_model=StockInitResponse)
def init_branch_stock(
    item_id: int,
    branch_id: int,
    payload: StockInitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*admin_roles)),
):
    stock = master_service.initialize_branch_stock(
        db,
        item_id=item_id,
        branch_id=branch_id,
        opening_qty=payload.opening_qty,
        notes=payload.notes,
        created_by=current_user.id,
    )
    return StockInitResponse(
        message="Branch stock initialised",
        item_id=item_id,
        entity_type="branch",
        entity_id=branch_id,
        current_qty=stock.current_qty,
    )


# Stock initialization for an item at a warehouse
@router.post("/items/{item_id}/stock/warehouse/{warehouse_id}", response_model=StockInitResponse)
def init_warehouse_stock(
    item_id: int,
    warehouse_id: int,
    payload: StockInitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*admin_roles)),
):
    stock = master_service.initialize_warehouse_stock(
        db,
        item_id=item_id,
        warehouse_id=warehouse_id,
        opening_qty=payload.opening_qty,
        notes=payload.notes,
        created_by=current_user.id,
    )
    return StockInitResponse(
        message="Warehouse stock initialised",
        item_id=item_id,
        entity_type="warehouse",
        entity_id=warehouse_id,
        current_qty=stock.current_qty,
    )


# ──────────────────────────────────────────────────────────────────────────
# INVENTORY VARIANCE REASONS
# ──────────────────────────────────────────────────────────────────────────

@router.get("/variance-reasons", response_model=list[VarianceReasonOut])
def list_variance_reasons(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.list_variance_reasons(db, active_only=active_only)


@router.post("/variance-reasons", response_model=VarianceReasonOut, status_code=201)
def create_variance_reason(
    payload: VarianceReasonCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.create_variance_reason(db, **payload.model_dump())


@router.put("/variance-reasons/{reason_id}", response_model=VarianceReasonOut)
def update_variance_reason(
    reason_id: int,
    payload: VarianceReasonUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.update_variance_reason(
        db, reason_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/variance-reasons/{reason_id}")
def delete_variance_reason(
    reason_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.delete_variance_reason(db, reason_id)


# ──────────────────────────────────────────────────────────────────────────
# RECEIVING VARIANCE REASONS
# ──────────────────────────────────────────────────────────────────────────

@router.get("/receiving-variance-reasons", response_model=list[VarianceReasonOut])
def list_receiving_variance_reasons(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    return master_service.list_receiving_variance_reasons(db, active_only=active_only)


@router.post("/receiving-variance-reasons", response_model=VarianceReasonOut, status_code=201)
def create_receiving_variance_reason(
    payload: VarianceReasonCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.create_receiving_variance_reason(db, **payload.model_dump())


@router.put("/receiving-variance-reasons/{reason_id}", response_model=VarianceReasonOut)
def update_receiving_variance_reason(
    reason_id: int,
    payload: VarianceReasonUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.update_receiving_variance_reason(
        db, reason_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/receiving-variance-reasons/{reason_id}")
def delete_receiving_variance_reason(
    reason_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*admin_roles)),
):
    return master_service.delete_receiving_variance_reason(db, reason_id)
