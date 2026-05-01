"""
AI Assistant router — answers employee questions and persists suggestions.

Endpoints:
    POST /api/v1/assistant/ask         — submit a question, get an answer (any user)
    GET  /api/v1/assistant/status      — check if the assistant is configured (any user)
    GET  /api/v1/assistant/suggestions — admin: list suggestions
    PATCH /api/v1/assistant/suggestions/{id} — admin: update status/note
    GET  /api/v1/assistant/suggestions/stats — admin: stats summary

Auth: required.
Rate limit: stricter on /ask to control OpenAI cost.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_current_active_user
from app.core.limiter import limit as rate_limit
from app.database import get_db
from app.models import (
    Branch,
    SuggestionCategory,
    SuggestionPriority,
    SuggestionStatus,
    User,
    UserSuggestion,
)
from app.schemas import (
    AssistantAskRequest,
    AssistantAskResponse,
    AssistantStatusResponse,
    SuggestionListItem,
    SuggestionStatsResponse,
    SuggestionUpdateRequest,
)
from app.services import assistant_service

router = APIRouter(prefix="/api/v1/assistant", tags=["AI Assistant"])


# ───────────────────────── helpers ─────────────────────────


def _resolve_user_role(user: User) -> str:
    user_roles = getattr(user, "user_roles", None) or []
    for ur in user_roles:
        role_obj = getattr(ur, "role", None)
        if role_obj is not None:
            name = getattr(role_obj, "name", None)
            if name is not None:
                return getattr(name, "value", str(name))
    return "unknown"


def _resolve_branch_name(db: Session, branch_id: Optional[int]) -> Optional[str]:
    if not branch_id:
        return None
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    return branch.branch_name if branch else None


def _is_admin(user: User) -> bool:
    """super_admin and admin can manage suggestions."""
    user_roles = getattr(user, "user_roles", None) or []
    for ur in user_roles:
        role_obj = getattr(ur, "role", None)
        if role_obj is not None:
            name = getattr(role_obj, "name", None)
            value = getattr(name, "value", str(name)) if name is not None else ""
            if value in {"super_admin", "admin"}:
                return True
    return False


def _serialize_suggestion(s: UserSuggestion, db: Session) -> SuggestionListItem:
    branch_name = _resolve_branch_name(db, s.branch_id)
    user_username = None
    user_obj = db.query(User).filter(User.id == s.user_id).first()
    if user_obj:
        user_username = getattr(user_obj, "username", None)
    return SuggestionListItem(
        id=s.id,
        user_id=s.user_id,
        user_username=user_username,
        role_at_creation=s.role_at_creation,
        branch_id=s.branch_id,
        branch_name=branch_name,
        suggestion_text=s.suggestion_text,
        category=getattr(s.category, "value", str(s.category)),
        priority=getattr(s.priority, "value", str(s.priority)),
        status=getattr(s.status, "value", str(s.status)),
        admin_note=s.admin_note,
        created_at=s.created_at.isoformat() if s.created_at else "",
    )


# ───────────────────────── public endpoints ─────────────────────────


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
@rate_limit("30/minute")
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
    branch_id = getattr(current_user, "branch_id", None)
    branch_name = _resolve_branch_name(db, branch_id)

    try:
        result = assistant_service.ask(
            question=payload.question,
            user_role=user_role,
            db=db,
            user_id=current_user.id,
            branch_id=branch_id,
            branch_name=branch_name,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return AssistantAskResponse(**result)


# ───────────────────────── admin endpoints ─────────────────────────


@router.get("/suggestions", response_model=list[SuggestionListItem])
def list_suggestions(
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required.")

    q = db.query(UserSuggestion).order_by(UserSuggestion.created_at.desc())
    if status_filter:
        try:
            q = q.filter(UserSuggestion.status == SuggestionStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")
    if category:
        try:
            q = q.filter(UserSuggestion.category == SuggestionCategory(category))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    if priority:
        try:
            q = q.filter(UserSuggestion.priority == SuggestionPriority(priority))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    rows = q.offset(offset).limit(limit).all()
    return [_serialize_suggestion(s, db) for s in rows]


@router.patch("/suggestions/{suggestion_id}", response_model=SuggestionListItem)
def update_suggestion(
    suggestion_id: int,
    payload: SuggestionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required.")

    row = db.query(UserSuggestion).filter(UserSuggestion.id == suggestion_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    if payload.status is not None:
        try:
            row.status = SuggestionStatus(payload.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")
        row.reviewed_by = current_user.id
        row.reviewed_at = datetime.utcnow()

    if payload.admin_note is not None:
        row.admin_note = payload.admin_note

    db.commit()
    db.refresh(row)
    return _serialize_suggestion(row, db)


@router.get("/suggestions/stats", response_model=SuggestionStatsResponse)
def suggestions_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required.")

    total = db.query(UserSuggestion).count()
    pending = db.query(UserSuggestion).filter(UserSuggestion.status == SuggestionStatus.pending).count()

    by_category: dict[str, int] = {}
    for cat in SuggestionCategory:
        by_category[cat.value] = (
            db.query(UserSuggestion).filter(UserSuggestion.category == cat).count()
        )

    by_priority: dict[str, int] = {}
    for pri in SuggestionPriority:
        by_priority[pri.value] = (
            db.query(UserSuggestion).filter(UserSuggestion.priority == pri).count()
        )

    return SuggestionStatsResponse(
        total=total,
        pending=pending,
        by_category=by_category,
        by_priority=by_priority,
    )
