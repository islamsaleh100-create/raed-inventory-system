var INVENTORY_EDITABLE_NUMERIC_FIELDS_ = Object.freeze([
  'received_qty', 'returned_qty', 'damaged_qty', 'closing_balance'
]);

function parseInventoryNumber_(value) {
  if (value === '' || value === null || typeof value === 'undefined' ||
      (typeof value === 'string' && value.trim() === '')) return { blank: true, value: '' };
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return { error: 'INVENTORY_INVALID_NUMBER' };
    if (value < 0) return { error: 'INVENTORY_NEGATIVE_VALUE' };
    return { blank: false, value: value };
  }
  if (typeof value !== 'string' || !/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value.trim())) {
    return { error: 'INVENTORY_INVALID_NUMBER' };
  }
  var parsed = Number(value.trim());
  if (!Number.isFinite(parsed)) return { error: 'INVENTORY_INVALID_NUMBER' };
  return { blank: false, value: parsed };
}

function normalizeInventoryLine_(source, openingBalance) {
  source = source && typeof source === 'object' && !Array.isArray(source) ? source : {};
  var normalized = { item_notes: typeof source.item_notes === 'string' ? source.item_notes.trim() : '' };
  var errors = [], complete = true;
  INVENTORY_EDITABLE_NUMERIC_FIELDS_.forEach(function (field) {
    var parsed = parseInventoryNumber_(source[field]);
    if (parsed.error) { errors.push({ field: field, code: parsed.error }); normalized[field] = ''; complete = false; }
    else if (parsed.blank) { normalized[field] = ''; complete = false; }
    else normalized[field] = parsed.value;
  });
  normalized.opening_balance = Number(openingBalance) || 0;
  normalized.consumption_qty = '';
  if (!errors.length && complete) {
    normalized.consumption_qty = normalized.opening_balance + normalized.received_qty -
      normalized.returned_qty - normalized.damaged_qty - normalized.closing_balance;
    if (!Number.isFinite(normalized.consumption_qty)) errors.push({ field: 'consumption_qty', code: 'INVENTORY_INVALID_NUMBER' });
    else if (normalized.consumption_qty < 0) errors.push({ field: 'consumption_qty', code: 'INVENTORY_NEGATIVE_CONSUMPTION' });
  }
  normalized.row_status = errors.length ? 'INVALID' : (complete ? 'VALID' : 'INCOMPLETE');
  return { normalized: normalized, errors: errors };
}

function validateInventoryPayload_(payload, approvedItems, openingBalances, mode) {
  payload = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : {};
  mode = String(mode || 'DRAFT').toUpperCase() === 'SUBMIT' ? 'SUBMIT' : 'DRAFT';
  var clientLines = Array.isArray(payload.items) ? payload.items : [];
  var approvedById = {}, clientById = {}, duplicateIds = [], foreignIds = [], errors = [];
  approvedItems.forEach(function (item) { approvedById[item.brand_item_id] = item; });
  clientLines.forEach(function (line) {
    var id = line && line.brand_item_id !== null && typeof line.brand_item_id !== 'undefined' ? String(line.brand_item_id) : '';
    if (!id || !approvedById[id]) { foreignIds.push(id); return; }
    if (clientById[id]) { duplicateIds.push(id); return; }
    clientById[id] = line;
  });
  if (duplicateIds.length) errors.push({ code: 'INVENTORY_DUPLICATE_LINE', item_ids: duplicateIds.slice() });
  if (foreignIds.length) errors.push({ code: 'INVENTORY_FOREIGN_ITEM', item_ids: foreignIds.slice() });
  var missingIds = approvedItems.filter(function (item) { return !clientById[item.brand_item_id]; })
    .map(function (item) { return item.brand_item_id; });
  if (mode === 'SUBMIT' && missingIds.length) errors.push({ code: 'INVENTORY_MISSING_ITEMS', item_ids: missingIds.slice() });
  var itemResults = approvedItems.map(function (item) {
    var result = normalizeInventoryLine_(clientById[item.brand_item_id] || {}, openingBalances[item.brand_item_id] || 0);
    result.errors.forEach(function (error) {
      errors.push({ code: error.code, field: error.field, brand_item_id: item.brand_item_id });
    });
    if (mode === 'SUBMIT' && result.normalized.row_status !== 'VALID') {
      errors.push({ code: 'INVENTORY_MISSING_ITEMS', brand_item_id: item.brand_item_id });
    }
    return {
      brand_item_id: item.brand_item_id, item_name: item.item_name, unit: item.unit,
      opening_balance: result.normalized.opening_balance,
      received_qty: result.normalized.received_qty, returned_qty: result.normalized.returned_qty,
      damaged_qty: result.normalized.damaged_qty, closing_balance: result.normalized.closing_balance,
      consumption_qty: result.normalized.consumption_qty, item_notes: result.normalized.item_notes,
      row_status: result.normalized.row_status, errors: result.errors
    };
  });
  return { valid: errors.length === 0, mode: mode, errors: errors, item_results: itemResults,
    missing_item_ids: missingIds, duplicate_item_ids: duplicateIds, foreign_item_ids: foreignIds };
}
