"""
Document Service — Phase F3.2

إدارة الوثائق الرسمية:
- وثائق الفرع: رخصة بلدية، دفاع مدني، سجل تجاري…
- وثائق الموظفين: شهادة صحية، هوية، عقد عمل…

يوفر CRUD، رفع/تنزيل ملف، تجديد الوثيقة (renew — يرشف القديم وينشئ جديد
مرتبط بـ renewed_from_id)، وحساب حالة الانتهاء:
  - expired    : expiry_date < today
  - due_soon   : today <= expiry_date <= today + reminder_days
  - valid      : expiry_date > today + reminder_days
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    Branch,
    Document,
    DocumentOwnerType,
    DocumentType,
    User,
)

logger = logging.getLogger(__name__)

# Mirror quality attachment limits/types to stay consistent
_ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")
_MAX_DOC_BYTES = 15 * 1024 * 1024  # 15 MB


# ─── helpers ────────────────────────────────────────────────────────────────

def _compute_status(doc: Document, today: Optional[date] = None) -> str:
    """Return one of: archived | expired | due_soon | valid."""
    if doc.is_archived:
        return "archived"
    today = today or date.today()
    # J2: guard against accidentally-null expiry_date in legacy rows
    if doc.expiry_date is None:
        return "valid"
    if doc.expiry_date < today:
        return "expired"
    days_left = (doc.expiry_date - today).days
    if days_left <= (doc.reminder_days or 30):
        return "due_soon"
    return "valid"


def _days_until_expiry(doc: Document, today: Optional[date] = None) -> int:
    today = today or date.today()
    if doc.expiry_date is None:
        return 0
    return (doc.expiry_date - today).days


def serialize(doc: Document) -> Dict[str, Any]:
    """Convert a Document row into the dict shape expected by DocumentOut."""
    today = date.today()
    out: Dict[str, Any] = {
        "id": doc.id,
        "owner_type": doc.owner_type,
        "branch_id": doc.branch_id,
        "user_id": doc.user_id,
        "doc_type": doc.doc_type,
        "title": doc.title,
        "issuer": doc.issuer,
        "doc_number": doc.doc_number,
        "issue_date": doc.issue_date,
        "expiry_date": doc.expiry_date,
        "reminder_days": doc.reminder_days,
        "file_path": doc.file_path,
        "file_name": doc.file_name,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
        "notes": doc.notes,
        "is_archived": doc.is_archived,
        "renewed_from_id": doc.renewed_from_id,
        "last_reminder_at": doc.last_reminder_at,
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "days_until_expiry": _days_until_expiry(doc, today),
        "status": _compute_status(doc, today),
        "branch_name": (doc.branch.branch_name if doc.branch else None),
        "user_full_name": (doc.user.full_name if doc.user else None),
    }
    return out


# ─── CRUD ────────────────────────────────────────────────────────────────────

def create_document(
    db: Session,
    *,
    owner_type: DocumentOwnerType,
    doc_type: DocumentType,
    title: str,
    expiry_date: date,
    branch_id: Optional[int] = None,
    user_id: Optional[int] = None,
    issuer: Optional[str] = None,
    doc_number: Optional[str] = None,
    issue_date: Optional[date] = None,
    reminder_days: int = 30,
    notes: Optional[str] = None,
    uploaded_by: Optional[int] = None,
    tenant_id: int = 1,
) -> Document:
    # Defensive validation — the DB check constraint also enforces this
    if owner_type == DocumentOwnerType.branch:
        if not branch_id or user_id:
            raise HTTPException(status_code=400, detail="وثيقة الفرع تحتاج branch_id فقط")
        if not db.query(Branch).filter(Branch.id == branch_id).first():
            raise HTTPException(status_code=404, detail="الفرع غير موجود")
    else:
        if not user_id or branch_id:
            raise HTTPException(status_code=400, detail="وثيقة الموظف تحتاج user_id فقط")
        if not db.query(User).filter(User.id == user_id).first():
            raise HTTPException(status_code=404, detail="الموظف غير موجود")

    if issue_date and issue_date > expiry_date:
        raise HTTPException(status_code=400, detail="تاريخ الإصدار بعد تاريخ الانتهاء")

    doc = Document(
        owner_type=owner_type,
        branch_id=branch_id,
        user_id=user_id,
        doc_type=doc_type,
        title=title.strip(),
        issuer=(issuer or None),
        doc_number=(doc_number or None),
        issue_date=issue_date,
        expiry_date=expiry_date,
        reminder_days=reminder_days,
        notes=notes,
        uploaded_by=uploaded_by,
        tenant_id=tenant_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def update_document(
    db: Session,
    doc_id: int,
    *,
    title: Optional[str] = None,
    issuer: Optional[str] = None,
    doc_number: Optional[str] = None,
    issue_date: Optional[date] = None,
    expiry_date: Optional[date] = None,
    reminder_days: Optional[int] = None,
    notes: Optional[str] = None,
) -> Document:
    doc = _get_or_404(db, doc_id)
    if doc.is_archived:
        raise HTTPException(status_code=409, detail="لا يمكن تعديل وثيقة مؤرشفة")

    if title is not None:        doc.title = title.strip()
    if issuer is not None:       doc.issuer = issuer or None
    if doc_number is not None:   doc.doc_number = doc_number or None
    if issue_date is not None:   doc.issue_date = issue_date
    if expiry_date is not None:  doc.expiry_date = expiry_date
    if reminder_days is not None:doc.reminder_days = reminder_days
    if notes is not None:        doc.notes = notes

    if doc.issue_date and doc.expiry_date and doc.issue_date > doc.expiry_date:
        raise HTTPException(status_code=400, detail="تاريخ الإصدار بعد تاريخ الانتهاء")

    db.commit()
    db.refresh(doc)
    return doc


def delete_document(db: Session, doc_id: int) -> None:
    """Soft-delete — لا نمسح السجل فعلياً للحفاظ على السجلات التاريخية."""
    doc = _get_or_404(db, doc_id)
    doc.is_deleted = True
    db.commit()


def get_document(db: Session, doc_id: int) -> Document:
    return _get_or_404(db, doc_id)


def _get_or_404(db: Session, doc_id: int) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.is_deleted == False)  # noqa: E712
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="الوثيقة غير موجودة")
    return doc


# ─── list / query ────────────────────────────────────────────────────────────

def list_documents(
    db: Session,
    *,
    owner_type: Optional[DocumentOwnerType] = None,
    branch_id: Optional[int] = None,
    user_id: Optional[int] = None,
    doc_type: Optional[DocumentType] = None,
    status: Optional[str] = None,   # valid | due_soon | expired | archived
    include_archived: bool = False,
    tenant_id: int = 1,
) -> List[Document]:
    q = db.query(Document).filter(
        Document.is_deleted == False,  # noqa: E712
        Document.tenant_id == tenant_id,
    )
    if not include_archived:
        q = q.filter(Document.is_archived == False)  # noqa: E712
    if owner_type:
        q = q.filter(Document.owner_type == owner_type)
    if branch_id:
        q = q.filter(Document.branch_id == branch_id)
    if user_id:
        q = q.filter(Document.user_id == user_id)
    if doc_type:
        q = q.filter(Document.doc_type == doc_type)

    rows = q.order_by(Document.expiry_date.asc(), Document.id.desc()).all()

    if status:
        today = date.today()
        rows = [r for r in rows if _compute_status(r, today) == status]
    return rows


def expiry_summary(db: Session, tenant_id: int = 1) -> Dict[str, int]:
    rows = (
        db.query(Document)
        .filter(
            Document.is_deleted == False,  # noqa: E712
            Document.is_archived == False,  # noqa: E712
            Document.tenant_id == tenant_id,
        )
        .all()
    )
    today = date.today()
    expired = due_soon = valid = 0
    for r in rows:
        s = _compute_status(r, today)
        if s == "expired":   expired += 1
        elif s == "due_soon":due_soon += 1
        elif s == "valid":   valid += 1
    return {
        "total": expired + due_soon + valid,
        "expired": expired,
        "due_soon": due_soon,
        "valid": valid,
    }


# ─── file upload / download ──────────────────────────────────────────────────

def attach_file(
    db: Session,
    doc_id: int,
    file: UploadFile,
    upload_root: str,
) -> Document:
    """رفع/استبدال ملف الوثيقة. يحفظ الملف على القرص ويحدث المسار في DB."""
    doc = _get_or_404(db, doc_id)

    mime = (file.content_type or "").lower()
    if mime and not any(mime.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=415,
            detail=f"نوع الملف غير مسموح ({mime}). المسموح: صور أو PDF",
        )

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="ملف فارغ")
    if len(data) > _MAX_DOC_BYTES:
        raise HTTPException(status_code=413, detail="حجم الملف أكبر من 15 ميجا")

    sub = f"doc_{doc.id}"
    upload_dir = os.path.join(upload_root, sub)
    os.makedirs(upload_dir, exist_ok=True)
    original = (file.filename or "document.bin").strip().replace("/", "_").replace("\\", "_")
    ext = os.path.splitext(original)[1].lower() or ""
    fname = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(upload_dir, fname)
    with open(full_path, "wb") as f:
        f.write(data)

    # If an old file existed, leave it on disk (audit) — only update the pointer
    doc.file_path = full_path
    doc.file_name = original[:255]
    doc.mime_type = mime[:100] if mime else None
    doc.size_bytes = len(data)
    db.commit()
    db.refresh(doc)
    return doc


def read_file(doc: Document) -> Tuple[bytes, str, str]:
    """Return (bytes, filename, mime). Raise 404 if no file."""
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="لا يوجد ملف مرفوع لهذه الوثيقة")
    with open(doc.file_path, "rb") as f:
        data = f.read()
    return data, (doc.file_name or "document.bin"), (doc.mime_type or "application/octet-stream")


# ─── renewal ────────────────────────────────────────────────────────────────

def renew_document(
    db: Session,
    doc_id: int,
    *,
    new_expiry_date: date,
    new_issue_date: Optional[date] = None,
    new_doc_number: Optional[str] = None,
    notes: Optional[str] = None,
    uploaded_by: Optional[int] = None,
) -> Document:
    """ينشئ وثيقة جديدة تحمل نفس owner/doc_type + تواريخ جديدة، ويرشف القديمة."""
    old = _get_or_404(db, doc_id)
    if old.is_archived:
        raise HTTPException(status_code=409, detail="هذه الوثيقة مؤرشفة بالفعل")
    if new_issue_date and new_issue_date > new_expiry_date:
        raise HTTPException(status_code=400, detail="تاريخ الإصدار بعد تاريخ الانتهاء")

    new_doc = Document(
        owner_type=old.owner_type,
        branch_id=old.branch_id,
        user_id=old.user_id,
        doc_type=old.doc_type,
        title=old.title,
        issuer=old.issuer,
        doc_number=(new_doc_number or old.doc_number),
        issue_date=new_issue_date,
        expiry_date=new_expiry_date,
        reminder_days=old.reminder_days,
        notes=(notes if notes is not None else old.notes),
        renewed_from_id=old.id,
        uploaded_by=uploaded_by,
        tenant_id=old.tenant_id,
    )
    old.is_archived = True
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    logger.info("Document renewed: old=%s → new=%s", old.id, new_doc.id)
    return new_doc


# ─── reminders (used by scheduler) ───────────────────────────────────────────

def due_for_reminder(db: Session, tenant_id: int = 1) -> List[Document]:
    """
    الوثائق التي تحتاج تذكير الآن:
      - غير مؤرشفة + غير محذوفة
      - (expiry - today) <= reminder_days  أي داخل نافذة التذكير أو منتهية
      - last_reminder_at = NULL أو من يوم سابق (حتى لا نكرر نفس اليوم)
    """
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    rows = (
        db.query(Document)
        .filter(
            Document.is_deleted == False,  # noqa: E712
            Document.is_archived == False,  # noqa: E712
            Document.tenant_id == tenant_id,
        )
        .all()
    )
    out: List[Document] = []
    for r in rows:
        days_left = (r.expiry_date - today).days
        if days_left > (r.reminder_days or 30):
            continue
        if r.last_reminder_at and r.last_reminder_at >= today_start:
            continue
        out.append(r)
    return out


def mark_reminder_sent(db: Session, doc_ids: List[int]) -> None:
    if not doc_ids:
        return
    db.query(Document).filter(Document.id.in_(doc_ids)).update(
        {Document.last_reminder_at: datetime.utcnow()},
        synchronize_session=False,
    )
    db.commit()
