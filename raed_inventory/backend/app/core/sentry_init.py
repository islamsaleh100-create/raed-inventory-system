"""
Sentry SDK initialization (optional).

يُفعَّل فقط إذا كان متغيّر البيئة SENTRY_DSN مُعيَّنًا. في حال غيابه أو
غياب حزمة sentry-sdk تتخطّى الدالة بهدوء بدون أن تكسر startup.

Environments:
  - production / staging: traces_sample_rate = 0.1
  - local:                traces_sample_rate = 0.0 (off by default)

Integration: sanitizer يُسقط الـ body من الطلبات (PII safety).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """
    Initialise Sentry SDK if configured. Returns True on success, False otherwise.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("SENTRY_DSN not set — Sentry disabled")
        return False

    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # type: ignore
        from sentry_sdk.integrations.logging import LoggingIntegration  # type: ignore
    except ImportError:
        logger.warning(
            "sentry-sdk not installed — set SENTRY_DSN and `pip install sentry-sdk[fastapi]` to enable"
        )
        return False

    environment = os.getenv("ENVIRONMENT", "local")
    release = os.getenv("APP_VERSION", "1.0.0")
    sample_rate = 0.1 if environment in {"production", "staging"} else 0.0

    def _strip_pii(event, hint):  # noqa: ANN001
        """Drop request body / headers likely to contain tokens or passwords."""
        request = event.get("request") or {}
        request.pop("data", None)
        request.pop("cookies", None)
        headers = request.get("headers") or {}
        for h in ("authorization", "cookie", "x-idempotency-key"):
            headers.pop(h, None)
            headers.pop(h.title(), None)
        if request:
            event["request"] = request
        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=sample_rate,
        send_default_pii=False,
        before_send=_strip_pii,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )

    logger.info(
        "Sentry initialised (env=%s, release=%s, traces=%.2f)",
        environment, release, sample_rate,
    )
    return True
