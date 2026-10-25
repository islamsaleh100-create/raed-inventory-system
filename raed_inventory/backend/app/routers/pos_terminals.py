"""POS terminals — internal audit registry."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_roles
from app.database import get_db
from app.models import User
from app.schemas.pos_terminal import PosTerminalCreate, PosTerminalUpdate
from app.services import pos_terminal_service as svc

router = APIRouter(prefix="/api/v1/audit/pos-terminals", tags=["Audit POS Terminals"])

_READ_WRITE = ("internal_auditor", "admin", "super_admin")


@router.get("")
def list_pos_terminals(
    search: Optional[str] = Query(None, max_length=128),
    provider: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*_READ_WRITE)),
):
    return svc.list_terminals(
        db,
        search=search,
        provider=provider,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("", status_code=201)
def create_pos_terminal(
    payload: PosTerminalCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READ_WRITE)),
):
    return svc.create_terminal(
        db,
        user_id=current_user.id,
        payload=payload,
        ip_address=request.client.host if request.client else None,
    )


@router.patch("/{terminal_id}")
def update_pos_terminal(
    terminal_id: int,
    payload: PosTerminalUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_READ_WRITE)),
):
    return svc.update_terminal(
        db,
        user_id=current_user.id,
        terminal_id=terminal_id,
        payload=payload,
        ip_address=request.client.host if request.client else None,
    )
