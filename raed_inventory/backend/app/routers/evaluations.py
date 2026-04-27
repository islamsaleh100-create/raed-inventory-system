import json
from datetime import date, datetime
from decimal import Decimal
from html import escape
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.auth import can_access_branch, get_user_roles, require_roles
from app.core.errors import AppError
from app.database import get_db
from app.models import (
    AreaManagerAssignment,
    Brand,
    Branch,
    BranchBrand,
    Evaluation,
    EvaluationActionPlan,
    EvaluationActionPlanStatus,
    EvaluationAnswer,
    EvaluationAttachment,
    EvaluationAuditLog,
    EvaluationStatus,
    EvaluationTargetMode,
    EvaluationTemplate,
    EvaluationTemplateQuestion,
    EvaluationTemplateSection,
    EvaluationTemplateVersion,
    EvaluationTemplateVersionStatus,
    EvaluationType,
    User,
)
from app.schemas import (
    EvaluationCreate,
    EvaluationActionPlanCreate,
    EvaluationActionPlanOut,
    EvaluationActionPlanUpdate,
    EvaluationAttachmentOut,
    EvaluationOut,
    EvaluationTemplateCreate,
    EvaluationTemplateOut,
    EvaluationTemplateUpdate,
    EvaluationTemplateVersionCreate,
    EvaluationTemplateVersionOut,
    EvaluationTemplateVersionUpdate,
    EvaluationTransitionPayload,
    EvaluationUpdate,
)
from app.services import evaluation_scoring_service, evaluation_storage_service


router = APIRouter(prefix="/api/evaluations", tags=["Evaluations"])

TEMPLATE_ROLES = ("quality_manager", "admin", "super_admin")
EVALUATION_CREATE_ROLES = ("evaluator", "quality_manager", "area_manager", "admin", "super_admin")
EVALUATION_VIEW_ROLES = ("evaluator", "quality_manager", "area_manager", "branch_manager", "hr_manager", "admin", "super_admin")
REVIEW_ROLES = ("quality_manager", "area_manager", "admin", "super_admin")
CLOSE_ROLES = ("quality_manager", "admin", "super_admin")
ACTION_PLAN_ROLES = ("quality_manager", "area_manager", "admin", "super_admin")
ATTACHMENT_ROLES = ("evaluator", "quality_manager", "area_manager", "admin", "super_admin")
REPORT_ROLES = ("quality_manager", "area_manager", "branch_manager", "hr_manager", "admin", "super_admin")


def _roles(user: User) -> list[str]:
    return get_user_roles(user)


def _broad(user: User) -> bool:
    return any(r in _roles(user) for r in ("admin", "super_admin", "quality_manager"))


def _audit(
    db: Session,
    *,
    user: User,
    action: str,
    evaluation_id: int | None = None,
    template_id: int | None = None,
    template_version_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    notes: str | None = None,
) -> None:
    db.add(EvaluationAuditLog(
        evaluation_id=evaluation_id,
        template_id=template_id,
        template_version_id=template_version_id,
        user_id=user.id,
        action=action,
        old_value=json.dumps(old_value, default=str) if old_value is not None else None,
        new_value=json.dumps(new_value, default=str) if new_value is not None else None,
        notes=notes,
    ))


def _ensure_brand(db: Session, brand_id: int) -> None:
    if not db.query(Brand).filter(Brand.id == brand_id).first():
        raise AppError(status_code=404, error_code="evaluations.brand_not_found", message="Brand not found")


def _load_user(db: Session, user_id: int) -> User:
    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise AppError(status_code=404, error_code="evaluations.user_not_found", message="User not found")
    return row


def _load_template(db: Session, template_id: int) -> EvaluationTemplate:
    row = db.query(EvaluationTemplate).options(joinedload(EvaluationTemplate.versions)).filter(EvaluationTemplate.id == template_id).first()
    if not row:
        raise AppError(status_code=404, error_code="evaluations.template_not_found", message="Template not found")
    return row


def _load_version(db: Session, version_id: int) -> EvaluationTemplateVersion:
    row = db.query(EvaluationTemplateVersion).options(
        joinedload(EvaluationTemplateVersion.template),
        joinedload(EvaluationTemplateVersion.sections).joinedload(EvaluationTemplateSection.questions),
    ).filter(EvaluationTemplateVersion.id == version_id).first()
    if not row:
        raise AppError(status_code=404, error_code="evaluations.template_version_not_found", message="Template version not found")
    return row


def _load_evaluation(db: Session, evaluation_id: int) -> Evaluation:
    row = db.query(Evaluation).options(
        joinedload(Evaluation.answers).joinedload(EvaluationAnswer.question),
        joinedload(Evaluation.answers).joinedload(EvaluationAnswer.attachments),
        joinedload(Evaluation.template),
        joinedload(Evaluation.template_version),
        joinedload(Evaluation.brand),
        joinedload(Evaluation.branch),
        joinedload(Evaluation.employee),
        joinedload(Evaluation.evaluator),
    ).filter(Evaluation.id == evaluation_id).first()
    if not row:
        raise AppError(status_code=404, error_code="evaluations.not_found", message="Evaluation not found")
    return row


def _require_eval_access(db: Session, user: User, row: Evaluation) -> None:
    roles = _roles(user)
    if _broad(user):
        return
    if "evaluator" in roles and row.evaluator_id == user.id:
        return
    if "hr_manager" in roles and row.employee_id is not None:
        return
    if "branch_manager" in roles and row.branch_id and user.branch_id == row.branch_id:
        return
    if "area_manager" in roles and row.branch_id and can_access_branch(user, row.branch_id, db=db):
        return
    raise AppError(status_code=403, error_code="evaluations.access_denied", message="Access denied")


def _apply_scope(db: Session, user: User, q):
    roles = _roles(user)
    if _broad(user):
        return q
    if "hr_manager" in roles:
        return q.filter(Evaluation.employee_id.isnot(None))
    if "branch_manager" in roles:
        return q.filter(Evaluation.branch_id == user.branch_id)
    if "evaluator" in roles:
        return q.filter(Evaluation.evaluator_id == user.id)
    if "area_manager" in roles:
        assignments = db.query(AreaManagerAssignment).filter(
            AreaManagerAssignment.user_id == user.id,
            AreaManagerAssignment.active == True,
        ).all()
        brand_ids = [a.brand_id for a in assignments]
        if not brand_ids:
            return q.filter(Evaluation.id == -1)
        branch_ids = [b.id for b in db.query(Branch).all() if can_access_branch(user, b.id, db=db)]
        return q.filter(Evaluation.brand_id.in_(brand_ids), Evaluation.branch_id.in_(branch_ids))
    return q.filter(Evaluation.id == -1)


def _replace_version_structure(db: Session, version: EvaluationTemplateVersion, payload_sections) -> None:
    version.sections.clear()
    db.flush()
    for section_data in payload_sections:
        section = EvaluationTemplateSection(
            template_version_id=version.id,
            name=section_data.name,
            weight_percent=section_data.weight_percent,
            display_order=section_data.display_order,
            active=section_data.active,
        )
        db.add(section)
        db.flush()
        for question_data in section_data.questions:
            db.add(EvaluationTemplateQuestion(
                section_id=section.id,
                question_text_ar=question_data.question_text_ar,
                question_text_en=question_data.question_text_en,
                max_score=question_data.max_score,
                allow_na=question_data.allow_na,
                requires_note_if_low_score=question_data.requires_note_if_low_score,
                low_score_threshold=question_data.low_score_threshold,
                requires_photo=question_data.requires_photo,
                display_order=question_data.display_order,
                active=question_data.active,
            ))


def _validate_publish(version: EvaluationTemplateVersion) -> None:
    active_sections = [s for s in version.sections if s.active]
    if not active_sections:
        raise AppError(status_code=400, error_code="evaluations.publish_no_sections", message="Template version must have active sections")
    for section in active_sections:
        if not [q for q in section.questions if q.active]:
            raise AppError(
                status_code=400,
                error_code="evaluations.publish_section_without_questions",
                message="Each active section must have at least one active question",
                detail={"section_id": section.id},
            )
    weights = [Decimal(str(s.weight_percent)) for s in active_sections if s.weight_percent is not None]
    if weights:
        if len(weights) != len(active_sections) or sum(weights, Decimal("0")) != Decimal("100"):
            raise AppError(status_code=400, error_code="evaluations.publish_weights_invalid", message="Active section weights must total exactly 100")


def _validate_target(target_mode: EvaluationTargetMode, branch_id: int | None, employee_id: int | None) -> None:
    if target_mode == EvaluationTargetMode.BRANCH and (branch_id is None or employee_id is not None):
        raise AppError(status_code=400, error_code="evaluations.invalid_branch_target", message="BRANCH target requires branch_id and no employee_id")
    if target_mode == EvaluationTargetMode.EMPLOYEE and (branch_id is None or employee_id is None):
        raise AppError(status_code=400, error_code="evaluations.invalid_employee_target", message="EMPLOYEE target requires branch_id and employee_id")
    if target_mode == EvaluationTargetMode.NONE and employee_id is not None:
        raise AppError(status_code=400, error_code="evaluations.invalid_none_target", message="NONE target cannot have employee_id")


def _validate_create_scope(
    db: Session,
    current_user: User,
    *,
    brand_id: int,
    branch_id: int | None,
    employee_id: int | None,
) -> None:
    if branch_id is not None:
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise AppError(status_code=404, error_code="evaluations.branch_not_found", message="Branch not found")
        brand_link = db.query(BranchBrand).filter(
            BranchBrand.branch_id == branch_id,
            BranchBrand.brand_id == brand_id,
        ).first()
        if not brand_link:
            raise AppError(
                status_code=400,
                error_code="evaluations.branch_brand_mismatch",
                message="Branch does not belong to evaluation brand",
                detail={"branch_id": branch_id, "brand_id": brand_id},
            )

    if employee_id is not None:
        employee = _load_user(db, employee_id)
        if branch_id is None or employee.branch_id != branch_id:
            raise AppError(
                status_code=400,
                error_code="evaluations.employee_branch_mismatch",
                message="Employee must belong to the selected branch",
                detail={"employee_id": employee_id, "branch_id": branch_id},
            )

    roles = _roles(current_user)
    if "area_manager" in roles and not _broad(current_user):
        if branch_id is None or not can_access_branch(current_user, branch_id, db=db):
            raise AppError(status_code=403, error_code="evaluations.create_scope_denied", message="Area manager cannot create evaluation for this branch")
        assignment = db.query(AreaManagerAssignment).filter(
            AreaManagerAssignment.user_id == current_user.id,
            AreaManagerAssignment.brand_id == brand_id,
            AreaManagerAssignment.active == True,
        ).first()
        if not assignment:
            raise AppError(status_code=403, error_code="evaluations.create_scope_denied", message="Area manager cannot create evaluation for this brand")


def _validate_answer(answer: EvaluationAnswer) -> None:
    question = answer.question
    if answer.is_na:
        if not question.allow_na:
            raise AppError(status_code=400, error_code="evaluations.na_not_allowed", message="N/A is not allowed for this question")
        if answer.score is not None:
            raise AppError(status_code=400, error_code="evaluations.na_score_invalid", message="N/A answers cannot have score")
        return
    if answer.score is None:
        return
    score = Decimal(str(answer.score))
    max_score = Decimal(str(answer.max_score_snapshot))
    if score < Decimal("1") or score > max_score:
        raise AppError(status_code=400, error_code="evaluations.score_invalid", message="Score must be between 1 and question max score")
    if question.requires_note_if_low_score and score <= Decimal(str(question.low_score_threshold)) and not (answer.note or "").strip():
        raise AppError(status_code=400, error_code="evaluations.low_score_note_required", message="Low score requires note", detail={"answer_id": answer.id})


def _answer_requires_photo_missing(answer: EvaluationAnswer) -> bool:
    return bool(answer.question and answer.question.requires_photo and not answer.attachments)


def _apply_date_filters(q, date_from: date | None, date_to: date | None):
    if date_from:
        q = q.filter(Evaluation.evaluation_date >= date_from)
    if date_to:
        q = q.filter(Evaluation.evaluation_date <= date_to)
    return q


def _is_weak_section(name: str, keywords: tuple[str, ...]) -> bool:
    lowered = (name or "").lower()
    return any(k in lowered for k in keywords)


@router.get("/templates", response_model=list[EvaluationTemplateOut])
def list_templates(
    brand_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*EVALUATION_VIEW_ROLES)),
):
    q = db.query(EvaluationTemplate)
    if brand_id:
        q = q.filter(EvaluationTemplate.brand_id == brand_id)
    return q.order_by(EvaluationTemplate.name).all()


@router.post("/templates", response_model=EvaluationTemplateOut, status_code=201)
def create_template(payload: EvaluationTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*TEMPLATE_ROLES))):
    _ensure_brand(db, payload.brand_id)
    row = EvaluationTemplate(**payload.model_dump(), created_by=current_user.id)
    db.add(row)
    db.flush()
    _audit(db, user=current_user, action="template_created", template_id=row.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(row)
    return row


@router.get("/templates/{template_id}", response_model=EvaluationTemplateOut)
def get_template(template_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*EVALUATION_VIEW_ROLES))):
    return _load_template(db, template_id)


@router.put("/templates/{template_id}", response_model=EvaluationTemplateOut)
def update_template(template_id: int, payload: EvaluationTemplateUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*TEMPLATE_ROLES))):
    row = _load_template(db, template_id)
    old = {"name": row.name, "active": row.active}
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="template_updated", template_id=row.id, old_value=old, new_value=payload.model_dump(exclude_unset=True))
    db.commit()
    return _load_template(db, template_id)


@router.post("/templates/{template_id}/duplicate", response_model=EvaluationTemplateOut, status_code=201)
def duplicate_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*TEMPLATE_ROLES))):
    src = _load_template(db, template_id)
    copy = EvaluationTemplate(
        name=f"{src.name} Copy",
        brand_id=src.brand_id,
        evaluation_type=src.evaluation_type,
        target_mode=src.target_mode,
        target_role=src.target_role,
        active=src.active,
        created_by=current_user.id,
    )
    db.add(copy)
    db.flush()
    source_version = sorted(src.versions, key=lambda v: v.version_no)[-1] if src.versions else None
    if source_version:
        loaded = _load_version(db, source_version.id)
        version = EvaluationTemplateVersion(template_id=copy.id, version_no=1, status=EvaluationTemplateVersionStatus.DRAFT, created_by=current_user.id, notes=loaded.notes)
        db.add(version)
        db.flush()
        for section in loaded.sections:
            new_section = EvaluationTemplateSection(template_version_id=version.id, name=section.name, weight_percent=section.weight_percent, display_order=section.display_order, active=section.active)
            db.add(new_section)
            db.flush()
            for q in section.questions:
                db.add(EvaluationTemplateQuestion(section_id=new_section.id, question_text_ar=q.question_text_ar, question_text_en=q.question_text_en, max_score=q.max_score, allow_na=q.allow_na, requires_note_if_low_score=q.requires_note_if_low_score, low_score_threshold=q.low_score_threshold, requires_photo=q.requires_photo, display_order=q.display_order, active=q.active))
    _audit(db, user=current_user, action="template_duplicated", template_id=copy.id, old_value={"source_template_id": src.id})
    db.commit()
    return _load_template(db, copy.id)


@router.post("/templates/{template_id}/activate", response_model=EvaluationTemplateOut)
def activate_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*TEMPLATE_ROLES))):
    row = _load_template(db, template_id)
    row.active = True
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="template_activated", template_id=row.id)
    db.commit()
    return _load_template(db, template_id)


@router.post("/templates/{template_id}/deactivate", response_model=EvaluationTemplateOut)
def deactivate_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*TEMPLATE_ROLES))):
    row = _load_template(db, template_id)
    row.active = False
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="template_deactivated", template_id=row.id)
    db.commit()
    return _load_template(db, template_id)


@router.get("/templates/{template_id}/versions", response_model=list[EvaluationTemplateVersionOut])
def list_versions(template_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*EVALUATION_VIEW_ROLES))):
    _load_template(db, template_id)
    return db.query(EvaluationTemplateVersion).options(joinedload(EvaluationTemplateVersion.sections).joinedload(EvaluationTemplateSection.questions)).filter(EvaluationTemplateVersion.template_id == template_id).order_by(EvaluationTemplateVersion.version_no).all()


@router.post("/templates/{template_id}/versions", response_model=EvaluationTemplateVersionOut, status_code=201)
def create_version(template_id: int, payload: EvaluationTemplateVersionCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*TEMPLATE_ROLES))):
    _load_template(db, template_id)
    max_version = db.query(EvaluationTemplateVersion).filter(EvaluationTemplateVersion.template_id == template_id).order_by(EvaluationTemplateVersion.version_no.desc()).first()
    row = EvaluationTemplateVersion(template_id=template_id, version_no=(max_version.version_no + 1 if max_version else 1), status=EvaluationTemplateVersionStatus.DRAFT, created_by=current_user.id, notes=payload.notes)
    db.add(row)
    db.flush()
    _replace_version_structure(db, row, payload.sections)
    _audit(db, user=current_user, action="template_version_created", template_id=template_id, template_version_id=row.id)
    db.commit()
    return _load_version(db, row.id)


@router.get("/template-versions/{version_id}", response_model=EvaluationTemplateVersionOut)
def get_version(version_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(*EVALUATION_VIEW_ROLES))):
    return _load_version(db, version_id)


@router.put("/template-versions/{version_id}", response_model=EvaluationTemplateVersionOut)
def update_version(version_id: int, payload: EvaluationTemplateVersionUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*TEMPLATE_ROLES))):
    row = _load_version(db, version_id)
    if row.status != EvaluationTemplateVersionStatus.DRAFT:
        raise AppError(status_code=400, error_code="evaluations.version_not_editable", message="Only draft versions can be edited")
    if payload.notes is not None:
        row.notes = payload.notes
    if payload.sections is not None:
        _replace_version_structure(db, row, payload.sections)
    _audit(db, user=current_user, action="template_version_updated", template_id=row.template_id, template_version_id=row.id)
    db.commit()
    return _load_version(db, version_id)


@router.post("/template-versions/{version_id}/publish", response_model=EvaluationTemplateVersionOut)
def publish_version(version_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*TEMPLATE_ROLES))):
    row = _load_version(db, version_id)
    _validate_publish(row)
    row.status = EvaluationTemplateVersionStatus.PUBLISHED
    row.published_at = datetime.utcnow()
    _audit(db, user=current_user, action="template_version_published", template_id=row.template_id, template_version_id=row.id)
    db.commit()
    return _load_version(db, version_id)


@router.post("/template-versions/{version_id}/archive", response_model=EvaluationTemplateVersionOut)
def archive_version(version_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*TEMPLATE_ROLES))):
    row = _load_version(db, version_id)
    row.status = EvaluationTemplateVersionStatus.ARCHIVED
    _audit(db, user=current_user, action="template_version_archived", template_id=row.template_id, template_version_id=row.id)
    db.commit()
    return _load_version(db, version_id)


@router.get("/reports/branch", response_model=list[EvaluationOut])
def branch_history(
    branch_id: int,
    brand_id: Optional[int] = None,
    template_id: Optional[int] = None,
    evaluation_type: Optional[EvaluationType] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*EVALUATION_VIEW_ROLES)),
):
    q = db.query(Evaluation).options(joinedload(Evaluation.answers)).filter(Evaluation.branch_id == branch_id)
    if brand_id:
        q = q.filter(Evaluation.brand_id == brand_id)
    if template_id:
        q = q.filter(Evaluation.template_id == template_id)
    if evaluation_type:
        q = q.filter(Evaluation.evaluation_type == evaluation_type)
    q = _apply_date_filters(q, date_from, date_to)
    q = _apply_scope(db, current_user, q)
    return q.order_by(Evaluation.evaluation_date.desc()).all()


@router.get("/reports/employee", response_model=list[EvaluationOut])
def employee_history(
    employee_id: int,
    branch_id: Optional[int] = None,
    role: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*EVALUATION_VIEW_ROLES)),
):
    q = db.query(Evaluation).options(joinedload(Evaluation.answers)).filter(Evaluation.employee_id == employee_id)
    if branch_id:
        q = q.filter(Evaluation.branch_id == branch_id)
    if role:
        q = q.filter(Evaluation.evaluated_role == role)
    q = _apply_date_filters(q, date_from, date_to)
    q = _apply_scope(db, current_user, q)
    return q.order_by(Evaluation.evaluation_date.desc()).all()


@router.get("/reports/action-plans", response_model=list[EvaluationActionPlanOut])
def action_plans_report(
    branch_id: Optional[int] = None,
    responsible_user_id: Optional[int] = None,
    status: Optional[str] = None,
    overdue_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    q = db.query(EvaluationActionPlan).join(Evaluation, Evaluation.id == EvaluationActionPlan.evaluation_id)
    q = _apply_scope(db, current_user, q)
    if branch_id:
        q = q.filter(EvaluationActionPlan.branch_id == branch_id)
    if responsible_user_id:
        q = q.filter(EvaluationActionPlan.responsible_user_id == responsible_user_id)
    if status:
        q = q.filter(EvaluationActionPlan.status == status)
    if overdue_only:
        q = q.filter(
            EvaluationActionPlan.due_date < date.today(),
            EvaluationActionPlan.status.notin_([EvaluationActionPlanStatus.CLOSED, EvaluationActionPlanStatus.CANCELLED]),
        )
    return q.order_by(EvaluationActionPlan.due_date.asc()).all()


@router.get("/reports/dashboard")
def evaluation_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    scoped = _apply_scope(db, current_user, db.query(Evaluation)).subquery()
    base = db.query(Evaluation).join(scoped, Evaluation.id == scoped.c.id)
    avg_brand = (
        db.query(Brand.name.label("brand"), func.avg(Evaluation.total_percentage).label("avg_score"))
        .join(scoped, Evaluation.id == scoped.c.id)
        .join(Brand, Brand.id == Evaluation.brand_id)
        .filter(Evaluation.total_percentage.isnot(None))
        .group_by(Brand.name)
        .all()
    )
    avg_branch = (
        db.query(Branch.branch_name.label("branch"), func.avg(Evaluation.total_percentage).label("avg_score"))
        .join(scoped, Evaluation.id == scoped.c.id)
        .join(Branch, Branch.id == Evaluation.branch_id)
        .filter(Evaluation.total_percentage.isnot(None))
        .group_by(Branch.branch_name)
        .all()
    )
    avg_role = (
        db.query(Evaluation.evaluated_role.label("role"), func.avg(Evaluation.total_percentage).label("avg_score"))
        .join(scoped, Evaluation.id == scoped.c.id)
        .filter(Evaluation.total_percentage.isnot(None))
        .group_by(Evaluation.evaluated_role)
        .all()
    )
    weak_rows = (
        db.query(EvaluationAnswer.question_text_snapshot, func.count(EvaluationAnswer.id).label("count"))
        .join(Evaluation, Evaluation.id == EvaluationAnswer.evaluation_id)
        .join(scoped, Evaluation.id == scoped.c.id)
        .filter(EvaluationAnswer.score.isnot(None), EvaluationAnswer.score <= 2)
        .group_by(EvaluationAnswer.question_text_snapshot)
        .having(func.count(EvaluationAnswer.id) >= 3)
        .all()
    )
    pending_plans = action_plans_report(db=db, current_user=current_user)
    overdue_plans = action_plans_report(overdue_only=True, db=db, current_user=current_user)
    this_month_start = date.today().replace(day=1)
    section_rows = (
        db.query(Brand.name, EvaluationAnswer.section_name_snapshot, func.avg((EvaluationAnswer.score / EvaluationAnswer.max_score_snapshot) * 100).label("avg_score"))
        .join(Evaluation, Evaluation.id == EvaluationAnswer.evaluation_id)
        .join(scoped, Evaluation.id == scoped.c.id)
        .join(Brand, Brand.id == Evaluation.brand_id)
        .filter(EvaluationAnswer.score.isnot(None), EvaluationAnswer.is_na == False)
        .group_by(Brand.name, EvaluationAnswer.section_name_snapshot)
        .all()
    )
    branch_below = base.filter(Evaluation.target_mode == EvaluationTargetMode.BRANCH, Evaluation.total_percentage < 60).all()
    employee_below = base.filter(Evaluation.target_mode == EvaluationTargetMode.EMPLOYEE, Evaluation.total_percentage < 70).all()
    hygiene_flags = [
        {"section": row.section_name_snapshot, "brand": row.name, "avg_score": float(row.avg_score)}
        for row in section_rows
        if row.avg_score is not None and row.avg_score < 70 and _is_weak_section(row.section_name_snapshot, ("hygiene", "cleanliness", "نظافة"))
    ]
    food_safety_flags = [
        {"section": row.section_name_snapshot, "brand": row.name, "avg_score": float(row.avg_score)}
        for row in section_rows
        if row.avg_score is not None and row.avg_score < 70 and _is_weak_section(row.section_name_snapshot, ("food safety", "safety", "سلامة"))
    ]
    return {
        "average_score_by_brand": [{"brand": r.brand, "avg_score": float(r.avg_score)} for r in avg_brand],
        "average_score_by_branch": [{"branch": r.branch, "avg_score": float(r.avg_score)} for r in avg_branch],
        "average_score_by_role": [{"role": r.role, "avg_score": float(r.avg_score)} for r in avg_role],
        "lowest_scoring_branches": [{"id": e.id, "branch_id": e.branch_id, "score": float(e.total_percentage or 0)} for e in base.filter(Evaluation.branch_id.isnot(None)).order_by(Evaluation.total_percentage.asc()).limit(10).all()],
        "lowest_scoring_employees": [{"id": e.id, "employee_id": e.employee_id, "score": float(e.total_percentage or 0)} for e in base.filter(Evaluation.employee_id.isnot(None)).order_by(Evaluation.total_percentage.asc()).limit(10).all()],
        "repeated_weak_points": [{"question": r.question_text_snapshot, "count": r.count} for r in weak_rows],
        "pending_action_plans": len([p for p in pending_plans if p.status not in (EvaluationActionPlanStatus.CLOSED, EvaluationActionPlanStatus.CANCELLED)]),
        "overdue_action_plans": len(overdue_plans),
        "evaluations_this_month": base.filter(Evaluation.evaluation_date >= this_month_start).count(),
        "branch_score_trend": [{"date": e.evaluation_date.isoformat(), "branch_id": e.branch_id, "score": float(e.total_percentage or 0)} for e in base.filter(Evaluation.branch_id.isnot(None)).order_by(Evaluation.evaluation_date.asc()).all()],
        "employee_score_trend": [{"date": e.evaluation_date.isoformat(), "employee_id": e.employee_id, "score": float(e.total_percentage or 0)} for e in base.filter(Evaluation.employee_id.isnot(None)).order_by(Evaluation.evaluation_date.asc()).all()],
        "section_performance_by_brand": [{"brand": r.name, "section": r.section_name_snapshot, "avg_score": float(r.avg_score)} for r in section_rows],
        "flags": {
            "branch_below_60": [{"evaluation_id": e.id, "branch_id": e.branch_id, "score": float(e.total_percentage or 0)} for e in branch_below],
            "employee_below_70": [{"evaluation_id": e.id, "employee_id": e.employee_id, "score": float(e.total_percentage or 0)} for e in employee_below],
            "repeated_low_score": [{"question": r.question_text_snapshot, "count": r.count} for r in weak_rows],
            "overdue_action_plan": [{"id": p.id, "branch_id": p.branch_id, "due_date": p.due_date.isoformat()} for p in overdue_plans],
            "hygiene_below_threshold": hygiene_flags,
            "food_safety_below_threshold": food_safety_flags,
        },
    }


@router.get("/reports/export/excel")
def export_evaluations_excel(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    rows = _apply_scope(db, current_user, db.query(Evaluation).options(joinedload(Evaluation.brand), joinedload(Evaluation.branch), joinedload(Evaluation.employee), joinedload(Evaluation.evaluator), joinedload(Evaluation.template))).order_by(Evaluation.evaluation_date.desc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Evaluations"
    ws.append(["evaluation id", "date", "brand", "branch", "employee", "evaluator", "template", "total_percentage", "final_rating", "status", "action_required_flag"])
    for e in rows:
        ws.append([
            e.id,
            e.evaluation_date.isoformat(),
            e.brand.name if e.brand else e.brand_id,
            e.branch.branch_name if e.branch else None,
            e.employee.full_name if e.employee else None,
            e.evaluator.full_name if e.evaluator else e.evaluator_id,
            e.template.name if e.template else e.template_id,
            float(e.total_percentage) if e.total_percentage is not None else None,
            e.final_rating.value if e.final_rating else None,
            e.status.value,
            e.action_required_flag,
        ])
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=evaluations_summary.xlsx"},
    )


@router.get("/action-plans", response_model=list[EvaluationActionPlanOut])
def list_action_plans(
    branch_id: Optional[int] = None,
    responsible_user_id: Optional[int] = None,
    status: Optional[str] = None,
    overdue_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    return action_plans_report(
        branch_id=branch_id,
        responsible_user_id=responsible_user_id,
        status=status,
        overdue_only=overdue_only,
        db=db,
        current_user=current_user,
    )


def _load_action_plan(db: Session, plan_id: int) -> EvaluationActionPlan:
    row = db.query(EvaluationActionPlan).join(Evaluation, Evaluation.id == EvaluationActionPlan.evaluation_id).filter(EvaluationActionPlan.id == plan_id).first()
    if not row:
        raise AppError(status_code=404, error_code="evaluations.action_plan_not_found", message="Action plan not found")
    return row


@router.put("/action-plans/{plan_id}", response_model=EvaluationActionPlanOut)
def update_action_plan(
    plan_id: int,
    payload: EvaluationActionPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ACTION_PLAN_ROLES)),
):
    row = _load_action_plan(db, plan_id)
    evaluation = _load_evaluation(db, row.evaluation_id)
    _require_eval_access(db, current_user, evaluation)
    if row.status in (EvaluationActionPlanStatus.CLOSED, EvaluationActionPlanStatus.CANCELLED) and not _broad(current_user):
        raise AppError(status_code=400, error_code="evaluations.action_plan_not_editable", message="Closed or cancelled action plans are not editable")
    if payload.status is not None:
        raise AppError(
            status_code=400,
            error_code="evaluations.action_plan_status_not_editable",
            message="Action plan status must be changed via dedicated transition endpoints",
        )
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="action_plan_updated", evaluation_id=row.evaluation_id, new_value=payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(row)
    return row


@router.post("/action-plans/{plan_id}/close", response_model=EvaluationActionPlanOut)
def close_action_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ACTION_PLAN_ROLES)),
):
    row = _load_action_plan(db, plan_id)
    evaluation = _load_evaluation(db, row.evaluation_id)
    _require_eval_access(db, current_user, evaluation)
    row.status = EvaluationActionPlanStatus.CLOSED
    row.closed_at = datetime.utcnow()
    row.closed_by = current_user.id
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="action_plan_closed", evaluation_id=row.evaluation_id, new_value={"action_plan_id": row.id})
    db.commit()
    db.refresh(row)
    return row


@router.post("/action-plans/{plan_id}/cancel", response_model=EvaluationActionPlanOut)
def cancel_action_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("quality_manager", "admin", "super_admin")),
):
    row = _load_action_plan(db, plan_id)
    row.status = EvaluationActionPlanStatus.CANCELLED
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="action_plan_cancelled", evaluation_id=row.evaluation_id, new_value={"action_plan_id": row.id})
    db.commit()
    db.refresh(row)
    return row


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ATTACHMENT_ROLES)),
):
    att = db.query(EvaluationAttachment).filter(EvaluationAttachment.id == attachment_id).first()
    if not att:
        raise AppError(status_code=404, error_code="evaluations.attachment_not_found", message="Attachment not found")
    row = _load_evaluation(db, att.evaluation_id)
    _require_eval_access(db, current_user, row)
    if row.status != EvaluationStatus.DRAFT and not _broad(current_user):
        raise AppError(status_code=400, error_code="evaluations.attachment_delete_not_allowed", message="Attachment cannot be deleted now")
    file_path = att.file_path
    db.delete(att)
    _audit(db, user=current_user, action="attachment_deleted", evaluation_id=row.id, old_value={"attachment_id": attachment_id})
    db.commit()
    evaluation_storage_service.delete_attachment(file_path)
    return None


@router.get("", response_model=list[EvaluationOut])
def list_evaluations(db: Session = Depends(get_db), current_user: User = Depends(require_roles(*EVALUATION_VIEW_ROLES))):
    q = db.query(Evaluation).options(joinedload(Evaluation.answers))
    return _apply_scope(db, current_user, q).order_by(Evaluation.created_at.desc()).all()


@router.post("", response_model=EvaluationOut, status_code=201)
def create_evaluation(payload: EvaluationCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*EVALUATION_CREATE_ROLES))):
    version = _load_version(db, payload.template_version_id)
    if version.status != EvaluationTemplateVersionStatus.PUBLISHED or not version.template.active:
        raise AppError(status_code=400, error_code="evaluations.version_not_published", message="Only published active template versions can be used")
    brand_id = payload.brand_id if payload.brand_id is not None else version.template.brand_id
    if brand_id != version.template.brand_id:
        raise AppError(status_code=400, error_code="evaluations.brand_mismatch", message="Evaluation brand must match template brand")
    _validate_target(version.template.target_mode, payload.branch_id, payload.employee_id)
    _validate_create_scope(
        db,
        current_user,
        brand_id=brand_id,
        branch_id=payload.branch_id,
        employee_id=payload.employee_id,
    )
    evaluator_id = current_user.id
    if payload.evaluator_id is not None:
        if not _broad(current_user):
            raise AppError(
                status_code=403,
                error_code="evaluations.evaluator_override_denied",
                message="Only admin or quality manager can create evaluation on behalf of another evaluator",
            )
        _load_user(db, payload.evaluator_id)
        evaluator_id = payload.evaluator_id
    row = Evaluation(
        template_id=version.template_id,
        template_version_id=version.id,
        brand_id=brand_id,
        branch_id=payload.branch_id,
        employee_id=payload.employee_id,
        evaluation_type=version.template.evaluation_type,
        target_mode=version.template.target_mode,
        evaluated_role=version.template.target_role,
        evaluator_id=evaluator_id,
        evaluation_date=payload.evaluation_date,
        status=EvaluationStatus.DRAFT,
        general_notes=payload.general_notes,
    )
    db.add(row)
    db.flush()
    for section in [s for s in version.sections if s.active]:
        for question in [q for q in section.questions if q.active]:
            db.add(EvaluationAnswer(
                evaluation_id=row.id,
                question_id=question.id,
                score=None,
                is_na=False,
                note=None,
                question_text_snapshot=question.question_text_ar,
                section_name_snapshot=section.name,
                max_score_snapshot=question.max_score,
                section_weight_snapshot=section.weight_percent,
                display_order_snapshot=question.display_order,
            ))
    _audit(db, user=current_user, action="evaluation_draft_created", evaluation_id=row.id, template_id=row.template_id, template_version_id=row.template_version_id)
    db.commit()
    return _load_evaluation(db, row.id)


@router.get("/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(evaluation_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*EVALUATION_VIEW_ROLES))):
    row = _load_evaluation(db, evaluation_id)
    _require_eval_access(db, current_user, row)
    return row


@router.post("/{evaluation_id}/action-plans", response_model=EvaluationActionPlanOut, status_code=201)
def create_action_plan(
    evaluation_id: int,
    payload: EvaluationActionPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ACTION_PLAN_ROLES)),
):
    row = _load_evaluation(db, evaluation_id)
    _require_eval_access(db, current_user, row)
    branch_id = payload.branch_id or row.branch_id
    employee_id = payload.employee_id if payload.employee_id is not None else row.employee_id
    if branch_id is None:
        raise AppError(status_code=400, error_code="evaluations.action_plan_branch_required", message="Action plan requires branch_id")
    if row.branch_id is not None and branch_id != row.branch_id:
        raise AppError(
            status_code=400,
            error_code="evaluations.action_plan_branch_mismatch",
            message="Action plan branch must match evaluation branch",
            detail={"evaluation_branch_id": row.branch_id, "branch_id": branch_id},
        )
    _load_user(db, payload.responsible_user_id)
    if employee_id is not None:
        employee = _load_user(db, employee_id)
        if employee.branch_id != branch_id:
            raise AppError(status_code=400, error_code="evaluations.employee_branch_mismatch", message="Employee must belong to action plan branch")
    plan = EvaluationActionPlan(
        evaluation_id=row.id,
        branch_id=branch_id,
        employee_id=employee_id,
        issue=payload.issue,
        corrective_action=payload.corrective_action,
        responsible_user_id=payload.responsible_user_id,
        due_date=payload.due_date,
        status=EvaluationActionPlanStatus.OPEN,
    )
    db.add(plan)
    db.flush()
    _audit(db, user=current_user, action="action_plan_created", evaluation_id=row.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{evaluation_id}/attachments", response_model=EvaluationAttachmentOut, status_code=201)
def upload_attachment(
    evaluation_id: int,
    answer_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ATTACHMENT_ROLES)),
):
    row = _load_evaluation(db, evaluation_id)
    _require_eval_access(db, current_user, row)
    if row.status != EvaluationStatus.DRAFT and not _broad(current_user):
        raise AppError(status_code=400, error_code="evaluations.attachment_not_allowed", message="Attachments can only be added to draft evaluations by evaluator")
    if answer_id is not None and answer_id not in {a.id for a in row.answers}:
        raise AppError(status_code=400, error_code="evaluations.answer_not_in_evaluation", message="Answer does not belong to evaluation")
    meta = evaluation_storage_service.save_attachment(file, evaluation_id=evaluation_id, answer_id=answer_id)
    att = EvaluationAttachment(evaluation_id=evaluation_id, answer_id=answer_id, uploaded_by=current_user.id, **meta)
    db.add(att)
    db.flush()
    _audit(db, user=current_user, action="attachment_added", evaluation_id=evaluation_id, new_value={"attachment_id": att.id, "answer_id": answer_id})
    db.commit()
    db.refresh(att)
    return att


@router.get("/{evaluation_id}/export/pdf")
def export_evaluation_pdf(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REPORT_ROLES)),
):
    row = _load_evaluation(db, evaluation_id)
    _require_eval_access(db, current_user, row)
    plans = db.query(EvaluationActionPlan).filter(EvaluationActionPlan.evaluation_id == row.id).all()
    attachments = db.query(EvaluationAttachment).filter(EvaluationAttachment.evaluation_id == row.id).all()
    sections: dict[str, list[EvaluationAnswer]] = {}
    for answer in row.answers:
        sections.setdefault(answer.section_name_snapshot, []).append(answer)
    section_html = ""
    for name, answers in sections.items():
        section_html += f"<h3>{escape(name)}</h3><ul>"
        for answer in answers:
            score = "N/A" if answer.is_na else (str(answer.score) if answer.score is not None else "-")
            section_html += f"<li>{escape(answer.question_text_snapshot)} - Score: {escape(score)}"
            if answer.note:
                section_html += f"<br><em>{escape(answer.note)}</em>"
            section_html += "</li>"
        section_html += "</ul>"
    plan_html = "".join(f"<li>{escape(p.issue)} - {escape(p.status.value)}</li>" for p in plans) or "<li>None</li>"
    attachment_html = "".join(f"<li>{escape(a.file_name)} ({escape(a.file_path)})</li>" for a in attachments) or "<li>None</li>"
    html = f"""
    <!doctype html>
    <html><head><meta charset="utf-8"><title>Evaluation {row.id}</title>
    <style>body{{font-family:Arial,sans-serif;margin:24px}} h1{{font-size:22px}} table{{border-collapse:collapse}} td{{padding:4px 10px;border:1px solid #ccc}}</style>
    </head><body>
    <button onclick="window.print()">Print / Save as PDF</button>
    <h1>Evaluation Report #{row.id}</h1>
    <table>
      <tr><td>Template</td><td>{escape(row.template.name if row.template else str(row.template_id))}</td></tr>
      <tr><td>Brand</td><td>{escape(row.brand.name if row.brand else str(row.brand_id))}</td></tr>
      <tr><td>Branch</td><td>{escape(row.branch.branch_name if row.branch else '-')}</td></tr>
      <tr><td>Employee</td><td>{escape(row.employee.full_name if row.employee else '-')}</td></tr>
      <tr><td>Evaluator</td><td>{escape(row.evaluator.full_name if row.evaluator else str(row.evaluator_id))}</td></tr>
      <tr><td>Date</td><td>{row.evaluation_date.isoformat()}</td></tr>
      <tr><td>Score</td><td>{escape(str(row.total_percentage or '-'))}</td></tr>
      <tr><td>Rating</td><td>{escape(row.final_rating.value if row.final_rating else '-')}</td></tr>
    </table>
    {section_html}
    <h3>Low Score Count</h3><p>{row.low_score_count or 0}</p>
    <h3>Action Plans</h3><ul>{plan_html}</ul>
    <h3>Attachments</h3><ul>{attachment_html}</ul>
    </body></html>
    """
    return HTMLResponse(html, headers={"Content-Disposition": f"inline; filename=evaluation_{row.id}.html"})


@router.put("/{evaluation_id}", response_model=EvaluationOut)
def update_evaluation(evaluation_id: int, payload: EvaluationUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*EVALUATION_CREATE_ROLES))):
    row = _load_evaluation(db, evaluation_id)
    _require_eval_access(db, current_user, row)
    if row.status != EvaluationStatus.DRAFT and not _broad(current_user):
        raise AppError(status_code=400, error_code="evaluations.not_editable", message="Submitted evaluations cannot be edited by evaluator")
    if payload.general_notes is not None:
        row.general_notes = payload.general_notes
    answer_map = {a.id: a for a in row.answers}
    for patch in payload.answers:
        answer = answer_map.get(patch.answer_id)
        if not answer:
            raise AppError(status_code=404, error_code="evaluations.answer_not_found", message="Answer not found")
        answer.is_na = patch.is_na
        answer.score = None if patch.is_na else patch.score
        answer.note = patch.note
        answer.updated_at = datetime.utcnow()
        _validate_answer(answer)
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="evaluation_updated", evaluation_id=row.id, new_value=payload.model_dump())
    db.commit()
    return _load_evaluation(db, row.id)


@router.post("/{evaluation_id}/submit", response_model=EvaluationOut)
def submit_evaluation(evaluation_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*EVALUATION_CREATE_ROLES))):
    row = _load_evaluation(db, evaluation_id)
    _require_eval_access(db, current_user, row)
    if row.status != EvaluationStatus.DRAFT:
        raise AppError(status_code=400, error_code="evaluations.invalid_status", message="Only draft evaluations can be submitted")
    if row.template_version.status != EvaluationTemplateVersionStatus.PUBLISHED:
        raise AppError(status_code=400, error_code="evaluations.version_not_published", message="Template version is not published")
    if not any(a.is_na or a.score is not None for a in row.answers):
        raise AppError(status_code=400, error_code="evaluations.empty", message="Cannot submit empty evaluation")
    for answer in row.answers:
        _validate_answer(answer)
        if _answer_requires_photo_missing(answer):
            raise AppError(
                status_code=400,
                error_code="evaluations.required_photo_missing",
                message="Required photo attachment is missing",
                detail={"answer_id": answer.id},
            )
    result = evaluation_scoring_service.calculate(row)
    for key, value in result.items():
        setattr(row, key, value)
    row.status = EvaluationStatus.SUBMITTED
    row.submitted_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="evaluation_submitted", evaluation_id=row.id, new_value=result)
    db.commit()
    return _load_evaluation(db, row.id)


@router.post("/{evaluation_id}/review", response_model=EvaluationOut)
def review_evaluation(evaluation_id: int, payload: EvaluationTransitionPayload | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*REVIEW_ROLES))):
    row = _load_evaluation(db, evaluation_id)
    _require_eval_access(db, current_user, row)
    if row.status != EvaluationStatus.SUBMITTED:
        raise AppError(status_code=400, error_code="evaluations.invalid_status", message="Only submitted evaluations can be reviewed")
    row.status = EvaluationStatus.ACTION_REQUIRED if row.action_required_flag else EvaluationStatus.REVIEWED
    row.reviewed_at = datetime.utcnow()
    row.reviewed_by = current_user.id
    row.updated_at = datetime.utcnow()
    if payload and payload.notes:
        row.general_notes = ((row.general_notes or "") + "\n" + payload.notes).strip()
    _audit(db, user=current_user, action="evaluation_reviewed", evaluation_id=row.id, notes=payload.notes if payload else None)
    db.commit()
    return _load_evaluation(db, row.id)


@router.post("/{evaluation_id}/close", response_model=EvaluationOut)
def close_evaluation(evaluation_id: int, payload: EvaluationTransitionPayload | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*CLOSE_ROLES))):
    row = _load_evaluation(db, evaluation_id)
    if row.status not in (EvaluationStatus.REVIEWED, EvaluationStatus.ACTION_REQUIRED):
        raise AppError(status_code=400, error_code="evaluations.invalid_status", message="Only reviewed or action-required evaluations can be closed")
    row.status = EvaluationStatus.CLOSED
    row.closed_at = datetime.utcnow()
    row.closed_by = current_user.id
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="evaluation_closed", evaluation_id=row.id, notes=payload.notes if payload else None)
    db.commit()
    return _load_evaluation(db, row.id)


@router.post("/{evaluation_id}/cancel", response_model=EvaluationOut)
def cancel_evaluation(evaluation_id: int, payload: EvaluationTransitionPayload | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*REVIEW_ROLES))):
    row = _load_evaluation(db, evaluation_id)
    _require_eval_access(db, current_user, row)
    if row.status not in (EvaluationStatus.DRAFT, EvaluationStatus.SUBMITTED, EvaluationStatus.REVIEWED):
        raise AppError(status_code=400, error_code="evaluations.invalid_status", message="Evaluation cannot be cancelled from current status")
    row.status = EvaluationStatus.CANCELLED
    row.updated_at = datetime.utcnow()
    _audit(db, user=current_user, action="evaluation_cancelled", evaluation_id=row.id, notes=payload.notes if payload else None)
    db.commit()
    return _load_evaluation(db, row.id)
