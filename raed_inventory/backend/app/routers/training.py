"""
Training Assessment Router — /api/v1/training
المقيّم: مدير المنطقة (area_manager)
المعتمِد: مدير الجودة أو مدير العمليات
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_roles
from app.database import get_db
from app.models import User, AssessmentStatus, TrainingRoleType
from app.schemas import (
    TrainingAssessmentCreate,
    TrainingAssessmentOut,
    TrainingAssessmentListResponse,
    TrainingAssessmentApproveRequest,
    TrainingAssessmentRejectRequest,
    TrainingAssessmentSignRequest,
    TrainingTemplateOut,
    TrainingDevelopmentPlanCreate,
    TrainingDevelopmentPlanOut,
    VerdictDistributionPoint,
)
from app.services import training_service

router = APIRouter(prefix="/api/v1/training", tags=["Training Assessments"])

# مدير المنطقة هو من يُجري التقييم ويرفعه
_EVALUATOR_ROLES = ("area_manager", "admin", "super_admin")
# مدير الجودة أو مدير العمليات يعتمد النتيجة
_APPROVER_ROLES  = ("quality_manager", "operations_manager", "admin", "super_admin")
# كل من له علاقة بالتقييمات يقدر يشوفها
_VIEW_ROLES      = ("area_manager", "branch_manager", "quality_manager",
                    "operations_manager", "internal_auditor", "admin", "super_admin")


# ─── Templates ────────────────────────────────────────────────────────────────

@router.get("/templates", response_model=list[TrainingTemplateOut])
def list_templates(
    role_type: Optional[TrainingRoleType] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """قائمة القوالب الفعّالة — قالب لموظفي الفروع وقالب لمدراء الفروع"""
    return training_service.list_templates(db, role_type=role_type)


@router.get("/templates/{template_id}", response_model=TrainingTemplateOut)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return training_service.get_template(db, template_id)


# ─── Assessments ──────────────────────────────────────────────────────────────

@router.get("/", response_model=TrainingAssessmentListResponse)
def list_assessments(
    trainee_id: Optional[int] = None,
    evaluator_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    status: Optional[AssessmentStatus] = None,
    role_type: Optional[TrainingRoleType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    # مدير المنطقة يشوف بس تقييماته هو
    if "area_manager" in user_roles and "quality_manager" not in user_roles and "admin" not in user_roles:
        evaluator_id = current_user.id

    total, items = training_service.list_assessments(
        db,
        trainee_id=trainee_id,
        trainer_id=evaluator_id,   # trainer_id في الـ model = المقيّم
        branch_id=branch_id,
        status_filter=status,
        role_type=role_type,
        page=page,
        page_size=page_size,
    )
    return TrainingAssessmentListResponse(
        total=total, page=page, page_size=page_size, items=items
    )


@router.post("/", response_model=TrainingAssessmentOut, status_code=201)
def create_assessment(
    data: TrainingAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_EVALUATOR_ROLES)),
):
    """مدير المنطقة ينشئ تقييماً لموظف فرع أو مدير فرع"""
    return training_service.create_assessment(db, data, created_by=current_user.id)


@router.get("/{assessment_id}", response_model=TrainingAssessmentOut)
def get_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    return training_service.get_assessment(db, assessment_id)


# ─── Workflow Actions ─────────────────────────────────────────────────────────

@router.post("/{assessment_id}/submit", response_model=TrainingAssessmentOut)
def submit_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_EVALUATOR_ROLES)),
):
    """مدير المنطقة يرفع التقييم للاعتماد"""
    return training_service.submit_assessment(db, assessment_id)


@router.post("/{assessment_id}/approve", response_model=TrainingAssessmentOut)
def approve_assessment(
    assessment_id: int,
    data: TrainingAssessmentApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_APPROVER_ROLES)),
):
    """مدير الجودة / مدير العمليات يعتمد التقييم مع الحكم وخطة التطوير"""
    return training_service.approve_assessment(
        db, assessment_id, data, approver_id=current_user.id
    )


@router.post("/{assessment_id}/reject", response_model=TrainingAssessmentOut)
def reject_assessment(
    assessment_id: int,
    data: TrainingAssessmentRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_APPROVER_ROLES)),
):
    """رد التقييم لمدير المنطقة لتصحيحه"""
    return training_service.reject_assessment(db, assessment_id, reason=data.reason)


# ─── Development Plan ─────────────────────────────────────────────────────────

@router.post("/{assessment_id}/dev-plan", response_model=TrainingDevelopmentPlanOut)
def upsert_dev_plan(
    assessment_id: int,
    data: TrainingDevelopmentPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_APPROVER_ROLES)),
):
    """إضافة أو تحديث خطة التطوير"""
    return training_service.add_dev_plan(db, assessment_id, data)


# ─── Signatures ──────────────────────────────────────────────────────────────

@router.post("/{assessment_id}/sign", response_model=TrainingAssessmentOut)
def sign_assessment(
    assessment_id: int,
    data: TrainingAssessmentSignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """توقيع التقييم (evaluator أو approver)"""
    user_roles = [ur.role.name.value for ur in current_user.user_roles]
    if data.role == "evaluator" and not any(r in user_roles for r in _EVALUATOR_ROLES):
        raise HTTPException(status_code=403, detail="دورك لا يسمح بالتوقيع كمقيّم")
    if data.role == "approver" and not any(r in user_roles for r in _APPROVER_ROLES):
        raise HTTPException(status_code=403, detail="دورك لا يسمح بالتوقيع كمعتمِد")
    return training_service.sign_assessment(
        db,
        assessment_id=assessment_id,
        role=data.role,
        signature=data.signature,
        signed_by=current_user.id,
    )


# ─── Analytics ───────────────────────────────────────────────────────────────

@router.get("/analytics/verdict-distribution", response_model=list[VerdictDistributionPoint])
def verdict_distribution(
    months: int = Query(6, ge=1, le=24),
    template_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """توزيع أحكام التقييم شهرياً (passed/conditional/failed)"""
    return training_service.verdict_distribution(db, months=months, template_id=template_id)
