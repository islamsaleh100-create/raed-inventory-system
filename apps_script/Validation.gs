var SALES_MONEY_FIELDS_ = Object.freeze([
  'total_sale', 'mada_sales', 'cash_sales', 'app_sales', 'refund_bill',
  'exchange_amount', 'expiry_amount', 'cash_expense', 'cash_deposited'
]);

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
    if (parsed.error) errors.push({ field: field, code: 'INVALID_NUMBER' });
    else if (parsed.blank) { normalized[field] = ''; if (requireComplete) errors.push({ field: field, code: 'REQUIRED' }); }
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
  if (normalized.cash_expense !== '' && normalized.cash_sales !== '' && normalized.cash_expense > normalized.cash_sales) errors.push({ field: 'cash_expense', code: 'EXCEEDS_CASH' });
  if (normalized.cash_expense !== '' && normalized.cash_expense > 0) {
    if (!normalized.expense_type) errors.push({ field: 'expense_type', code: 'REQUIRED' });
    if (!normalized.expense_details) errors.push({ field: 'expense_details', code: 'REQUIRED' });
  }
  var paymentReady = ['mada_sales', 'cash_sales', 'app_sales', 'total_sale'].every(function (f) { return normalized[f] !== ''; });
  var cashReady = ['cash_sales', 'cash_expense', 'cash_deposited'].every(function (f) { return normalized[f] !== ''; });
  var paymentDifference = paymentReady ? Math.round((normalized.mada_sales + normalized.cash_sales + normalized.app_sales - normalized.total_sale) * 100) / 100 : null;
  var cashDifference = cashReady ? Math.round((normalized.cash_sales - normalized.cash_expense - normalized.cash_deposited) * 100) / 100 : null;
  if (requireComplete && paymentReady && Math.abs(paymentDifference) > 0.01) errors.push({ field: 'payments', code: 'MISMATCH' });
  if (requireComplete && cashReady && Math.abs(cashDifference) > 0.01) errors.push({ field: 'cash_deposited', code: 'MISMATCH' });
  return { ok: errors.length === 0, normalized: normalized, errors: errors, payment_difference: paymentDifference, cash_difference: cashDifference };
}

function validateSales(salesPayload) {
  var result = validateSalesPayload_(salesPayload, true);
  return result.ok ? success_(result) : { ok: false, code: 'SALES_VALIDATION_FAILED', message: publicError_('SALES_VALIDATION_FAILED').message, data: result };
}
