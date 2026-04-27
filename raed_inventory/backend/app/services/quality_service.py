"""
Quality Visit Service
الـ Business Logic لموديول زيارات الجودة
"""
import os
import uuid
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, and_, or_
from fastapi import HTTPException, status, UploadFile
from datetime import datetime
from typing import Optional, List

from app.models import (
    QualityVisit, QualityVisitResponse, QualityVisitSection, QualityVisitItem,
    QualityVisitAttachment,
    QualityVisitStatus, QualityResponseStatus, QualityItemResponseType,
    Branch, User,
    UserStatus,
)
from app.schemas import (
    QualityVisitCreate, QualityVisitReviewRequest, QualityVisitResponseUpdate,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _attach_display_names(visit: QualityVisit) -> QualityVisit:
    """
    I1 — ضع الحقول العرضية (branch_name / visitor_name ...) على كائن الزيارة
    حتى تستطيع Pydantic قراءتها عبر `from_attributes`.
    """
    try:
        br = getattr(visit, "branch", None)
        if br is not None:
            name = getattr(br, "branch_name", None) or getattr(br, "name", None)
            visit.branch_name = name
            # جداول الفروع تخزن الاسم العربي في branch_name؛ نكرره في الحقل _ar لسهولة الواجهة
            visit.branch_name_ar = name
            visit.branch_name_en = (
                getattr(br, "branch_name_en", None)
                or getattr(br, "name_en", None)
            )
        if getattr(visit, "brand_key", None):
            visit.brand_name = _brand_label(visit.brand_key)
        vis = getattr(visit, "visitor", None)
        if vis is not None:
            visit.visitor_name = getattr(vis, "full_name", None) or getattr(vis, "username", None)
        inc = getattr(visit, "in_charge", None)
        if inc is not None:
            visit.branch_in_charge_name = getattr(inc, "full_name", None) or getattr(inc, "username", None)
        rev = getattr(visit, "reviewer", None)
        if rev is not None:
            visit.reviewed_by_name = getattr(rev, "full_name", None) or getattr(rev, "username", None)
    except Exception:
        # لا نفشل الاستجابة بسبب حقل إضافي
        pass
    return visit


def _visit_load_options():
    """خيارات eager-loading قياسية لأي query بترجع QualityVisit."""
    return [
        selectinload(QualityVisit.responses)
            .joinedload(QualityVisitResponse.item)
            .joinedload(QualityVisitItem.section),
        selectinload(QualityVisit.responses)
            .selectinload(QualityVisitResponse.attachments),
        selectinload(QualityVisit.visit_attachments),
        joinedload(QualityVisit.branch),
        joinedload(QualityVisit.visitor),
        joinedload(QualityVisit.in_charge),
        joinedload(QualityVisit.reviewer),
    ]


def _load_visit(db: Session, visit_id: int) -> QualityVisit:
    visit = (
        db.query(QualityVisit)
        .options(*_visit_load_options())
        .filter(QualityVisit.id == visit_id, QualityVisit.is_deleted == False)
        .first()
    )
    if not visit:
        raise HTTPException(status_code=404, detail="زيارة الجودة غير موجودة")
    return _attach_display_names(visit)


_QUALITY_BRAND_LABELS = {
    "onda": "Onda",
    "ronaldos": "Ronaldos Pizza",
    "shawarma": "Shawarma",
    "griddle": "Griddle",
}


def _brand_label(brand_key: Optional[str]) -> Optional[str]:
    if not brand_key:
        return None
    return _QUALITY_BRAND_LABELS.get(str(brand_key).strip().lower(), brand_key)


def _infer_brand_key_from_branch_name(branch_name: Optional[str]) -> Optional[str]:
    if not branch_name:
        return None
    value = str(branch_name).strip().lower()
    if any(token in value for token in ("ronaldos", "pizza", "pizzeria")):
        return "ronaldos"
    if "shawarma" in value:
        return "shawarma"
    if any(token in value for token in ("griddle", "burger", "grill")):
        return "griddle"
    if any(token in value for token in ("onda", "coffee", "cafe", "café")):
        return "onda"
    return None


def resolve_visit_brand_key(
    db: Session,
    *,
    branch_id: Optional[int] = None,
    brand_key: Optional[str] = None,
) -> Optional[str]:
    if brand_key:
        normalized = str(brand_key).strip().lower()
        return normalized or None
    if not branch_id:
        return None
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_deleted == False).first()
    if not branch:
        return None
    return _infer_brand_key_from_branch_name(getattr(branch, "branch_name", None))


def _calc_compliance(responses: list[QualityVisitResponse]) -> Optional[float]:
    """
    احسب نسبة الالتزام الموزونة من الردود.
    - يعتمد فقط على بنود Y/N (yes_no) — بنود numeric/text إعلامية
    - Yes = 1، No = 0، N/A مستثنى
    - الوزن يُؤخذ من `section.weight` (٪)، كل بند داخل القسم له وزن متساوٍ ضمن وزن القسم
    - إذا لم تتوفر أوزان، نستخدم متوسط بسيط
    """
    # فلتر: yes_no فقط، ومش N/A
    yn_responses = []
    for r in responses:
        item = r.item
        if item is None:
            continue
        rtype = getattr(item, "response_type", "yes_no") or "yes_no"
        if rtype != "yes_no":
            continue
        if r.status == QualityResponseStatus.na or r.status is None:
            continue
        yn_responses.append(r)

    if not yn_responses:
        return None

    # جمّع حسب القسم: {section_id: (weight, [0/1 per response])}
    from collections import defaultdict
    by_section: dict[int, list[int]] = defaultdict(list)
    section_weights: dict[int, float] = {}
    for r in yn_responses:
        sec = r.item.section
        sec_id = sec.id if sec else 0
        by_section[sec_id].append(1 if r.status == QualityResponseStatus.yes else 0)
        if sec is not None:
            try:
                section_weights[sec_id] = float(sec.weight or 0.0)
            except (TypeError, ValueError):
                section_weights[sec_id] = 0.0

    total_weight = sum(section_weights.get(sid, 0.0) for sid in by_section.keys())

    # fallback: لو مفيش أوزان مضبوطة، اعتمد متوسط حسابي بسيط
    if total_weight <= 0:
        flat = [v for vals in by_section.values() for v in vals]
        return round(sum(flat) / len(flat) * 100, 2) if flat else None

    # weighted: كل قسم يحسب score داخلي (avg of 0/1) ثم يضرب في وزنه
    weighted_sum = 0.0
    for sec_id, vals in by_section.items():
        if not vals:
            continue
        sec_score = sum(vals) / len(vals)
        w = section_weights.get(sec_id, 0.0)
        weighted_sum += sec_score * w

    return round(weighted_sum / total_weight * 100, 2)


def _assert_status(visit: QualityVisit, allowed: list[QualityVisitStatus], action: str):
    if visit.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"لا يمكن {action} في حالة '{visit.status.value}'",
        )


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def get_visit(db: Session, visit_id: int) -> QualityVisit:
    return _load_visit(db, visit_id)


def list_visits(
    db: Session,
    branch_id: Optional[int] = None,
    visitor_id: Optional[int] = None,
    status_filter: Optional[QualityVisitStatus] = None,
    page: int = 1,
    page_size: int = 20,
):
    q = db.query(QualityVisit).filter(QualityVisit.is_deleted == False)
    if branch_id:
        q = q.filter(QualityVisit.branch_id == branch_id)
    if visitor_id:
        q = q.filter(QualityVisit.visitor_id == visitor_id)
    if status_filter:
        q = q.filter(QualityVisit.status == status_filter)

    total = q.count()
    items = (
        q.options(
            joinedload(QualityVisit.branch),
            joinedload(QualityVisit.visitor),
        )
        .order_by(QualityVisit.visit_date.desc(), QualityVisit.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    # I1 — attach display names so the list view can render branch/visitor names
    for v in items:
        _attach_display_names(v)
    return total, items


def create_visit(db: Session, data: QualityVisitCreate, created_by: int) -> QualityVisit:
    # تحقق: الزائر المذكور موجود وله دور quality_visitor أو أعلى
    branch = (
        db.query(Branch)
        .filter(Branch.id == data.branch_id, Branch.is_deleted == False, Branch.active == True)
        .first()
    )
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود أو غير نشط")

    visitor = (
        db.query(User)
        .filter(
            User.id == data.visitor_id,
            User.status == UserStatus.active,
            User.is_deleted == False,
        )
        .first()
    )
    if not visitor:
        raise HTTPException(status_code=404, detail="الزائر غير موجود أو غير نشط")

    resolved_brand_key = resolve_visit_brand_key(
        db,
        branch_id=data.branch_id,
        brand_key=data.brand_key,
    )

    visit = QualityVisit(
        branch_id=data.branch_id,
        brand_key=resolved_brand_key,
        visitor_id=data.visitor_id,
        branch_in_charge=data.branch_in_charge,
        visit_date=data.visit_date,
        shift=data.shift,
        summary_notes=data.summary_notes,
        status=QualityVisitStatus.draft,
        created_by=created_by,
    )
    db.add(visit)
    db.flush()  # get visit.id

    # أضف الردود
    response_objs = []
    for r in data.responses:
        item = (
            db.query(QualityVisitItem)
            .join(QualityVisitSection, QualityVisitSection.id == QualityVisitItem.section_id)
            .filter(QualityVisitItem.id == r.item_id, QualityVisitItem.is_active == True)
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail=f"بند الجودة رقم {r.item_id} غير موجود")
        item_brand_key = getattr(item.section, "brand_key", None) if item.section else None
        if resolved_brand_key and item_brand_key and item_brand_key != resolved_brand_key:
            raise HTTPException(
                status_code=400,
                detail="بنود الزيارة لا تطابق البراند المختار",
            )
        resp = QualityVisitResponse(
            visit_id=visit.id,
            item_id=r.item_id,
            status=r.status,
            numeric_value=r.numeric_value,
            text_value=r.text_value,
            notes=r.notes,
            corrective_action=r.corrective_action,
            action_owner=r.action_owner,
            due_date=r.due_date,
        )
        response_objs.append(resp)
    db.bulk_save_objects(response_objs)
    db.commit()
    db.refresh(visit)
    return _load_visit(db, visit.id)


def submit_visit(db: Session, visit_id: int) -> QualityVisit:
    """الزائر يرفع الزيارة للمراجعة"""
    visit = _load_visit(db, visit_id)
    _assert_status(visit, [QualityVisitStatus.draft], "رفع الزيارة")

    visit.compliance_pct = _calc_compliance(visit.responses)
    visit.status = QualityVisitStatus.submitted
    db.commit()
    db.refresh(visit)
    return _load_visit(db, visit_id)


def review_visit(
    db: Session,
    visit_id: int,
    data: QualityVisitReviewRequest,
    reviewer_id: int,
) -> QualityVisit:
    """مسؤول الجودة يراجع الزيارة"""
    visit = _load_visit(db, visit_id)
    _assert_status(visit, [QualityVisitStatus.submitted], "مراجعة الزيارة")

    # تحقق: المراجع لا يستطيع مراجعة زيارته هو (فصل الصلاحيات)
    if visit.visitor_id == reviewer_id:
        raise HTTPException(
            status_code=403,
            detail="لا يمكن مراجعة زيارتك الخاصة — يجب أن يراجعها شخص آخر",
        )

    visit.status = QualityVisitStatus.reviewed
    visit.reviewed_by = reviewer_id
    visit.reviewed_at = datetime.utcnow()
    if data.summary_notes is not None:
        visit.summary_notes = data.summary_notes
    if data.follow_up_date is not None:
        visit.follow_up_date = data.follow_up_date

    db.commit()
    db.refresh(visit)
    return _load_visit(db, visit_id)


def close_visit(db: Session, visit_id: int) -> QualityVisit:
    """إغلاق الزيارة بعد اكتمال الإجراءات"""
    visit = _load_visit(db, visit_id)
    _assert_status(visit, [QualityVisitStatus.reviewed], "إغلاق الزيارة")

    visit.status = QualityVisitStatus.closed
    visit.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(visit)
    return _load_visit(db, visit_id)


def update_response(
    db: Session,
    visit_id: int,
    response_id: int,
    data: QualityVisitResponseUpdate,
) -> QualityVisitResponse:
    """تحديث رد واحد — للزائر (في draft) أو المراجع (في reviewed)"""
    visit = db.query(QualityVisit).filter(
        QualityVisit.id == visit_id,
        QualityVisit.is_deleted == False,
    ).first()
    if not visit:
        raise HTTPException(status_code=404, detail="زيارة الجودة غير موجودة")

    resp = db.query(QualityVisitResponse).filter(
        QualityVisitResponse.id == response_id,
        QualityVisitResponse.visit_id == visit_id,
    ).first()
    if not resp:
        raise HTTPException(status_code=404, detail="الرد غير موجود")

    if data.status is not None:
        resp.status = data.status
    if data.numeric_value is not None:
        resp.numeric_value = data.numeric_value
    if data.text_value is not None:
        resp.text_value = data.text_value
    if data.notes is not None:
        resp.notes = data.notes
    if data.corrective_action is not None:
        resp.corrective_action = data.corrective_action
    if data.action_owner is not None:
        resp.action_owner = data.action_owner
    if data.due_date is not None:
        resp.due_date = data.due_date
    if data.is_resolved is not None:
        resp.is_resolved = data.is_resolved

    # أعد حساب نسبة الالتزام إذا تغير الحالة (الـ numeric/text لا تؤثر)
    if data.status is not None:
        all_responses = (
            db.query(QualityVisitResponse)
            .options(
                joinedload(QualityVisitResponse.item).joinedload(QualityVisitItem.section)
            )
            .filter(QualityVisitResponse.visit_id == visit_id)
            .all()
        )
        visit.compliance_pct = _calc_compliance(all_responses)

    db.commit()
    db.refresh(resp)
    return resp


def delete_visit(db: Session, visit_id: int) -> None:
    """Soft delete — draft فقط"""
    visit = db.query(QualityVisit).filter(
        QualityVisit.id == visit_id,
        QualityVisit.is_deleted == False,
    ).first()
    if not visit:
        raise HTTPException(status_code=404, detail="زيارة الجودة غير موجودة")
    if visit.status != QualityVisitStatus.draft:
        raise HTTPException(
            status_code=409,
            detail="لا يمكن حذف زيارة تم رفعها — أرجع إلى مسودة أولاً",
        )
    visit.is_deleted = True
    db.commit()


# ─── Template / Checklist ─────────────────────────────────────────────────────

def list_sections(
    db: Session,
    *,
    branch_id: Optional[int] = None,
    brand_key: Optional[str] = None,
) -> list[QualityVisitSection]:
    resolved_brand_key = resolve_visit_brand_key(db, branch_id=branch_id, brand_key=brand_key)
    q = (
        db.query(QualityVisitSection)
        .options(selectinload(QualityVisitSection.items))
        .filter(QualityVisitSection.is_active == True)
    )
    if resolved_brand_key:
        brand_rows = (
            q.filter(QualityVisitSection.brand_key == resolved_brand_key)
            .order_by(QualityVisitSection.order)
            .all()
        )
        if brand_rows:
            return brand_rows
    return q.filter(QualityVisitSection.brand_key.is_(None)).order_by(QualityVisitSection.order).all()


# ─── Analytics / Open actions ────────────────────────────────────────────────

def list_open_actions(
    db: Session,
    branch_id: Optional[int] = None,
    branch_ids: Optional[list[int]] = None,
    overdue_only: bool = False,
    due_within_days: Optional[int] = None,
    owner: Optional[str] = None,
):
    """
    كل بند رد = `no` غير محلول وله إجراء تصحيحي. قابل للفلترة:
      - branch_id أو branch_ids
      - overdue_only: الاستحقاق انقضى
      - due_within_days: تاريخ الاستحقاق خلال N يوم قادم
      - owner: اسم المسؤول (بحث جزئي)
    """
    from datetime import date as date_type
    q = (
        db.query(QualityVisitResponse)
        .join(QualityVisit, QualityVisit.id == QualityVisitResponse.visit_id)
        .options(
            joinedload(QualityVisitResponse.item).joinedload(QualityVisitItem.section),
            joinedload(QualityVisitResponse.visit),
        )
        .filter(
            QualityVisit.is_deleted == False,
            QualityVisitResponse.status == QualityResponseStatus.no,
            QualityVisitResponse.is_resolved == False,
        )
    )
    if branch_id is not None:
        q = q.filter(QualityVisit.branch_id == branch_id)
    elif branch_ids:
        q = q.filter(QualityVisit.branch_id.in_(branch_ids))

    if owner:
        q = q.filter(QualityVisitResponse.action_owner.ilike(f"%{owner}%"))

    today = date_type.today()
    if overdue_only:
        q = q.filter(QualityVisitResponse.due_date != None, QualityVisitResponse.due_date < today)
    elif due_within_days is not None:
        from datetime import timedelta
        threshold = today + timedelta(days=due_within_days)
        q = q.filter(QualityVisitResponse.due_date != None, QualityVisitResponse.due_date <= threshold)

    return q.order_by(QualityVisitResponse.due_date.asc().nulls_last()).all()


def list_action_owners(db: Session, branch_id: Optional[int] = None) -> List[str]:
    """قائمة بأسماء أصحاب الإجراءات (فريدة) — لاستخدامها في الفلتر"""
    q = (
        db.query(QualityVisitResponse.action_owner)
        .join(QualityVisit, QualityVisit.id == QualityVisitResponse.visit_id)
        .filter(
            QualityVisit.is_deleted == False,
            QualityVisitResponse.action_owner != None,
            QualityVisitResponse.action_owner != "",
        )
    )
    if branch_id is not None:
        q = q.filter(QualityVisit.branch_id == branch_id)
    rows = q.distinct().all()
    return sorted({r[0] for r in rows if r[0]})


def resolve_open_action(
    db: Session,
    response_id: int,
    notes: Optional[str] = None,
    resolved_by: Optional[int] = None,
) -> QualityVisitResponse:
    """علّم إجراء تصحيحي كمحلول — يسجل المنفّذ + التوقيت"""
    resp = (
        db.query(QualityVisitResponse)
        .options(joinedload(QualityVisitResponse.item).joinedload(QualityVisitItem.section))
        .filter(QualityVisitResponse.id == response_id)
        .first()
    )
    if not resp:
        raise HTTPException(status_code=404, detail="الرد غير موجود")
    if resp.is_resolved:
        raise HTTPException(status_code=409, detail="الإجراء محلول مسبقاً")
    resp.is_resolved = True
    resp.resolved_by = resolved_by
    resp.resolved_at = datetime.utcnow()
    if notes:
        prev = resp.notes or ""
        resp.notes = (prev + "\n" if prev else "") + f"[حل] {notes}"
    db.commit()
    db.refresh(resp)
    return resp


def bulk_resolve_actions(
    db: Session,
    response_ids: list[int],
    notes: Optional[str] = None,
    resolved_by: Optional[int] = None,
) -> dict:
    """إغلاق عدة إجراءات دفعة واحدة. يرجع dict بعدد المنفذ/المتخطى والمعرفات الفاشلة."""
    resolved = 0
    skipped = 0
    failed = []
    rows = (
        db.query(QualityVisitResponse)
        .filter(QualityVisitResponse.id.in_(response_ids))
        .all()
    )
    found_ids = {r.id for r in rows}
    for rid in response_ids:
        if rid not in found_ids:
            failed.append(rid)
    for r in rows:
        if r.is_resolved:
            skipped += 1
            continue
        r.is_resolved = True
        r.resolved_by = resolved_by
        r.resolved_at = datetime.utcnow()
        if notes:
            prev = r.notes or ""
            r.notes = (prev + "\n" if prev else "") + f"[حل] {notes}"
        resolved += 1
    db.commit()
    return {"resolved": resolved, "skipped": skipped, "failed": failed}


# ─── Attachments ─────────────────────────────────────────────────────────────

_ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB


def create_attachment(
    db: Session,
    response_id: int,
    file: UploadFile,
    uploaded_by: Optional[int],
    upload_dir: str,
    kind: str = "photo",
) -> QualityVisitAttachment:
    """حفظ مرفق (صورة/PDF) مرتبط برد زيارة جودة.
    - يُقرأ الملف في الذاكرة (الحد 10 ميجا)
    - يُحفظ باسم فريد uuid لتفادي التعارض
    """
    resp = db.query(QualityVisitResponse).filter(QualityVisitResponse.id == response_id).first()
    if not resp:
        raise HTTPException(status_code=404, detail="الرد غير موجود")

    mime = (file.content_type or "").lower()
    if mime and not any(mime.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=415,
            detail=f"نوع الملف غير مسموح ({mime}). المسموح: صور أو PDF",
        )

    data = file.file.read()
    if len(data) > _MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="حجم الملف أكبر من 10 ميجا")
    if not data:
        raise HTTPException(status_code=400, detail="ملف فارغ")

    os.makedirs(upload_dir, exist_ok=True)
    original = (file.filename or "upload.bin").strip().replace("/", "_").replace("\\", "_")
    ext = os.path.splitext(original)[1].lower() or ""
    fname = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(upload_dir, fname)
    with open(full_path, "wb") as f:
        f.write(data)

    att = QualityVisitAttachment(
        response_id=response_id,
        file_path=full_path,
        original_name=original[:255],
        mime_type=mime[:100] if mime else None,
        size_bytes=len(data),
        kind=kind if kind in ("photo", "document", "signature") else "photo",
        uploaded_by=uploaded_by,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def list_attachments(db: Session, response_id: int) -> list[QualityVisitAttachment]:
    return (
        db.query(QualityVisitAttachment)
        .filter(QualityVisitAttachment.response_id == response_id)
        .order_by(QualityVisitAttachment.uploaded_at.asc(), QualityVisitAttachment.id.asc())
        .all()
    )


# I3 — visit-level attachments (not tied to a specific checklist response)
def create_visit_attachment(
    db: Session,
    visit_id: int,
    file: UploadFile,
    uploaded_by: Optional[int],
    upload_dir: str,
    kind: str = "photo",
) -> QualityVisitAttachment:
    """حفظ مرفق على مستوى الزيارة نفسها (صورة/PDF عامة)."""
    visit = db.query(QualityVisit).filter(
        QualityVisit.id == visit_id,
        QualityVisit.is_deleted == False,
    ).first()
    if not visit:
        raise HTTPException(status_code=404, detail="زيارة الجودة غير موجودة")

    mime = (file.content_type or "").lower()
    if mime and not any(mime.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=415,
            detail=f"نوع الملف غير مسموح ({mime}). المسموح: صور أو PDF",
        )

    data = file.file.read()
    if len(data) > _MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="حجم الملف أكبر من 10 ميجا")
    if not data:
        raise HTTPException(status_code=400, detail="ملف فارغ")

    os.makedirs(upload_dir, exist_ok=True)
    original = (file.filename or "upload.bin").strip().replace("/", "_").replace("\\", "_")
    ext = os.path.splitext(original)[1].lower() or ""
    fname = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(upload_dir, fname)
    with open(full_path, "wb") as f:
        f.write(data)

    att = QualityVisitAttachment(
        visit_id=visit_id,
        response_id=None,
        file_path=full_path,
        original_name=original[:255],
        mime_type=mime[:100] if mime else None,
        size_bytes=len(data),
        kind=kind if kind in ("photo", "document", "signature") else "photo",
        uploaded_by=uploaded_by,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def list_visit_attachments(db: Session, visit_id: int) -> list[QualityVisitAttachment]:
    return (
        db.query(QualityVisitAttachment)
        .filter(
            QualityVisitAttachment.visit_id == visit_id,
            QualityVisitAttachment.response_id == None,
        )
        .order_by(QualityVisitAttachment.uploaded_at.asc(), QualityVisitAttachment.id.asc())
        .all()
    )


def delete_attachment(db: Session, attachment_id: int) -> None:
    att = db.query(QualityVisitAttachment).filter(QualityVisitAttachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="المرفق غير موجود")
    # امسح الملف من القرص إن أمكن
    try:
        if att.file_path and os.path.exists(att.file_path):
            os.remove(att.file_path)
    except OSError:
        pass
    db.delete(att)
    db.commit()


# ─── Signatures ──────────────────────────────────────────────────────────────

def sign_visit(
    db: Session,
    visit_id: int,
    role: str,
    signature: str,
    signed_by: Optional[int] = None,
) -> QualityVisit:
    """توقيع الزيارة بواسطة الزائر أو مدير الفرع.
    - role: 'visitor' أو 'branch_manager'
    - signature: الاسم المكتوب أو base64 للتوقيع
    - مسموح بعد الرفع (submitted) أو المراجعة (reviewed)
    """
    if role not in ("visitor", "branch_manager"):
        raise HTTPException(status_code=400, detail="الدور يجب أن يكون visitor أو branch_manager")

    visit = _load_visit(db, visit_id)
    _assert_status(
        visit,
        [QualityVisitStatus.submitted, QualityVisitStatus.reviewed, QualityVisitStatus.closed],
        "توقيع الزيارة",
    )

    sig = (signature or "").strip()
    if len(sig) < 2:
        raise HTTPException(status_code=400, detail="التوقيع قصير جداً")
    sig = sig[:200]

    now = datetime.utcnow()
    if role == "visitor":
        # الزائر يوقع نفسه فقط
        if signed_by is not None and visit.visitor_id and signed_by != visit.visitor_id:
            raise HTTPException(status_code=403, detail="لا يمكنك التوقيع كزائر — لست صاحب الزيارة")
        visit.visitor_signature = sig
        visit.visitor_signed_at = now
    else:
        visit.branch_mgr_signature = sig
        visit.branch_mgr_signed_at = now

    db.commit()
    db.refresh(visit)
    return _load_visit(db, visit_id)


# ─── Section analytics ───────────────────────────────────────────────────────

def section_compliance(
    db: Session,
    branch_id: Optional[int] = None,
    months: int = 6,
) -> list[dict]:
    """
    متوسط الالتزام لكل قسم من أقسام الـ checklist عبر آخر N شهر.
    Returns list of dicts with section_id, section_name_ar/en, avg_compliance, responses_count, no_count.
    """
    from datetime import date as date_type
    from collections import defaultdict

    today = date_type.today()
    year = today.year
    month = today.month - (months - 1)
    while month <= 0:
        month += 12
        year -= 1
    first_month = date_type(year, month, 1)

    q = (
        db.query(QualityVisitResponse)
        .join(QualityVisit, QualityVisit.id == QualityVisitResponse.visit_id)
        .options(
            joinedload(QualityVisitResponse.item).joinedload(QualityVisitItem.section),
        )
        .filter(
            QualityVisit.is_deleted == False,
            QualityVisit.status.in_([QualityVisitStatus.reviewed, QualityVisitStatus.closed]),
            QualityVisit.visit_date >= first_month,
        )
    )
    if branch_id is not None:
        q = q.filter(QualityVisit.branch_id == branch_id)

    responses = q.all()

    # aggregate by section, only yes_no and not N/A
    by_section = defaultdict(lambda: {"yes": 0, "no": 0, "total": 0, "name_ar": "", "name_en": "", "order": 0})
    for r in responses:
        item = r.item
        if item is None or item.section is None:
            continue
        rtype = getattr(item, "response_type", "yes_no") or "yes_no"
        if rtype != "yes_no":
            continue
        if r.status == QualityResponseStatus.na or r.status is None:
            continue
        sec = item.section
        bucket = by_section[sec.id]
        bucket["name_ar"] = sec.name_ar or ""
        bucket["name_en"] = sec.name_en or ""
        bucket["order"] = sec.order or 0
        bucket["total"] += 1
        if r.status == QualityResponseStatus.yes:
            bucket["yes"] += 1
        elif r.status == QualityResponseStatus.no:
            bucket["no"] += 1

    result = []
    for sid, b in by_section.items():
        if b["total"] == 0:
            continue
        result.append({
            "section_id": sid,
            "section_name_ar": b["name_ar"],
            "section_name_en": b["name_en"],
            "avg_compliance": round(b["yes"] / b["total"] * 100, 2),
            "responses_count": b["total"],
            "no_count": b["no"],
            "_order": b["order"],
        })
    result.sort(key=lambda x: x["_order"])
    for r in result:
        r.pop("_order", None)
    return result


def compliance_trend(
    db: Session,
    branch_id: Optional[int] = None,
    months: int = 6,
):
    """
    متوسط compliance_pct شهرياً — للزيارات المغلقة/المراجعة.
    يرجع قائمة {month: 'YYYY-MM', branch_id, avg_compliance, visits_count}
    """
    from datetime import date as date_type
    from collections import defaultdict

    today = date_type.today()
    # نحسب نقطة البداية: أول يوم في الشهر قبل `months - 1` شهر
    first_month = (today.replace(day=1))
    if months > 1:
        # ارجع (months-1) شهر للخلف
        year = first_month.year
        month = first_month.month - (months - 1)
        while month <= 0:
            month += 12
            year -= 1
        first_month = date_type(year, month, 1)

    q = db.query(QualityVisit).filter(
        QualityVisit.is_deleted == False,
        QualityVisit.status.in_([QualityVisitStatus.reviewed, QualityVisitStatus.closed]),
        QualityVisit.visit_date >= first_month,
        QualityVisit.compliance_pct != None,
    )
    if branch_id is not None:
        q = q.filter(QualityVisit.branch_id == branch_id)

    rows = q.all()
    # aggregate: {(month, branch_id): [pct, ...]}
    buckets = defaultdict(list)
    for v in rows:
        key = (v.visit_date.strftime("%Y-%m"), v.branch_id)
        buckets[key].append(float(v.compliance_pct))

    result = []
    for (month, b_id), pcts in sorted(buckets.items()):
        avg = sum(pcts) / len(pcts) if pcts else 0.0
        result.append({
            "month": month,
            "branch_id": b_id,
            "avg_compliance": round(float(avg), 2),
            "visits_count": len(pcts),
        })
    return result
