"""
Request-ID context + middleware.

هدفه: إلحاق UUID لكل طلب HTTP حتى نتمكّن من تتبّع الطلب عبر عدة خدمات
(backend log lines → Sentry → reverse-proxy logs). يُضاف:
  - Header في الـ response: X-Request-ID
  - Field في كل سطر لوج JSON: request_id
  - Tag في Sentry (لو مفعّل): request_id
"""
from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ContextVar مرئي داخل نفس الـ async task — يسمح للـ logging filter بقراءته
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


def get_request_id() -> str:
    """Return the current request's ID (or '-' outside of a request)."""
    return _request_id_var.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    - يُولّد request_id جديد لكل طلب (أو يعتمد على X-Request-ID من العميل إذا أُرسل).
    - يخزّنه في ContextVar ليظهر في كل سطر لوج داخل الطلب.
    - يُرجع X-Request-ID في الـ response header للعميل/الـ proxy.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get("X-Request-ID")
        request_id = incoming or uuid.uuid4().hex
        token = _request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestIdLogFilter(logging.Filter):
    """Injects `request_id` into every LogRecord so formatters can emit it."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = get_request_id()
        return True
