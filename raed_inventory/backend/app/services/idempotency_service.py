from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IdempotencyRequest


DEFAULT_IDEMPOTENCY_HOURS = 48


def get_idempotency_request(
    db: Session,
    *,
    tenant_id: int,
    client_request_id: str,
    operation_name: str,
) -> IdempotencyRequest | None:
    return (
        db.query(IdempotencyRequest)
        .filter(
            IdempotencyRequest.tenant_id == tenant_id,
            IdempotencyRequest.client_request_id == client_request_id,
            IdempotencyRequest.operation_name == operation_name,
        )
        .first()
    )


def register_idempotency_request(
    db: Session,
    *,
    tenant_id: int,
    client_request_id: str,
    operation_name: str,
    user_id: int | None = None,
    request_hash: str | None = None,
    expires_in_hours: int = DEFAULT_IDEMPOTENCY_HOURS,
) -> IdempotencyRequest:
    record = IdempotencyRequest(
        tenant_id=tenant_id,
        client_request_id=client_request_id,
        operation_name=operation_name,
        user_id=user_id,
        request_hash=request_hash,
        status="pending",
        expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(record)
    return record


def complete_idempotency_request(
    db: Session,
    *,
    record: IdempotencyRequest,
    response_reference_type: str,
    response_reference_id: str | int,
) -> IdempotencyRequest:
    record.status = "completed"
    record.response_reference_type = response_reference_type
    record.response_reference_id = str(response_reference_id)
    db.commit()
    db.refresh(record)
    return record


def cleanup_expired_idempotency_requests(db: Session, *, now: datetime | None = None) -> int:
    cutoff = now or datetime.utcnow()
    deleted_count = (
        db.query(IdempotencyRequest)
        .filter(IdempotencyRequest.expires_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted_count


def replay_response(
    *,
    record: IdempotencyRequest,
    response_payload: dict,
) -> dict:
    payload = dict(response_payload)
    payload["_idempotency"] = {
        "replayed": True,
        "operation_name": record.operation_name,
        "response_reference_type": record.response_reference_type,
        "response_reference_id": record.response_reference_id,
    }
    return payload
