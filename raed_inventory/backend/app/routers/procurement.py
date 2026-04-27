from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_user_roles, require_roles
from app.core.errors import AppError
from app.database import get_db
from app.models import Item, PurchaseRequest, PurchaseRequestLine, PurchaseRequestStatus, Supplier, User, Warehouse
from app.schemas import PurchaseRequestCreate, PurchaseRequestOut, SupplierCreate, SupplierOut


router = APIRouter(prefix="/api/v1/procurement", tags=["Procurement"])


def _is_admin(user: User) -> bool:
    return any(role in ("admin", "super_admin") for role in get_user_roles(user))


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_manager", "admin", "super_admin")),
):
    return db.query(Supplier).order_by(Supplier.name).all()


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_manager", "admin", "super_admin")),
):
    exists = db.query(Supplier).filter(Supplier.supplier_code == payload.supplier_code).first()
    if exists:
        raise AppError(status_code=400, error_code="procurement.supplier_code_exists", message="Supplier code already exists")
    row = Supplier(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/purchase-requests", response_model=list[PurchaseRequestOut])
def list_purchase_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_manager", "admin", "super_admin")),
):
    q = db.query(PurchaseRequest).options(joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.item))
    if not _is_admin(current_user) and current_user.warehouse_id:
        q = q.filter(PurchaseRequest.warehouse_id == current_user.warehouse_id)
    return q.order_by(PurchaseRequest.created_at.desc()).all()


@router.post("/purchase-requests", response_model=PurchaseRequestOut, status_code=201)
def create_purchase_request(
    payload: PurchaseRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("warehouse_manager", "admin", "super_admin")),
):
    warehouse = db.query(Warehouse).filter(Warehouse.id == payload.warehouse_id).first()
    if not warehouse:
        raise AppError(status_code=404, error_code="procurement.warehouse_not_found", message="Warehouse not found")
    if not _is_admin(current_user) and current_user.warehouse_id and current_user.warehouse_id != payload.warehouse_id:
        raise AppError(status_code=403, error_code="procurement.warehouse_scope_denied", message="Cannot create purchase request for another warehouse")

    row = PurchaseRequest(
        warehouse_id=payload.warehouse_id,
        requested_by=current_user.id,
        status=PurchaseRequestStatus.DRAFT,
        notes=payload.notes,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    for line in payload.lines:
        item = db.query(Item).filter(Item.id == line.item_id, Item.is_deleted == False).first()
        if not item:
            raise AppError(status_code=400, error_code="procurement.item_not_found", message="Purchase request item not found")
        row.lines.append(
            PurchaseRequestLine(
                item_id=line.item_id,
                qty_requested=line.qty_requested,
                notes=line.notes,
            )
        )
    db.add(row)
    db.commit()
    db.refresh(row)
    return db.query(PurchaseRequest).options(joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.item)).filter(PurchaseRequest.id == row.id).first()
