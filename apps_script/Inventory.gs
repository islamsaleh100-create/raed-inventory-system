function requireInventoryContext_(sessionToken, shiftId) {
  var session = requireSessionBranch_(sessionToken);
  var users = readSheetRecords_(AUTH_CONFIG.SHEETS.USERS, AUTH_CONFIG.REQUIRED_COLUMNS.Users)
    .filter(function (row) { return String(row.user_id) === String(session.user_id) && isTrue_(row.is_active); });
  if (users.length !== 1 || String(users[0].branch_id) !== String(session.branch_id)) {
    throw createInternalError_('INVALID_SESSION');
  }
  var branches = readSheetRecords_(AUTH_CONFIG.SHEETS.BRANCHES, AUTH_CONFIG.REQUIRED_COLUMNS.Branches)
    .filter(function (row) { return String(row.branch_id) === String(session.branch_id) && isTrue_(row.is_active); });
  if (branches.length !== 1 || !branches[0].brand_code) throw createInternalError_('INVALID_SESSION');
  var authoritativeBrand = String(branches[0].brand_code);
  if (session.brand && String(session.brand) !== authoritativeBrand) throw createInternalError_('INVALID_SESSION');
  session.brand = authoritativeBrand;
  var shift = requireOwnedShift_(session, shiftId).record;
  return { session: session, shift: shift };
}

function loadApprovedInventoryItems_(brandCode) {
  var data = readOperationalRows_(AUTH_CONFIG.SHEETS.BRAND_ITEMS, AUTH_CONFIG.REQUIRED_COLUMNS.Brand_Items);
  var brands = readSheetRecords_(AUTH_CONFIG.SHEETS.BRANDS, AUTH_CONFIG.REQUIRED_COLUMNS.Brands)
    .filter(function (row) { return String(row.brand_code) === String(brandCode) && isTrue_(row.is_active); });
  if (brands.length !== 1) throw createInternalError_('INVENTORY_DATA_CORRUPTION');
  var brandId = String(brands[0].brand_id);
  var items = data.rows.filter(function (row) {
    return String(row.brand_id) === brandId && isTrue_(row.is_active) && isTrue_(row.shift_count_enabled);
  }).map(function (row) {
    return { brand_item_id: String(row.item_id), item_name: String(row.item_name), unit: String(row.unit),
      display_order: Number(row.display_order) || 0 };
  });
  var seen = {};
  items.forEach(function (item) {
    if (!item.brand_item_id || seen[item.brand_item_id]) throw createInternalError_('INVENTORY_DATA_CORRUPTION');
    seen[item.brand_item_id] = true;
  });
  items.sort(function (a, b) { return a.display_order - b.display_order || a.brand_item_id.localeCompare(b.brand_item_id); });
  return items;
}

function findInventoryByShift_(shiftId) {
  var data = readOperationalRows_(AUTH_CONFIG.SHEETS.INVENTORY, AUTH_CONFIG.REQUIRED_COLUMNS.Inventory);
  var matches = data.rows.filter(function (row) { return String(row.shift_id) === String(shiftId); });
  if (matches.length > 1) throw createInternalError_('INVENTORY_DUPLICATE_HEADER');
  if (matches.length && AUTH_CONFIG.INVENTORY_STATUSES.indexOf(String(matches[0].status)) === -1) {
    throw createInternalError_('INVENTORY_INVALID_STATUS');
  }
  return { sheet: data.sheet, headers: data.headers, record: matches[0] || null };
}

function loadInventoryLines_(inventoryId, approvedItems, inventoryStatus) {
  var data = readOperationalRows_(AUTH_CONFIG.SHEETS.INVENTORY_LINES, AUTH_CONFIG.REQUIRED_COLUMNS.Inventory_Lines);
  var lines = data.rows.filter(function (row) { return String(row.inventory_id) === String(inventoryId); });
  var approved = {}, byItem = {};
  approvedItems.forEach(function (item) { approved[item.brand_item_id] = true; });
  lines.forEach(function (line) {
    var id = String(line.brand_item_id);
    if (!approved[id]) throw createInternalError_('INVENTORY_FOREIGN_ITEM');
    if (byItem[id]) throw createInternalError_('INVENTORY_DUPLICATE_LINE');
    if (AUTH_CONFIG.INVENTORY_LINE_STATUSES.indexOf(String(line.row_status)) === -1) {
      throw createInternalError_('INVENTORY_DATA_CORRUPTION');
    }
    if (String(inventoryStatus) === 'SUBMITTED' && String(line.row_status) !== 'VALID') {
      throw createInternalError_('INVENTORY_DATA_CORRUPTION');
    }
    if (String(inventoryStatus) === 'LOCKED' && String(line.row_status) !== 'LOCKED') {
      throw createInternalError_('INVENTORY_DATA_CORRUPTION');
    }
    byItem[id] = line;
  });
  return { sheet: data.sheet, headers: data.headers, lines: lines, byItem: byItem };
}

function resolveOpeningBalances_(shift, approvedItems) {
  var openings = {};
  approvedItems.forEach(function (item) { openings[item.brand_item_id] = 0; });
  var shifts = readOperationalRows_(AUTH_CONFIG.SHEETS.SHIFTS, AUTH_CONFIG.REQUIRED_COLUMNS.Shifts).rows;
  var inventoryRows = readOperationalRows_(AUTH_CONFIG.SHEETS.INVENTORY, AUTH_CONFIG.REQUIRED_COLUMNS.Inventory).rows;
  var inventoryByShift = {};
  inventoryRows.forEach(function (row) {
    var key = String(row.shift_id);
    if (!inventoryByShift[key]) inventoryByShift[key] = [];
    inventoryByShift[key].push(row);
  });
  var inventoryForShift = function (shiftId) {
    var matches = inventoryByShift[String(shiftId)] || [];
    if (matches.length > 1) throw createInternalError_('INVENTORY_DUPLICATE_HEADER');
    if (matches.length && AUTH_CONFIG.INVENTORY_STATUSES.indexOf(String(matches[0].status)) === -1) {
      throw createInternalError_('INVENTORY_INVALID_STATUS');
    }
    return matches[0] || null;
  };
  var sourceShift = null, sourceInventory = null;
  if (Number(shift.shift_number) === 2) {
    var sameDay = shifts.filter(function (candidate) {
      return String(candidate.branch_id) === String(shift.branch_id) &&
        String(candidate.shift_date) === String(shift.shift_date) && Number(candidate.shift_number) === 1;
    });
    if (sameDay.length > 1) throw createInternalError_('INVENTORY_DATA_CORRUPTION');
    sourceShift = sameDay[0] || null;
    if (sourceShift) {
      sourceInventory = inventoryForShift(sourceShift.shift_id);
      if (!sourceInventory || ['SUBMITTED', 'LOCKED'].indexOf(String(sourceInventory.status)) === -1) sourceInventory = null;
    }
  } else {
    var earlier = shifts.filter(function (candidate) {
      if (String(candidate.branch_id) !== String(shift.branch_id)) return false;
      var candidateKey = String(candidate.shift_date) + '|' + String(Number(candidate.shift_number)).padStart(4, '0');
      var currentKey = String(shift.shift_date) + '|' + String(Number(shift.shift_number)).padStart(4, '0');
      return candidateKey < currentKey;
    }).sort(function (a, b) {
      var ak = String(a.shift_date) + '|' + String(Number(a.shift_number)).padStart(4, '0');
      var bk = String(b.shift_date) + '|' + String(Number(b.shift_number)).padStart(4, '0');
      return ak < bk ? 1 : (ak > bk ? -1 : 0);
    });
    for (var i = 0; i < earlier.length; i += 1) {
      var candidateInventory = inventoryForShift(earlier[i].shift_id);
      if (candidateInventory && ['SUBMITTED', 'LOCKED'].indexOf(String(candidateInventory.status)) !== -1) {
        sourceShift = earlier[i]; sourceInventory = candidateInventory; break;
      }
    }
  }
  if (!sourceShift || !sourceInventory) return openings;
  var sourceLines = loadInventoryLines_(sourceInventory.inventory_id, approvedItems, sourceInventory.status).byItem;
  approvedItems.forEach(function (item) {
    var source = sourceLines[item.brand_item_id];
    var closing = source ? parseInventoryNumber_(source.closing_balance) : { blank: true };
    openings[item.brand_item_id] = source && !closing.blank && !closing.error ? closing.value : 0;
  });
  return openings;
}

function inventoryPayloadFromStored_(storedLines, generalNotes) {
  return { general_notes: generalNotes || '', items: Object.keys(storedLines).map(function (id) {
    var line = storedLines[id];
    return { brand_item_id: id, received_qty: line.received_qty, returned_qty: line.returned_qty,
      damaged_qty: line.damaged_qty, closing_balance: line.closing_balance, item_notes: line.item_notes };
  }) };
}

function buildInventoryResponse_(header, validation, readOnly) {
  return { inventory_id: header ? String(header.inventory_id) : '', status: header ? String(header.status) : 'DRAFT',
    general_notes: header ? String(header.general_notes || '') : '', items: validation.item_results,
    read_only: Boolean(readOnly) };
}

function loadInventoryDraft(sessionToken, shiftId) {
  return safeOperation_('loadInventoryDraft', function () {
    var context = requireInventoryContext_(sessionToken, shiftId);
    var items = loadApprovedInventoryItems_(context.session.brand);
    var found = findInventoryByShift_(context.shift.shift_id);
    var openings = resolveOpeningBalances_(context.shift, items);
    var stored = found.record ? loadInventoryLines_(found.record.inventory_id, items, found.record.status).byItem : {};
    var payload = inventoryPayloadFromStored_(stored, found.record ? found.record.general_notes : '');
    var validation = validateInventoryPayload_(payload, items, openings, 'DRAFT');
    return success_(buildInventoryResponse_(found.record, validation,
      found.record && ['SUBMITTED', 'LOCKED'].indexOf(String(found.record.status)) !== -1));
  });
}

function validateInventory(sessionToken, shiftId, inventoryPayload, mode) {
  return safeOperation_('validateInventory', function () {
    var context = requireInventoryContext_(sessionToken, shiftId);
    var items = loadApprovedInventoryItems_(context.session.brand);
    return success_(validateInventoryPayload_(inventoryPayload, items,
      resolveOpeningBalances_(context.shift, items), mode));
  });
}

function mergeInventoryDraftPayload_(inventoryPayload, storedByItem, existingGeneralNotes) {
  var merged = {};
  Object.keys(storedByItem).forEach(function (id) {
    var line = storedByItem[id];
    merged[id] = { brand_item_id: id, received_qty: line.received_qty, returned_qty: line.returned_qty,
      damaged_qty: line.damaged_qty, closing_balance: line.closing_balance, item_notes: line.item_notes };
  });
  var seen = {};
  var clientItems = inventoryPayload && Array.isArray(inventoryPayload.items) ? inventoryPayload.items : [];
  clientItems.forEach(function (line) {
    var id = line && line.brand_item_id !== null && typeof line.brand_item_id !== 'undefined' ? String(line.brand_item_id) : '';
    if (seen[id]) throw createInternalError_('INVENTORY_DUPLICATE_LINE');
    seen[id] = true;
    merged[id] = { brand_item_id: id, received_qty: line && line.received_qty,
      returned_qty: line && line.returned_qty, damaged_qty: line && line.damaged_qty,
      closing_balance: line && line.closing_balance, item_notes: line && line.item_notes };
  });
  return { general_notes: inventoryPayload && typeof inventoryPayload.general_notes === 'string'
      ? inventoryPayload.general_notes.trim() : String(existingGeneralNotes || ''),
    items: Object.keys(merged).map(function (id) { return merged[id]; }) };
}

function saveInventoryDraft(sessionToken, shiftId, inventoryPayload) {
  return safeOperation_('saveInventoryDraft', function () {
    requireInventoryContext_(sessionToken, shiftId);
    return withScriptLock_(function () {
      var context = requireInventoryContext_(sessionToken, shiftId);
      var items = loadApprovedInventoryItems_(context.session.brand);
      var found = findInventoryByShift_(context.shift.shift_id);
      if (found.record && String(found.record.status) === 'SUBMITTED') throw createInternalError_('INVENTORY_ALREADY_SUBMITTED');
      if (found.record && String(found.record.status) === 'LOCKED') throw createInternalError_('INVENTORY_ALREADY_LOCKED');
      var linesData = found.record ? loadInventoryLines_(found.record.inventory_id, items, found.record.status) : null;
      var mergedPayload = mergeInventoryDraftPayload_(inventoryPayload, linesData ? linesData.byItem : {},
        found.record ? found.record.general_notes : '');
      var openings = resolveOpeningBalances_(context.shift, items);
      var validation = validateInventoryPayload_(mergedPayload, items, openings, 'DRAFT');
      if (validation.duplicate_item_ids.length) throw createInternalError_('INVENTORY_DUPLICATE_LINE');
      if (validation.foreign_item_ids.length) throw createInternalError_('INVENTORY_FOREIGN_ITEM');
      var timestamp = nowIso_();
      var header = found.record ? publicRecord_(found.record) : {
        inventory_id: 'INVENTORY_' + Utilities.getUuid(), shift_id: String(context.shift.shift_id),
        created_by: String(context.session.user_id), created_at: timestamp, submitted_by: '', submitted_at: ''
      };
      header.status = 'DRAFT';
      header.general_notes = mergedPayload.general_notes;
      header.updated_by = String(context.session.user_id); header.updated_at = timestamp;
      writeRecordRow_(found.sheet, found.headers, found.record ? found.record.__row : null, header);
      var currentLines = linesData || loadInventoryLines_(header.inventory_id, items, header.status);
      validation.item_results.forEach(function (result) {
        var existing = currentLines.byItem[result.brand_item_id];
        var line = {
          inventory_line_id: existing ? String(existing.inventory_line_id) : 'INVENTORY_LINE_' + Utilities.getUuid(),
          inventory_id: String(header.inventory_id), brand_item_id: result.brand_item_id,
          opening_balance: result.opening_balance, received_qty: result.received_qty,
          returned_qty: result.returned_qty, damaged_qty: result.damaged_qty,
          closing_balance: result.closing_balance, consumption_qty: result.consumption_qty,
          item_notes: result.item_notes, row_status: result.row_status,
          created_at: existing ? existing.created_at : timestamp, updated_at: timestamp
        };
        writeRecordRow_(currentLines.sheet, currentLines.headers, existing ? existing.__row : null, line);
      });
      return success_(buildInventoryResponse_(header, validation, false));
    });
  });
}

function submitInventory(sessionToken, shiftId, inventoryPayload) {
  return safeOperation_('submitInventory', function () {
    requireInventoryContext_(sessionToken, shiftId);
    return withScriptLock_(function () {
      var context = requireInventoryContext_(sessionToken, shiftId);
      var items = loadApprovedInventoryItems_(context.session.brand);
      var found = findInventoryByShift_(context.shift.shift_id);
      if (!found.record) throw createInternalError_('INVENTORY_NOT_FOUND');
      if (String(found.record.status) === 'SUBMITTED') throw createInternalError_('INVENTORY_ALREADY_SUBMITTED');
      if (String(found.record.status) === 'LOCKED') throw createInternalError_('INVENTORY_ALREADY_LOCKED');
      if (String(found.record.status) !== 'DRAFT') throw createInternalError_('INVENTORY_INVALID_STATUS');
      var stored = loadInventoryLines_(found.record.inventory_id, items, found.record.status);
      var payload = inventoryPayload && Array.isArray(inventoryPayload.items)
        ? inventoryPayload : inventoryPayloadFromStored_(stored.byItem, found.record.general_notes);
      var validation = validateInventoryPayload_(payload, items, resolveOpeningBalances_(context.shift, items), 'SUBMIT');
      if (!validation.valid) throw createInternalError_('INVENTORY_MISSING_ITEMS');
      var timestamp = nowIso_();
      validation.item_results.forEach(function (result) {
        var existing = stored.byItem[result.brand_item_id];
        if (!existing) throw createInternalError_('INVENTORY_MISSING_ITEMS');
        existing.opening_balance = result.opening_balance; existing.received_qty = result.received_qty;
        existing.returned_qty = result.returned_qty; existing.damaged_qty = result.damaged_qty;
        existing.closing_balance = result.closing_balance; existing.consumption_qty = result.consumption_qty;
        existing.item_notes = result.item_notes; existing.row_status = 'VALID'; existing.updated_at = timestamp;
        writeRecordRow_(stored.sheet, stored.headers, existing.__row, existing);
      });
      var header = publicRecord_(found.record);
      header.status = 'SUBMITTED';
      header.general_notes = payload && typeof payload.general_notes === 'string'
        ? payload.general_notes.trim() : String(found.record.general_notes || '');
      header.updated_by = String(context.session.user_id); header.updated_at = timestamp;
      header.submitted_by = String(context.session.user_id); header.submitted_at = timestamp;
      writeRecordRow_(found.sheet, found.headers, found.record.__row, header);
      return success_(buildInventoryResponse_(header, validation, true));
    });
  });
}

function lockInventory(sessionToken, shiftId) {
  return safeOperation_('lockInventory', function () {
    requireInventoryContext_(sessionToken, shiftId);
    throw createInternalError_('INVENTORY_LOCK_AUTHORIZATION_BLOCKED');
  });
}
