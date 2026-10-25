"""Shared helpers for POS terminal search and normalization."""
from __future__ import annotations

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def normalize_terminal_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().translate(_AR_DIGITS).translate(_FA_DIGITS)
    return text or None
