"""Pure validation rules for branch shift operations (no DB side effects)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.config import settings


def _d(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _is_blank(value: Optional[str]) -> bool:
    return value is None or not str(value).strip()


def validate_non_negative_fields(fields: dict[str, Any], field_names: list[str]) -> list[str]:
    errors: list[str] = []
    for name in field_names:
        raw = fields.get(name)
        if raw is None:
            continue
        if _d(raw) < 0:
            errors.append(name)
    return errors


def compute_movement_diff(
    opening: Decimal,
    received: Decimal,
    returned: Decimal,
    damaged: Decimal,
    closing: Decimal,
) -> Decimal:
    return opening + received - returned - damaged - closing


def evaluate_count_line(
    *,
    opening_balance: Decimal,
    received_qty: Optional[Decimal],
    returned_qty: Optional[Decimal],
    damaged_qty: Optional[Decimal],
    closing_balance: Optional[Decimal],
    movement_exception_reason: Optional[str],
    opening_count: bool = False,
) -> dict[str, Any]:
    received = _d(received_qty)
    returned = _d(returned_qty)
    damaged = _d(damaged_qty)

    if any(v < 0 for v in (opening_balance, received, returned, damaged)):
        return {"row_status": "invalid", "movement_diff": None}

    if closing_balance is None:
        return {"row_status": "incomplete", "movement_diff": None}

    closing = _d(closing_balance)
    if closing < 0:
        return {"row_status": "invalid", "movement_diff": None}

    movement_diff = compute_movement_diff(opening_balance, received, returned, damaged, closing)
    if (
        not opening_count
        and movement_diff < 0
        and (not movement_exception_reason or len(movement_exception_reason.strip()) < 5)
    ):
        return {"row_status": "valid", "movement_diff": movement_diff, "error_code": "MOVEMENT_EXCEPTION_REASON_REQUIRED"}

    return {"row_status": "valid", "movement_diff": movement_diff}


def validate_cash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return normalized cash fields + validation errors list."""
    errors: list[dict[str, str]] = []

    total_sale = payload.get("total_sale")
    bill_count = payload.get("bill_count")
    mada = _d(payload.get("mada_sales"))
    cash = _d(payload.get("cash_sales"))
    app = _d(payload.get("app_sales"))
    cash_expense = _d(payload.get("cash_expense"))
    cash_float = _d(payload.get("cash_float_carried_forward"))
    deposited = payload.get("cash_deposited")
    expense_type = payload.get("expense_type")
    expense_details = payload.get("expense_details")
    variance_reason = payload.get("cash_variance_reason")

    neg_fields = validate_non_negative_fields(
        payload,
        [
            "total_sale",
            "mada_sales",
            "cash_sales",
            "app_sales",
            "refund_bill",
            "exchange_amount",
            "expiry_amount",
            "cash_expense",
            "cash_float_carried_forward",
            "cash_deposited",
        ],
    )
    for field in neg_fields:
        errors.append({"field": field, "code": "NEGATIVE_VALUE"})

    if total_sale is not None:
        total = _d(total_sale)
        if abs(mada + cash + app - total) > Decimal("0.01"):
            errors.append({"field": "payment_methods", "code": "PAYMENT_METHODS_MISMATCH"})

        if bill_count is not None and int(bill_count) == 0 and total > 0:
            errors.append({"field": "bill_count", "code": "BILL_COUNT_REQUIRED"})

    expected = cash - cash_expense - cash_float
    variance = None
    if deposited is not None:
        variance = _d(deposited) - expected

    if cash_expense > cash:
        errors.append({"field": "cash_expense", "code": "EXPENSE_EXCEEDS_CASH"})

    if cash_expense > 0:
        if _is_blank(expense_type):
            errors.append({"field": "expense_type", "code": "REQUIRED"})
        if _is_blank(expense_details):
            errors.append({"field": "expense_details", "code": "REQUIRED"})

    if cash_float > (cash - cash_expense):
        errors.append({"field": "cash_float_carried_forward", "code": "CASH_FLOAT_EXCEEDS_AVAILABLE_CASH"})

    if expected < 0:
        errors.append({"field": "expected_deposited", "code": "NEGATIVE_EXPECTED_CASH"})

    tolerance = Decimal(str(settings.CASH_VARIANCE_TOLERANCE))
    if variance is not None and abs(variance) > tolerance and _is_blank(variance_reason):
        errors.append({"field": "cash_variance_reason", "code": "CASH_VARIANCE_REASON_REQUIRED"})

    informational = {
        "refund_bill": payload.get("refund_bill"),
        "exchange_amount": payload.get("exchange_amount"),
        "expiry_amount": payload.get("expiry_amount"),
        "informational": True,
    }

    return {
        "expected_deposited": expected,
        "cash_variance": variance,
        "errors": errors,
        "informational_fields": informational,
    }


def cash_regression_case_061595be() -> dict[str, Decimal]:
    """Real row from gate acceptance — refund must NOT enter expected formula."""
    payload = {
        "cash_sales": Decimal("650"),
        "cash_expense": Decimal("0"),
        "refund_bill": Decimal("1.00"),
        "cash_float_carried_forward": Decimal("500"),
        "cash_deposited": Decimal("150"),
        "mada_sales": Decimal("0"),
        "app_sales": Decimal("0"),
        "total_sale": Decimal("650"),
        "bill_count": 1,
    }
    result = validate_cash_payload(payload)
    return {
        "expected_deposited": result["expected_deposited"],
        "cash_variance": result["cash_variance"],
    }
