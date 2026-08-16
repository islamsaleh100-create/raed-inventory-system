#!/usr/bin/env python3
"""Applies the shift-ops frontend wiring in place.

Surgical only:
  - narrows the OLD /inventory routes and nav items to admin/super_admin
  - adds the new /shift-ops routes and one nav entry
  - merges i18n keys into ar.json / en.json (adds only, never overwrites)
  - exports shiftOpsApi from services/api.js

Run from the repo root. Idempotent: re-running changes nothing.
"""
import io
import json
import re
import sys
from pathlib import Path

SRC = Path("raed_inventory/frontend/src")
changed, skipped = [], []


def read(p):
    return io.open(p, encoding="utf-8").read()


def write(p, s):
    io.open(p, "w", encoding="utf-8", newline="").write(s)


# ── 1. App.jsx ────────────────────────────────────────────────────────────────
app = SRC / "App.jsx"
s = read(app)
orig = s

OLD_ROLES = "allowed={['branch_user', 'branch_manager', 'admin', 'super_admin']}"
NEW_ROLES = "allowed={['admin', 'super_admin']}"
for path in ('"/inventory"', '"/inventory/new"', '"/inventory/:id"'):
    pat = re.compile(r'(<Route path=' + re.escape(path) + r'\s+element=\{)' + re.escape(OLD_ROLES))
    s = pat.sub(lambda m: m.group(1) + NEW_ROLES, s)

if "ShiftListPage" not in s:
    # imports — placed next to the other lazy/page imports
    anchor = "import { InventoryListPage }"
    if anchor in s:
        s = s.replace(
            anchor,
            "import { ShiftListPage } from './pages/shift_ops/ShiftListPage'\n"
            "import { ShiftCountPage } from './pages/shift_ops/ShiftCountPage'\n"
            "import { ShiftCashPage } from './pages/shift_ops/ShiftCashPage'\n"
            "import { ShiftOpsReportPage } from './pages/shift_ops/ShiftOpsReportPage'\n"
            + anchor,
            1,
        )
    else:
        skipped.append("App.jsx: import anchor not found — add the 4 imports manually")

    BRANCH = "['branch_user', 'branch_manager', 'area_manager', 'operations_manager', 'admin', 'super_admin']"
    AUDIT = "['internal_auditor', 'area_manager', 'operations_manager', 'admin', 'super_admin']"
    routes = (
        f'          <Route path="/shift-ops" element={{<RouteRoleGuard allowed={{{BRANCH}}}><ShiftListPage /></RouteRoleGuard>}} />\n'
        f'          <Route path="/shift-ops/:shiftId/count" element={{<RouteRoleGuard allowed={{{BRANCH}}}><ShiftCountPage /></RouteRoleGuard>}} />\n'
        f'          <Route path="/shift-ops/:shiftId/cash" element={{<RouteRoleGuard allowed={{{BRANCH}}}><ShiftCashPage /></RouteRoleGuard>}} />\n'
        f'          <Route path="/shift-ops/report" element={{<RouteRoleGuard allowed={{{AUDIT}}}><ShiftOpsReportPage /></RouteRoleGuard>}} />\n'
    )
    m = re.search(r'^.*<Route path="/inventory"[^\n]*\n', s, re.M)
    if m:
        s = s[: m.start()] + routes + s[m.start():]
    else:
        skipped.append("App.jsx: route anchor not found — add the 4 routes manually")

if s != orig:
    write(app, s)
    changed.append("App.jsx")

# ── 2. layouts ────────────────────────────────────────────────────────────────
for name, label_key in (("AppLayoutV2.jsx", True), ("AppLayout.jsx", False)):
    p = SRC / "components" / "layout" / name
    if not p.exists():
        skipped.append(f"{name}: missing")
        continue
    s = read(p)
    orig = s
    # narrow the legacy daily-inventory entry
    s = re.sub(
        r"(\{ to: '/inventory',[^}]*roles: )\['branch_user', 'branch_manager'\]",
        r"\1['admin', 'super_admin']",
        s,
    )
    # rename it so two entries are never both called "الجرد"
    s = s.replace("labelKey: 'nav.daily_inventory'", "labelKey: 'nav.daily_inventory_legacy'")
    s = s.replace("label: 'الجرد اليومي'", "label: 'الجرد اليومي (قديم)'")

    if "/shift-ops" not in s:
        entry = (
            "      { to: '/shift-ops', icon: ClipboardList, "
            + ("labelKey: 'nav.shift_ops'" if label_key else "label: 'عمليات الشفت'")
            + ", roles: ['branch_user', 'branch_manager', 'area_manager', 'operations_manager', 'admin', 'super_admin'] },\n"
        )
        m = re.search(r"^.*\{ to: '/inventory',.*\n", s, re.M)
        if m:
            s = s[: m.start()] + entry + s[m.start():]
        else:
            skipped.append(f"{name}: nav anchor not found — add the entry manually")
    if s != orig:
        write(p, s)
        changed.append(name)

# ── 3. services/api.js ────────────────────────────────────────────────────────
apijs = SRC / "services" / "api.js"
s = read(apijs)
if "shiftOpsApi" not in s:
    s = s.replace(
        "export default api",
        "export { shiftOpsApi } from './shiftOpsApi'\n\nexport default api",
        1,
    )
    write(apijs, s)
    changed.append("services/api.js")

# ── 4. i18n ───────────────────────────────────────────────────────────────────
AR = {
    "nav": {"shift_ops": "عمليات الشفت", "daily_inventory_legacy": "الجرد اليومي (قديم)"},
    "shift_ops": {
        "title": "عمليات الشفت", "open_shift": "فتح شفت جديد", "opened": "تم فتح الشفت",
        "shift_date": "تاريخ الشفت", "shift_number": "رقم الشفت", "shift_n": "الشفت {n}",
        "count": "الجرد", "cash": "الكاش", "partial": "ناقص",
        "filter_partial_only": "الشفتات الناقصة فقط",
        "shift_config_unavailable": "إعدادات شفتات الفرع غير متاحة — راجع الإدارة",
        "override_warning": "الشفت السابق غير مقفول. المتابعة ستقفله استثنائيًا.",
        "override_reason_placeholder": "سبب التجاوز (٥ أحرف على الأقل)",
        "confirm_override": "تأكيد التجاوز وفتح الشفت",
        "locked_readonly": "الشفت مقفول — عرض فقط",
        "opening": "رصيد أول",
        "negative_movement_hint": "فرق الحركة سالب — السبب مطلوب، والترحيل غير ممنوع",
        "movement_reason_placeholder": "سبب الفرق (وارد غير مسجّل، تحويل، ...)",
        "completed_of": "{done} من {total} مكتمل",
        "reason_missing": "سبب فرق الحركة مطلوب",
        "submit_count": "ترحيل الجرد", "count_submitted": "تم ترحيل الجرد",
        "submit_cash": "ترحيل الكاش", "cash_submitted": "تم ترحيل الكاش",
        "group_sales": "المبيعات", "group_informational": "معلومات فقط",
        "group_drawer": "تسوية الصندوق",
        "informational_hint": "هذه الحقول للتسجيل فقط ولا تدخل في أي معادلة أو مراجعة",
        "payment_match": "✓ طرق الدفع مطابقة للإجمالي",
        "payment_mismatch": "✗ فرق {diff} — طرق الدفع لا تساوي الإجمالي",
        "expected_deposited": "الكاش المتوقع تسليمه", "variance": "الفرق",
        "variance_reason": "سبب الفرق",
        "variance_over_tolerance": "تعدّى الحد المسموح ({tol}). السبب إلزامي",
        "negative_expected": "الكاش المتوقع سالب — راجع المصروف والعهدة المرحّلة",
        "cash_ready": "الكاش جاهز للترحيل", "cash_incomplete": "الكاش غير مكتمل",
        "reopen": "إعادة فتح", "confirm_reopen": "تأكيد إعادة الفتح", "reopened": "تمت إعادة الفتح",
        "reopen_reason_placeholder": "سبب إعادة الفتح (٥ أحرف على الأقل)",
        "close_no_activity": "إغلاق بلا نشاط",
        "confirm_close_no_activity": "تأكيد الإغلاق", "closed_no_activity": "تم الإغلاق بلا نشاط",
        "close_reason_placeholder": "السبب (٥ أحرف على الأقل)",
        "report_title": "تقرير عمليات الشفت",
        "movement_total": "إجمالي فرق الحركة", "damaged_total": "إجمالي التالف",
        "negative_exceptions": "استثناءات الحركة السالبة",
        "reopen_events": "أحداث إعادة الفتح", "chain_gap": "فجوة في سلسلة الرصيد",
        "status": {"draft": "مسودة", "submitted": "مُرحَّل", "exception_locked": "مقفول استثنائيًا"},
        "section_status": {"draft": "مسودة", "submitted": "مُرحَّل", "none": "لم يبدأ"},
        "exception_type": {"stuck_previous": "شفت سابق عالق", "branch_closed": "الفرع مغلق", "manual_gap": "فجوة يدوية"},
        "reopen_target": {"count": "الجرد", "cash": "الكاش", "both": "الاثنان"},
        "expense_type": {"invoices": "فواتير", "advance": "سلفة", "handed_to_person": "تسليم لشخص", "operational": "تشغيلي", "other": "أخرى"},
        "field": {
            "received_qty": "وارد", "returned_qty": "مرتجع", "damaged_qty": "تالف",
            "closing_balance": "رصيد آخر", "movement_diff": "فرق الحركة",
            "total_sale": "إجمالي المبيعات", "bill_count": "عدد الفواتير",
            "mada_sales": "مدى", "cash_sales": "كاش", "app_sales": "تطبيقات",
            "refund_bill": "مرتجع فواتير", "exchange_amount": "استبدال", "expiry_amount": "تالف/منتهي",
            "cash_expense": "المصروف من الكاش", "cash_float_carried_forward": "العهدة المرحّلة",
            "cash_deposited": "الكاش المُسلَّم", "expense_type": "نوع المصروف",
            "expense_details": "تفاصيل المصروف", "cash_variance_reason": "سبب الفرق",
        },
        "filter": {
            "partial_only": "ناقصة", "exception_only": "استثنائية", "reopened_only": "مُعاد فتحها",
            "variance_only": "بها فرق كاش", "negative_movement_only": "حركة سالبة",
        },
        "error": {
            "PAYMENT_METHODS_MISMATCH": "طرق الدفع لا تساوي الإجمالي",
            "EXPENSE_EXCEEDS_CASH": "المصروف أكبر من مبيعات الكاش",
            "CASH_FLOAT_EXCEEDS_AVAILABLE_CASH": "العهدة أكبر من الكاش المتاح",
            "NEGATIVE_EXPECTED_CASH": "الكاش المتوقع سالب",
            "CASH_VARIANCE_REASON_REQUIRED": "سبب الفرق مطلوب",
            "BILL_COUNT_REQUIRED": "عدد الفواتير مطلوب",
            "REQUIRED": "هذا الحقل مطلوب",
        },
    },
}

EN = {
    "nav": {"shift_ops": "Shift Operations", "daily_inventory_legacy": "Daily Inventory (legacy)"},
    "shift_ops": {
        "title": "Shift Operations", "open_shift": "Open new shift", "opened": "Shift opened",
        "shift_date": "Shift date", "shift_number": "Shift number", "shift_n": "Shift {n}",
        "count": "Count", "cash": "Cash", "partial": "Incomplete",
        "filter_partial_only": "Incomplete shifts only",
        "shift_config_unavailable": "Branch shift configuration unavailable — contact admin",
        "override_warning": "The previous shift is not closed. Continuing will close it as an exception.",
        "override_reason_placeholder": "Override reason (min 5 chars)",
        "confirm_override": "Confirm override and open shift",
        "locked_readonly": "Shift is locked — read only",
        "opening": "Opening",
        "negative_movement_hint": "Movement difference is negative — a reason is required, submission is not blocked",
        "movement_reason_placeholder": "Reason (unrecorded receipt, transfer, ...)",
        "completed_of": "{done} of {total} complete",
        "reason_missing": "Movement exception reason required",
        "submit_count": "Submit count", "count_submitted": "Count submitted",
        "submit_cash": "Submit cash", "cash_submitted": "Cash submitted",
        "group_sales": "Sales", "group_informational": "Informational only",
        "group_drawer": "Drawer reconciliation",
        "informational_hint": "Recorded for reference only — not part of any formula or check",
        "payment_match": "✓ Payment methods match the total",
        "payment_mismatch": "✗ Off by {diff} — payment methods do not match the total",
        "expected_deposited": "Expected cash to deposit", "variance": "Variance",
        "variance_reason": "Variance reason",
        "variance_over_tolerance": "exceeds tolerance ({tol}); reason required",
        "negative_expected": "Expected cash is negative — check expense and carried float",
        "cash_ready": "Cash ready to submit", "cash_incomplete": "Cash incomplete",
        "reopen": "Reopen", "confirm_reopen": "Confirm reopen", "reopened": "Reopened",
        "reopen_reason_placeholder": "Reopen reason (min 5 chars)",
        "close_no_activity": "Close (no activity)",
        "confirm_close_no_activity": "Confirm close", "closed_no_activity": "Closed with no activity",
        "close_reason_placeholder": "Reason (min 5 chars)",
        "report_title": "Shift Operations Report",
        "movement_total": "Total movement difference", "damaged_total": "Total damaged",
        "negative_exceptions": "Negative movement exceptions",
        "reopen_events": "Reopen events", "chain_gap": "Opening-balance chain gap",
        "status": {"draft": "Draft", "submitted": "Submitted", "exception_locked": "Exception locked"},
        "section_status": {"draft": "Draft", "submitted": "Submitted", "none": "Not started"},
        "exception_type": {"stuck_previous": "Previous shift stuck", "branch_closed": "Branch closed", "manual_gap": "Manual gap"},
        "reopen_target": {"count": "Count", "cash": "Cash", "both": "Both"},
        "expense_type": {"invoices": "Invoices", "advance": "Advance", "handed_to_person": "Handed to person", "operational": "Operational", "other": "Other"},
        "field": {
            "received_qty": "Received", "returned_qty": "Returned", "damaged_qty": "Damaged",
            "closing_balance": "Closing", "movement_diff": "Movement difference",
            "total_sale": "Total sales", "bill_count": "Bills",
            "mada_sales": "Mada", "cash_sales": "Cash", "app_sales": "Apps",
            "refund_bill": "Refunded bills", "exchange_amount": "Exchange", "expiry_amount": "Expired/damaged",
            "cash_expense": "Cash expense", "cash_float_carried_forward": "Carried float",
            "cash_deposited": "Cash deposited", "expense_type": "Expense type",
            "expense_details": "Expense details", "cash_variance_reason": "Variance reason",
        },
        "filter": {
            "partial_only": "Incomplete", "exception_only": "Exception", "reopened_only": "Reopened",
            "variance_only": "Cash variance", "negative_movement_only": "Negative movement",
        },
        "error": {
            "PAYMENT_METHODS_MISMATCH": "Payment methods do not match the total",
            "EXPENSE_EXCEEDS_CASH": "Expense exceeds cash sales",
            "CASH_FLOAT_EXCEEDS_AVAILABLE_CASH": "Float exceeds available cash",
            "NEGATIVE_EXPECTED_CASH": "Expected cash is negative",
            "CASH_VARIANCE_REASON_REQUIRED": "Variance reason required",
            "BILL_COUNT_REQUIRED": "Bill count required",
            "REQUIRED": "This field is required",
        },
    },
}


def merge(dst, src):
    """Adds missing keys only. Never overwrites an existing translation."""
    for k, v in src.items():
        if isinstance(v, dict):
            dst.setdefault(k, {})
            if isinstance(dst[k], dict):
                merge(dst[k], v)
        else:
            dst.setdefault(k, v)


for fname, payload in (("ar.json", AR), ("en.json", EN)):
    p = SRC / "i18n" / "dict" / fname
    data = json.loads(read(p))
    before = json.dumps(data, ensure_ascii=False, sort_keys=True)
    merge(data, payload)
    after = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if before != after:
        write(p, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        changed.append(f"i18n/{fname}")

print("changed:", ", ".join(changed) if changed else "(nothing — already applied)")
if skipped:
    print("MANUAL FOLLOW-UP NEEDED:")
    for x in skipped:
        print("  -", x)
    sys.exit(2)
