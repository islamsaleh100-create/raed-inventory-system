"""
Auto-replenishment scheduler (native asyncio, AST-aware).

يشتغل إذا `settings.REPLENISHMENT_SCHEDULER_ENABLED=True`. كل يوم، في الساعة
المحدَّدة (افتراضياً 6:00 AM بتوقيت الرياض AST)، يمر على كل الفروع النشطة
ويولّد طلبية تلقائية بناءً على آخر جرد مُعتمد للفرع.

لماذا asyncio وليس APScheduler؟
- الخدمة بسيطة جداً (مهمة واحدة يومية). إضافة APScheduler = dependency زيادة
  + pool threads + تعقيد في لحظة shutdown.
- هنفضّل مهمة asyncio واحدة تعيش داخل lifespan الـ FastAPI مع ضمان
  idempotency (مش هيعمل طلبية للـ inventory نفسها مرتين بسبب الحماية في
  `generate_replenishment_order`).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.timezone import app_tz, now_tz
from app.database import SessionLocal
from app.models import (
    Branch,
    DailyInventory,
    InventoryStatus,
    User,
    UserRole,
    Role,
    RoleName,
)
from app.services.replenishment_service import generate_replenishment_order

logger = logging.getLogger(__name__)


def _next_run_at(
    hour: int, minute: int, *, from_dt: Optional[datetime] = None
) -> datetime:
    """Compute the next occurrence of hh:mm in the app timezone (AST)."""
    now = from_dt or now_tz()
    if now.tzinfo is None:
        now = now.replace(tzinfo=app_tz())
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return target


def _system_user(db: Session) -> Optional[User]:
    """
    Return a deterministic "system" user for generated orders.
    Prefers a super_admin; falls back to any admin.
    """
    user = (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(Role.name == RoleName.super_admin, User.is_deleted == False)  # noqa: E712
        .order_by(User.id.asc())
        .first()
    )
    if user:
        return user
    return (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(Role.name == RoleName.admin, User.is_deleted == False)  # noqa: E712
        .order_by(User.id.asc())
        .first()
    )


def run_auto_replenishment_once(db: Session, *, days_of_cover: int = 3) -> dict:
    """
    Execute one replenishment pass across all active branches.

    For each active branch: find the most recent *approved* inventory and ask
    `generate_replenishment_order` to create a draft order. The generator is
    idempotent per inventory, so repeated runs on the same day are safe.
    """
    system_user = _system_user(db)
    if system_user is None:
        logger.warning("No system user found for auto-replenishment — skipping run")
        return {"status": "skipped", "reason": "no_system_user"}

    branches = (
        db.query(Branch)
        .filter(Branch.active == True, Branch.is_deleted == False)  # noqa: E712
        .all()
    )
    created = 0
    skipped = 0
    errors: list[dict] = []

    for branch in branches:
        latest_approved = (
            db.query(DailyInventory)
            .filter(
                DailyInventory.branch_id == branch.id,
                DailyInventory.status == InventoryStatus.approved,
            )
            .order_by(DailyInventory.inventory_date.desc())
            .first()
        )
        if not latest_approved:
            skipped += 1
            continue
        try:
            order = generate_replenishment_order(
                db,
                inventory_id=latest_approved.id,
                user=system_user,
                days_of_cover=days_of_cover,
            )
            if order:
                created += 1
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Auto-replenishment failed for branch %s: %s", branch.id, exc
            )
            errors.append({"branch_id": branch.id, "error": str(exc)})
            db.rollback()

    return {
        "status": "completed",
        "created_orders": created,
        "skipped_branches": skipped,
        "errors": errors,
        "total_branches": len(branches),
    }


async def _scheduler_loop() -> None:
    """Long-running asyncio loop — sleeps until the next scheduled run."""
    hour = settings.REPLENISHMENT_SCHEDULE_HOUR
    minute = settings.REPLENISHMENT_SCHEDULE_MINUTE

    while True:
        next_run = _next_run_at(hour, minute)
        wait_s = max(1, int((next_run - now_tz()).total_seconds()))
        logger.info(
            "Auto-replenishment next run at %s (in %ss)",
            next_run.isoformat(),
            wait_s,
        )
        try:
            await asyncio.sleep(wait_s)
        except asyncio.CancelledError:
            logger.info("Auto-replenishment scheduler cancelled")
            raise

        db = SessionLocal()
        try:
            logger.info("Running auto-replenishment pass")
            result = run_auto_replenishment_once(db)
            logger.info("Auto-replenishment result: %s", result)
        except Exception:  # noqa: BLE001
            logger.exception("Auto-replenishment pass crashed; scheduler continues")
        finally:
            db.close()

        # Run quality/training reminders once a day as well
        db = SessionLocal()
        try:
            from app.services.quality_reminder_service import run_quality_training_reminders
            logger.info("Running quality/training reminder sweep")
            rem = run_quality_training_reminders(db)
            logger.info("Quality/training reminders result: %s", rem)
        except Exception:  # noqa: BLE001
            logger.exception("Quality/training reminders pass crashed; continuing")
        finally:
            db.close()

        # Run document expiry reminders (health certs, branch licenses, etc.)
        db = SessionLocal()
        try:
            from app.services.document_reminder_service import run_document_reminders
            logger.info("Running document expiry reminder sweep")
            doc_rem = run_document_reminders(db)
            logger.info("Document reminders result: %s", doc_rem)
        except Exception:  # noqa: BLE001
            logger.exception("Document reminders pass crashed; continuing")
        finally:
            db.close()

        # Small buffer so we don't re-schedule instantly inside the same minute
        await asyncio.sleep(60)


def start_scheduler(app) -> None:
    """Attach the scheduler task to the FastAPI app state (idempotent)."""
    if not settings.REPLENISHMENT_SCHEDULER_ENABLED:
        logger.info("Auto-replenishment scheduler disabled (set REPLENISHMENT_SCHEDULER_ENABLED=true)")
        return
    existing = getattr(app.state, "replenishment_scheduler_task", None)
    if existing and not existing.done():
        return
    app.state.replenishment_scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info(
        "Auto-replenishment scheduler started (runs daily at %02d:%02d %s)",
        settings.REPLENISHMENT_SCHEDULE_HOUR,
        settings.REPLENISHMENT_SCHEDULE_MINUTE,
        settings.DEFAULT_TIMEZONE,
    )


def stop_scheduler(app) -> None:
    """Cancel the scheduler task on shutdown."""
    task = getattr(app.state, "replenishment_scheduler_task", None)
    if task and not task.done():
        task.cancel()
