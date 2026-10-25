from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import require_roles
from app.database import get_db
from app.models import User
from app.schemas.count_audit import CountAuditEventCreate, CountAuditFindingCreate
from app.services import count_audit_service as svc
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/audit/findings/count-audit", tags=["Count Audit"])

_ROUTE_ROLES = (
    "internal_auditor",
    "admin",
    "super_admin",
    "operations_manager",
    "area_manager",
    "branch_manager",
)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("/filters")
def filters(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ROUTE_ROLES)),
):
    return svc.get_filters(db, current_user)


@router.get("/coverage")
def coverage(
    date_from: date = Query(...),
    date_to: date = Query(...),
    brand_id: Optional[int] = None,
    city: Optional[str] = None,
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ROUTE_ROLES)),
):
    return svc.get_coverage(db, current_user, date_from=date_from, date_to=date_to, brand_id=brand_id, city=city, branch_id=branch_id)


@router.get("/shifts")
def shifts(
    date_from: date = Query(...),
    date_to: date = Query(...),
    brand_id: Optional[int] = None,
    city: Optional[str] = None,
    branch_id: Optional[int] = None,
    status: Optional[str] = None,
    has_diff: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ROUTE_ROLES)),
):
    return svc.list_shifts(
        db,
        current_user,
        date_from=date_from,
        date_to=date_to,
        brand_id=brand_id,
        city=city,
        branch_id=branch_id,
        status=status,
        has_diff=has_diff,
        page=page,
        page_size=page_size,
    )


@router.get("/shifts/{shift_id}")
def shift_detail(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ROUTE_ROLES)),
):
    return svc.get_shift_detail(db, current_user, shift_id)


@router.get("/variances")
def variances(
    date_from: date = Query(...),
    date_to: date = Query(...),
    direction: str = Query("all"),
    brand_id: Optional[int] = None,
    city: Optional[str] = None,
    branch_id: Optional[int] = None,
    item_id: Optional[int] = None,
    min_abs_diff: Optional[float] = None,
    group: str = Query("line"),
    min_occurrences: int = Query(2, ge=2),
    include_opening: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ROUTE_ROLES)),
):
    return svc.list_variances(
        db,
        current_user,
        date_from=date_from,
        date_to=date_to,
        direction=direction,
        brand_id=brand_id,
        city=city,
        branch_id=branch_id,
        item_id=item_id,
        min_abs_diff=min_abs_diff,
        group=group,
        min_occurrences=min_occurrences,
        include_opening=include_opening,
        page=page,
        page_size=page_size,
    )


@router.get("/findings")
def findings_list(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    queue: Optional[str] = None,
    status: Optional[str] = None,
    branch_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ROUTE_ROLES)),
):
    return svc.list_findings(
        db,
        current_user,
        date_from=date_from,
        date_to=date_to,
        queue=queue,
        status=status,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
    )


@router.get("/findings/{finding_id}")
def finding_detail(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ROUTE_ROLES)),
):
    return svc.get_finding_detail(db, current_user, finding_id)


@router.post("/findings")
def create_finding(
    payload: CountAuditFindingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("internal_auditor", "admin", "super_admin")),
):
    return svc.create_finding(db, current_user, payload, _ip(request))


@router.post("/findings/{finding_id}/events")
def post_event(
    finding_id: int,
    payload: CountAuditEventCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ROUTE_ROLES)),
):
    return svc.post_event(db, current_user, finding_id, payload, _ip(request))
