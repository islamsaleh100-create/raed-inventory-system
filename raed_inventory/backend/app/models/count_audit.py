"""Count Audit — finding events and item snapshots (append-only events)."""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class AuditFindingEvent(Base):
    __tablename__ = "audit_finding_events"

    id = Column(Integer, primary_key=True)
    finding_id = Column(Integer, ForeignKey("audit_findings.id"), nullable=False)
    event_type = Column(String(30), nullable=False)
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_role = Column(String(30), nullable=False)
    note = Column(Text, nullable=True)
    client_request_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index("idx_audit_finding_events_finding", "finding_id", "created_at"),
        Index("uq_audit_finding_events_request", "finding_id", "client_request_id", unique=True),
    )


class AuditFindingItem(Base):
    __tablename__ = "audit_finding_items"

    id = Column(Integer, primary_key=True)
    finding_id = Column(Integer, ForeignKey("audit_findings.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    line_id = Column(Integer, ForeignKey("branch_shift_count_lines.id"), nullable=True)
    item_name_snapshot = Column(String(150), nullable=False)
    closing_balance_snapshot = Column(Numeric(12, 2), nullable=True)
    movement_diff_snapshot = Column(Numeric(12, 2), nullable=True)

    __table_args__ = (
        UniqueConstraint("finding_id", "item_id", name="uq_audit_finding_items_finding_item"),
        Index("idx_audit_finding_items_finding", "finding_id"),
        Index("idx_audit_finding_items_item", "item_id"),
    )
