import pytest

from app.core import sales_permissions as perms


MATRIX = [
    (
        "can_create_daily_sales",
        ["branch_manager", "area_manager", "admin", "super_admin"],
        ["sales_manager", "operations_manager", "warehouse_manager", "branch_user"],
    ),
    (
        "can_edit_daily_sales",
        ["branch_manager", "area_manager", "sales_manager", "admin", "super_admin"],
        ["operations_manager", "warehouse_manager", "branch_user"],
    ),
    (
        "can_manage_statements",
        ["sales_manager", "admin", "super_admin"],
        ["branch_manager", "area_manager", "operations_manager", "warehouse_manager"],
    ),
    (
        "can_manage_commissions",
        ["sales_manager", "admin", "super_admin"],
        ["branch_manager", "area_manager", "operations_manager"],
    ),
    (
        "can_close_month",
        ["sales_manager", "admin", "super_admin"],
        ["branch_manager", "area_manager", "operations_manager"],
    ),
    (
        "can_reopen_month",
        ["sales_manager", "admin", "super_admin"],
        ["branch_manager", "area_manager", "operations_manager"],
    ),
    (
        "can_read_reconciliation",
        ["branch_manager", "area_manager", "operations_manager", "sales_manager", "admin", "super_admin"],
        ["warehouse_manager"],
    ),
    (
        "can_read_channels",
        ["branch_manager", "area_manager", "operations_manager", "sales_manager", "admin", "super_admin"],
        ["warehouse_manager"],
    ),
]


@pytest.mark.parametrize("predicate_name,allowed,denied", MATRIX)
def test_permission_matrix_allowed(predicate_name, allowed, denied):
    predicate = getattr(perms, predicate_name)
    for role in allowed:
        assert predicate([role]) is True, f"{predicate_name} must allow {role}"
    for role in denied:
        assert predicate([role]) is False, f"{predicate_name} must deny {role}"


def test_edit_window_role_mapping():
    assert perms.edit_window_allowed_role("branch_manager") == {"branch_manager"}
    assert perms.edit_window_allowed_role("area_manager") == {"area_manager"}
    assert perms.edit_window_allowed_role("sales_manager") == {"sales_manager"}
    assert perms.edit_window_allowed_role("unknown") == set()
