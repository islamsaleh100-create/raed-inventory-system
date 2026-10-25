from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

PosProvider = Literal["hala", "nami", "riyad_bank"]
PosStatus = Literal["active", "disabled", "withdrawn"]


class PosTerminalCreate(BaseModel):
    provider: PosProvider
    terminal_number: str = Field(min_length=1, max_length=64)
    serial_number: Optional[str] = Field(default=None, max_length=128)
    branch_id: Optional[int] = None
    branch_label: Optional[str] = Field(default=None, max_length=128)
    status: PosStatus = "active"
    notes: Optional[str] = Field(default=None, max_length=2000)


class PosTerminalUpdate(BaseModel):
    provider: Optional[PosProvider] = None
    terminal_number: Optional[str] = Field(default=None, min_length=1, max_length=64)
    serial_number: Optional[str] = Field(default=None, max_length=128)
    branch_id: Optional[int] = None
    branch_label: Optional[str] = Field(default=None, max_length=128)
    status: Optional[PosStatus] = None
    notes: Optional[str] = None
