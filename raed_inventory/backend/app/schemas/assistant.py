"""Pydantic schemas for the AI Assistant router."""
from typing import Optional

from pydantic import BaseModel, Field


class AssistantAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="The user's question")


class AssistantAskResponse(BaseModel):
    answer: str
    language: str
    model: str
    suggestion_saved: bool = False
    suggestion_id: Optional[int] = None
    suggestion_category: Optional[str] = None
    suggestion_priority: Optional[str] = None


class AssistantStatusResponse(BaseModel):
    available: bool
    model: Optional[str] = None
    reason: Optional[str] = None


class SuggestionListItem(BaseModel):
    id: int
    user_id: int
    user_username: Optional[str] = None
    role_at_creation: str
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    suggestion_text: str
    category: str
    priority: str
    status: str
    admin_note: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class SuggestionUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, description="pending | reviewed | approved | rejected | implemented")
    admin_note: Optional[str] = None


class SuggestionStatsResponse(BaseModel):
    total: int
    pending: int
    by_category: dict
    by_priority: dict
