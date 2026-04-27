"""
Raed Branch Daily Inventory & Auto Replenishment System
FastAPI Application Entry Point
"""
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
import time
from app.config import settings
from app.core.logging_config import setup_logging
from app.core.errors import AppError, error_response_payload
from app.core.audit_permissions import is_read_only
from app.core.security import decode_access_token
from app.core.request_context import RequestIdMiddleware
from app.core.sentry_init import init_sentry
from app.database import SessionLocal, get_db
from app.models import Role, User, UserRole
from app.routers import auth, users, master, inventory, orders, dashboard, stock, ledger, reports, alerts, export, audit, audit_findings, import_data, quality, training, delivery_analytics, notifications, documents, settings as settings_router, sales_channels, branch_requests, production_orders, warehouse_lines, delivery_orders, supply_chain, evaluations, procurement, branch_employees
from app.core.tenant import TenantMiddleware
from app.services.idempotency_service import cleanup_expired_idempotency_requests
from app.services.scheduler_service import start_scheduler, stop_scheduler
from app.startup_schema import ensure_local_schema_compatibility

# Initialise logging before any other module emits log records
setup_logging()

# Initialise Sentry SDK (no-op if SENTRY_DSN is unset or sentry-sdk missing)
init_sentry()

logger = logging.getLogger(__name__)
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"

app = FastAPI(
    title=settings.APP_NAME,
    description="Branch Daily Inventory & Auto Replenishment System for Raed Food Corporation",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── Rate limiting (slowapi) ───────────────────────────────────────────────────
# الـ Limiter instance مشترك مع الـ routers عبر app/core/limiter.py
# حتى نتمكّن من تطبيق حدود مخصّصة على routes معيّنة (مثل /auth/login).
from app.core.limiter import limiter as _shared_limiter  # noqa: E402

if _shared_limiter is not None:
    try:
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware

        app.state.limiter = _shared_limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)
        logger.info("Rate limiting enabled: default=%s, auth=%s",
                    settings.RATE_LIMIT_DEFAULT, settings.RATE_LIMIT_AUTH)
    except ImportError:
        logger.warning("slowapi not installed — rate limiting disabled. Run: pip install slowapi")

# CORS — مسموح فقط بالـ methods والـ headers اللازمة
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Idempotency-Key"],
)

# Tenant context (pass-through in single-tenant mode)
app.add_middleware(TenantMiddleware)

# Request-ID middleware — adds X-Request-ID to response and log records.
# يُضاف بعد الباقي ليكون الـ outermost (أول من يدخل، آخر من يخرج) فيكتب الـ header
# قبل أن تعود الـ response للعميل.
app.add_middleware(RequestIdMiddleware)


async def _idempotency_cleanup_loop():
    while True:
        await asyncio.sleep(settings.IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            deleted_count = cleanup_expired_idempotency_requests(db)
            if deleted_count:
                logger.info("Cleaned up %s expired idempotency records", deleted_count)
        finally:
            db.close()


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def block_writes_for_internal_auditor(request: Request, call_next):
    if request.method not in {"POST", "PATCH", "PUT", "DELETE"}:
        return await call_next(request)

    path = request.url.path or ""
    if path in {"/api/v1/auth/login", "/api/v1/auth/change-password"}:
        return await call_next(request)
    if path.startswith("/api/v1/audit/findings"):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return await call_next(request)

    token = auth_header.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    user_id = payload.get("sub") if payload else None
    if not user_id:
        return await call_next(request)

    override_db_factory = request.app.dependency_overrides.get(get_db)
    db = override_db_factory() if override_db_factory else SessionLocal()
    should_close = override_db_factory is None
    try:
        user = (
            db.query(User)
            .filter(User.id == int(user_id), User.is_deleted == False)
            .first()
        )
        if not user:
            return await call_next(request)
        roles = [role_name.value if hasattr(role_name, "value") else str(role_name) for (role_name,) in (
            db.query(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user.id)
            .all()
        )]
        if is_read_only(roles):
            return JSONResponse(status_code=403, content={"detail": "Internal auditor is read-only"})
    finally:
        if should_close:
            db.close()
    return await call_next(request)


def _ensure_training_templates_seeded() -> None:
    """
    I5/J1 safety net: if the training template tables are empty (migration
    didn't run, or seed was skipped), seed them on startup so the
    Training Assessment page never appears without items.
    Idempotent: skipped if items already exist.
    """
    try:
        from app.models import TrainingTemplate, TrainingTemplateItem
    except Exception:
        logger.exception("J1: training models not importable; skipping auto-seed")
        return

    db = SessionLocal()
    try:
        has_items = db.query(TrainingTemplateItem).limit(1).first() is not None
        if has_items:
            return
        # Either no templates, or templates exist but items missing → (re)seed
        try:
            import os, sys
            backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if backend_root not in sys.path:
                sys.path.insert(0, backend_root)
            from seed_quality_training import seed_training_templates  # type: ignore
        except Exception:
            logger.exception("J1: seed_quality_training not importable; training page may be empty")
            return
        try:
            seed_training_templates(db)
            logger.info("J1: training templates auto-seeded on startup")
        except Exception:
            logger.exception("J1: auto-seed failed; continuing")
            db.rollback()
    finally:
        db.close()


def _ensure_evaluation_templates_seeded() -> None:
    try:
        from app.models import EvaluationTemplate
    except Exception:
        logger.exception("Evaluation template models not importable; skipping auto-seed")
        return

    db = SessionLocal()
    try:
        if db.query(EvaluationTemplate).limit(1).first() is not None:
            return
        from app.services.evaluation_seed_service import seed_evaluation_templates
        created = seed_evaluation_templates(db)
        if created:
            logger.info("Evaluation templates auto-seeded: %s", created)
    except Exception:
        logger.exception("Evaluation templates auto-seed failed; continuing")
        db.rollback()
    finally:
        db.close()


def _ensure_quality_checklists_seeded() -> None:
    try:
        from app.models import QualityVisitSection
    except Exception:
        logger.exception("Quality checklist models not importable; skipping auto-seed")
        return

    db = SessionLocal()
    try:
        # Seed missing brand-specific checklists only; do not overwrite legacy global checklist.
        from app.services.quality_checklist_seed_service import ensure_quality_checklists_seeded
        created = ensure_quality_checklists_seeded(db)
        if any(created.values()):
            logger.info("Quality checklist brand seeds added: %s", created)
    except Exception:
        logger.exception("Quality checklist auto-seed failed; continuing")
        db.rollback()
    finally:
        db.close()


def _run_startup_seed_tasks() -> None:
    """
    Run non-critical seed/repair tasks outside the FastAPI startup critical path.

    Railway marks the service unhealthy if the app takes too long to start
    serving ``/health``. These tasks are helpful, but they should not block
    the HTTP server from booting.
    """
    try:
        _ensure_training_templates_seeded()
    except Exception:
        logger.exception("J1: auto-seed wrapper crashed; continuing")
    try:
        _ensure_evaluation_templates_seeded()
    except Exception:
        logger.exception("Evaluation template auto-seed wrapper crashed; continuing")
    try:
        _ensure_quality_checklists_seeded()
    except Exception:
        logger.exception("Quality checklist auto-seed wrapper crashed; continuing")


async def _startup_seed_background_task() -> None:
    logger.info("Startup background seed tasks scheduled")
    await asyncio.to_thread(_run_startup_seed_tasks)
    logger.info("Startup background seed tasks completed")


@app.on_event("startup")
async def startup_event():
    try:
        ensure_local_schema_compatibility()
    except Exception:
        logger.exception("Startup schema compatibility check failed; continuing without local schema patching")
    app.state.startup_seed_task = asyncio.create_task(_startup_seed_background_task())
    app.state.idempotency_cleanup_task = asyncio.create_task(_idempotency_cleanup_loop())
    start_scheduler(app)


@app.on_event("shutdown")
async def shutdown_event():
    seed_task = getattr(app.state, "startup_seed_task", None)
    if seed_task and not seed_task.done():
        seed_task.cancel()
    task = getattr(app.state, "idempotency_cleanup_task", None)
    if task:
        task.cancel()
    stop_scheduler(app)


# Global exception handler
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response_payload(exc),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the full exception with traceback + request id so operators can
    # correlate a user-facing error with server logs without leaking
    # stack details to the client.
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled exception on %s %s (request_id=%s): %s",
        request.method, request.url.path, request_id, exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "internal_server_error",
            "message": "Internal server error",
            "detail": None,
            "request_id": request_id,
        }
    )


# Register routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(master.router)
app.include_router(inventory.router)
app.include_router(orders.router)
app.include_router(dashboard.router)
app.include_router(stock.router)
app.include_router(ledger.router)
app.include_router(reports.router)
app.include_router(alerts.router)
app.include_router(export.router)
app.include_router(audit.router)
app.include_router(audit_findings.router)
app.include_router(import_data.router)
app.include_router(quality.router)
app.include_router(training.router)
app.include_router(delivery_analytics.router)
app.include_router(sales_channels.router)
app.include_router(branch_requests.router)
app.include_router(production_orders.router)
app.include_router(warehouse_lines.router)
app.include_router(delivery_orders.router)
app.include_router(supply_chain.router)
app.include_router(evaluations.router)
app.include_router(procurement.router)
app.include_router(branch_employees.router)
app.include_router(notifications.router)
app.include_router(documents.router)
app.include_router(settings_router.router)


@app.get("/", include_in_schema=False)
def root():
    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/api/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/api/v1/health")
def health_check_v1():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
    }


@app.get("/api/v1/ready")
def readiness_check():
    """
    Readiness: verifies database connectivity. Use for load balancers after migrations;
    liveness can stay on /health or /api/v1/health (no DB).
    """
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "ok",
            "environment": settings.ENVIRONMENT,
            "timestamp": time.time(),
        }
    except Exception as exc:  # noqa: BLE001 — return 503, not 500 trace to client
        logger.warning("readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "error",
                "environment": settings.ENVIRONMENT,
                "message": "Database connectivity check failed",
            },
        )
    finally:
        db.close()


@app.get("/api/v1/meta")
def app_meta():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_app(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "not_found",
                "message": "Endpoint not found",
                "detail": None,
            },
        )

    requested_path = FRONTEND_DIST_DIR / full_path
    if requested_path.is_file():
        return FileResponse(requested_path)

    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        status_code=404,
        content={
            "error_code": "frontend_not_built",
            "message": "Frontend build output not found",
            "detail": str(FRONTEND_DIST_DIR),
        },
    )
