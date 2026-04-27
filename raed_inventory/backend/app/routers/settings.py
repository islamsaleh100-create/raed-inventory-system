"""
System Settings Router — /api/v1/settings
Admin-only endpoints to read and update system_settings table.

Settings are stored as key/value strings; validation is per-key
(numeric, boolean, time HH:MM, enum).
"""

import re
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.errors import AppError
from app.database import get_db
from app.models import SystemSetting, User
from app.schemas import (
    SystemSettingOut,
    SystemSettingUpdate,
    SystemSettingsBulkUpdate,
)

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])

_ADMIN_ROLES = ("admin", "super_admin")

# ──────────────────────────────────────────────
# Validation rules per key
# ──────────────────────────────────────────────

# Numeric-positive settings (stored as strings, validated as int/float)
_INT_SETTINGS = {
    "days_of_cover_target",
    "max_exceptional_order_per_day",
}
_PCT_SETTINGS = {
    "variance_warning_threshold_pct",
    "variance_critical_threshold_pct",
}
_BOOL_SETTINGS = {
    "auto_generate_order_on_approval",
    "require_variance_reason",
}
_ENUM_SETTINGS = {
    "avg_consumption_mode": {"last_7_days", "last_14_days", "last_30_days"},
}
_TIME_SETTINGS = {
    "inventory_reminder_time",
}


def _validate(key: str, value: str) -> str:
    """Validate + normalise a setting value. Raises AppError on bad input."""
    v = (value or "").strip()

    if key in _INT_SETTINGS:
        if not v.isdigit():
            raise AppError(
                status_code=400,
                error_code="settings.invalid_int",
                message=f"القيمة لازم تكون رقم صحيح موجب لـ {key}",
                detail={"key": key},
            )
        n = int(v)
        if n <= 0:
            raise AppError(
                status_code=400,
                error_code="settings.invalid_positive",
                message=f"القيمة لازم تكون أكبر من صفر لـ {key}",
                detail={"key": key},
            )
        return str(n)

    if key in _PCT_SETTINGS:
        try:
            f = float(v)
        except ValueError:
            raise AppError(
                status_code=400,
                error_code="settings.invalid_float",
                message=f"القيمة لازم تكون رقم لـ {key}",
                detail={"key": key},
            )
        if f < 0 or f > 100:
            raise AppError(
                status_code=400,
                error_code="settings.invalid_pct",
                message=f"النسبة لازم تكون بين 0 و 100 لـ {key}",
                detail={"key": key},
            )
        return str(f) if f != int(f) else str(int(f))

    if key in _BOOL_SETTINGS:
        if v.lower() in ("true", "1", "yes"):
            return "true"
        if v.lower() in ("false", "0", "no"):
            return "false"
        raise AppError(
            status_code=400,
            error_code="settings.invalid_bool",
            message=f"القيمة لازم تكون true أو false لـ {key}",
            detail={"key": key},
        )

    if key in _ENUM_SETTINGS:
        allowed = _ENUM_SETTINGS[key]
        if v not in allowed:
            raise AppError(
                status_code=400,
                error_code="settings.invalid_enum",
                message=f"القيمة لازم تكون واحدة من: {', '.join(sorted(allowed))}",
                detail={"key": key, "allowed": sorted(allowed)},
            )
        return v

    if key in _TIME_SETTINGS:
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise AppError(
                status_code=400,
                error_code="settings.invalid_time",
                message=f"الوقت لازم يكون بصيغة HH:MM لـ {key}",
                detail={"key": key},
            )
        return v

    # Unknown key → accept as-is (free-form string)
    return v


def _to_out(setting: SystemSetting, db: Session) -> SystemSettingOut:
    updater_name = None
    if setting.updated_by:
        u = db.query(User).filter(User.id == setting.updated_by).first()
        if u:
            updater_name = u.full_name or u.username
    return SystemSettingOut(
        id=setting.id,
        key=setting.key,
        value=setting.value,
        description=setting.description,
        updated_at=setting.updated_at,
        updated_by=setting.updated_by,
        updated_by_name=updater_name,
    )


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.get("", response_model=List[SystemSettingOut])
def list_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ADMIN_ROLES)),
):
    """Return all system settings (admin only)."""
    rows = db.query(SystemSetting).order_by(SystemSetting.key.asc()).all()
    return [_to_out(r, db) for r in rows]


@router.get("/{key}", response_model=SystemSettingOut)
def get_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ADMIN_ROLES)),
):
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        raise AppError(
            status_code=404,
            error_code="settings.not_found",
            message=f"الإعداد '{key}' غير موجود",
            detail={"key": key},
        )
    return _to_out(row, db)


@router.put("/{key}", response_model=SystemSettingOut)
def update_setting(
    key: str,
    payload: SystemSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ADMIN_ROLES)),
):
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not row:
        raise AppError(
            status_code=404,
            error_code="settings.not_found",
            message=f"الإعداد '{key}' غير موجود",
            detail={"key": key},
        )
    row.value = _validate(key, payload.value)
    row.updated_by = current_user.id
    db.commit()
    db.refresh(row)
    return _to_out(row, db)


@router.put("", response_model=List[SystemSettingOut])
def bulk_update_settings(
    payload: SystemSettingsBulkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*_ADMIN_ROLES)),
):
    """Update multiple settings in one call — atomic."""
    if not isinstance(payload.settings, dict) or not payload.settings:
        raise AppError(
            status_code=400,
            error_code="settings.empty_payload",
            message="لازم تبعت الإعدادات المطلوب تحديثها",
            detail={},
        )

    # Validate all first — don't commit partial updates
    validated: list[tuple[SystemSetting, str]] = []
    for key, raw_val in payload.settings.items():
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not row:
            raise AppError(
                status_code=404,
                error_code="settings.not_found",
                message=f"الإعداد '{key}' غير موجود",
                detail={"key": key},
            )
        validated.append((row, _validate(key, raw_val)))

    # All good — commit
    for row, v in validated:
        row.value = v
        row.updated_by = current_user.id
    db.commit()

    keys = list(payload.settings.keys())
    rows = (
        db.query(SystemSetting)
        .filter(SystemSetting.key.in_(keys))
        .order_by(SystemSetting.key.asc())
        .all()
    )
    return [_to_out(r, db) for r in rows]
