"""
Documents Router — /api/v1/documents  (Phase F3.3)

الصلاحيات:
- عرض: admin, super_admin, area_manager, branch_manager, warehouse_manager, quality_manager
- تعديل/إنشاء/رفع: admin, super_admin, area_manager, branch_manager, quality_manager
- مدير الفرع يرى/يعدّل فقط وثائق فرعه أو موظفيه (enforced in helpers)
"""
from __future__ import annotations

import io
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_roles
from app.config import settings
from app.database import get_db
from app.models import (
    Document,
    DocumentOwnerType,
    DocumentType,
    User,
)
from app.schemas import (
    DocumentCreate,
    DocumentExpirySummary,
    DocumentOut,
    DocumentRenew,
    DocumentUpdate,
)
from app.services import document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

_VIEW_ROLES = (
    "admin", "super_admin",
    "area_manager", "branch_manager",
    "warehouse_manager", "quality_manager", "internal_auditor",
)
_EDIT_ROLES = (
    "admin", "super_admin",
    "area_manager", "branch_manager",
    "quality_manager",
)


# ─── auth helpers ────────────────────────────────────────────────────────────

def _role_names(user: User) -> set[str]:
    return {ur.role.name.value if hasattr(ur.role.name, "value") else ur.role.name
            for ur in (user.user_roles or [])}


def _is_privileged(user: User) -> bool:
    roles = _role_names(user)
    return bool(roles & {"admin", "super_admin", "area_manager", "quality_manager"})


def _assert_can_touch(user: User, doc: Document) -> None:
    """Branch-scoped: branch_manager can only access docs tied to their branch
    or to employees who belong to their branch."""
    if _is_privileged(user):
        return
    roles = _role_names(user)
    if "branch_manager" in roles:
        if doc.owner_type == DocumentOwnerType.branch:
            if doc.branch_id != user.branch_id:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لوثائق فرع آخر")
            return
        if doc.owner_type == DocumentOwnerType.employee and doc.user:
            if doc.user.branch_id != user.branch_id:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لموظف من فرع آخر")
            return
    raise HTTPException(status_code=403, detail="صلاحيات غير كافية")


def _assert_can_view(user: User, doc: Document) -> None:
    roles = _role_names(user)
    if roles & {"admin", "super_admin", "area_manager", "quality_manager", "warehouse_manager"}:
        return
    if "branch_manager" in roles:
        _assert_can_touch(user, doc)
        return
    raise HTTPException(status_code=403, detail="صلاحيات غير كافية")


# ─── list / summary ──────────────────────────────────────────────────────────

@router.get("/", response_model=list[DocumentOut])
def list_documents(
    owner_type: Optional[DocumentOwnerType] = None,
    branch_id: Optional[int] = None,
    user_id: Optional[int] = None,
    doc_type: Optional[DocumentType] = None,
    status: Optional[str] = Query(None, pattern="^(valid|due_soon|expired|archived)$"),
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    # branch_manager restricted to their own branch
    if "branch_manager" in _role_names(current_user) and not _is_privileged(current_user):
        branch_id = current_user.branch_id

    rows = document_service.list_documents(
        db,
        owner_type=owner_type,
        branch_id=branch_id,
        user_id=user_id,
        doc_type=doc_type,
        status=status,
        include_archived=include_archived,
    )
    return [document_service.serialize(r) for r in rows]


@router.get("/summary", response_model=DocumentExpirySummary)
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    return document_service.expiry_summary(db)


@router.get("/expiring", response_model=list[DocumentOut])
def list_expiring(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    """الوثائق التي تنتهي خلال N يوم (أو منتهية بالفعل)."""
    today = date.today()
    try:
        rows = document_service.list_documents(db, include_archived=False)
    except Exception:
        logger.exception("J2: list_documents failed in /expiring; returning empty")
        return []

    branch_scope = None
    if "branch_manager" in _role_names(current_user) and not _is_privileged(current_user):
        branch_scope = current_user.branch_id

    filtered = []
    for r in rows:
        try:
            # J2: skip legacy rows with null expiry_date rather than crash
            if r.expiry_date is None:
                continue
            days_left = (r.expiry_date - today).days
            if days_left > days:
                continue
            if branch_scope is not None:
                # scope branch_manager
                if r.owner_type == DocumentOwnerType.branch and r.branch_id != branch_scope:
                    continue
                if r.owner_type == DocumentOwnerType.employee and (not r.user or r.user.branch_id != branch_scope):
                    continue
            filtered.append(r)
        except Exception:
            logger.exception("J2: skipping document row id=%s due to error", getattr(r, "id", "?"))
            continue

    try:
        return [document_service.serialize(r) for r in filtered]
    except Exception:
        logger.exception("J2: serialize failed in /expiring; returning empty")
        return []


# ─── CRUD ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=DocumentOut, status_code=201)
def create(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_EDIT_ROLES)),
):
    # Scope: branch_manager can only create under their own branch
    if "branch_manager" in _role_names(current_user) and not _is_privileged(current_user):
        if payload.owner_type == DocumentOwnerType.branch and payload.branch_id != current_user.branch_id:
            raise HTTPException(status_code=403, detail="لا يمكنك إنشاء وثيقة لفرع آخر")
        if payload.owner_type == DocumentOwnerType.employee:
            target = db.query(User).filter(User.id == payload.user_id).first()
            if not target or target.branch_id != current_user.branch_id:
                raise HTTPException(status_code=403, detail="الموظف ليس ضمن فرعك")

    doc = document_service.create_document(
        db,
        owner_type=payload.owner_type,
        doc_type=payload.doc_type,
        title=payload.title,
        branch_id=payload.branch_id,
        user_id=payload.user_id,
        issuer=payload.issuer,
        doc_number=payload.doc_number,
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        reminder_days=payload.reminder_days,
        notes=payload.notes,
        uploaded_by=current_user.id,
    )
    return document_service.serialize(doc)


@router.get("/{doc_id}", response_model=DocumentOut)
def get_one(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    doc = document_service.get_document(db, doc_id)
    _assert_can_view(current_user, doc)
    return document_service.serialize(doc)


@router.patch("/{doc_id}", response_model=DocumentOut)
def update(
    doc_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_EDIT_ROLES)),
):
    doc = document_service.get_document(db, doc_id)
    _assert_can_touch(current_user, doc)
    updated = document_service.update_document(
        db, doc_id,
        title=payload.title,
        issuer=payload.issuer,
        doc_number=payload.doc_number,
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        reminder_days=payload.reminder_days,
        notes=payload.notes,
    )
    return document_service.serialize(updated)


@router.delete("/{doc_id}", status_code=204)
def remove(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_EDIT_ROLES)),
):
    doc = document_service.get_document(db, doc_id)
    _assert_can_touch(current_user, doc)
    document_service.delete_document(db, doc_id)


# ─── file upload / download ──────────────────────────────────────────────────

@router.post("/{doc_id}/file", response_model=DocumentOut)
def upload_file(
    doc_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_EDIT_ROLES)),
):
    doc = document_service.get_document(db, doc_id)
    _assert_can_touch(current_user, doc)
    updated = document_service.attach_file(db, doc_id, file, settings.DOCUMENTS_UPLOAD_DIR)
    return document_service.serialize(updated)


@router.get("/{doc_id}/file")
def download_file(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
):
    doc = document_service.get_document(db, doc_id)
    _assert_can_view(current_user, doc)
    data, filename, mime = document_service.read_file(doc)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ─── renewal ────────────────────────────────────────────────────────────────

@router.post("/{doc_id}/renew", response_model=DocumentOut, status_code=201)
def renew(
    doc_id: int,
    payload: DocumentRenew,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_EDIT_ROLES)),
):
    doc = document_service.get_document(db, doc_id)
    _assert_can_touch(current_user, doc)
    new_doc = document_service.renew_document(
        db, doc_id,
        new_expiry_date=payload.new_expiry_date,
        new_issue_date=payload.new_issue_date,
        new_doc_number=payload.new_doc_number,
        notes=payload.notes,
        uploaded_by=current_user.id,
    )
    return document_service.serialize(new_doc)
