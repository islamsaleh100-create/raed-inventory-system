from decimal import Decimal

from app.services.shift_ops_validation import (
    cash_regression_case_061595be,
    evaluate_count_line,
    validate_cash_payload,
)


def test_cash_expected_deposited_ignores_refund_bill():
    result = validate_cash_payload(
        {
            "total_sale": Decimal("650"),
            "bill_count": 1,
            "mada_sales": Decimal("0"),
            "cash_sales": Decimal("650"),
            "app_sales": Decimal("0"),
            "refund_bill": Decimal("1.00"),
            "cash_expense": Decimal("0"),
            "cash_float_carried_forward": Decimal("500"),
            "cash_deposited": Decimal("150"),
        }
    )
    assert result["expected_deposited"] == Decimal("150.00")
    assert result["cash_variance"] == Decimal("0.00")
    assert result["informational_fields"]["informational"] is True


def test_regression_row_061595be():
    values = cash_regression_case_061595be()
    assert values["expected_deposited"] == Decimal("150.00")
    assert values["cash_variance"] == Decimal("0.00")


def test_payment_methods_mismatch():
    result = validate_cash_payload(
        {
            "total_sale": Decimal("100"),
            "mada_sales": Decimal("10"),
            "cash_sales": Decimal("10"),
            "app_sales": Decimal("10"),
        }
    )
    codes = {e["code"] for e in result["errors"]}
    assert "PAYMENT_METHODS_MISMATCH" in codes


def test_movement_diff_negative_requires_reason():
    result = evaluate_count_line(
        opening_balance=Decimal("10"),
        received_qty=Decimal("0"),
        returned_qty=Decimal("0"),
        damaged_qty=Decimal("0"),
        closing_balance=Decimal("15"),
        movement_exception_reason=None,
    )
    assert result["error_code"] == "MOVEMENT_EXCEPTION_REASON_REQUIRED"


def test_movement_diff_negative_allowed_with_reason():
    result = evaluate_count_line(
        opening_balance=Decimal("10"),
        received_qty=Decimal("0"),
        returned_qty=Decimal("0"),
        damaged_qty=Decimal("0"),
        closing_balance=Decimal("15"),
        movement_exception_reason="Unregistered delivery",
    )
    assert result["row_status"] == "valid"
    assert result["movement_diff"] == Decimal("-5")
