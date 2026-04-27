"""
Shared slowapi Limiter instance.

يُستورد من app/main.py لتفعيل الـ middleware، ومن الـ routers (مثل auth)
لتطبيق حدود مخصّصة عبر الـ decorator: @limiter.limit("5/minute").

ملاحظة: عندما يكون RATE_LIMIT_ENABLED=False أو slowapi غير مثبّت،
`limiter` يكون None — والـ decorator الآمن في هذا الملف يصبح no-op.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from app.config import settings

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    _slowapi_available = True
except ImportError:  # pragma: no cover
    Limiter = None  # type: ignore[assignment]
    get_remote_address = None  # type: ignore[assignment]
    _slowapi_available = False

# Fail-loud in production if limits are required but slowapi is missing.
if not _slowapi_available and settings.RATE_LIMIT_ENABLED and settings.is_production:
    raise RuntimeError(
        "RATE_LIMIT_ENABLED=true في production لكن slowapi غير مثبّت. "
        "شغّل: pip install slowapi==0.1.9"
    )

# In local/staging: explicit warning instead of silent no-op.
if not _slowapi_available and settings.RATE_LIMIT_ENABLED:
    logging.getLogger(__name__).warning(
        "RATE_LIMIT_ENABLED=true لكن slowapi غير مثبّت — "
        "الحدود معطّلة. شغّل: pip install slowapi==0.1.9"
    )


limiter: Optional[Any] = None

if _slowapi_available and settings.RATE_LIMIT_ENABLED:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.RATE_LIMIT_DEFAULT],
    )


def limit(rate: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator آمن يستدعي `limiter.limit(rate)` إذا كان الـ limiter مفعَّلاً،
    وإلا يرجِع الدالة كما هي بلا تأثير (no-op).

    مثال:
        from app.core.limiter import limit
        from app.config import settings

        @router.post("/login")
        @limit(settings.RATE_LIMIT_AUTH)   # e.g. "20/minute"
        def login(request: Request, ...):
            ...
    """
    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if limiter is None:
            return fn
        return limiter.limit(rate)(fn)

    return _decorator
