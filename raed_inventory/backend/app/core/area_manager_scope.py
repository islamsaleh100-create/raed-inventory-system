"""
Area Manager scope — single source of truth via AreaManagerAssignment.

Scope rule: active assignment on (user_id, city, brand_id).
A branch is in scope when Branch.city matches assignment.city exactly and
the branch carries that brand via branch_brands.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Set

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models import AreaManagerAssignment, Branch, BranchBrand, User


def get_active_area_manager_assignments(user: User, db: Session) -> List[AreaManagerAssignment]:
    now = datetime.utcnow()
    return (
        db.query(AreaManagerAssignment)
        .filter(
            AreaManagerAssignment.user_id == user.id,
            AreaManagerAssignment.active == True,  # noqa: E712
            or_(
                AreaManagerAssignment.ended_at.is_(None),
                AreaManagerAssignment.ended_at > now,
            ),
        )
        .all()
    )


def get_area_manager_branch_ids(user: User, db: Session) -> List[int]:
    """Branch ids visible to an area manager (city + brand assignments)."""
    assignments = get_active_area_manager_assignments(user, db)
    if not assignments:
        return []

    branch_ids: Set[int] = set()
    for assignment in assignments:
        rows = (
            db.query(Branch.id)
            .join(BranchBrand, BranchBrand.branch_id == Branch.id)
            .filter(
                Branch.is_deleted == False,  # noqa: E712
                Branch.active == True,  # noqa: E712
                Branch.city == assignment.city,
                BranchBrand.brand_id == assignment.brand_id,
            )
            .all()
        )
        branch_ids.update(row[0] for row in rows)
    return sorted(branch_ids)


def branch_in_area_manager_scope(
    user: User,
    db: Session,
    branch_id: int,
    brand_id: Optional[int] = None,
) -> bool:
    assignments = get_active_area_manager_assignments(user, db)
    if not assignments:
        return False

    branch = (
        db.query(Branch)
        .filter(Branch.id == branch_id, Branch.is_deleted == False)  # noqa: E712
        .first()
    )
    if not branch:
        return False

    if brand_id is not None:
        return any(
            assignment.city == branch.city and assignment.brand_id == brand_id
            for assignment in assignments
        )

    branch_brand_ids = {
        row[0]
        for row in db.query(BranchBrand.brand_id)
        .filter(BranchBrand.branch_id == branch_id)
        .all()
    }
    if not branch_brand_ids:
        return False

    return any(
        assignment.city == branch.city and assignment.brand_id in branch_brand_ids
        for assignment in assignments
    )


def apply_area_manager_branch_filter(q: Query, user: User, db: Session, branch_column):
    """Restrict a query to branches in the area manager's assignments."""
    branch_ids = get_area_manager_branch_ids(user, db)
    if not branch_ids:
        return q.filter(branch_column.in_([]))
    return q.filter(branch_column.in_(branch_ids))
