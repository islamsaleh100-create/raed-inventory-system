"""
Row-level locking helpers.

`lock_row()` should only request `SELECT ... FOR UPDATE` on databases that
actually honour it. SQLite ignores row-level locks, so callers should not rely
on this helper to provide concurrency safety there.
"""
import logging

from sqlalchemy.orm import Query

from app.config import settings


_LOG = logging.getLogger(__name__)
_SQLITE_WARNING_EMITTED = False


def _supports_row_locks() -> bool:
    """Return True only for dialects that honour SELECT FOR UPDATE."""
    return not settings.DATABASE_URL.lower().startswith("sqlite")


def lock_row(query: Query, *, skip_locked: bool = False) -> Query:
    """
    Add a row lock to the query before evaluation.

    On SQLite this is a no-op because row-level locks are not supported.
    """
    global _SQLITE_WARNING_EMITTED
    if not _supports_row_locks():
        if not _SQLITE_WARNING_EMITTED:
            _LOG.warning("SQLite in use: lock_row() is a no-op and is not safe for concurrent writers.")
            _SQLITE_WARNING_EMITTED = True
        return query
    if skip_locked:
        return query.with_for_update(skip_locked=True)
    return query.with_for_update()
