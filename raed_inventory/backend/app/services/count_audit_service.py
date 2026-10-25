"""Count Audit — post-submit shift count review (no writes to branch_shift* tables)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.area_manager_scope import get_area_manager_branch_ids
from app.core.auth import GLOBAL_BRANCH_ACCESS_ROLES, can_access_branch, get_user_roles
from app.models import AuditFinding, Branch, BranchBrand, Brand, Item, User
from app.models.branch_shift_ops import (
    BranchShift,
    BranchShiftCount,
    BranchShiftCountLine,
    BranchShiftReopenEvent,
    ShiftSectionStatus,
)
from app.models.count_audit import AuditFindingEvent, AuditFindingItem
from app.schemas.count_audit import CountAuditEventCreate, CountAuditFindingCreate, CountAuditEventAction
from app.services import audit_service
from app.services.shift_ops_service import _is_opening_count, _serialize_count

ENTITY_TYPE = "shift_count"
COUNT_AUDIT_ROLES = frozenset(
    {"internal_auditor", "admin", "super_admin", "operations_manager", "area_manager", "branch_manager"}
)
CREATE_ROLES = frozenset({"internal_auditor", "admin", "super_admin"})
CLOSED_STATUS = "closed"
STATUSES = frozenset(
    {"open", "acknowledged", "clarification_requested", "escalated", "accepted", "closed"}
)
QUEUE_WAITING_RESPONSE = frozenset({"open", "clarification_requested", "escalated"})
QUEUE_WAITING_AUDITOR = frozenset({"acknowledged", "accepted"})


def _err(status: int, code: str, message: str, **extra: Any) -> None:
    raise HTTPException(status_code=status, detail={"error_code": code, "message": message, **extra})


def _require_count_audit_role(user: User) -> list[str]:
    roles = get_user_roles(user)
    if not any(r in COUNT_AUDIT_ROLES for r in roles):
        _err(403, "COUNT_AUDIT_FORBIDDEN", "Access denied")
    return roles


def _scope_branch_ids(user: User, db: Session) -> Optional[set[int]]:
    roles = get_user_roles(user)
    if any(r in GLOBAL_BRANCH_ACCESS_ROLES for r in roles):
        return None
    if "area_manager" in roles:
        return set(get_area_manager_branch_ids(user, db))
    if "branch_manager" in roles:
        return {user.branch_id} if user.branch_id else set()
    _err(403, "COUNT_AUDIT_FORBIDDEN", "Access denied")
    return set()


def _assert_branch_filter(user: User, db: Session, branch_id: Optional[int]) -> None:
    if branch_id is None:
        return
    scope = _scope_branch_ids(user, db)
    if scope is not None and branch_id not in scope:
        _err(403, "COUNT_AUDIT_BRANCH_FORBIDDEN", "Access denied for this branch")


def _assert_shift_in_scope(user: User, db: Session, shift: BranchShift) -> None:
    scope = _scope_branch_ids(user, db)
    if scope is not None and shift.branch_id not in scope:
        _err(404, "COUNT_AUDIT_NOT_FOUND", "Not found")


def _parse_dates(date_from: date, date_to: date, max_days: int) -> tuple[datetime, datetime]:
    if date_from > date_to:
        _err(422, "COUNT_AUDIT_INVALID_RANGE", "date_from after date_to")
    if (date_to - date_from).days + 1 > max_days:
        _err(422, "COUNT_AUDIT_RANGE_TOO_LARGE", "Date range too large")
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to, time.max)
    return start, end


def _queue_for_status(status: str) -> str:
    if status == CLOSED_STATUS:
        return "closed"
    if status in QUEUE_WAITING_RESPONSE:
        return "waiting_response"
    if status in QUEUE_WAITING_AUDITOR:
        return "waiting_auditor"
    return "all"


def get_filters(db: Session, user: User) -> dict[str, Any]:
    _require_count_audit_role(user)
    scope = _scope_branch_ids(user, db)
    q = db.query(Branch).filter(Branch.is_deleted == False, Branch.active == True)  # noqa: E712
    if scope is not None:
        q = q.filter(Branch.id.in_(scope) if scope else Branch.id == -1)
    branches = q.order_by(Branch.branch_name).all()
    branch_ids = [b.id for b in branches]
    cities = sorted({b.city for b in branches if b.city})
    brand_rows = (
        db.query(Brand.id, Brand.name)
        .join(BranchBrand, BranchBrand.brand_id == Brand.id)
        .filter(BranchBrand.branch_id.in_(branch_ids) if branch_ids else BranchBrand.branch_id == -1)
        .distinct()
        .order_by(Brand.name)
        .all()
    )
    return {
        "brands": [{"brand_id": r.id, "name": r.name} for r in brand_rows],
        "cities": cities,
        "branches": [{"branch_id": b.id, "branch_name": b.branch_name, "city": b.city} for b in branches],
    }


def _is_opening_count_shift(db: Session, shift: BranchShift) -> bool:
    return _is_opening_count(db, shift.branch_id, shift)


def _opening_shift_ids_for_branches(db: Session, branch_ids: Iterable[int]) -> set[int]:
    """First submitted count shift per branch (matches shift_ops _is_opening_count)."""
    ids = list(branch_ids)
    if not ids:
        return set()
    rows = (
        db.query(BranchShift.branch_id, BranchShift.id)
        .join(BranchShiftCount, BranchShiftCount.shift_id == BranchShift.id)
        .filter(
            BranchShift.branch_id.in_(ids),
            BranchShiftCount.status == ShiftSectionStatus.submitted.value,
        )
        .order_by(
            BranchShift.branch_id,
            BranchShift.shift_date,
            BranchShift.shift_number,
            BranchShift.id,
        )
        .all()
    )
    opening: set[int] = set()
    seen_branch: set[int] = set()
    for br_id, shift_id in rows:
        if br_id in seen_branch:
            continue
        seen_branch.add(br_id)
        opening.add(shift_id)
    return opening


def _opening_shift_ids_for_variance_scope(
    db: Session,
    *,
    scope: Optional[set[int]],
    branch_id: Optional[int],
    brand_id: Optional[int],
    city: Optional[str],
) -> set[int]:
    """First submitted count shift id per branch visible under the same filters as list_variances."""
    bq = db.query(Branch.id).filter(Branch.is_deleted == False)  # noqa: E712
    if scope is not None:
        bq = bq.filter(Branch.id.in_(scope) if scope else Branch.id == -1)
    if branch_id is not None:
        bq = bq.filter(Branch.id == branch_id)
    if city:
        bq = bq.filter(Branch.city == city)
    if brand_id is not None:
        bq = bq.join(BranchBrand, BranchBrand.branch_id == Branch.id).filter(BranchBrand.brand_id == brand_id)
    branch_ids = [r[0] for r in bq.all()]
    return _opening_shift_ids_for_branches(db, branch_ids)


def _exclude_opening_shifts_from_variance_query(
    q,
    db: Session,
    *,
    include_opening: bool,
    scope: Optional[set[int]],
    branch_id: Optional[int],
    brand_id: Optional[int],
    city: Optional[str],
):
    if include_opening:
        return q
    opening_ids = _opening_shift_ids_for_variance_scope(
        db, scope=scope, branch_id=branch_id, brand_id=brand_id, city=city
    )
    if opening_ids:
        q = q.filter(BranchShift.id.notin_(opening_ids))
    return q


def _zero_opening_variance_fields(item: dict[str, Any]) -> None:
    item["shortage_lines"] = 0
    item["surplus_lines"] = 0
    item["shortage_qty_total"] = 0.0
    item["surplus_qty_total"] = 0.0


def _line_agg_subquery(db: Session):
    return (
        db.query(
            BranchShiftCountLine.count_id.label("count_id"),
            func.count(BranchShiftCountLine.id).label("lines_total"),
            func.sum(case((BranchShiftCountLine.movement_diff > 0, 1), else_=0)).label("shortage_lines"),
            func.sum(case((BranchShiftCountLine.movement_diff < 0, 1), else_=0)).label("surplus_lines"),
            func.sum(case((BranchShiftCountLine.movement_diff > 0, BranchShiftCountLine.movement_diff), else_=0)).label(
                "shortage_qty_total"
            ),
            func.sum(case((BranchShiftCountLine.movement_diff < 0, -BranchShiftCountLine.movement_diff), else_=0)).label(
                "surplus_qty_total"
            ),
            func.sum(case((BranchShiftCountLine.closing_balance.isnot(None), 1), else_=0)).label("lines_filled"),
        )
        .group_by(BranchShiftCountLine.count_id)
        .subquery()
    )


def _open_findings_subquery(db: Session):
    return (
        db.query(
            AuditFinding.entity_id.label("shift_id"),
            func.count(AuditFinding.id).label("open_findings"),
        )
        .filter(
            AuditFinding.entity_type == ENTITY_TYPE,
            AuditFinding.status != CLOSED_STATUS,
        )
        .group_by(AuditFinding.entity_id)
        .subquery()
    )


def _reopen_count_subquery(db: Session):
    return (
        db.query(
            BranchShiftReopenEvent.shift_id.label("shift_id"),
            func.count(BranchShiftReopenEvent.id).label("reopen_count"),
        )
        .group_by(BranchShiftReopenEvent.shift_id)
        .subquery()
    )


def list_shifts(
    db: Session,
    user: User,
    *,
    date_from: date,
    date_to: date,
    brand_id: Optional[int] = None,
    city: Optional[str] = None,
    branch_id: Optional[int] = None,
    status: Optional[str] = None,
    has_diff: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    _require_count_audit_role(user)
    _assert_branch_filter(user, db, branch_id)
    _parse_dates(date_from, date_to, 93)
    scope = _scope_branch_ids(user, db)
    page_size = min(page_size, 100)
    agg = _line_agg_subquery(db)
    open_f = _open_findings_subquery(db)
    reopen_f = _reopen_count_subquery(db)
    q = (
        db.query(
            BranchShift,
            BranchShiftCount,
            Branch,
            agg.c.lines_total,
            agg.c.lines_filled,
            agg.c.shortage_lines,
            agg.c.surplus_lines,
            agg.c.shortage_qty_total,
            agg.c.surplus_qty_total,
            func.coalesce(open_f.c.open_findings, 0).label("open_findings"),
            func.coalesce(reopen_f.c.reopen_count, 0).label("reopen_count"),
        )
        .join(Branch, Branch.id == BranchShift.branch_id)
        .outerjoin(BranchShiftCount, BranchShiftCount.shift_id == BranchShift.id)
        .outerjoin(agg, agg.c.count_id == BranchShiftCount.id)
        .outerjoin(open_f, open_f.c.shift_id == BranchShift.id)
        .outerjoin(reopen_f, reopen_f.c.shift_id == BranchShift.id)
        .filter(BranchShift.shift_date >= date_from, BranchShift.shift_date <= date_to)
    )
    if scope is not None:
        q = q.filter(BranchShift.branch_id.in_(scope) if scope else BranchShift.branch_id == -1)
    if branch_id is not None:
        q = q.filter(BranchShift.branch_id == branch_id)
    if city:
        q = q.filter(Branch.city == city)
    if brand_id is not None:
        q = q.join(BranchBrand, BranchBrand.branch_id == Branch.id).filter(BranchBrand.brand_id == brand_id)
    if status:
        q = q.filter(BranchShift.status == status)
    if has_diff is True:
        q = q.filter(or_(agg.c.shortage_lines > 0, agg.c.surplus_lines > 0))
    elif has_diff is False:
        q = q.filter(or_(agg.c.shortage_lines == 0, agg.c.shortage_lines.is_(None)), or_(agg.c.surplus_lines == 0, agg.c.surplus_lines.is_(None)))
    total = q.count()
    rows = q.order_by(BranchShift.shift_date.desc(), BranchShift.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    opening_ids = _opening_shift_ids_for_branches(db, {branch.id for _, _, branch, *_ in rows})
    items = []
    for shift, count, branch, lt, lf, sl, surl, sq, suq, of, rc in rows:
        opening = bool(
            count
            and count.status == ShiftSectionStatus.submitted.value
            and shift.id in opening_ids
        )
        item = {
            "shift_id": shift.id,
            "branch_id": branch.id,
            "branch_name": branch.branch_name,
            "shift_date": shift.shift_date.isoformat(),
            "shift_number": shift.shift_number,
            "shift_status": shift.status,
            "count_status": count.status if count else None,
            "is_partial": bool(count and lt and lf and int(lf or 0) < int(lt or 0)),
            "is_opening_count": opening,
            "exception_type": shift.exception_type,
            "lines_total": int(lt or 0),
            "lines_filled": int(lf or 0),
            "shortage_lines": int(sl or 0),
            "surplus_lines": int(surl or 0),
            "shortage_qty_total": float(sq or 0),
            "surplus_qty_total": float(suq or 0),
            "reopen_count": int(rc or 0),
            "open_findings": int(of or 0),
        }
        if opening:
            _zero_opening_variance_fields(item)
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def get_shift_detail(db: Session, user: User, shift_id: int) -> dict[str, Any]:
    _require_count_audit_role(user)
    shift = db.query(BranchShift).filter(BranchShift.id == shift_id).first()
    if not shift:
        _err(404, "COUNT_AUDIT_NOT_FOUND", "Not found")
    _assert_shift_in_scope(user, db, shift)
    count = db.query(BranchShiftCount).filter(BranchShiftCount.shift_id == shift.id).first()
    findings = (
        db.query(AuditFinding)
        .filter(AuditFinding.entity_type == ENTITY_TYPE, AuditFinding.entity_id == shift.id)
        .order_by(AuditFinding.created_at.desc())
        .all()
    )
    reopen_events = (
        db.query(BranchShiftReopenEvent)
        .filter(BranchShiftReopenEvent.shift_id == shift.id)
        .order_by(BranchShiftReopenEvent.reopened_at.asc())
        .all()
    )
    opening = bool(
        count and count.status == ShiftSectionStatus.submitted.value and _is_opening_count_shift(db, shift)
    )
    count_payload = _serialize_count(count, db) if count else None
    if opening and count_payload:
        for line in count_payload.get("lines") or []:
            line["movement_diff"] = "0"
    payload: dict[str, Any] = {
        "shift_id": shift.id,
        "count_id": count.id if count else None,
        "is_opening_count": opening,
        "shift": {
            "id": shift.id,
            "branch_id": shift.branch_id,
            "shift_date": shift.shift_date.isoformat(),
            "shift_number": shift.shift_number,
            "status": shift.status,
        },
        "count": count_payload,
        "reopen_events": [
            {
                "id": e.id,
                "target": e.target,
                "reason": e.reason,
                "created_at": e.reopened_at.isoformat() if e.reopened_at else None,
            }
            for e in reopen_events
        ],
        "findings": [_finding_summary(db, f) for f in findings],
    }
    return payload


def _finding_summary(db: Session, row: AuditFinding) -> dict[str, Any]:
    creator = db.query(User.full_name).filter(User.id == row.created_by).scalar()
    return {
        "id": row.id,
        "finding_no": row.finding_no,
        "severity": row.severity,
        "title": row.title,
        "status": row.status,
        "queue": _queue_for_status(row.status),
        "created_by_name": creator,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _load_finding(db: Session, finding_id: int) -> AuditFinding:
    row = db.query(AuditFinding).filter(AuditFinding.id == finding_id, AuditFinding.entity_type == ENTITY_TYPE).first()
    if not row:
        _err(404, "COUNT_AUDIT_NOT_FOUND", "Not found")
    return row


def _assert_finding_scope(db: Session, user: User, finding: AuditFinding) -> None:
    if finding.branch_id is None:
        shift = db.query(BranchShift).filter(BranchShift.id == finding.entity_id).first()
        if shift:
            _assert_shift_in_scope(user, db, shift)
            return
    scope = _scope_branch_ids(user, db)
    if scope is not None and finding.branch_id not in scope:
        _err(404, "COUNT_AUDIT_NOT_FOUND", "Not found")


def compute_allowed_actions(finding: AuditFinding, user: User, db: Session) -> list[str]:
    roles = get_user_roles(user)
    if finding.status == CLOSED_STATUS:
        if any(r in ("internal_auditor", "admin", "super_admin") for r in roles):
            return ["reopen"]
        return []
    actions: list[str] = []
    st = finding.status
    if st in ("open", "clarification_requested"):
        if any(r in ("branch_manager", "area_manager", "admin", "super_admin") for r in roles):
            if "branch_manager" in roles and user.branch_id == finding.branch_id:
                actions.append("respond")
            elif "area_manager" in roles and finding.branch_id and can_access_branch(user, finding.branch_id, db):
                actions.append("respond")
            elif any(r in ("admin", "super_admin") for r in roles):
                actions.append("respond")
    if st == "escalated" and any(r in ("operations_manager", "admin", "super_admin") for r in roles):
        actions.append("respond")
    if st in ("acknowledged", "accepted") and any(r in ("internal_auditor", "admin", "super_admin") for r in roles):
        actions.append("request_clarification")
    if st == "acknowledged" and any(r in ("internal_auditor", "admin", "super_admin") for r in roles):
        actions.append("accept")
    if st in ("open", "clarification_requested", "acknowledged") and any(
        r in ("area_manager", "internal_auditor", "admin", "super_admin") for r in roles
    ):
        if "area_manager" not in roles or (finding.branch_id and can_access_branch(user, finding.branch_id, db)):
            if "area_manager" in roles or any(r in ("internal_auditor", "admin", "super_admin") for r in roles):
                actions.append("escalate")
    if st != CLOSED_STATUS and any(r in ("internal_auditor", "admin", "super_admin") for r in roles):
        actions.append("close")
    return sorted(set(actions))


def get_finding_detail(db: Session, user: User, finding_id: int) -> dict[str, Any]:
    _require_count_audit_role(user)
    finding = _load_finding(db, finding_id)
    _assert_finding_scope(db, user, finding)
    shift = db.query(BranchShift).filter(BranchShift.id == finding.entity_id).first()
    count = db.query(BranchShiftCount).filter(BranchShiftCount.shift_id == finding.entity_id).first()
    items = db.query(AuditFindingItem).filter(AuditFindingItem.finding_id == finding.id).all()
    events = (
        db.query(AuditFindingEvent)
        .filter(AuditFindingEvent.finding_id == finding.id)
        .order_by(AuditFindingEvent.created_at.asc(), AuditFindingEvent.id.asc())
        .all()
    )
    item_payloads = []
    for it in items:
        line = db.query(BranchShiftCountLine).filter(BranchShiftCountLine.id == it.line_id).first() if it.line_id else None
        current_closing = line.closing_balance if line else None
        current_diff = line.movement_diff if line else None
        changed = (
            (current_closing is not None and it.closing_balance_snapshot is not None and current_closing != it.closing_balance_snapshot)
            or (current_diff is not None and it.movement_diff_snapshot is not None and current_diff != it.movement_diff_snapshot)
        )
        item_payloads.append(
            {
                "item_id": it.item_id,
                "line_id": it.line_id,
                "item_name_snapshot": it.item_name_snapshot,
                "closing_balance_snapshot": float(it.closing_balance_snapshot) if it.closing_balance_snapshot is not None else None,
                "movement_diff_snapshot": float(it.movement_diff_snapshot) if it.movement_diff_snapshot is not None else None,
                "closing_balance_current": float(current_closing) if current_closing is not None else None,
                "movement_diff_current": float(current_diff) if current_diff is not None else None,
                "changed_since_finding": bool(changed),
            }
        )
    return {
        "finding": _finding_detail_dict(db, finding, shift, count),
        "items": item_payloads,
        "events": [_event_dict(db, e) for e in events],
        "allowed_actions": compute_allowed_actions(finding, user, db),
    }


def _finding_detail_dict(db: Session, finding: AuditFinding, shift: Optional[BranchShift], count: Optional[BranchShiftCount]) -> dict[str, Any]:
    branch_name = None
    if finding.branch_id:
        branch_name = db.query(Branch.branch_name).filter(Branch.id == finding.branch_id).scalar()
    return {
        "id": finding.id,
        "finding_no": finding.finding_no,
        "severity": finding.severity,
        "title": finding.title,
        "description": finding.description,
        "status": finding.status,
        "queue": _queue_for_status(finding.status),
        "branch_id": finding.branch_id,
        "branch_name": branch_name,
        "shift_id": finding.entity_id,
        "count_id": count.id if count else None,
        "shift_date": shift.shift_date.isoformat() if shift else None,
        "shift_number": shift.shift_number if shift else None,
        "response_text": finding.response_text,
        "acknowledged_by": finding.acknowledged_by,
        "acknowledged_at": finding.acknowledged_at.isoformat() if finding.acknowledged_at else None,
        "created_at": finding.created_at.isoformat() if finding.created_at else None,
        "last_event_at": finding.last_event_at.isoformat() if finding.last_event_at else None,
        "closed_at": finding.closed_at.isoformat() if finding.closed_at else None,
    }


def _event_dict(db: Session, event: AuditFindingEvent) -> dict[str, Any]:
    actor_name = db.query(User.full_name).filter(User.id == event.actor_id).scalar()
    return {
        "id": event.id,
        "event_type": event.event_type,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "actor_id": event.actor_id,
        "actor_role": event.actor_role,
        "actor_name": actor_name,
        "note": event.note,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _finding_replay_for_client_request(
    db: Session,
    user: User,
    payload: CountAuditFindingCreate,
) -> Optional[dict[str, Any]]:
    existing = db.query(AuditFinding).filter(AuditFinding.client_request_id == payload.client_request_id).first()
    if not existing:
        return None
    existing_item_ids = {
        row.item_id
        for row in db.query(AuditFindingItem.item_id).filter(AuditFindingItem.finding_id == existing.id).all()
    }
    same_payload = (
        existing.entity_type == ENTITY_TYPE
        and existing.entity_id == payload.shift_id
        and existing.severity == payload.severity.value
        and existing.title == payload.title.strip()
        and existing.description == payload.description.strip()
        and existing_item_ids == set(payload.item_ids)
    )
    if not same_payload:
        _err(409, "COUNT_AUDIT_IDEMPOTENCY_KEY_REUSED", "Idempotency key reused")
    return {"finding": get_finding_detail(db, user, existing.id)["finding"], "idempotent_replay": True}


def create_finding(
    db: Session,
    user: User,
    payload: CountAuditFindingCreate,
    ip_address: Optional[str],
) -> dict[str, Any]:
    roles = get_user_roles(user)
    if not any(r in CREATE_ROLES for r in roles):
        _err(403, "COUNT_AUDIT_FORBIDDEN", "Cannot create")
    replay = _finding_replay_for_client_request(db, user, payload)
    if replay:
        return replay
    shift = db.query(BranchShift).filter(BranchShift.id == payload.shift_id).with_for_update().first()
    if not shift:
        count_row = db.query(BranchShiftCount).filter(BranchShiftCount.id == payload.shift_id).first()
        if count_row:
            _err(422, "COUNT_AUDIT_INVALID_SHIFT_ID", "shift_id must be branch_shifts.id not count id")
        _err(404, "COUNT_AUDIT_NOT_FOUND", "Shift not found")
    replay = _finding_replay_for_client_request(db, user, payload)
    if replay:
        return replay
    _assert_shift_in_scope(user, db, shift)
    count = db.query(BranchShiftCount).filter(BranchShiftCount.shift_id == shift.id).first()
    if not count or count.status != ShiftSectionStatus.submitted.value:
        _err(422, "COUNT_AUDIT_COUNT_NOT_SUBMITTED", "Count not submitted")
    if payload.item_ids:
        line_rows = (
            db.query(BranchShiftCountLine)
            .filter(BranchShiftCountLine.count_id == count.id, BranchShiftCountLine.item_id.in_(payload.item_ids))
            .all()
        )
        if len(line_rows) != len(set(payload.item_ids)):
            _err(422, "COUNT_AUDIT_ITEM_NOT_IN_COUNT", "Item not in count")
    else:
        line_rows = []
    if payload.item_ids and _is_opening_count_shift(db, shift):
        _err(
            422,
            "COUNT_AUDIT_OPENING_COUNT_NO_VARIANCE",
            "Opening count lines cannot be attached to a variance finding.",
        )
    for item_id in payload.item_ids:
        dup = (
            db.query(AuditFinding)
            .join(AuditFindingItem, AuditFindingItem.finding_id == AuditFinding.id)
            .filter(
                AuditFinding.entity_type == ENTITY_TYPE,
                AuditFinding.entity_id == shift.id,
                AuditFinding.status != CLOSED_STATUS,
                AuditFindingItem.item_id == item_id,
            )
            .first()
        )
        if dup:
            _err(409, "COUNT_AUDIT_DUPLICATE_OPEN_FINDING", "Duplicate open finding", existing_finding_no=dup.finding_no)
    now = datetime.utcnow()
    row = AuditFinding(
        finding_no="AF-PENDING",
        entity_type=ENTITY_TYPE,
        entity_id=shift.id,
        severity=payload.severity.value,
        title=payload.title.strip(),
        description=payload.description.strip(),
        created_by=user.id,
        status="open",
        branch_id=shift.branch_id,
        client_request_id=payload.client_request_id,
        last_event_at=now,
    )
    db.add(row)
    db.flush()
    row.finding_no = f"AF-{row.id:06d}"
    for line in line_rows:
        item = db.query(Item).filter(Item.id == line.item_id).first()
        db.add(
            AuditFindingItem(
                finding_id=row.id,
                item_id=line.item_id,
                line_id=line.id,
                item_name_snapshot=(item.item_name_en if item else str(line.item_id))[:150],
                closing_balance_snapshot=line.closing_balance,
                movement_diff_snapshot=line.movement_diff,
            )
        )
    db.add(
        AuditFindingEvent(
            finding_id=row.id,
            event_type="created",
            from_status=None,
            to_status="open",
            actor_id=user.id,
            actor_role=roles[0],
            note=payload.description.strip(),
            client_request_id=f"create-{payload.client_request_id}",
        )
    )
    audit_service.log(
        db,
        user_id=user.id,
        action="count_audit_create",
        module="audit",
        entity_type=ENTITY_TYPE,
        entity_id=shift.id,
        new_values={"finding_no": row.finding_no, "shift_id": shift.id},
        ip_address=ip_address,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = _finding_replay_for_client_request(db, user, payload)
        if replay:
            return replay
        raise
    db.refresh(row)
    return {"finding": get_finding_detail(db, user, row.id)["finding"], "idempotent_replay": False}


def _action_forbidden_for_roles(action: str, roles: list[str], finding: AuditFinding, user: User, db: Session) -> bool:
    """True when no role the user holds may ever perform this action (→ 403)."""
    if action == "respond":
        if any(r in ("admin", "super_admin") for r in roles):
            return False
        if "operations_manager" in roles:
            return False
        if "branch_manager" in roles and user.branch_id == finding.branch_id:
            return False
        if "area_manager" in roles and finding.branch_id and can_access_branch(user, finding.branch_id, db):
            return False
        return True
    if action in ("request_clarification", "accept", "close", "reopen"):
        return not any(r in ("internal_auditor", "admin", "super_admin") for r in roles)
    if action == "escalate":
        if any(r in ("internal_auditor", "admin", "super_admin") for r in roles):
            return False
        if "area_manager" in roles and finding.branch_id and can_access_branch(user, finding.branch_id, db):
            return False
        if "operations_manager" in roles:
            return True
        if "branch_manager" in roles:
            return True
        return True
    return True


def _transition(action: str, from_status: str) -> Optional[str]:
    table = {
        ("respond", "open"): "acknowledged",
        ("respond", "clarification_requested"): "acknowledged",
        ("respond", "escalated"): "acknowledged",
        ("request_clarification", "acknowledged"): "clarification_requested",
        ("request_clarification", "accepted"): "clarification_requested",
        ("accept", "acknowledged"): "accepted",
        ("escalate", "open"): "escalated",
        ("escalate", "clarification_requested"): "escalated",
        ("escalate", "acknowledged"): "escalated",
        ("close", "open"): CLOSED_STATUS,
        ("close", "acknowledged"): CLOSED_STATUS,
        ("close", "clarification_requested"): CLOSED_STATUS,
        ("close", "escalated"): CLOSED_STATUS,
        ("close", "accepted"): CLOSED_STATUS,
        ("reopen", CLOSED_STATUS): "open",
    }
    return table.get((action, from_status))


def post_event(
    db: Session,
    user: User,
    finding_id: int,
    payload: CountAuditEventCreate,
    ip_address: Optional[str],
) -> dict[str, Any]:
    _require_count_audit_role(user)
    roles = get_user_roles(user)
    finding = (
        db.query(AuditFinding)
        .filter(AuditFinding.id == finding_id, AuditFinding.entity_type == ENTITY_TYPE)
        .with_for_update()
        .first()
    )
    if not finding:
        _err(404, "COUNT_AUDIT_NOT_FOUND", "Not found")
    _assert_finding_scope(db, user, finding)
    prior = (
        db.query(AuditFindingEvent)
        .filter(
            AuditFindingEvent.finding_id == finding.id,
            AuditFindingEvent.client_request_id == payload.client_request_id,
        )
        .first()
    )
    action = payload.action.value
    if prior:
        if prior.event_type != action or (prior.note or "").strip() != payload.note.strip():
            _err(409, "COUNT_AUDIT_IDEMPOTENCY_KEY_REUSED", "Idempotency key reused")
        return {"event": _event_dict(db, prior), "finding": get_finding_detail(db, user, finding.id)["finding"], "idempotent_replay": True}
    if _action_forbidden_for_roles(action, roles, finding, user, db):
        _err(403, "COUNT_AUDIT_FORBIDDEN", "Action not permitted for this role")
    if action == "respond" and "operations_manager" in roles and finding.status != "escalated":
        _err(403, "COUNT_AUDIT_FORBIDDEN", "Operations manager cannot respond before escalation")
    if action == "respond" and finding.status == "escalated" and "branch_manager" in roles:
        _err(403, "COUNT_AUDIT_FORBIDDEN", "Branch manager cannot respond when escalated")
    to_status = _transition(action, finding.status)
    if not to_status:
        _err(409, "COUNT_AUDIT_INVALID_TRANSITION", "Invalid transition", current_status=finding.status)
    allowed = compute_allowed_actions(finding, user, db)
    if action not in allowed:
        _err(409, "COUNT_AUDIT_INVALID_TRANSITION", "Action not allowed", current_status=finding.status)
    now = datetime.utcnow()
    from_status = finding.status
    finding.status = to_status
    finding.last_event_at = now
    if to_status == CLOSED_STATUS:
        finding.closed_at = now
    if action == "reopen":
        finding.closed_at = None
    if action == "respond":
        finding.acknowledged_by = user.id
        finding.acknowledged_at = now
        finding.response_text = payload.note
    event = AuditFindingEvent(
        finding_id=finding.id,
        event_type=action,
        from_status=from_status,
        to_status=to_status,
        actor_id=user.id,
        actor_role=next((r for r in roles if r in COUNT_AUDIT_ROLES), roles[0]),
        note=payload.note,
        client_request_id=payload.client_request_id,
    )
    db.add(event)
    audit_service.log(
        db,
        user_id=user.id,
        action=f"count_audit_{action}",
        module="audit",
        entity_type=ENTITY_TYPE,
        entity_id=finding.entity_id,
        new_values={"finding_no": finding.finding_no, "from": from_status, "to": to_status},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(event)
    return {"event": _event_dict(db, event), "finding": get_finding_detail(db, user, finding.id)["finding"], "idempotent_replay": False}


def _findings_scope_base_query(
    db: Session,
    scope: Optional[set[int]],
    *,
    branch_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    q = db.query(AuditFinding).filter(AuditFinding.entity_type == ENTITY_TYPE)
    if scope is not None:
        q = q.filter(AuditFinding.branch_id.in_(scope) if scope else AuditFinding.branch_id == -1)
    if branch_id is not None:
        q = q.filter(AuditFinding.branch_id == branch_id)
    if date_from:
        q = q.filter(AuditFinding.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.filter(AuditFinding.created_at <= datetime.combine(date_to, time.max))
    return q


def _apply_findings_list_filters(q, *, queue: Optional[str], status: Optional[str]):
    if status:
        q = q.filter(AuditFinding.status == status)
    if queue and queue != "all":
        if queue == "waiting_response":
            q = q.filter(AuditFinding.status.in_(tuple(QUEUE_WAITING_RESPONSE)))
        elif queue == "waiting_auditor":
            q = q.filter(AuditFinding.status.in_(tuple(QUEUE_WAITING_AUDITOR)))
        elif queue == "closed":
            q = q.filter(AuditFinding.status == CLOSED_STATUS)
    return q


def _serialize_finding_list_item(
    row: AuditFinding,
    *,
    branch_name: Optional[str],
    creator_name: Optional[str],
    shift: Optional[BranchShift],
    items_count: int,
    last_actor_name: Optional[str],
) -> dict[str, Any]:
    age_days = max(int((datetime.utcnow() - row.created_at).total_seconds() // 86400), 0) if row.created_at else 0
    return {
        "id": row.id,
        "finding_no": row.finding_no,
        "severity": row.severity,
        "title": row.title,
        "status": row.status,
        "queue": _queue_for_status(row.status),
        "branch_id": row.branch_id,
        "branch_name": branch_name,
        "shift_id": row.entity_id,
        "shift_date": shift.shift_date.isoformat() if shift else None,
        "shift_number": shift.shift_number if shift else None,
        "items_count": int(items_count),
        "created_by_name": creator_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_event_at": row.last_event_at.isoformat() if row.last_event_at else None,
        "last_actor_name": last_actor_name,
        "age_days": age_days,
    }


def _build_finding_list_items(
    db: Session,
    page_rows: list[tuple[AuditFinding, Optional[str], Optional[str]]],
) -> list[dict[str, Any]]:
    if not page_rows:
        return []
    finding_ids = [r[0].id for r in page_rows]
    shift_ids = list({r[0].entity_id for r in page_rows})
    shifts = {s.id: s for s in db.query(BranchShift).filter(BranchShift.id.in_(shift_ids)).all()}
    item_counts = {
        fid: int(cnt)
        for fid, cnt in db.query(AuditFindingItem.finding_id, func.count(AuditFindingItem.id))
        .filter(AuditFindingItem.finding_id.in_(finding_ids))
        .group_by(AuditFindingItem.finding_id)
        .all()
    }
    latest_sub = (
        db.query(
            AuditFindingEvent.finding_id.label("finding_id"),
            func.max(AuditFindingEvent.id).label("max_event_id"),
        )
        .filter(AuditFindingEvent.finding_id.in_(finding_ids))
        .group_by(AuditFindingEvent.finding_id)
        .subquery()
    )
    latest_events = (
        db.query(AuditFindingEvent)
        .join(
            latest_sub,
            and_(
                AuditFindingEvent.finding_id == latest_sub.c.finding_id,
                AuditFindingEvent.id == latest_sub.c.max_event_id,
            ),
        )
        .all()
    )
    event_by_finding = {e.finding_id: e for e in latest_events}
    actor_ids = {e.actor_id for e in latest_events}
    actor_names: dict[int, str] = {}
    if actor_ids:
        actor_names = dict(db.query(User.id, User.full_name).filter(User.id.in_(actor_ids)).all())
    items: list[dict[str, Any]] = []
    for finding, branch_name, creator_name in page_rows:
        ev = event_by_finding.get(finding.id)
        last_actor = actor_names.get(ev.actor_id) if ev else None
        items.append(
            _serialize_finding_list_item(
                finding,
                branch_name=branch_name,
                creator_name=creator_name,
                shift=shifts.get(finding.entity_id),
                items_count=item_counts.get(finding.id, 0),
                last_actor_name=last_actor,
            )
        )
    return items


def list_findings(
    db: Session,
    user: User,
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    queue: Optional[str] = None,
    status: Optional[str] = None,
    branch_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    _require_count_audit_role(user)
    _assert_branch_filter(user, db, branch_id)
    scope = _scope_branch_ids(user, db)
    page_size = min(page_size, 100)
    base_q = _findings_scope_base_query(db, scope, branch_id=branch_id, date_from=date_from, date_to=date_to)
    q = _apply_findings_list_filters(base_q, queue=queue, status=status)
    total = q.count()
    page_rows = (
        q.outerjoin(Branch, Branch.id == AuditFinding.branch_id)
        .outerjoin(User, User.id == AuditFinding.created_by)
        .order_by(AuditFinding.last_event_at.desc().nullslast(), AuditFinding.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .with_entities(AuditFinding, Branch.branch_name, User.full_name)
        .all()
    )
    summary = {
        "waiting_response": base_q.filter(AuditFinding.status.in_(tuple(QUEUE_WAITING_RESPONSE))).count(),
        "waiting_auditor": base_q.filter(AuditFinding.status.in_(tuple(QUEUE_WAITING_AUDITOR))).count(),
        "closed": base_q.filter(AuditFinding.status == CLOSED_STATUS).count(),
    }
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": summary,
        "items": _build_finding_list_items(db, page_rows),
    }


def get_coverage(
    db: Session,
    user: User,
    *,
    date_from: date,
    date_to: date,
    brand_id: Optional[int] = None,
    city: Optional[str] = None,
    branch_id: Optional[int] = None,
) -> dict[str, Any]:
    _require_count_audit_role(user)
    _assert_branch_filter(user, db, branch_id)
    _parse_dates(date_from, date_to, 62)
    scope = _scope_branch_ids(user, db)
    bq = db.query(Branch).filter(Branch.is_deleted == False, Branch.active == True)  # noqa: E712
    if scope is not None:
        bq = bq.filter(Branch.id.in_(scope) if scope else Branch.id == -1)
    if branch_id is not None:
        bq = bq.filter(Branch.id == branch_id)
    if city:
        bq = bq.filter(Branch.city == city)
    if brand_id is not None:
        bq = bq.join(BranchBrand, BranchBrand.branch_id == Branch.id).filter(BranchBrand.brand_id == brand_id)
    branches = bq.order_by(Branch.branch_name).all()
    dates = []
    d = date_from
    while d <= date_to:
        dates.append(d.isoformat())
        d += timedelta(days=1)
    agg = _line_agg_subquery(db)
    shift_rows = (
        db.query(
            BranchShift.branch_id,
            BranchShift.shift_date,
            BranchShift.id,
            BranchShift.status,
            BranchShiftCount.status,
            agg.c.shortage_lines,
            agg.c.surplus_lines,
        )
        .outerjoin(BranchShiftCount, BranchShiftCount.shift_id == BranchShift.id)
        .outerjoin(agg, agg.c.count_id == BranchShiftCount.id)
        .filter(BranchShift.shift_date >= date_from, BranchShift.shift_date <= date_to)
    )
    if scope is not None:
        shift_rows = shift_rows.filter(BranchShift.branch_id.in_(scope) if scope else BranchShift.branch_id == -1)
    if branch_id is not None:
        shift_rows = shift_rows.filter(BranchShift.branch_id == branch_id)
    shift_map: dict[tuple[int, str], dict] = {}
    raw_shift_rows = shift_rows.all()
    shift_ids = [r[2] for r in raw_shift_rows if r[2]]
    branch_ids_cov = {r[0] for r in raw_shift_rows}
    opening_ids = _opening_shift_ids_for_branches(db, branch_ids_cov)
    for br_id, sdate, sid, sst, cst, sl, surl in raw_shift_rows:
        key = (br_id, sdate.isoformat())
        state = "no_record"
        if sid:
            if cst == ShiftSectionStatus.submitted.value:
                state = "submitted"
            elif cst == ShiftSectionStatus.draft.value:
                state = "draft"
            else:
                state = "exception"
        has_diff = bool((sl or 0) > 0 or (surl or 0) > 0)
        if sid and cst == ShiftSectionStatus.submitted.value and sid in opening_ids:
            has_diff = False
        prev = shift_map.get(key)
        if not prev or _state_rank(state) > _state_rank(prev["state"]):
            shift_map[key] = {"state": state, "shift_id": sid, "has_diff": has_diff}
    out_branches = []
    for b in branches:
        days = {}
        for ds in dates:
            cell = shift_map.get((b.id, ds), {"state": "no_record", "shift_id": None, "has_diff": False})
            days[ds] = cell
        out_branches.append({"branch_id": b.id, "branch_name": b.branch_name, "days": days})
    return {"dates": dates, "branches": out_branches}


def _state_rank(state: str) -> int:
    order = {"exception": 5, "draft": 4, "partial": 3, "submitted": 2, "no_record": 1}
    return order.get(state, 0)


def list_variances(
    db: Session,
    user: User,
    *,
    date_from: date,
    date_to: date,
    direction: str = "all",
    brand_id: Optional[int] = None,
    city: Optional[str] = None,
    branch_id: Optional[int] = None,
    item_id: Optional[int] = None,
    min_abs_diff: Optional[float] = None,
    group: str = "line",
    min_occurrences: int = 2,
    include_opening: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    _require_count_audit_role(user)
    _assert_branch_filter(user, db, branch_id)
    _parse_dates(date_from, date_to, 93)
    scope = _scope_branch_ids(user, db)
    page_size = min(page_size, 100)
    q = (
        db.query(
            BranchShiftCountLine,
            BranchShift,
            Branch,
            Item,
        )
        .join(BranchShiftCount, BranchShiftCount.id == BranchShiftCountLine.count_id)
        .join(BranchShift, BranchShift.id == BranchShiftCount.shift_id)
        .join(Branch, Branch.id == BranchShift.branch_id)
        .join(Item, Item.id == BranchShiftCountLine.item_id)
        .filter(
            BranchShift.shift_date >= date_from,
            BranchShift.shift_date <= date_to,
            BranchShiftCount.status == ShiftSectionStatus.submitted.value,
        )
    )
    if scope is not None:
        q = q.filter(BranchShift.branch_id.in_(scope) if scope else BranchShift.branch_id == -1)
    if branch_id is not None:
        q = q.filter(BranchShift.branch_id == branch_id)
    if city:
        q = q.filter(Branch.city == city)
    if brand_id is not None:
        q = q.join(BranchBrand, BranchBrand.branch_id == Branch.id).filter(BranchBrand.brand_id == brand_id)
    if item_id is not None:
        q = q.filter(BranchShiftCountLine.item_id == item_id)
    if direction == "shortage":
        q = q.filter(BranchShiftCountLine.movement_diff > 0)
    elif direction == "surplus":
        q = q.filter(BranchShiftCountLine.movement_diff < 0)
    else:
        q = q.filter(BranchShiftCountLine.movement_diff != 0)
    if min_abs_diff is not None:
        q = q.filter(func.abs(BranchShiftCountLine.movement_diff) >= min_abs_diff)
    q = _exclude_opening_shifts_from_variance_query(
        q,
        db,
        include_opening=include_opening,
        scope=scope,
        branch_id=branch_id,
        brand_id=brand_id,
        city=city,
    )
    if group == "repeat":
        # aggregate in Python for SQLite compatibility in tests; pagination stays in Python
        rows = q.all()
        buckets: dict[tuple[int, int], list] = {}
        for line, shift, branch, item in rows:
            buckets.setdefault((branch.id, item.id), []).append((line, shift, branch, item))
        items = []
        for (bid, iid), group_rows in buckets.items():
            if len(group_rows) < min_occurrences:
                continue
            branch = group_rows[0][2]
            item = group_rows[0][3]
            shortage_total = sum(float(l.movement_diff) for l, *_ in group_rows if l.movement_diff and l.movement_diff > 0)
            surplus_total = sum(float(-l.movement_diff) for l, *_ in group_rows if l.movement_diff and l.movement_diff < 0)
            last_date = max(s.shift_date for _, s, _, _ in group_rows)
            reasons = list({l.movement_exception_reason for l, *_ in group_rows if l.movement_exception_reason})[:3]
            items.append(
                {
                    "branch_id": bid,
                    "branch_name": branch.branch_name,
                    "item_id": iid,
                    "item_name": item.item_name_en,
                    "occurrences": len(group_rows),
                    "shortage_total": shortage_total,
                    "surplus_total": surplus_total,
                    "last_date": last_date.isoformat(),
                    "reasons_sample": reasons,
                }
            )
        total = len(items)
        page_items = items[(page - 1) * page_size : page * page_size]
        return {"total": total, "page": page, "page_size": page_size, "group": "repeat", "items": page_items}
    total = q.count()
    rows = (
        q.order_by(BranchShift.shift_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for line, shift, branch, item in rows:
        diff = float(line.movement_diff or 0)
        items.append(
            {
                "line_id": line.id,
                "shift_id": shift.id,
                "branch_id": branch.id,
                "branch_name": branch.branch_name,
                "shift_date": shift.shift_date.isoformat(),
                "item_id": item.id,
                "item_name": item.item_name_en,
                "unit": None,
                "opening_balance": float(line.opening_balance or 0),
                "received_qty": float(line.received_qty or 0),
                "returned_qty": float(line.returned_qty or 0),
                "damaged_qty": float(line.damaged_qty or 0),
                "closing_balance": float(line.closing_balance or 0),
                "movement_diff": diff,
                "reason": line.movement_exception_reason,
                "direction": "shortage" if diff > 0 else "surplus",
            }
        )
    return {"total": total, "page": page, "page_size": page_size, "group": "line", "items": items}
