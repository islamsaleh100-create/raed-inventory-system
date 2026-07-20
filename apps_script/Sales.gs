function findSalesByShift_(shiftId) {
  var data = readOperationalRows_(AUTH_CONFIG.SHEETS.SALES, AUTH_CONFIG.REQUIRED_COLUMNS.Sales);
  var matches = data.rows.filter(function (row) { return String(row.shift_id) === String(shiftId); });
  if (matches.length > 1) throw createInternalError_('DATA_INTEGRITY_ERROR');
  return { sheet: data.sheet, headers: data.headers, record: matches[0] || null };
}

function loadSalesDraft(sessionToken, shiftId) {
  return safeOperation_('loadSalesDraft', function () {
    var session = requireSessionBranch_(sessionToken);
    var shift = requireOwnedShift_(session, shiftId).record;
    var sales = findSalesByShift_(shiftId).record;
    if (!sales) throw createInternalError_('SALES_NOT_FOUND');
    return success_({ sales: publicRecord_(sales), shift_status: String(shift.status) });
  });
}

function buildSalesRecord_(existing, shiftId, normalized, session, status, timestamp) {
  var record = existing ? publicRecord_(existing) : {};
  record.sales_id = existing ? String(existing.sales_id) : 'SALES_' + Utilities.getUuid();
  record.shift_id = String(shiftId); record.status = status;
  SALES_MONEY_FIELDS_.forEach(function (field) { record[field] = normalized[field]; });
  record.bill_count = normalized.bill_count; record.expense_type = normalized.expense_type;
  record.expense_details = normalized.expense_details; record.shift_notes = normalized.shift_notes;
  record.created_by = existing ? String(existing.created_by) : String(session.user_id);
  record.updated_by = String(session.user_id); record.submitted_by = status === 'SUBMITTED' ? String(session.user_id) : '';
  record.created_at = existing ? existing.created_at : timestamp; record.updated_at = timestamp;
  record.submitted_at = status === 'SUBMITTED' ? timestamp : '';
  return record;
}

function saveSalesDraft(sessionToken, shiftId, salesPayload) {
  return safeOperation_('saveSalesDraft', function () {
    var session = requireSessionBranch_(sessionToken);
    return withScriptLock_(function () {
      var shift = requireOwnedShift_(session, shiftId).record;
      if (String(shift.status) === 'LOCKED') throw createInternalError_('SHIFT_LOCKED');
      if (String(shift.status) !== 'DRAFT') throw createInternalError_('SHIFT_ALREADY_SUBMITTED');
      var validation = validateSalesPayload_(salesPayload, false);
      if (!validation.ok) return { ok: false, code: 'SALES_VALIDATION_FAILED', message: 'بيانات المبيعات غير مكتملة أو غير صحيحة.', data: validation };
      var found = findSalesByShift_(shiftId);
      if (found.record && String(found.record.status) !== 'DRAFT') throw createInternalError_(String(found.record.status) === 'LOCKED' ? 'SHIFT_LOCKED' : 'SHIFT_ALREADY_SUBMITTED');
      var timestamp = nowIso_();
      var record = buildSalesRecord_(found.record, shiftId, validation.normalized, session, 'DRAFT', timestamp);
      writeRecordRow_(found.sheet, found.headers, found.record ? found.record.__row : null, record);
      return success_({ sales: record, validation: validation, shift_status: 'DRAFT', last_saved_at: timestamp });
    });
  });
}

function submitSales(sessionToken, shiftId, salesPayload) {
  return safeOperation_('submitSales', function () {
    var session = requireSessionBranch_(sessionToken);
    return withScriptLock_(function () {
      var owned = requireOwnedShift_(session, shiftId), shift = owned.record;
      if (String(shift.status) === 'LOCKED') throw createInternalError_('SHIFT_LOCKED');
      if (String(shift.status) !== 'DRAFT') throw createInternalError_('SHIFT_ALREADY_SUBMITTED');
      var validation = validateSalesPayload_(salesPayload, true);
      if (!validation.ok) return { ok: false, code: 'SALES_VALIDATION_FAILED', message: 'بيانات المبيعات غير مكتملة أو غير صحيحة.', data: validation };
      var found = findSalesByShift_(shiftId);
      if (found.record && String(found.record.status) !== 'DRAFT') throw createInternalError_(String(found.record.status) === 'LOCKED' ? 'SHIFT_LOCKED' : 'SHIFT_ALREADY_SUBMITTED');
      var timestamp = nowIso_();
      var sales = buildSalesRecord_(found.record, shiftId, validation.normalized, session, 'SUBMITTED', timestamp);
      writeRecordRow_(found.sheet, found.headers, found.record ? found.record.__row : null, sales);
      shift.status = 'SUBMITTED'; shift.submitted_by = String(session.user_id); shift.submitted_at = timestamp;
      writeRecordRow_(owned.sheet, owned.headers, shift.__row, shift);
      return success_({ sales: sales, shift_status: 'SUBMITTED', submitted_at: timestamp });
    });
  });
}

function lockSales(sessionToken, shiftId) {
  return safeOperation_('lockSales', function () {
    var session = requireSessionBranch_(sessionToken);
    return withScriptLock_(function () {
      var owned = requireOwnedShift_(session, shiftId), shift = owned.record;
      if (String(shift.status) === 'LOCKED') throw createInternalError_('SHIFT_LOCKED');
      if (String(shift.status) !== 'SUBMITTED') throw createInternalError_('SHIFT_NOT_FOUND');
      var found = findSalesByShift_(shiftId);
      if (!found.record) throw createInternalError_('SALES_NOT_FOUND');
      if (String(found.record.status) !== 'SUBMITTED') throw createInternalError_('DATA_INTEGRITY_ERROR');
      var timestamp = nowIso_(); found.record.status = 'LOCKED'; found.record.updated_by = String(session.user_id); found.record.updated_at = timestamp;
      shift.status = 'LOCKED'; shift.locked_at = timestamp;
      writeRecordRow_(found.sheet, found.headers, found.record.__row, found.record);
      writeRecordRow_(owned.sheet, owned.headers, shift.__row, shift);
      return success_({ sales: publicRecord_(found.record), shift_status: 'LOCKED', locked_at: timestamp });
    });
  });
}
