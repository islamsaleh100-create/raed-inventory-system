import os
import re
import time
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.errors import AppError


UPLOAD_ROOT = Path("uploads") / "evaluations"


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name or "attachment")
    return cleaned[:120] or "attachment"


def save_attachment(file: UploadFile, *, evaluation_id: int, answer_id: int | None = None) -> dict:
    try:
        data = file.file.read()
    finally:
        try:
            file.file.close()
        except Exception:
            pass
    if not data:
        raise AppError(status_code=400, error_code="evaluations.empty_attachment", message="Attachment file is empty")
    folder = UPLOAD_ROOT / str(evaluation_id)
    if answer_id is not None:
        folder = folder / "answers" / str(answer_id)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}_{_safe_name(file.filename or 'attachment')}"
    path = folder / filename
    path.write_bytes(data)
    return {
        "storage_disk": "local",
        "file_path": str(path).replace("\\", "/"),
        "file_name": file.filename or filename,
        "mime_type": file.content_type or "application/octet-stream",
        "file_size": len(data),
    }


def delete_attachment(path: str) -> None:
    last_error = None
    for _ in range(3):
        try:
            os.remove(path)
            return
        except FileNotFoundError:
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.05)
    if last_error is not None:
        return
