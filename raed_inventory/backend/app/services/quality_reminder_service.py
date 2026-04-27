"""
Quality/Training Reminder Service — Phase E8.4

يُستدعى مرة يومياً من الـ scheduler لتسجيل مهام التذكير:
  - الإجراءات التصحيحية المتأخرة / المستحقة خلال 3 أيام
  - تقييمات التدريب المعلّقة (needs_reeval) التي اقتربت من re_eval_date

هذا الـ service لا يرسل إيميلات حالياً — النظام يعتمد على جرس الإشعارات
في الواجهة (polling من notifications router)، والـ scheduler يسجّل ملخصاً
يمكن اعتباره hook للإضافة لاحقة (email/push/sms).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import (
    QualityVisit,
    QualityVisitResponse,
    QualityResponseStatus,
    TrainingAssessment,
    AssessmentStatus,
)

logger = logging.getLogger(__name__)


def _overdue_quality_actions(db: Session) -> List[int]:
    today = date.today()
    rows = (
        db.query(QualityVisitResponse.id)
        .join(QualityVisit, QualityVisit.id == QualityVisitResponse.visit_id)
        .filter(
            QualityVisit.is_deleted == False,  # noqa: E712
            QualityVisitResponse.status == QualityResponseStatus.no,
            QualityVisitResponse.is_resolved == False,  # noqa: E712
            QualityVisitResponse.due_date != None,  # noqa: E711
            QualityVisitResponse.due_date < today,
        )
        .all()
    )
    return [r[0] for r in rows]


def _due_soon_quality_actions(db: Session, days: int = 3) -> List[int]:
    today = date.today()
    threshold = today + timedelta(days=days)
    rows = (
        db.query(QualityVisitResponse.id)
        .join(QualityVisit, QualityVisit.id == QualityVisitResponse.visit_id)
        .filter(
            QualityVisit.is_deleted == False,  # noqa: E712
            QualityVisitResponse.status == QualityResponseStatus.no,
            QualityVisitResponse.is_resolved == False,  # noqa: E712
            QualityVisitResponse.due_date != None,  # noqa: E711
            QualityVisitResponse.due_date >= today,
            QualityVisitResponse.due_date <= threshold,
        )
        .all()
    )
    return [r[0] for r in rows]


def _reeval_due_soon(db: Session, days: int = 7) -> List[int]:
    today = date.today()
    threshold = today + timedelta(days=days)
    rows = (
        db.query(TrainingAssessment.id)
        .filter(
            TrainingAssessment.status == AssessmentStatus.needs_reeval,
            TrainingAssessment.re_eval_date != None,  # noqa: E711
            TrainingAssessment.re_eval_date >= today,
            TrainingAssessment.re_eval_date <= threshold,
        )
        .all()
    )
    return [r[0] for r in rows]


def _reeval_overdue(db: Session) -> List[int]:
    today = date.today()
    rows = (
        db.query(TrainingAssessment.id)
        .filter(
            TrainingAssessment.status == AssessmentStatus.needs_reeval,
            TrainingAssessment.re_eval_date != None,  # noqa: E711
            TrainingAssessment.re_eval_date < today,
        )
        .all()
    )
    return [r[0] for r in rows]


def run_quality_training_reminders(db: Session) -> Dict[str, Any]:
    """
    مرور تذكيري يومي. يرجع dict بإحصائيات ليتم log-ing.
    إضافات مستقبلية: إرسال إيميل للمسؤول عند تجاوز عتبة محددة.
    """
    try:
        overdue_actions = _overdue_quality_actions(db)
        due_soon_actions = _due_soon_quality_actions(db, days=3)
        reeval_soon = _reeval_due_soon(db, days=7)
        reeval_overdue = _reeval_overdue(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("reminders query failed: %s", exc)
        return {"status": "error", "reason": str(exc)}

    summary = {
        "status": "completed",
        "date": date.today().isoformat(),
        "overdue_quality_actions": len(overdue_actions),
        "due_soon_quality_actions": len(due_soon_actions),
        "reeval_due_soon": len(reeval_soon),
        "reeval_overdue": len(reeval_overdue),
    }

    # أرقام مهمة: سجّلها بمستوى warning إذا تعدّت العتبة
    if len(overdue_actions) > 0:
        logger.warning(
            "Quality reminder: %d overdue corrective actions — IDs: %s",
            len(overdue_actions),
            overdue_actions[:20],
        )
    if len(reeval_overdue) > 0:
        logger.warning(
            "Training reminder: %d overdue re-evaluations — IDs: %s",
            len(reeval_overdue),
            reeval_overdue[:20],
        )
    logger.info("Reminder sweep summary: %s", summary)
    return summary
