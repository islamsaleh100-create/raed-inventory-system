"""
Deactivate supply-chain demo branches (hide from active_only selectors) and optionally
remap users still assigned to those branches to the nearest official branch (same city
+ overlapping brand).

Idempotent — safe to run multiple times.

Run from backend/:
    python finalize_demo_branch_transition.py
    python finalize_demo_branch_transition.py --dry-run
    python finalize_demo_branch_transition.py --no-remap-users

Requires: official branches seeded (seed_official_branches.py) for remap to find targets.
Demo branch codes are defined alongside DEMO_BRANCHES in seed_supply_chain_demo.py
(DEMO_BRANCH_CODES).

Strategy: set Branch.active = False (never sets is_deleted) so FK history and admin
master list (active_only=false) remain intact; Supply Chain UI uses active_only=true.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import func

from app.database import SessionLocal
from app.models import Branch, BranchBrand, User

from seed_supply_chain_demo import DEMO_BRANCH_CODES


def _find_replacement_branch(db, demo_branch: Branch) -> Branch | None:
    """Smallest-id active branch sharing city (case-insensitive) and a branch_brand with demo branch."""
    brand_ids = [row.brand_id for row in demo_branch.branch_brands]
    if not brand_ids:
        return None
    city = (demo_branch.city or "").strip().lower()
    if not city:
        return None
    return (
        db.query(Branch)
        .join(BranchBrand, BranchBrand.branch_id == Branch.id)
        .filter(
            Branch.is_deleted == False,  # noqa: E712
            Branch.active == True,  # noqa: E712
            Branch.branch_code.notin_(DEMO_BRANCH_CODES),
            func.lower(func.trim(Branch.city)) == city,
            BranchBrand.brand_id.in_(brand_ids),
        )
        .order_by(Branch.id.asc())
        .first()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Deactivate demo branches and remap users.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without committing.")
    parser.add_argument("--no-remap-users", action="store_true", help="Only deactivate branches.")
    args = parser.parse_args()

    db = SessionLocal()
    deactivated: list[str] = []
    remapped: list[str] = []
    warnings: list[str] = []

    try:
        demo_rows = (
            db.query(Branch)
            .filter(Branch.branch_code.in_(DEMO_BRANCH_CODES), Branch.is_deleted == False)  # noqa: E712
            .all()
        )
        for br in demo_rows:
            if br.active:
                deactivated.append(br.branch_code)
                if not args.dry_run:
                    br.active = False

        if not args.no_remap_users:
            demo_ids = {b.id for b in demo_rows}
            users = (
                db.query(User)
                .filter(User.branch_id.in_(demo_ids), User.is_deleted == False)  # noqa: E712
                .all()
            )
            for u in users:
                br = next((b for b in demo_rows if b.id == u.branch_id), None)
                if not br:
                    continue
                replacement = _find_replacement_branch(db, br)
                if replacement:
                    remapped.append(f"{u.username} ({u.id}): {br.branch_code} -> {replacement.branch_code}")
                    if not args.dry_run:
                        u.branch_id = replacement.id
                else:
                    warnings.append(
                        f"user {u.username} (id={u.id}) remains on inactive demo branch {br.branch_code} "
                        f"— no active official branch with same city + brand"
                    )

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print(f"demo_branch_codes={sorted(DEMO_BRANCH_CODES)}")
        print(f"deactivated_count={len(deactivated)}")
        for c in sorted(deactivated):
            print(f"  deactivated: {c}")
        print(f"remapped_users={len(remapped)}")
        for line in remapped:
            print(f"  {line}")
        for w in warnings:
            print(f"  WARNING: {w}")
        if args.dry_run:
            print("(dry-run: no database changes committed)")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
