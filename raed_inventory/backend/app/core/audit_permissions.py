from typing import Iterable


_READ_ONLY_ROLES = {"internal_auditor"}
_AUDITOR_FINDING_MANAGER_ROLES = {"area_manager", "operations_manager", "admin", "super_admin"}


def _as_set(roles: Iterable[str]) -> set[str]:
    return set(roles or ())


def is_read_only(roles: Iterable[str]) -> bool:
    return bool(_as_set(roles) & _READ_ONLY_ROLES)


def can_create_audit_finding(roles: Iterable[str]) -> bool:
    role_set = _as_set(roles)
    return "internal_auditor" in role_set or "admin" in role_set or "super_admin" in role_set


def can_acknowledge_audit_finding(roles: Iterable[str]) -> bool:
    return bool(_as_set(roles) & _AUDITOR_FINDING_MANAGER_ROLES)
