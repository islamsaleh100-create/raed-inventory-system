var SALES_MONEY_FIELDS_ = Object.freeze([
  'total_sale', 'mada_sales', 'cash_sales', 'app_sales', 'refund_bill',
  'exchange_amount', 'expiry_amount', 'cash_expense',
  'cash_float_carried_forward', 'cash_deposited'
]);

function salesValidationError_(field, code, message) {
  return { field: field, code: code, message: message };
}

function normalizeBusinessDate_(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  var parts = value.split('-').map(Number);
  var date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
  if (date.toISOString().slice(0, 10) !== value) return null;
  var today = Utilities.formatDate(new Date(), AUTH_CONFIG.TIME_ZONE, 'yyyy-MM-dd');
  return value <= today ? value : null;
}

function parseMoney_(value) {
  if (value === '' || value === null || typeof value === 'undefined') return { blank: true, value: '' };
  if ((typeof value !== 'number' && typeof value !== 'string') || String(value).trim() === '') return { error: true };
  var number = Number(value);
  if (!Number.isFinite(number) || number < 0) return { error: true };
  return { blank: false, value: Math.round((number + Number.EPSILON) * 100) / 100 };
}

function validateSalesPayload_(payload, requireComplete) {
  payload = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : {};
  var normalized = {}, errors = [];
  SALES_MONEY_FIELDS_.forEach(function (field) {
    var parsed = parseMoney_(payload[field]);
    if (parsed.error) {
      normalized[field] = '';
      errors.push(field === 'cash_float_carried_forward'
        ? salesValidationError_(field, Number(payload[field]) < 0 ? 'CASH_FLOAT_NEGATIVE' : 'CASH_FLOAT_INVALID', Number(payload[field]) < 0 ? 'رصيد الصندوق المرحّل لا يجوز أن يكون سالبًا.' : 'رصيد الصندوق المرحّل يجب أن يكون رقمًا صالحًا.')
        : salesValidationError_(field, 'INVALID_NUMBER', 'يرجى إدخال قيمة رقمية صحيحة غير سالبة.'));
    }
    else if (parsed.blank) {
      normalized[field] = '';
      if (requireComplete) errors.push(field === 'cash_float_carried_forward'
        ? salesValidationError_(field, 'CASH_FLOAT_REQUIRED', 'رصيد الصندوق المرحّل مطلوب.')
        : salesValidationError_(field, 'REQUIRED', 'هذا الحقل مطلوب.'));
    }
    else normalized[field] = parsed.value;
  });
  var bill = payload.bill_count;
  if (bill === '' || bill === null || typeof bill === 'undefined') {
    normalized.bill_count = '';
    if (requireComplete) errors.push({ field: 'bill_count', code: 'REQUIRED' });
  } else if (!Number.isInteger(Number(bill)) || Number(bill) < (requireComplete ? 1 : 0)) {
    errors.push({ field: 'bill_count', code: 'INVALID_INTEGER' });
  } else normalized.bill_count = Number(bill);
  normalized.expense_type = typeof payload.expense_type === 'string' ? payload.expense_type.trim() : '';
  normalized.expense_details = typeof payload.expense_details === 'string' ? payload.expense_details.trim() : '';
  normalized.shift_notes = typeof payload.shift_notes === 'string' ? payload.shift_notes.trim() : '';
  if (normalized.shift_notes.length > 300) errors.push({ field: 'shift_notes', code: 'MAX_LENGTH' });
  if (normalized.expense_type && AUTH_CONFIG.EXPENSE_TYPES.indexOf(normalized.expense_type) === -1) errors.push({ field: 'expense_type', code: 'INVALID_OPTION' });
  if (normalized.cash_expense !== '' && normalized.cash_sales !== '' && normalized.cash_expense > normalized.cash_sales) errors.push(salesValidationError_('cash_expense', 'EXCEEDS_CASH', 'المصروف من الكاش أكبر من مبيعات الكاش.'));
  if (normalized.cash_expense !== '' && normalized.cash_expense > 0) {
    if (!normalized.expense_type) errors.push({ field: 'expense_type', code: 'REQUIRED' });
    if (!normalized.expense_details) errors.push({ field: 'expense_details', code: 'REQUIRED' });
  }
  var cashAvailable = normalized.cash_sales !== '' && normalized.cash_expense !== ''
    ? Math.round((normalized.cash_sales - normalized.cash_expense) * 100) / 100 : null;
  if (cashAvailable !== null && normalized.cash_float_carried_forward !== '' && normalized.cash_float_carried_forward > cashAvailable) {
    errors.push(salesValidationError_('cash_float_carried_forward', 'CASH_FLOAT_EXCEEDS_AVAILABLE_CASH', 'رصيد الصندوق المرحّل أكبر من الكاش المتاح بعد المصروفات.'));
  }
  var paymentReady = ['mada_sales', 'cash_sales', 'app_sales', 'total_sale'].every(function (f) { return normalized[f] !== ''; });
  var cashReady = ['cash_sales', 'cash_expense', 'cash_float_carried_forward', 'cash_deposited'].every(function (f) { return normalized[f] !== ''; });
  var paymentDifference = paymentReady ? Math.round((normalized.mada_sales + normalized.cash_sales + normalized.app_sales - normalized.total_sale) * 100) / 100 : null;
  var expectedCashDeposited = cashReady ? Math.round((normalized.cash_sales - normalized.cash_expense - normalized.cash_float_carried_forward) * 100) / 100 : null;
  var cashDifference = cashReady ? Math.round((normalized.cash_deposited - expectedCashDeposited) * 100) / 100 : null;
  if (requireComplete && paymentReady && Math.abs(paymentDifference) > 0.01) errors.push(salesValidationError_('payment_methods', 'PAYMENT_METHODS_MISMATCH', 'إجمالي طرق الدفع لا يساوي إجمالي المبيعات.'));
  if (requireComplete && cashReady && expectedCashDeposited >= 0 && Math.abs(cashDifference) > 0.01) errors.push(salesValidationError_('cash_deposited', 'CASH_DEPOSIT_MISMATCH', 'الكاش المسلم لا يساوي الكاش المتوقع تسليمه.'));
  return { ok: errors.length === 0, normalized: normalized, errors: errors, payment_difference: paymentDifference, expected_cash_deposited: expectedCashDeposited, cash_difference: cashDifference };
}

function validateSales(salesPayload) {
  var result = validateSalesPayload_(salesPayload, true);
  return result.ok ? success_(result) : { ok: false, code: 'SALES_VALIDATION_FAILED', message: publicError_('SALES_VALIDATION_FAILED').message, data: result };
}
