"""Pydantic schemas for the AI Assistant router."""
from typing import Optional

from pydantic import BaseModel, Field


class AssistantAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="The user's question")


class AssistantAskResponse(BaseModel):
    answer: str
    language: str
    model: str


class AssistantStatusResponse(BaseModel):
    available: bool
    model: Optional[str] = None
    reason: Optional[str] = None
