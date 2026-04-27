from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.models import Item, StockTransaction, TransactionType


def post_transaction(
    db: Session,
    *,
    transaction_type: TransactionType,
    item_id: int,
    qty,
    source_type: str | None = None,
    source_id: int | None = None,
    destination_type: str | None = None,
    destination_id: int | None = None,
    reference_no: str | None = None,
    notes: str | None = None,
    created_by: int | None = None,
) -> StockTransaction | None:
    quantity = Decimal(str(qty))
    if quantity == 0:
        return None

    transaction = StockTransaction(
        transaction_date=datetime.utcnow(),
        transaction_type=transaction_type,
        source_type=source_type,
        source_id=source_id,
        destination_type=destination_type,
        destination_id=destination_id,
        item_id=item_id,
        qty=quantity,
        reference_no=reference_no,
        notes=notes,
        created_by=created_by,
    )
    db.add(transaction)
    return transaction


def get_item_stock_card(
    db: Session,
    *,
    item_id: int,
    limit: int = 100,
    transaction_type: TransactionType | None = None,
    source_type: str | None = None,
    destination_type: str | None = None,
    reference_no: str | None = None,
) -> dict:
    item = db.query(Item).filter(Item.id == item_id, Item.is_deleted == False).first()
    if not item:
        raise AppError(
            status_code=404,
            error_code="ledger.item_not_found",
            message="Item not found",
            detail={"item_id": item_id},
        )

    query = db.query(StockTransaction).options(
        joinedload(StockTransaction.item)
    ).filter(
        StockTransaction.item_id == item_id
    )

    if transaction_type is not None:
        query = query.filter(StockTransaction.transaction_type == transaction_type)
    if source_type is not None:
        query = query.filter(StockTransaction.source_type == source_type)
    if destination_type is not None:
        query = query.filter(StockTransaction.destination_type == destination_type)
    if reference_no is not None:
        query = query.filter(StockTransaction.reference_no == reference_no)

    transactions = query.order_by(
        StockTransaction.transaction_date.desc(),
        StockTransaction.id.desc(),
    ).limit(limit).all()

    return {
        "item_id": item.id,
        "item_code": item.item_code,
        "item_name_ar": item.item_name_ar,
        "item_name_en": item.item_name_en,
        "transactions": transactions,
    }
