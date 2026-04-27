"""
Timezone-aware datetime helpers (AST / Asia/Riyadh by default).

لماذا هذا الملف موجود:
- النظام بيستخدم `datetime.utcnow()` في أغلب الأماكن، وده نقطة ضعف عند
  التعامل مع حدود اليوم التجاري في السعودية (توقيت AST = UTC+3).
- `inventory_date` (Date) المفروض يتحسب بتوقيت المحل (AST) مش UTC.
- سكدجولر التجديد (auto-replenishment) المفروض يشتغل الساعة 6 صباحاً بتوقيت الرياض.

الاستخدام:
    from app.core.timezone import now_tz, today_tz, to_tz, utcnow_aware

    now = now_tz()          # datetime مع timezone = AST
    today = today_tz()      # date بتوقيت AST (حد اليوم التجاري)
    dt_aware = to_tz(dt)    # حوّل naive UTC → aware AST
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Optional

try:
    # Python 3.9+ standard library
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from app.config import settings


@lru_cache(maxsize=4)
def _get_zone(name: str):
    """Cached ZoneInfo lookup (avoids repeated tzdata loads)."""
    if ZoneInfo is None:
        raise RuntimeError(
            "zoneinfo module is not available. Upgrade to Python 3.9+ or install backports.zoneinfo"
        )
    return ZoneInfo(name)


def app_tz():
    """Returns the configured application timezone (AST by default)."""
    return _get_zone(settings.DEFAULT_TIMEZONE)


def utcnow_aware() -> datetime:
    """UTC current time — aware (tzinfo=UTC). استبدل `datetime.utcnow()` ب ده."""
    return datetime.now(timezone.utc)


def now_tz(tz_name: Optional[str] = None) -> datetime:
    """Current datetime in the application timezone (AST by default), aware."""
    zone = _get_zone(tz_name) if tz_name else app_tz()
    return datetime.now(zone)


def today_tz(tz_name: Optional[str] = None) -> date:
    """Today's *business date* in the configured timezone.

    Use this — NOT `date.today()` — for any business-day boundaries like
    `inventory_date`, daily report cutoffs, or scheduler triggers.
    """
    return now_tz(tz_name).date()


def to_tz(dt: datetime, tz_name: Optional[str] = None) -> datetime:
    """
    يحوّل datetime إلى الـ timezone المحلي (AST افتراضياً).
    - لو الـ datetime naive، نفترض أنه UTC (الاصطلاح في الـ DB).
    - لو aware، نحوّله.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    zone = _get_zone(tz_name) if tz_name else app_tz()
    return dt.astimezone(zone)


def to_utc(dt: datetime) -> datetime:
    """
    يحوّل datetime إلى UTC للتخزين في الـ DB.
    - لو aware، يحوّل.
    - لو naive، نفترض أنه بالفعل UTC ونعيده كما هو (محافظين على التوافقية).
    """
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc)


def format_tz(dt: datetime, fmt: str = "%Y-%m-%d %H:%M %Z", tz_name: Optional[str] = None) -> str:
    """تنسيق datetime بتوقيت العرض (AST) للرسائل والتقارير."""
    return to_tz(dt, tz_name).strftime(fmt)
