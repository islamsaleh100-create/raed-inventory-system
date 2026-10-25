"""POS terminal registry for internal audit (branch lookup on failure)."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database import Base


class PosTerminalProvider(str, enum.Enum):
    hala = "hala"
    nami = "nami"
    riyad_bank = "riyad_bank"


class PosTerminalStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
    withdrawn = "withdrawn"


class PosTerminal(Base):
    __tablename__ = "pos_terminals"

    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False, index=True)
    terminal_number = Column(String(64), nullable=False)
    serial_number = Column(String(128), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    branch_label = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default=PosTerminalStatus.active.value, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "terminal_number", name="uq_pos_terminals_provider_terminal_number"),
    )
