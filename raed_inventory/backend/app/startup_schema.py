from sqlalchemy import inspect, text
import logging

from app.database import engine
from app.models import Base, IdempotencyRequest


logger = logging.getLogger(__name__)

# NOTE: BranchItemAvailability and ItemChangeRequest were moved from this file
# into Alembic migration c1d2e3f4a5b6 (2026-06-14). They are no longer created
# at runtime — use `alembic upgrade head` to create them on a fresh database.

SQLITE_COMPAT_ALTERS = {
    "items": [
        ("item_type", "ALTER TABLE items ADD COLUMN item_type VARCHAR(50) NOT NULL DEFAULT 'raw_material'"),
        ("storage_type", "ALTER TABLE items ADD COLUMN storage_type VARCHAR(50) NOT NULL DEFAULT 'ambient'"),
        ("purchase_unit_id", "ALTER TABLE items ADD COLUMN purchase_unit_id INTEGER"),
        ("supply_unit_id", "ALTER TABLE items ADD COLUMN supply_unit_id INTEGER"),
        ("conversion_ratio", "ALTER TABLE items ADD COLUMN conversion_ratio NUMERIC(12, 4) NOT NULL DEFAULT 1"),
        ("shelf_life_days", "ALTER TABLE items ADD COLUMN shelf_life_days INTEGER NOT NULL DEFAULT 0"),
        ("source_type", "ALTER TABLE items ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'WAREHOUSE'"),
        ("default_source", "ALTER TABLE items ADD COLUMN default_source VARCHAR(20) NOT NULL DEFAULT 'WAREHOUSE'"),
        ("kitchen_section_id", "ALTER TABLE items ADD COLUMN kitchen_section_id INTEGER"),
        ("visible_in_branch_ui", "ALTER TABLE items ADD COLUMN visible_in_branch_ui BOOLEAN NOT NULL DEFAULT 1"),
    ],
    "replenishment_orders": [
        ("cancelled_at", "ALTER TABLE replenishment_orders ADD COLUMN cancelled_at DATETIME"),
        ("cancelled_by", "ALTER TABLE replenishment_orders ADD COLUMN cancelled_by INTEGER"),
        ("cancellation_reason", "ALTER TABLE replenishment_orders ADD COLUMN cancellation_reason TEXT"),
    ],
}


def ensure_local_schema_compatibility() -> None:
    """
    SQLite-only compatibility layer executed at app startup.

    This helper is intentionally limited to:
    1. Creating the idempotency_requests table if an old local SQLite DB lacks it
       (SQLite only — PostgreSQL gets this via Alembic).
    2. Patching a few legacy SQLite columns that pre-date proper Alembic history.

    All application feature tables must be managed by Alembic migrations.
    Do NOT add new tables here — add a migration instead.
    """
    inspector = inspect(engine)
    is_sqlite = str(engine.url).startswith("sqlite")

    if not is_sqlite:
        # On PostgreSQL, runtime schema creation is disabled entirely.
        # All tables must exist via `alembic upgrade head`.
        return

    with engine.begin() as conn:
        existing_before = set(inspector.get_table_names())
        target_tables = [IdempotencyRequest.__table__]
        Base.metadata.create_all(bind=conn, tables=target_tables, checkfirst=True)
        created = [t.name for t in target_tables if t.name not in existing_before]
        if created:
            logger.warning(
                "Startup schema: created %d legacy compatibility tables outside Alembic: %s. "
                "TODO: retire this fallback once all local DBs are migrated.",
                len(created), created,
            )

        if not str(engine.url).startswith("sqlite"):
            return

        for table_name, operations in SQLITE_COMPAT_ALTERS.items():
            if not inspector.has_table(table_name):
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in operations:
                if column_name not in existing_columns:
                    conn.execute(text(ddl))
                    logger.warning(
                        "Startup schema: added legacy compatibility column %s.%s outside Alembic. "
                        "TODO: retire after local DB migration cleanup.",
                        table_name, column_name,
                    )
