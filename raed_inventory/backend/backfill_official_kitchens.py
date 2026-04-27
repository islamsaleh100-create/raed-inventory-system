"""
Create official Kitchen rows (Dammam / Riyadh) and link all active KitchenSection rows.

Idempotent. Run after Alembic revision z6a7b8c9d0e1 (kitchens + kitchen_kitchen_sections).

Usage (from backend/):
  python backfill_official_kitchens.py
"""
from __future__ import annotations

from app.database import SessionLocal
from app.models import Kitchen, KitchenSection

OFFICIAL = (
    ("Official Kitchen — Dammam", "Dammam"),
    ("Official Kitchen — Riyadh", "Riyadh"),
)


def main() -> None:
    db = SessionLocal()
    try:
        sections = (
            db.query(KitchenSection)
            .filter(KitchenSection.active == True)  # noqa: E712
            .order_by(KitchenSection.id)
            .all()
        )
        linked = 0
        for name, city in OFFICIAL:
            k = db.query(Kitchen).filter(Kitchen.name == name).first()
            if not k:
                k = Kitchen(name=name, city=city, active=True)
                db.add(k)
                db.flush()
            for sec in sections:
                if sec not in k.sections:
                    k.sections.append(sec)
                    linked += 1
        db.commit()
        kitchens = db.query(Kitchen).filter(Kitchen.name.in_([n for n, _ in OFFICIAL])).all()
        print(f"kitchens_upserted={len(kitchens)} section_links_added_this_run={linked} sections_total={len(sections)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
