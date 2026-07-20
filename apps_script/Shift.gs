function storedBusinessDate_(value, spreadsheetTimeZone) {
  if (value instanceof Date && !isNaN(value.getTime())) {
    return Utilities.formatDate(value, spreadsheetTimeZone || AUTH_CONFIG.TIME_ZONE, 'yyyy-MM-dd');
  }
  var text = String(value || '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : '';
}

function publicShiftRecord_(record, spreadsheetTimeZone) {
  var output = publicRecord_(record);
  output.shift_date = storedBusinessDate_(record.shift_date, spreadsheetTimeZone);
  return output;
}

function canonicalShiftMatch_(matches) {
  if (matches.length < 2) return matches[0] || null;

  var progressed = matches.filter(function (row) {
    if (AUTH_CONFIG.SHIFT_STATUSES.indexOf(String(row.status)) === -1) {
      throw createInternalError_('DATA_INTEGRITY_ERROR');
    }
    return String(row.status) !== 'DRAFT';
  });
  if (progressed.length > 1) throw createInternalError_('DATA_INTEGRITY_ERROR');

  var selected = progressed[0] || matches.slice().sort(function (left, right) {
    var leftOpened = Date.parse(String(left.opened_at || ''));
    var rightOpened = Date.parse(String(right.opened_at || ''));
    leftOpened = isNaN(leftOpened) ? Number.MAX_SAFE_INTEGER : leftOpened;
    rightOpened = isNaN(rightOpened) ? Number.MAX_SAFE_INTEGER : rightOpened;
    return leftOpened - rightOpened || Number(left.__row) - Number(right.__row);
  })[0];

  console.warn(JSON.stringify({
    code: 'SHIFT_DUPLICATE_RESOLVED',
    match_count: matches.length,
    selected_shift_id: String(selected.shift_id)
  }));
  return selected;
}

function findShiftByKey_(branchId, businessDate, shiftNumber) {
  var data = readOperationalRows_(AUTH_CONFIG.SHEETS.SHIFTS, AUTH_CONFIG.REQUIRED_COLUMNS.Shifts);
  var spreadsheetTimeZone = data.sheet.getParent().getSpreadsheetTimeZone();
  var matches = data.rows.filter(function (row) {
    return String(row.branch_id) === branchId && storedBusinessDate_(row.shift_date, spreadsheetTimeZone) === businessDate && Number(row.shift_number) === shiftNumber;
  });
  return { sheet: data.sheet, headers: data.headers, record: canonicalShiftMatch_(matches), spreadsheetTimeZone: spreadsheetTimeZone };
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
      if (found.record) return success_(publicShiftRecord_(found.record, found.spreadsheetTimeZone));
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
    return success_(publicShiftRecord_(found.record, found.spreadsheetTimeZone));
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
