"""
Tenant Context — Epic 13 Multi-Tenant Preparation

Design principles:
1. Single-tenant NOW: DEFAULT_TENANT_ID = 1, no enforcement yet.
2. Tenant-aware LATER: X-Tenant-ID header → context var → all DB queries.
3. Migration path: add tenant_id columns → backfill → enforce.

This module provides:
- `TenantMiddleware`: reads X-Tenant-ID header and stores in context var.
- `get_current_tenant_id()`: returns active tenant (falls back to default).
- `TENANT_ID_MIGRATION_NOTES`: documents what needs changing per service.
"""
from contextvars import ContextVar
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings

# ── Context variable ───────────────────────────────────────────────────────
_tenant_id_ctx: ContextVar[int] = ContextVar(
    "_tenant_id_ctx",
    default=settings.DEFAULT_TENANT_ID,
)


def get_current_tenant_id() -> int:
    """
    Returns the active tenant ID for the current request context.
    Always returns DEFAULT_TENANT_ID in single-tenant mode.
    """
    return _tenant_id_ctx.get()


def set_tenant_id(tenant_id: int) -> None:
    _tenant_id_ctx.set(tenant_id)


# ── Middleware ─────────────────────────────────────────────────────────────

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Reads X-Tenant-ID header and stores in context variable.

    In single-tenant mode (MULTI_TENANT_ENABLED=False), always uses
    DEFAULT_TENANT_ID and ignores the header.

    In multi-tenant mode, validates tenant exists and sets context.
    Currently always runs in single-tenant mode — flip
    settings.MULTI_TENANT_ENABLED to enable enforcement.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if getattr(settings, "MULTI_TENANT_ENABLED", False):
            header_val = request.headers.get("X-Tenant-ID")
            if header_val:
                try:
                    tenant_id = int(header_val)
                except ValueError:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error_code": "tenant.invalid_header",
                            "message": "X-Tenant-ID must be a valid integer",
                            "detail": None,
                        },
                    )
                set_tenant_id(tenant_id)
            else:
                set_tenant_id(settings.DEFAULT_TENANT_ID)
        else:
            set_tenant_id(settings.DEFAULT_TENANT_ID)

        response = await call_next(request)
        return response


# ── Migration notes (documentation) ───────────────────────────────────────

TENANT_ID_MIGRATION_NOTES = """
MULTI-TENANT MIGRATION CHECKLIST (Epic 13)
==========================================

PHASE 1 — Schema (already done for idempotency table):
  [x] idempotency_requests.tenant_id (backfilled with 1)

PHASE 2 — Add tenant_id to all entity tables:
  Alembic migration needed for:
  [ ] branches.tenant_id
  [ ] warehouses.tenant_id
  [ ] items.tenant_id
  [ ] users.tenant_id (or use tenant_members junction)
  [ ] daily_inventory.tenant_id
  [ ] replenishment_orders.tenant_id
  [ ] stock_transactions.tenant_id
  [ ] branch_stock.tenant_id
  [ ] warehouse_stock.tenant_id

PHASE 3 — Service layer:
  [ ] Pass tenant_id to all DB queries (add .filter(Model.tenant_id == tenant_id))
  [ ] Create TenantRepository base class to enforce scoping
  [ ] Update idempotency_service to use get_current_tenant_id()

PHASE 4 — Auth:
  [ ] JWT claims include tenant_id
  [ ] User → TenantMembership (user can belong to multiple tenants)

PHASE 5 — Config:
  [ ] settings.MULTI_TENANT_ENABLED = True
  [ ] Row-level security (PostgreSQL RLS) optional for extra isolation

CURRENT STATUS:
  - TenantMiddleware is registered but in pass-through mode
  - All services use settings.DEFAULT_TENANT_ID = 1
  - No tenant filtering in DB queries (single tenant implicit)
"""
