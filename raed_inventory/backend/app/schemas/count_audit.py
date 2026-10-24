from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CountAuditSeverity(str, Enum):
    info = "info"
    warning = "warning"
    violation = "violation"


class CountAuditEventAction(str, Enum):
    respond = "respond"
    request_clarification = "request_clarification"
    accept = "accept"
    escalate = "escalate"
    close = "close"
    reopen = "reopen"


class CountAuditFindingCreate(BaseModel):
    client_request_id: str = Field(..., min_length=8, max_length=64)
    shift_id: int
    severity: CountAuditSeverity
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    item_ids: List[int] = Field(default_factory=list, max_length=50)

    @field_validator("item_ids")
    @classmethod
    def _item_ids_limit(cls, v: List[int]) -> List[int]:
        if len(v) > 50:
            raise ValueError("item_ids max 50")
        return v


class CountAuditEventCreate(BaseModel):
    client_request_id: str = Field(..., min_length=8, max_length=64)
    action: CountAuditEventAction
    note: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _note_min_by_action(self) -> "CountAuditEventCreate":
        min_len = 5 if self.action == CountAuditEventAction.accept else 10
        if len(self.note.strip()) < min_len:
            raise ValueError(f"note min length {min_len}")
        self.note = self.note.strip()
        return self
