"""
Quality Visit Router — /api/v1/quality
"""
import logging
import os
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.auth import get_current_active_user, require_roles
from app.config import settings
from app.database import get_db
from app.models import User, QualityVisitStatus
from app.schemas import (
    QualityVisitCreate,
    QualityVisitOut,
    QualityVisitListResponse,
    QualityVisitReviewRequest,
    QualityVisitResponseUpdate,
    QualityVisitResponseOut,
    QualityVisitSectionOut,
    QualityOpenActionOut,
    ComplianceTrendPoint,
    QualityVisitAttachmentOut,
    QualityVisitSignRequest,
    BulkResolveRequest,
    BulkResolveResult,
    SectionComplianceOut,
)
from app.services import quality_service

router = APIRouter(prefix="/api/v1/quality", tags=["Quality Visits"])

_VISITOR_ROLES = ("quality_visitor", "quality_manager", "admin", "super_admin")
_REVIEWER_ROLES = ("quality_manager", "admin", "super_admin")
_VIEW_ROLES = ("quality_visitor", "quality_manager", "branch_manager", "area_manager", "internal_auditor", "admin", "super_admin")
_ACTION_RESOLVER_ROLES = ("quality_manager", "branch_manager", "area_manager", "admin", "super_admin")


# ─── Checklist Template ───────────────────────────────────────────────────────

@router.get("/checklist", response_model=list[QualityVisitSectionOut])
def get_checklist(
    branch_id: Optional[int] = None,
    brand_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """قائمة بنود الزيارة — مصنفة حسب المحاور"""
    return quality_service.list_sections(db, branch_id=branch_id, brand_key=brand_key)


# ─── Visits CRUD ──────────────────────────────────────────────────────────────

@router.get("/", response_model=QualityVisitListResponse)
def list_visits(
    branch_id: Optional[int] = None,
    visitor_id: Optional[int] = None,
    status: Optional[QualityVisitStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    # الزائر يشوف بس زياراته
    if "quality_visitor" in user_roles and "quality_manager" not in user_roles:
        visitor_id = current_user.id

    total, items = quality_service.list_visits(
        db,
        branch_id=branch_id,
        visitor_id=visitor_id,
        status_filter=status,
        page=page,
        page_size=page_size,
    )
    return QualityVisitListResponse(total=total, page=page, page_size=page_size, items=items)


@router.post("/", response_model=QualityVisitOut, status_code=201)
def create_visit(
    data: QualityVisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VISITOR_ROLES)),
):
    return quality_service.create_visit(db, data, created_by=current_user.id)


# ─── Open Corrective Actions (static paths MUST be declared before /{visit_id}) ─

@router.get("/open-actions/owners", response_model=list[str])
def list_action_owners(
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """قائمة بأسماء أصحاب الإجراءات — لبناء فلتر الواجهة"""
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    if "branch_manager" in user_roles and not any(
        r in user_roles for r in ("quality_manager", "admin", "super_admin", "area_manager")
    ):
        branch_id = current_user.branch_id
    return quality_service.list_action_owners(db, branch_id=branch_id)


@router.post("/open-actions/bulk-resolve", response_model=BulkResolveResult)
def bulk_resolve_open_actions(
    data: BulkResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ACTION_RESOLVER_ROLES)),
):
    """إغلاق مجموعة إجراءات تصحيحية دفعة واحدة"""
    result = quality_service.bulk_resolve_actions(
        db,
        response_ids=data.response_ids,
        notes=data.notes,
        resolved_by=current_user.id,
    )
    return BulkResolveResult(**result)


@router.get("/open-actions", response_model=list[QualityOpenActionOut])
def list_open_actions(
    branch_id: Optional[int] = None,
    overdue_only: bool = False,
    due_within_days: Optional[int] = Query(None, ge=0, le=365),
    owner: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """قائمة الإجراءات التصحيحية المفتوحة"""
    from datetime import date as date_type
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    # branch_manager محصور بفرعه
    branch_ids = None
    if "branch_manager" in user_roles and not any(
        r in user_roles for r in ("quality_manager", "admin", "super_admin", "area_manager")
    ):
        mgr_branch = current_user.branch_id
        if mgr_branch is None:
            return []
        branch_id = mgr_branch

    rows = quality_service.list_open_actions(
        db,
        branch_id=branch_id,
        branch_ids=branch_ids,
        overdue_only=overdue_only,
        due_within_days=due_within_days,
        owner=owner,
    )

    today = date_type.today()
    out = []
    for r in rows:
        try:
            visit = r.visit if hasattr(r, "visit") and r.visit else None
            # fallback if visit relationship wasn't loaded — load minimally
            b_id = visit.branch_id if visit else None
            v_date = visit.visit_date if visit else None
            if b_id is None or v_date is None:
                # query visit row directly
                from app.models import QualityVisit as _QV
                v = db.query(_QV).filter(_QV.id == r.visit_id).first()
                if v:
                    b_id = v.branch_id
                    v_date = v.visit_date
            # لو الزيارة اتمسحت أو الفرع مفقود، فوّت الصف بدلاً من 500
            if b_id is None or v_date is None:
                logger.warning(
                    "open-action response %s has no linked visit/branch — skipping",
                    r.id,
                )
                continue
            is_overdue = bool(r.due_date and r.due_date < today)
            out.append(
                QualityOpenActionOut(
                    id=r.id,
                    visit_id=r.visit_id,
                    branch_id=b_id,
                    visit_date=v_date,
                    item_id=r.item_id,
                    item=r.item,   # قد يكون None — الـ schema يسمح
                    corrective_action=r.corrective_action,
                    action_owner=r.action_owner,
                    due_date=r.due_date,
                    is_overdue=is_overdue,
                    notes=r.notes,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Failed to serialize open-action response %s: %s", r.id, exc
            )
            continue
    return out


@router.post("/open-actions/{response_id}/resolve", response_model=QualityVisitResponseOut)
def resolve_open_action(
    response_id: int,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ACTION_RESOLVER_ROLES)),
):
    """علّم إجراء تصحيحي كمحلول"""
    return quality_service.resolve_open_action(
        db, response_id, notes=notes, resolved_by=current_user.id
    )


@router.get("/{visit_id}", response_model=QualityVisitOut)
def get_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    return quality_service.get_visit(db, visit_id)


@router.delete("/{visit_id}", status_code=204)
def delete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VISITOR_ROLES)),
):
    quality_service.delete_visit(db, visit_id)


# ─── Workflow Actions ─────────────────────────────────────────────────────────

@router.post("/{visit_id}/submit", response_model=QualityVisitOut)
def submit_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VISITOR_ROLES)),
):
    """رفع الزيارة للمراجعة"""
    return quality_service.submit_visit(db, visit_id)


@router.post("/{visit_id}/review", response_model=QualityVisitOut)
def review_visit(
    visit_id: int,
    data: QualityVisitReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_REVIEWER_ROLES)),
):
    """مسؤول الجودة يراجع الزيارة"""
    return quality_service.review_visit(db, visit_id, data, reviewer_id=current_user.id)


@router.post("/{visit_id}/close", response_model=QualityVisitOut)
def close_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_REVIEWER_ROLES)),
):
    """إغلاق الزيارة بعد اكتمال الإجراءات"""
    return quality_service.close_visit(db, visit_id)


# ─── Responses ────────────────────────────────────────────────────────────────

@router.patch("/{visit_id}/responses/{response_id}", response_model=QualityVisitResponseOut)
def update_response(
    visit_id: int,
    response_id: int,
    data: QualityVisitResponseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VISITOR_ROLES)),
):
    """تحديث رد واحد على بند معين"""
    return quality_service.update_response(db, visit_id, response_id, data)


# ─── Attachments ─────────────────────────────────────────────────────────────

@router.get("/responses/{response_id}/attachments", response_model=list[QualityVisitAttachmentOut])
def list_response_attachments(
    response_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """قائمة مرفقات رد معين"""
    return quality_service.list_attachments(db, response_id)


@router.post(
    "/responses/{response_id}/attachments",
    response_model=QualityVisitAttachmentOut,
    status_code=201,
)
def upload_response_attachment(
    response_id: int,
    file: UploadFile = File(...),
    kind: str = Form("photo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VISITOR_ROLES)),
):
    """رفع صورة/PDF كمرفق لرد معين"""
    upload_dir = os.path.join(settings.QUALITY_UPLOAD_DIR, f"resp_{response_id}")
    return quality_service.create_attachment(
        db,
        response_id=response_id,
        file=file,
        uploaded_by=current_user.id,
        upload_dir=upload_dir,
        kind=kind,
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VISITOR_ROLES)),
):
    """حذف مرفق"""
    quality_service.delete_attachment(db, attachment_id)


# ─── I3 — Visit-level attachments (صور على مستوى الزيارة) ─────────────────────

@router.get(
    "/{visit_id}/attachments",
    response_model=list[QualityVisitAttachmentOut],
)
def list_visit_attachments(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """قائمة المرفقات على مستوى الزيارة (مش مرتبطة ببند معين)"""
    return quality_service.list_visit_attachments(db, visit_id)


@router.post(
    "/{visit_id}/attachments",
    response_model=QualityVisitAttachmentOut,
    status_code=201,
)
def upload_visit_attachment(
    visit_id: int,
    file: UploadFile = File(...),
    kind: str = Form("photo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VISITOR_ROLES)),
):
    """رفع صورة/PDF كمرفق على الزيارة نفسها (غير مرتبط ببند)"""
    upload_dir = os.path.join(settings.QUALITY_UPLOAD_DIR, f"visit_{visit_id}")
    return quality_service.create_visit_attachment(
        db,
        visit_id=visit_id,
        file=file,
        uploaded_by=current_user.id,
        upload_dir=upload_dir,
        kind=kind,
    )


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """تنزيل مرفق"""
    from app.models import QualityVisitAttachment
    att = db.query(QualityVisitAttachment).filter(
        QualityVisitAttachment.id == attachment_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="المرفق غير موجود")
    if not att.file_path or not os.path.exists(att.file_path):
        raise HTTPException(status_code=404, detail="الملف الأصلي غير متوفر على الخادم")
    return FileResponse(
        att.file_path,
        media_type=att.mime_type or "application/octet-stream",
        filename=att.original_name or os.path.basename(att.file_path),
    )


# ─── Signatures ──────────────────────────────────────────────────────────────

@router.post("/{visit_id}/sign", response_model=QualityVisitOut)
def sign_visit(
    visit_id: int,
    data: QualityVisitSignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """توقيع الزيارة (visitor أو branch_manager)"""
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    # تحقق: فقط branch_manager/admins يوقعون كـ branch_manager
    if data.role == "branch_manager" and not any(
        r in user_roles for r in ("branch_manager", "area_manager", "quality_manager", "admin", "super_admin")
    ):
        raise HTTPException(status_code=403, detail="دورك لا يسمح بالتوقيع كمدير فرع")
    if data.role == "visitor" and not any(
        r in user_roles for r in ("quality_visitor", "quality_manager", "admin", "super_admin")
    ):
        raise HTTPException(status_code=403, detail="دورك لا يسمح بالتوقيع كزائر")
    return quality_service.sign_visit(
        db,
        visit_id=visit_id,
        role=data.role,
        signature=data.signature,
        signed_by=current_user.id,
    )


# ─── Analytics ───────────────────────────────────────────────────────────────

@router.get("/analytics/compliance-trend", response_model=list[ComplianceTrendPoint])
def compliance_trend(
    branch_id: Optional[int] = None,
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """اتجاه نسبة الالتزام الشهري"""
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    if "branch_manager" in user_roles and not any(
        r in user_roles for r in ("quality_manager", "admin", "super_admin", "area_manager")
    ):
        branch_id = current_user.branch_id
    return quality_service.compliance_trend(db, branch_id=branch_id, months=months)


@router.get("/analytics/section-compliance", response_model=list[SectionComplianceOut])
def section_compliance(
    branch_id: Optional[int] = None,
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """متوسط الالتزام لكل قسم من أقسام الـ checklist"""
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    if "branch_manager" in user_roles and not any(
        r in user_roles for r in ("quality_manager", "admin", "super_admin", "area_manager")
    ):
        branch_id = current_user.branch_id
    rows = quality_service.section_compliance(db, branch_id=branch_id, months=months)
    return [SectionComplianceOut(**r) for r in rows]
