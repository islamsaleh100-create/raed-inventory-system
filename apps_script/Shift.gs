function findShiftByKey_(branchId, businessDate, shiftNumber) {
  var data = readOperationalRows_(AUTH_CONFIG.SHEETS.SHIFTS, AUTH_CONFIG.REQUIRED_COLUMNS.Shifts);
  var matches = data.rows.filter(function (row) {
    return String(row.branch_id) === branchId && String(row.shift_date) === businessDate && Number(row.shift_number) === shiftNumber;
  });
  if (matches.length > 1) throw createInternalError_('DATA_INTEGRITY_ERROR');
  return { sheet: data.sheet, headers: data.headers, record: matches[0] || null };
}

function requireAllowedShift_(branchId, shiftNumber) {
  if (!Number.isInteger(Number(shiftNumber)) || Number(shiftNumber) < 1) throw createInternalError_('SHIFT_NOT_ALLOWED');
  var branches = readSheetRecords_(AUTH_CONFIG.SHEETS.BRANCHES, AUTH_CONFIG.REQUIRED_COLUMNS.Branches)
    .filter(function (row) { return String(row.branch_id) === branchId && isTrue_(row.is_active); });
  if (branches.length !== 1) throw createInternalError_('SHIFT_NOT_ALLOWED');
  var allowed = readSheetRecords_(AUTH_CONFIG.SHEETS.SHIFT_CONFIG, AUTH_CONFIG.REQUIRED_COLUMNS.Shift_Config)
    .filter(function (row) { return String(row.branch_id) === branchId && Number(row.shift_number) === Number(shiftNumber) && isTrue_(row.is_active) && isTrue_(row.source_confirmed); });
  if (allowed.length !== 1) throw createInternalError_(allowed.length ? 'DATA_INTEGRITY_ERROR' : 'SHIFT_NOT_ALLOWED');
  return Number(shiftNumber);
}

function openShift(sessionToken, businessDate, shiftNumber) {
  return safeOperation_('openShift', function () {
    var session = requireSessionBranch_(sessionToken);
    var date = normalizeBusinessDate_(businessDate);
    if (!date) throw createInternalError_('SHIFT_NOT_ALLOWED');
    var number = requireAllowedShift_(String(session.branch_id), shiftNumber);
    return withScriptLock_(function () {
      var found = findShiftByKey_(String(session.branch_id), date, number);
      if (found.record) return success_(publicRecord_(found.record));
      var timestamp = nowIso_();
      var record = { shift_id: 'SHIFT_' + Utilities.getUuid(), branch_id: String(session.branch_id), shift_date: date,
        shift_number: number, status: 'DRAFT', opened_by: String(session.user_id), opened_at: timestamp,
        submitted_by: '', submitted_at: '', reopened_by: '', reopened_at: '', locked_at: '', notes: '' };
      writeRecordRow_(found.sheet, found.headers, null, record);
      return success_(record);
    });
  });
}

function getCurrentShift(sessionToken, businessDate, shiftNumber) {
  return safeOperation_('getCurrentShift', function () {
    var session = requireSessionBranch_(sessionToken);
    var date = normalizeBusinessDate_(businessDate);
    if (!date) throw createInternalError_('SHIFT_NOT_ALLOWED');
    var number = requireAllowedShift_(String(session.branch_id), shiftNumber);
    var found = findShiftByKey_(String(session.branch_id), date, number);
    if (!found.record) throw createInternalError_('SHIFT_NOT_FOUND');
    return success_(publicRecord_(found.record));
  });
}

function requireOwnedShift_(session, shiftId) {
  var data = readOperationalRows_(AUTH_CONFIG.SHEETS.SHIFTS, AUTH_CONFIG.REQUIRED_COLUMNS.Shifts);
  var matches = data.rows.filter(function (row) { return String(row.shift_id) === String(shiftId); });
  if (matches.length > 1) throw createInternalError_('DATA_INTEGRITY_ERROR');
  if (matches.length !== 1 || String(matches[0].branch_id) !== String(session.branch_id)) throw createInternalError_('SHIFT_NOT_FOUND');
  if (AUTH_CONFIG.SHIFT_STATUSES.indexOf(String(matches[0].status)) === -1) throw createInternalError_('DATA_INTEGRITY_ERROR');
  return { sheet: data.sheet, headers: data.headers, record: matches[0] };
}
