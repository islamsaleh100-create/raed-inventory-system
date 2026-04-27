from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.models import IdempotencyRequest, User
from app.services import idempotency_service


def begin(
    db: Session,
    *,
    client_request_id: str | None,
    operation_name: str,
    current_user: User,
) -> tuple[IdempotencyRequest | None, bool]:
    if not client_request_id:
        return None, False

    existing_record = idempotency_service.get_idempotency_request(
        db,
        tenant_id=settings.DEFAULT_TENANT_ID,
        client_request_id=client_request_id,
        operation_name=operation_name,
    )
    if existing_record and existing_record.status == "completed":
        return existing_record, True

    if not existing_record:
        try:
            record = idempotency_service.register_idempotency_request(
                db,
                tenant_id=settings.DEFAULT_TENANT_ID,
                client_request_id=client_request_id,
                operation_name=operation_name,
                user_id=current_user.id,
            )
            return record, False
        except IntegrityError:
            duplicate_record = idempotency_service.get_idempotency_request(
                db,
                tenant_id=settings.DEFAULT_TENANT_ID,
                client_request_id=client_request_id,
                operation_name=operation_name,
            )
            if duplicate_record and duplicate_record.status == "completed":
                return duplicate_record, True
            raise AppError(
                status_code=409,
                error_code="supply_chain.duplicate_request_in_progress",
                message="Duplicate request is already in progress",
                detail={"operation_name": operation_name},
            )

    return None, False


def complete(
    db: Session,
    *,
    record: IdempotencyRequest | None,
    response_reference_type: str,
    response_reference_id: str | int,
) -> None:
    if not record:
        return
    idempotency_service.complete_idempotency_request(
        db,
        record=record,
        response_reference_type=response_reference_type,
        response_reference_id=response_reference_id,
    )
