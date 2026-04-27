"""
Sales Channels permissions — Model C (2026-04-24).

Returns True if the given user has the stated capability. Each predicate
takes `roles: Iterable[str]` so it can be called from both router
dependencies and service-layer checks without needing the ORM User.

Central rule: super_admin always returns True.
admin must be granted explicitly by each capability predicate.
"""
from typing import Iterable


_PLATFORM_ADMINS = {"super_admin"}


def _as_set(roles: Iterable[str]) -> set[str]:
    return set(roles or ())


def _is_platform_admin(roles: Iterable[str]) -> bool:
    return bool(_as_set(roles) & _PLATFORM_ADMINS)


def can_create_daily_sales(roles: Iterable[str]) -> bool:
    """Enter daily sales for a branch (branch_manager own, area_manager region)."""
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(r & {"branch_manager", "area_manager", "admin"})


def can_edit_daily_sales(roles: Iterable[str]) -> bool:
    """Coarse gate at the PATCH endpoint level. Service layer enforces window rules."""
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(r & {"branch_manager", "area_manager", "sales_manager", "admin"})


def can_read_daily_sales(roles: Iterable[str]) -> bool:
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(
        r & {"branch_manager", "area_manager", "operations_manager", "sales_manager", "admin", "internal_auditor"}
    )


def can_manage_statements(roles: Iterable[str]) -> bool:
    """Upload / edit monthly statements from delivery apps."""
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(r & {"sales_manager", "admin"})


def can_manage_commissions(roles: Iterable[str]) -> bool:
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(r & {"sales_manager", "admin"})


def can_close_month(roles: Iterable[str]) -> bool:
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(r & {"sales_manager", "admin"})


def can_reopen_month(roles: Iterable[str]) -> bool:
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(r & {"sales_manager", "admin"})


def can_read_reconciliation(roles: Iterable[str]) -> bool:
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(
        r & {"branch_manager", "area_manager", "operations_manager", "sales_manager", "admin", "internal_auditor"}
    )


def can_read_compliance(roles: Iterable[str]) -> bool:
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(
        r & {"branch_manager", "area_manager", "operations_manager", "sales_manager", "admin", "internal_auditor"}
    )


def can_read_channels(roles: Iterable[str]) -> bool:
    """List sales channels (for daily-entry dropdown + admin screen)."""
    r = _as_set(roles)
    return _is_platform_admin(r) or bool(
        r & {"branch_manager", "area_manager", "operations_manager", "sales_manager", "admin", "internal_auditor"}
    )


def edit_window_allowed_role(required_role: str) -> set[str]:
    """Which operational role is allowed to edit in the named window."""
    if required_role == "branch_manager":
        return {"branch_manager"}
    if required_role == "area_manager":
        return {"area_manager"}
    if required_role == "sales_manager":
        return {"sales_manager"}
    return set()
