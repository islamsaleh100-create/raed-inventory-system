"""Seed training templates (barista + branch manager) - I5."""

from __future__ import annotations

import logging
import os
import sys

from alembic import op
import sqlalchemy as sa


revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


log = logging.getLogger(__name__)


def _backend_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))


def upgrade() -> None:
    backend_root = _backend_root()
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    required_tables = {
        "training_templates",
        "training_template_sections",
        "training_template_items",
    }
    missing = sorted(required_tables - set(inspector.get_table_names()))
    if missing:
        log.warning("I5: training template seed skipped because tables are missing: %s", missing)
        return

    try:
        from seed_quality_training import seed_training_templates  # type: ignore
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "I5: seed_quality_training not importable (%s). "
            "Templates can be seeded later with `python seed_quality_training.py`.",
            exc,
        )
        return

    from sqlalchemy.orm import Session

    session = Session(bind=bind)
    try:
        seed_training_templates(session)
        session.flush()
        log.info("I5: training templates seeded (barista + branch manager)")
    except Exception as exc:  # noqa: BLE001
        # Do not rollback the outer Alembic transaction. Just skip the seed.
        log.warning("I5: training template seed skipped (%s)", exc)
    finally:
        session.close()


def downgrade() -> None:
    pass
