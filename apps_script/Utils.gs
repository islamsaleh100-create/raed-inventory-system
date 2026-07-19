/** Shared authentication utilities. Never log passwords, hashes, salts, or full tokens. */
function createInternalError_(code) {
  var error = new Error(code);
  error.internalCode = code;
  return error;
}

function normalizeUsername_(username) {
  if (typeof username !== 'string') return '';
  return username.trim().toLowerCase();
}

function isTrue_(value) {
  return value === true || String(value).trim().toUpperCase() === 'TRUE';
}

function utf8Bytes_(value) {
  return Utilities.newBlob(String(value)).getBytes();
}

function unsignedBytes_(bytes) {
  return bytes.map(function (value) { return value < 0 ? value + 256 : value; });
}

function signedBytes_(bytes) {
  return bytes.map(function (value) { return value > 127 ? value - 256 : value; });
}

function int32Bytes_(value) {
  return [(value >>> 24) & 255, (value >>> 16) & 255, (value >>> 8) & 255, value & 255];
}

function hmacSha256_(messageBytes, keyBytes) {
  return unsignedBytes_(Utilities.computeHmacSha256Signature(
    signedBytes_(messageBytes), signedBytes_(keyBytes)
  ));
}

/** Standards-compatible PBKDF2-HMAC-SHA256, one 32-byte derived-key block. */
function derivePasswordBytes_(password, saltBytes, iterations) {
  var keyBytes = utf8Bytes_(password);
  var block = saltBytes.concat(int32Bytes_(1));
  var u = hmacSha256_(block, keyBytes);
  var output = u.slice();
  for (var i = 1; i < iterations; i += 1) {
    u = hmacSha256_(u, keyBytes);
    for (var j = 0; j < output.length; j += 1) output[j] ^= u[j];
  }
  return output;
}

function constantTimeEqual_(left, right) {
  var a = left || [];
  var b = right || [];
  var length = Math.max(a.length, b.length);
  var difference = a.length ^ b.length;
  for (var i = 0; i < length; i += 1) {
    difference |= (a[i % (a.length || 1)] || 0) ^ (b[i % (b.length || 1)] || 0);
  }
  return difference === 0;
}

function createPasswordHash(password) {
  if (typeof password !== 'string' || password.length < AUTH_CONFIG.PASSWORD_MIN_LENGTH) {
    throw createInternalError_('INVALID_PASSWORD_POLICY');
  }
  var entropy = Utilities.getUuid() + '|' + new Date().getTime() + '|' + Math.random();
  var salt = unsignedBytes_(Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256, utf8Bytes_(entropy)
  )).slice(0, 16);
  var derived = derivePasswordBytes_(password, salt, AUTH_CONFIG.HASH_ITERATIONS);
  return [
    AUTH_CONFIG.HASH_VERSION,
    AUTH_CONFIG.HASH_ITERATIONS,
    Utilities.base64Encode(signedBytes_(salt)),
    Utilities.base64Encode(signedBytes_(derived))
  ].join('$');
}

function verifyPassword(password, storedHash) {
  try {
    if (typeof password !== 'string' || !password || typeof storedHash !== 'string') return false;
    var parts = storedHash.split('$');
    if (parts.length !== 4 || parts[0] !== AUTH_CONFIG.HASH_VERSION) return false;
    var iterations = Number(parts[1]);
    if (!Number.isInteger(iterations) || iterations < 10000 || iterations > 1000000) return false;
    var salt = unsignedBytes_(Utilities.base64Decode(parts[2]));
    var expected = unsignedBytes_(Utilities.base64Decode(parts[3]));
    if (salt.length < 16 || expected.length !== 32) return false;
    var actual = derivePasswordBytes_(password, salt, iterations);
    return constantTimeEqual_(actual, expected);
  } catch (error) {
    return false;
  }
}

function sha256Hex_(value) {
  return unsignedBytes_(Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256, utf8Bytes_(value)
  )).map(function (byte) { return ('0' + byte.toString(16)).slice(-2); }).join('');
}

function readSheetRecords_(sheetName, requiredColumns) {
  var spreadsheet = SpreadsheetApp.openById(getSpreadsheetId());
  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  var values = sheet.getDataRange().getValues();
  if (!values.length) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  var headers = values[0].map(function (value) { return String(value).trim(); });
  var seen = {};
  headers.forEach(function (header) {
    if (!header || seen[header]) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
    seen[header] = true;
  });
  requiredColumns.forEach(function (column) {
    if (!seen[column]) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  });
  return values.slice(1).filter(function (row) {
    return row.some(function (value) { return value !== '' && value !== null; });
  }).map(function (row) {
    var record = {};
    headers.forEach(function (header, index) { record[header] = row[index]; });
    return record;
  });
}

function safeDiagnostic_(code, context) {
  console.error(JSON.stringify({ code: code, context: context || null }));
}

function publicError_(code) {
  var messages = {
    INVENTORY_NOT_FOUND: 'Inventory was not found.',
    INVENTORY_ALREADY_SUBMITTED: 'Inventory has already been submitted.',
    INVENTORY_ALREADY_LOCKED: 'Inventory is locked.',
    INVENTORY_INVALID_STATUS: 'Inventory status is invalid.',
    INVENTORY_DUPLICATE_HEADER: 'Duplicate Inventory headers were found.',
    INVENTORY_DUPLICATE_LINE: 'Duplicate Inventory lines were found.',
    INVENTORY_MISSING_ITEMS: 'Required Inventory items are missing.',
    INVENTORY_FOREIGN_ITEM: 'An Inventory item is outside the authenticated brand.',
    INVENTORY_INVALID_NUMBER: 'An Inventory quantity is invalid.',
    INVENTORY_NEGATIVE_VALUE: 'Inventory quantities cannot be negative.',
    INVENTORY_NEGATIVE_CONSUMPTION: 'Calculated consumption cannot be negative.',
    INVENTORY_OPENING_BALANCE_MISMATCH: 'Opening balance is not authoritative.',
    INVENTORY_LOCK_AUTHORIZATION_BLOCKED: 'Inventory locking authorization is not configured.',
    INVENTORY_DATA_CORRUPTION: 'Inventory data is inconsistent.',
    INVALID_CREDENTIALS: 'اسم المستخدم أو كلمة المرور غير صحيحة.',
    SYSTEM_CONFIGURATION_ERROR: 'تعذر إكمال الطلب بسبب إعدادات النظام.',
    SESSION_EXPIRED: 'انتهت صلاحية الجلسة. يرجى تسجيل الدخول مرة أخرى.',
    INVALID_SESSION: 'الجلسة غير صالحة. يرجى تسجيل الدخول مرة أخرى.',
    SHIFT_NOT_ALLOWED: 'هذا الشفت غير متاح للفرع.',
    SHIFT_NOT_FOUND: 'لم يتم العثور على الشفت.',
    SHIFT_ALREADY_SUBMITTED: 'تم إرسال هذا الشفت ولا يمكن تعديله.',
    SHIFT_LOCKED: 'هذا الشفت مقفل.',
    SALES_VALIDATION_FAILED: 'بيانات المبيعات غير مكتملة أو غير صحيحة.',
    SALES_NOT_FOUND: 'لم يتم العثور على بيانات المبيعات.',
    DATA_INTEGRITY_ERROR: 'تعذر إكمال الطلب بسبب تعارض في البيانات.'
  };
  return { ok: false, code: code, message: messages[code] || messages.SYSTEM_CONFIGURATION_ERROR };
}

function success_(data) { return { ok: true, data: data }; }

function nowIso_() { return new Date().toISOString(); }

function requireSessionBranch_(sessionToken) {
  var session = readSession_(sessionToken);
  if (!session.ok) throw createInternalError_(session.code);
  if (!session.payload.branch_id || !session.payload.user_id) {
    throw createInternalError_('INVALID_SESSION');
  }
  return session.payload;
}

function getOperationalSheet_(sheetName, requiredColumns) {
  var sheet = SpreadsheetApp.openById(getSpreadsheetId()).getSheetByName(sheetName);
  if (!sheet) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
    .map(function (value) { return String(value).trim(); });
  if (headers.length !== requiredColumns.length || headers.some(function (h, i) { return h !== requiredColumns[i]; })) {
    throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  }
  return { sheet: sheet, headers: headers };
}

function readOperationalRows_(sheetName, requiredColumns) {
  var contract = getOperationalSheet_(sheetName, requiredColumns);
  var lastRow = contract.sheet.getLastRow();
  if (lastRow < 2) return { sheet: contract.sheet, headers: contract.headers, rows: [] };
  var values = contract.sheet.getRange(2, 1, lastRow - 1, contract.headers.length).getValues();
  var rows = values.map(function (row, index) {
    var record = { __row: index + 2 };
    contract.headers.forEach(function (header, column) { record[header] = row[column]; });
    return record;
  }).filter(function (record) {
    return contract.headers.some(function (header) { return record[header] !== '' && record[header] !== null; });
  });
  return { sheet: contract.sheet, headers: contract.headers, rows: rows };
}

function writeRecordRow_(sheet, headers, rowNumber, record) {
  var values = headers.map(function (header) {
    return Object.prototype.hasOwnProperty.call(record, header) ? record[header] : '';
  });
  if (rowNumber) sheet.getRange(rowNumber, 1, 1, headers.length).setValues([values]);
  else sheet.appendRow(values);
}

function publicRecord_(record) {
  var output = {};
  Object.keys(record).forEach(function (key) { if (key !== '__row') output[key] = record[key]; });
  return output;
}

function withScriptLock_(callback) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(AUTH_CONFIG.LOCK_TIMEOUT_MS)) throw createInternalError_('DATA_INTEGRITY_ERROR');
  try { return callback(); } finally { lock.releaseLock(); }
}

function safeOperation_(context, callback) {
  try { return callback(); }
  catch (error) {
    var allowed = ['INVALID_SESSION', 'SESSION_EXPIRED', 'SHIFT_NOT_ALLOWED', 'SHIFT_NOT_FOUND',
      'SHIFT_ALREADY_SUBMITTED', 'SHIFT_LOCKED', 'SALES_VALIDATION_FAILED', 'SALES_NOT_FOUND',
      'SYSTEM_CONFIGURATION_ERROR', 'DATA_INTEGRITY_ERROR', 'INVENTORY_NOT_FOUND',
      'INVENTORY_ALREADY_SUBMITTED', 'INVENTORY_ALREADY_LOCKED', 'INVENTORY_INVALID_STATUS',
      'INVENTORY_DUPLICATE_HEADER', 'INVENTORY_DUPLICATE_LINE', 'INVENTORY_MISSING_ITEMS',
      'INVENTORY_FOREIGN_ITEM', 'INVENTORY_INVALID_NUMBER', 'INVENTORY_NEGATIVE_VALUE',
      'INVENTORY_NEGATIVE_CONSUMPTION', 'INVENTORY_OPENING_BALANCE_MISMATCH',
      'INVENTORY_LOCK_AUTHORIZATION_BLOCKED', 'INVENTORY_DATA_CORRUPTION'];
    var code = error && allowed.indexOf(error.internalCode) !== -1
      ? error.internalCode : 'SYSTEM_CONFIGURATION_ERROR';
    safeDiagnostic_(code, context);
    return publicError_(code);
  }
}
