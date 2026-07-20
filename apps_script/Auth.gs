/** Authentication and identity resolution. Client-supplied role, branch, brand, and scope are never accepted. */
function login(username, pin) {
  try {
    var normalized = normalizeUsername_(username);
    if (!normalized || typeof pin !== 'string' || !/^\d{6}$/.test(pin)) {
      return publicError_('INVALID_CREDENTIALS');
    }
    var user = findLoginUser_(normalized);
    if (!user || !isTrue_(user.is_active) || String(user.login_pin || '') !== pin) {
      return publicError_('INVALID_CREDENTIALS');
    }
    if (AUTH_CONFIG.ALLOWED_ROLES.indexOf(String(user.role_code)) === -1) {
      throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
    }
    var identity = resolveIdentity_(user, normalized);
    var session = createSession_(identity);
    return {
      ok: true,
      session_token: session.token,
      user: minimumClientIdentity_(session.payload),
      expires_at: session.payload.expires_at
    };
  } catch (error) {
    var code = error && error.internalCode === 'SYSTEM_CONFIGURATION_ERROR'
      ? 'SYSTEM_CONFIGURATION_ERROR' : 'INVALID_CREDENTIALS';
    safeDiagnostic_(code, 'login');
    return publicError_(code);
  }
}

function findLoginUser_(normalizedUsername) {
  var users = readSheetRecords_(
    AUTH_CONFIG.SHEETS.USERS,
    AUTH_CONFIG.REQUIRED_COLUMNS.Users
  );
  var matches = users.filter(function (user) {
    return normalizeUsername_(user.username) === normalizedUsername;
  });
  if (matches.length > 1) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  return matches.length === 1 ? matches[0] : null;
}

function resolveIdentity_(user, normalizedUsername) {
  var role = String(user.role_code);
  var identity = {
    user_id: String(user.user_id),
    username: normalizedUsername,
    display_name: String(user.display_name || ''),
    role: role,
    branch_id: null,
    branch_name: null,
    brand: null,
    city: null,
    scope: null
  };
  if (!identity.user_id) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  if (role === 'BRANCH_USER') return resolveBranchUser_(identity, user);
  if (role === 'BRAND_MANAGER') return resolveBrandManager_(identity);
  if (role === 'OPERATIONS_MANAGER') {
    identity.scope = { type: 'OPERATIONS', all_brands: true, all_cities: true };
    return identity;
  }
  if (role === 'ADMIN') {
    identity.scope = { type: 'ADMIN_AUTHENTICATION_ONLY' };
    return identity;
  }
  throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
}

function resolveBranchUser_(identity, user) {
  var branchId = String(user.branch_id || '').trim();
  if (!branchId) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  var branches = readSheetRecords_(AUTH_CONFIG.SHEETS.BRANCHES, AUTH_CONFIG.REQUIRED_COLUMNS.Branches);
  var matches = branches.filter(function (branch) { return String(branch.branch_id) === branchId; });
  if (matches.length !== 1 || !isTrue_(matches[0].is_active)) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  var branch = matches[0];
  var brand = requireActiveBrand_(String(branch.brand_code));
  identity.branch_id = branchId;
  identity.branch_name = String(branch.branch_name_ar || branch.branch_name_en || '');
  identity.brand = String(brand.brand_code);
  identity.city = String(branch.city_code);
  identity.scope = { type: 'BRANCH', branch_id: branchId, brand: identity.brand, city: identity.city };
  return identity;
}

function resolveBrandManager_(identity) {
  var scopes = readSheetRecords_(AUTH_CONFIG.SHEETS.USER_SCOPES, AUTH_CONFIG.REQUIRED_COLUMNS.User_Scopes)
    .filter(function (scope) { return String(scope.user_id) === identity.user_id && isTrue_(scope.is_active); });
  if (!scopes.length) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  var seen = {};
  var normalizedScopes = scopes.map(function (scope) {
    var brandCode = String(scope.brand_code);
    var cityCode = String(scope.city_code);
    var key = cityCode + '|' + brandCode;
    if (!cityCode || seen[key]) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
    seen[key] = true;
    requireActiveBrand_(brandCode);
    return { scope_id: String(scope.scope_id), city: cityCode, brand: brandCode };
  });
  identity.scope = { type: 'CITY_BRAND', records: normalizedScopes };
  return identity;
}

function requireActiveBrand_(brandCode) {
  var brands = readSheetRecords_(AUTH_CONFIG.SHEETS.BRANDS, AUTH_CONFIG.REQUIRED_COLUMNS.Brands);
  var matches = brands.filter(function (brand) { return String(brand.brand_code) === brandCode; });
  if (matches.length !== 1 || !isTrue_(matches[0].is_active)) throw createInternalError_('SYSTEM_CONFIGURATION_ERROR');
  return matches[0];
}

function minimumClientIdentity_(payload) {
  var user = {
    user_id: payload.user_id,
    username: payload.username,
    display_name: payload.display_name,
    role: payload.role
  };
  if (payload.branch_id) user.branch_id = payload.branch_id;
  if (payload.branch_name) user.branch_name = payload.branch_name;
  if (payload.brand) user.brand = payload.brand;
  if (payload.city) user.city = payload.city;
  if (payload.scope) user.scope = payload.scope;
  return user;
}
