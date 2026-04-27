"""
Pack C / Phase 1 — Seed Sales Channels (idempotent).

Seeds the 10 operational channels per SPEC v3:
    7 delivery_apps: Jahez, HungerStation, Keeta, Ninja, The Chefz, Noon, ToYou
    3 payment_methods: Cash, Mada, Mastercard

Default commission rates are placeholders that the sales_manager can later
adjust via the admin UI (they reflect typical Saudi market ranges but the
exact figure per contract should be confirmed by management).

Run:
    python seed_sales_channels.py

ASCII-safe output (works on Windows cp1256 terminals).
"""
from decimal import Decimal

from app.database import SessionLocal
from app.models.sales_channels import SalesChannel


# (code, name_ar, name_en, type, commission_rate, sort_order)
CHANNELS = [
    # ─── Delivery apps (7) ────────────────────────────────────
    ("jahez",         "جاهز",         "Jahez",         "delivery_app",   Decimal("15.00"), 10),
    ("hungerstation", "هنقرستيشن",    "HungerStation", "delivery_app",   Decimal("17.00"), 20),
    ("keeta",         "كيتا",         "Keeta",         "delivery_app",   Decimal("20.00"), 30),
    ("ninja",         "نينجا",        "Ninja",         "delivery_app",   Decimal("15.00"), 40),
    ("the_chefz",     "ذا شيفز",      "The Chefz",     "delivery_app",   Decimal("20.00"), 50),
    ("noon_food",     "نون فوود",     "Noon Food",     "delivery_app",   Decimal("20.00"), 60),
    ("toyou",         "تو يو",        "ToYou",         "delivery_app",   Decimal("20.00"), 70),
    # Koinz pending — will be added in a separate revision once management decides.

    # ─── Payment methods (3) ──────────────────────────────────
    ("cash",          "كاش",          "Cash",          "payment_method", None,             100),
    ("mada",          "مدى",          "Mada",          "payment_method", None,             110),
    ("mastercard",    "ماستركارد",    "Mastercard",    "payment_method", None,             120),
]


def seed() -> None:
    db = SessionLocal()
    try:
        created = 0
        skipped = 0
        for code, ar, en, ctype, rate, order in CHANNELS:
            existing = db.query(SalesChannel).filter(SalesChannel.code == code).first()
            if existing:
                print(f"[skip]   {code:14s}  ({ctype}) already exists")
                skipped += 1
                continue
            db.add(SalesChannel(
                code=code,
                name_ar=ar,
                name_en=en,
                type=ctype,
                commission_rate=rate,
                is_active=True,
                sort_order=order,
            ))
            print(f"[create] {code:14s}  ({ctype})  rate={rate}")
            created += 1
        db.commit()
        print("-" * 50)
        print(f"Done. created={created}, skipped={skipped}, total={len(CHANNELS)}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
