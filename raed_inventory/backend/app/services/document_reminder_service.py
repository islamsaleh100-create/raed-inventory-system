"""
Document Reminder Service — Phase F3.4

يعمل ضمن الـ daily scheduler. يستدعي document_service.due_for_reminder
وينشئ إشعارات (notifications) موجهة للأدوار المعنية:

- وثيقة فرع منتهية / قاربت على الانتهاء → branch_manager (للفرع), area_manager
- وثيقة موظف منتهية / قاربت على الانتهاء → branch_manager (لفرع الموظف), area_manager

الهدف: أن يرى المسؤول تذكيراً في جرس الإشعارات قبل يحدث تقصير.

لا يُرسل إيميل حالياً — يعتمد على نظام الإشعارات الداخلي كبقية الوحدات.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentOwnerType,
    User,
    Branch,
)
from app.services import document_service

logger = logging.getLogger(__name__)


def _recipients_for(db: Session, doc: Document) -> List[int]:
    """نحدد مستخدمي الإشعار بناءً على نوع الوثيقة."""
    recipients: List[int] = []

    target_branch_id: Optional[int] = None
    if doc.owner_type == DocumentOwnerType.branch:
        target_branch_id = doc.branch_id
    elif doc.owner_type == DocumentOwnerType.employee and doc.user:
        target_branch_id = doc.user.branch_id

    # مدير الفرع المعني
    if target_branch_id:
        branch_managers = (
            db.query(User.id)
            .join(User.user_roles)
            .filter(
                User.branch_id == target_branch_id,
                User.is_deleted == False,  # noqa: E712
            )
            .all()
        )
        # filter roles manually to avoid double-joining
        for uid_row in branch_managers:
            u = db.query(User).get(uid_row[0])
            if not u:
                continue
            roles = {ur.role.name.value if hasattr(ur.role.name, "value") else ur.role.name
                     for ur in (u.user_roles or [])}
            if "branch_manager" in roles:
                recipients.append(u.id)

    # كل area_manager وadmin
    supervisors = (
        db.query(User)
        .filter(User.is_deleted == False)  # noqa: E712
        .all()
    )
    for u in supervisors:
        roles = {ur.role.name.value if hasattr(ur.role.name, "value") else ur.role.name
                 for ur in (u.user_roles or [])}
        if roles & {"area_manager", "admin", "super_admin"}:
            recipients.append(u.id)

    # dedupe
    return list(dict.fromkeys(recipients))


def _compose_message(doc: Document, today: date) -> Dict[str, str]:
    days_left = (doc.expiry_date - today).days
    kind_ar = {
        "municipality_license":    "رخصة بلدية",
        "civil_defense_license":   "رخصة دفاع مدني",
        "commercial_registration": "سجل تجاري",
        "food_safety_permit":      "تصريح سلامة غذاء",
        "branch_other":            "وثيقة فرع",
        "health_certificate":      "شهادة صحية",
        "national_id":             "هوية",
        "work_permit":             "رخصة عمل",
        "work_contract":           "عقد عمل",
        "employee_other":          "وثيقة موظف",
    }.get(doc.doc_type.value if hasattr(doc.doc_type, "value") else doc.doc_type, "وثيقة")

    subject_ar = ""
    if doc.owner_type == DocumentOwnerType.branch and doc.branch:
        subject_ar = f"فرع {doc.branch.branch_name}"
    elif doc.owner_type == DocumentOwnerType.employee and doc.user:
        subject_ar = f"موظف {doc.user.full_name}"

    if days_left < 0:
        title = f"⚠️ {kind_ar} منتهية — {subject_ar}"
        body = f"انتهت صلاحية {kind_ar} ({doc.title}) منذ {abs(days_left)} يوم."
    elif days_left == 0:
        title = f"⚠️ {kind_ar} تنتهي اليوم — {subject_ar}"
        body = f"{kind_ar} ({doc.title}) تنتهي صلاحيتها اليوم. يلزم التجديد."
    else:
        title = f"⏰ {kind_ar} تقترب من الانتهاء — {subject_ar}"
        body = f"{kind_ar} ({doc.title}) تنتهي خلال {days_left} يوم (بتاريخ {doc.expiry_date})."
    return {"title": title, "body": body}


def _emit_notifications(db: Session, doc: Document, user_ids: List[int], today: date) -> int:
    """نستخدم notification_service إن وُجد، وإلا نسجل log فقط."""
    if not user_ids:
        return 0
    try:
        from app.services import notification_service  # type: ignore
    except Exception:  # noqa: BLE001
        notification_service = None

    msg = _compose_message(doc, today)
    sent = 0
    if notification_service and hasattr(notification_service, "create_notification"):
        for uid in user_ids:
            try:
                notification_service.create_notification(
                    db,
                    user_id=uid,
                    title=msg["title"],
                    body=msg["body"],
                    category="document_expiry",
                    link=f"/documents/{doc.id}",
                )
                sent += 1
            except Exception:  # noqa: BLE001
                logger.exception("Failed to push doc reminder for user %s doc %s", uid, doc.id)
    else:
        logger.info(
            "Doc reminder (no notification_service): doc=%s users=%s msg=%s",
            doc.id, user_ids, msg["title"],
        )
    return sent


def run_document_reminders(db: Session) -> Dict[str, Any]:
    """المرور اليومي — يحسب الوثائق المستحقة ويُنشئ إشعارات."""
    today = date.today()
    try:
        docs = document_service.due_for_reminder(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("document reminders query failed: %s", exc)
        return {"status": "error", "reason": str(exc)}

    expired = 0
    due_soon = 0
    notifications_sent = 0
    processed_ids: List[int] = []

    for doc in docs:
        try:
            days_left = (doc.expiry_date - today).days
            if days_left < 0:
                expired += 1
            else:
                due_soon += 1
            recipients = _recipients_for(db, doc)
            notifications_sent += _emit_notifications(db, doc, recipients, today)
            processed_ids.append(doc.id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to process reminder for doc %s", doc.id)

    if processed_ids:
        document_service.mark_reminder_sent(db, processed_ids)

    summary = {
        "status": "completed",
        "date": today.isoformat(),
        "docs_due": len(docs),
        "expired": expired,
        "due_soon": due_soon,
        "notifications_sent": notifications_sent,
    }
    if expired:
        logger.warning("Document reminders: %d expired docs processed", expired)
    logger.info("Document reminder sweep: %s", summary)
    return summary
