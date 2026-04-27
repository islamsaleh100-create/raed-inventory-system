"""
Training Assessment Service
الـ Business Logic لموديول تقييم التدريب
"""
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func
from fastapi import HTTPException, status
from datetime import datetime
from typing import Optional

from app.models import (
    TrainingTemplate, TrainingTemplateSection, TrainingTemplateItem,
    TrainingAssessment, TrainingAssessmentItem, TrainingDevelopmentPlan,
    TrainingRoleType, AssessmentStatus, AssessmentVerdict,
    User,
    UserStatus,
)
from app.schemas import (
    TrainingAssessmentCreate, TrainingAssessmentApproveRequest,
    TrainingDevelopmentPlanCreate,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_assessment(db: Session, assessment_id: int) -> TrainingAssessment:
    assessment = (
        db.query(TrainingAssessment)
        .options(
            joinedload(TrainingAssessment.template)
                .selectinload(TrainingTemplate.sections)
                .selectinload(TrainingTemplateSection.items),
            selectinload(TrainingAssessment.items)
                .joinedload(TrainingAssessmentItem.item),
            joinedload(TrainingAssessment.dev_plan),
            # H12: eager-load related users + branch for name display
            joinedload(TrainingAssessment.trainee),
            joinedload(TrainingAssessment.trainer),
            joinedload(TrainingAssessment.branch),
            joinedload(TrainingAssessment.approver),
        )
        .filter(TrainingAssessment.id == assessment_id)
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="التقييم غير موجود")
    # H12: attach display-only fields so TrainingAssessmentOut can surface them
    trainee = assessment.trainee
    trainer = assessment.trainer
    branch  = assessment.branch
    tmpl    = assessment.template
    approver = assessment.approver
    assessment.trainee_name        = trainee.full_name if trainee else None
    assessment.trainee_employee_no = (trainee.username if trainee else None)
    assessment.trainer_name        = trainer.full_name if trainer else None
    assessment.branch_name         = (getattr(branch, "branch_name", None) or
                                      getattr(branch, "name", None)) if branch else None
    assessment.role_type           = (tmpl.role_type.value if tmpl and tmpl.role_type else None)
    assessment.approver_name       = approver.full_name if approver else None
    return assessment


def _calc_overall_score(items: list[TrainingAssessmentItem]) -> Optional[float]:
    """متوسط الدرجات (1-5) كـ percentage"""
    if not items:
        return None
    total = sum(i.score for i in items)
    max_score = len(items) * 5
    return round(total / max_score * 100, 2)


def _derive_verdict(score: Optional[float]) -> AssessmentVerdict:
    """حكم تلقائي: ≥80% → passed، 60-79% → conditional، <60% → failed"""
    if score is None:
        return AssessmentVerdict.failed
    if score >= 80:
        return AssessmentVerdict.passed
    if score >= 60:
        return AssessmentVerdict.conditional
    return AssessmentVerdict.failed


def _assert_status(assessment: TrainingAssessment, allowed: list[AssessmentStatus], action: str):
    if assessment.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"لا يمكن {action} في حالة '{assessment.status.value}'",
        )


# ─── Templates ────────────────────────────────────────────────────────────────

def list_templates(db: Session, role_type: Optional[TrainingRoleType] = None) -> list[TrainingTemplate]:
    q = (
        db.query(TrainingTemplate)
        .options(
            selectinload(TrainingTemplate.sections).selectinload(TrainingTemplateSection.items)
        )
        .filter(TrainingTemplate.is_active == True)
    )
    if role_type:
        q = q.filter(TrainingTemplate.role_type == role_type)
    return q.order_by(TrainingTemplate.role_type, TrainingTemplate.version.desc()).all()


def get_template(db: Session, template_id: int) -> TrainingTemplate:
    tmpl = (
        db.query(TrainingTemplate)
        .options(
            selectinload(TrainingTemplate.sections).selectinload(TrainingTemplateSection.items)
        )
        .filter(TrainingTemplate.id == template_id)
        .first()
    )
    if not tmpl:
        raise HTTPException(status_code=404, detail="القالب غير موجود")
    return tmpl


# ─── Assessments ──────────────────────────────────────────────────────────────

def get_assessment(db: Session, assessment_id: int) -> TrainingAssessment:
    return _load_assessment(db, assessment_id)


def list_assessments(
    db: Session,
    trainee_id: Optional[int] = None,
    trainer_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    status_filter: Optional[AssessmentStatus] = None,
    role_type: Optional[TrainingRoleType] = None,
    page: int = 1,
    page_size: int = 20,
):
    # H12: eager-load related entities so the list can expose names + role
    q = db.query(TrainingAssessment).options(
        joinedload(TrainingAssessment.trainee),
        joinedload(TrainingAssessment.trainer),
        joinedload(TrainingAssessment.branch),
        joinedload(TrainingAssessment.template),
    )
    if trainee_id:
        q = q.filter(TrainingAssessment.trainee_id == trainee_id)
    if trainer_id:
        q = q.filter(TrainingAssessment.trainer_id == trainer_id)
    if branch_id:
        q = q.filter(TrainingAssessment.branch_id == branch_id)
    if status_filter:
        q = q.filter(TrainingAssessment.status == status_filter)
    if role_type:
        q = q.join(TrainingTemplate).filter(TrainingTemplate.role_type == role_type)

    total = q.count()
    items = (
        q.order_by(TrainingAssessment.assessment_date.desc(), TrainingAssessment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    # Attach display fields so Pydantic's from_attributes picks them up
    for a in items:
        trainee = a.trainee
        trainer = a.trainer
        branch  = a.branch
        tmpl    = a.template
        a.trainee_name        = trainee.full_name if trainee else None
        a.trainee_employee_no = (trainee.username if trainee else None)
        a.trainer_name        = trainer.full_name if trainer else None
        a.branch_name         = (getattr(branch, "branch_name", None) or
                                 getattr(branch, "name", None)) if branch else None
        a.role_type           = (tmpl.role_type.value if tmpl and tmpl.role_type else None)
        a.template_name       = (getattr(tmpl, "name_ar", None) or
                                 getattr(tmpl, "name_en", None)) if tmpl else None
    return total, items


def create_assessment(
    db: Session,
    data: TrainingAssessmentCreate,
    created_by: int,
) -> TrainingAssessment:
    # تحقق إن القالب موجود
    tmpl = db.query(TrainingTemplate).filter(
        TrainingTemplate.id == data.template_id,
        TrainingTemplate.is_active == True,
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="القالب غير موجود أو غير فعّال")

    # تحقق إن المتدرب والمقيّم موجودين
    trainee = (
        db.query(User)
        .filter(
            User.id == data.trainee_id,
            User.status == UserStatus.active,
            User.is_deleted == False,
        )
        .first()
    )
    if not trainee:
        raise HTTPException(status_code=404, detail="المتدرب غير موجود أو غير نشط")
    trainer = (
        db.query(User)
        .filter(
            User.id == data.trainer_id,
            User.status == UserStatus.active,
            User.is_deleted == False,
        )
        .first()
    )
    if not trainer:
        raise HTTPException(status_code=404, detail="المقيّم غير موجود أو غير نشط")
    if data.trainee_id == data.trainer_id:
        raise HTTPException(
            status_code=422, detail="لا يمكن تقييم نفسك — اختر متدرباً آخر",
        )

    # منع تقييم مفتوح مكرر لنفس (المتدرب، القالب) — draft/submitted/needs_reeval
    open_states = [
        AssessmentStatus.draft,
        AssessmentStatus.submitted,
        AssessmentStatus.needs_reeval,
    ]
    existing_open = (
        db.query(TrainingAssessment)
        .filter(
            TrainingAssessment.trainee_id == data.trainee_id,
            TrainingAssessment.template_id == data.template_id,
            TrainingAssessment.status.in_(open_states),
        )
        .first()
    )
    if existing_open:
        raise HTTPException(
            status_code=409,
            detail=f"يوجد تقييم مفتوح لهذا المتدرب (رقم {existing_open.id}، حالة: {existing_open.status.value})"
                   " — أكمله أو ألغه قبل فتح تقييم جديد",
        )

    assessment = TrainingAssessment(
        template_id=data.template_id,
        trainee_id=data.trainee_id,
        trainer_id=data.trainer_id,
        branch_id=data.branch_id,
        assessment_date=data.assessment_date,
        status=AssessmentStatus.draft,
    )
    db.add(assessment)
    db.flush()

    item_objs = []
    for item_data in data.items:
        item_objs.append(TrainingAssessmentItem(
            assessment_id=assessment.id,
            item_id=item_data.item_id,
            score=item_data.score,
            notes=item_data.notes,
        ))
    db.bulk_save_objects(item_objs)
    db.commit()
    db.refresh(assessment)

    # احسب الدرجة بعد الحفظ
    loaded = _load_assessment(db, assessment.id)
    loaded.overall_score = _calc_overall_score(loaded.items)
    db.commit()
    return _load_assessment(db, assessment.id)


def submit_assessment(db: Session, assessment_id: int) -> TrainingAssessment:
    """المدرب يرفع التقييم للاعتماد"""
    assessment = _load_assessment(db, assessment_id)
    _assert_status(assessment, [AssessmentStatus.draft], "رفع التقييم")

    if not assessment.items:
        raise HTTPException(status_code=422, detail="لا يمكن رفع تقييم بدون بنود")

    assessment.overall_score = _calc_overall_score(assessment.items)
    assessment.status = AssessmentStatus.submitted
    # عند إعادة الرفع بعد رد، امسح سبب الرد السابق
    assessment.rejection_reason = None
    db.commit()
    return _load_assessment(db, assessment_id)


def approve_assessment(
    db: Session,
    assessment_id: int,
    data: TrainingAssessmentApproveRequest,
    approver_id: int,
) -> TrainingAssessment:
    """مدير العمليات أو مدير الجودة يعتمد التقييم"""
    assessment = _load_assessment(db, assessment_id)
    _assert_status(assessment, [AssessmentStatus.submitted], "اعتماد التقييم")

    # فصل الصلاحيات: المعتمِد لا يعتمد تقييماً أعدّه بنفسه
    if assessment.trainer_id == approver_id:
        raise HTTPException(
            status_code=403,
            detail="لا يمكن اعتماد تقييم أجريته بنفسك — يجب اعتماده من شخص آخر",
        )

    # حكم نهائي — يمكن override من المعتمِد، وإذا لم يُقدَّم نستنتجه من الدرجة
    verdict = data.verdict or _derive_verdict(assessment.overall_score)
    assessment.verdict = verdict
    assessment.approved_by = approver_id
    assessment.approved_at = datetime.utcnow()
    assessment.re_eval_date = data.re_eval_date

    if verdict == AssessmentVerdict.passed:
        assessment.status = AssessmentStatus.certified
    else:
        # conditional أو failed → يحتاج إعادة تقييم أو متابعة
        assessment.status = AssessmentStatus.needs_reeval

    # خطة التطوير
    if data.dev_plan:
        existing_plan = db.query(TrainingDevelopmentPlan).filter(
            TrainingDevelopmentPlan.assessment_id == assessment_id
        ).first()
        if existing_plan:
            existing_plan.strengths = data.dev_plan.strengths
            existing_plan.areas_for_improvement = data.dev_plan.areas_for_improvement
            existing_plan.required_actions = data.dev_plan.required_actions
            existing_plan.re_evaluation_date = data.dev_plan.re_evaluation_date
        else:
            plan = TrainingDevelopmentPlan(
                assessment_id=assessment_id,
                strengths=data.dev_plan.strengths,
                areas_for_improvement=data.dev_plan.areas_for_improvement,
                required_actions=data.dev_plan.required_actions,
                re_evaluation_date=data.dev_plan.re_evaluation_date,
            )
            db.add(plan)

    db.commit()
    return _load_assessment(db, assessment_id)


def reject_assessment(db: Session, assessment_id: int, reason: str) -> TrainingAssessment:
    """إرجاع التقييم للمدرب لتصحيح البيانات"""
    assessment = _load_assessment(db, assessment_id)
    _assert_status(assessment, [AssessmentStatus.submitted], "رد التقييم")

    assessment.status = AssessmentStatus.draft
    assessment.rejection_reason = reason
    db.commit()
    return _load_assessment(db, assessment_id)


def add_dev_plan(
    db: Session,
    assessment_id: int,
    data: TrainingDevelopmentPlanCreate,
) -> TrainingDevelopmentPlan:
    """أضف أو حدّث خطة التطوير"""
    assessment = db.query(TrainingAssessment).filter(
        TrainingAssessment.id == assessment_id
    ).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="التقييم غير موجود")

    existing = db.query(TrainingDevelopmentPlan).filter(
        TrainingDevelopmentPlan.assessment_id == assessment_id
    ).first()

    if existing:
        existing.strengths = data.strengths
        existing.areas_for_improvement = data.areas_for_improvement
        existing.required_actions = data.required_actions
        existing.re_evaluation_date = data.re_evaluation_date
        db.commit()
        db.refresh(existing)
        return existing
    else:
        plan = TrainingDevelopmentPlan(
            assessment_id=assessment_id,
            **data.model_dump(),
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan


# ─── Signatures ──────────────────────────────────────────────────────────────

def sign_assessment(
    db: Session,
    assessment_id: int,
    role: str,
    signature: str,
    signed_by: Optional[int] = None,
) -> TrainingAssessment:
    """توقيع التقييم بواسطة المقيّم أو المعتمِد.
    - role: 'evaluator' أو 'approver'
    - مسموح بعد الرفع (submitted) أو الاعتماد
    - فصل الصلاحيات: المقيّم يوقع كـ evaluator فقط، وأي شخص آخر كمعتمِد
    """
    if role not in ("evaluator", "approver"):
        raise HTTPException(status_code=400, detail="الدور يجب أن يكون evaluator أو approver")

    assessment = _load_assessment(db, assessment_id)
    allowed = [
        AssessmentStatus.submitted,
        AssessmentStatus.approved,
        AssessmentStatus.certified,
        AssessmentStatus.needs_reeval,
    ]
    if assessment.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"لا يمكن التوقيع في حالة '{assessment.status.value}'",
        )

    sig = (signature or "").strip()
    if len(sig) < 2:
        raise HTTPException(status_code=400, detail="التوقيع قصير جداً")
    sig = sig[:200]

    now = datetime.utcnow()
    if role == "evaluator":
        # المقيّم يوقع نفسه فقط
        if signed_by is not None and assessment.trainer_id and signed_by != assessment.trainer_id:
            raise HTTPException(status_code=403, detail="لا يمكنك التوقيع كمقيّم — لست صاحب التقييم")
        assessment.evaluator_signature = sig
        assessment.evaluator_signed_at = now
    else:
        # المعتمِد لا يوقع تقييماً أعدّه بنفسه
        if signed_by is not None and assessment.trainer_id == signed_by:
            raise HTTPException(status_code=403, detail="لا يمكن اعتماد تقييمك الخاص")
        assessment.approver_signature = sig
        assessment.approver_signed_at = now

    db.commit()
    return _load_assessment(db, assessment_id)


# ─── Analytics ───────────────────────────────────────────────────────────────

def verdict_distribution(
    db: Session,
    months: int = 6,
    template_id: Optional[int] = None,
):
    """
    توزيع verdicts الشهري — يعتمد على التقييمات المعتمدة/المُقرّرة.
    يرجع قائمة {month, verdict, count}
    """
    from datetime import date as date_type
    from collections import defaultdict

    today = date_type.today()
    first_month = today.replace(day=1)
    if months > 1:
        year = first_month.year
        month = first_month.month - (months - 1)
        while month <= 0:
            month += 12
            year -= 1
        first_month = date_type(year, month, 1)

    q = db.query(TrainingAssessment).filter(
        TrainingAssessment.status.in_([
            AssessmentStatus.approved,
            AssessmentStatus.certified,
            AssessmentStatus.needs_reeval,
        ]),
        TrainingAssessment.verdict != None,
        TrainingAssessment.assessment_date >= first_month,
    )
    if template_id is not None:
        q = q.filter(TrainingAssessment.template_id == template_id)

    rows = q.all()
    buckets = defaultdict(int)
    for a in rows:
        month_key = a.assessment_date.strftime("%Y-%m")
        verdict_key = a.verdict.value if a.verdict else "unknown"
        buckets[(month_key, verdict_key)] += 1

    return [
        {"month": month, "verdict": verdict, "count": count}
        for (month, verdict), count in sorted(buckets.items())
    ]
