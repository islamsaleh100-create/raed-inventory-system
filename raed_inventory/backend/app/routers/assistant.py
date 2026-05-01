"""
AI Assistant router — answers employee questions about the system.

Endpoint:
    POST /api/v1/assistant/ask    — submit a question, get an answer
    GET  /api/v1/assistant/status — check if the assistant is configured

Auth: required (any active user with a role can ask).
Rate limit: stricter than default to control OpenAI cost.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_current_active_user
from app.core.limiter import limit as rate_limit
from app.database import get_db
from app.models import Branch, User
from app.schemas import (
    AssistantAskRequest,
    AssistantAskResponse,
    AssistantStatusResponse,
)
from app.services import assistant_service

router = APIRouter(prefix="/api/v1/assistant", tags=["AI Assistant"])


def _resolve_user_role(user: User) -> str:
    """Return the primary role name (string) for the user, or 'unknown' if none."""
    user_roles = getattr(user, "user_roles", None) or []
    for ur in user_roles:
        role_obj = getattr(ur, "role", None)
        if role_obj is not None:
            name = getattr(role_obj, "name", None)
            if name is not None:
                return getattr(name, "value", str(name))
    return "unknown"


def _resolve_branch_name(db: Session, user: User) -> str | None:
    branch_id = getattr(user, "branch_id", None)
    if not branch_id:
        return None
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    return branch.branch_name if branch else None


@router.get("/status", response_model=AssistantStatusResponse)
def get_status(_: User = Depends(get_current_active_user)):
    """Cheap endpoint the frontend uses to decide whether to show the chat widget."""
    if not assistant_service.is_available():
        return AssistantStatusResponse(
            available=False,
            reason="OpenAI API key not configured or feature disabled",
        )
    return AssistantStatusResponse(
        available=True,
        model=settings.OPENAI_MODEL,
    )


@router.post("/ask", response_model=AssistantAskResponse)
@rate_limit("30/minute")  # protect OpenAI cost
def ask(
    request: Request,
    payload: AssistantAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not assistant_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Assistant is currently unavailable.",
        )

    user_role = _resolve_user_role(current_user)
    branch_name = _resolve_branch_name(db, current_user)

    try:
        result = assistant_service.ask(
            question=payload.question,
            user_role=user_role,
            branch_name=branch_name,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return AssistantAskResponse(**result)
