/** Sessions are opaque tokens; only a SHA-256 token fingerprint is used as the cache key. */
function createSession_(identity) {
  var now = new Date().getTime();
  var tokenMaterial = [Utilities.getUuid(), Utilities.getUuid(), now, Math.random()].join('|');
  var token = Utilities.base64EncodeWebSafe(signedBytes_(unsignedBytes_(Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256, utf8Bytes_(tokenMaterial)
  )))).replace(/=+$/, '');
  var payload = {
    user_id: identity.user_id,
    username: identity.username,
    display_name: identity.display_name || '',
    role: identity.role,
    branch_id: identity.branch_id || null,
    branch_name: identity.branch_name || null,
    brand: identity.brand || null,
    city: identity.city || null,
    scope: identity.scope,
    login_time: new Date(now).toISOString(),
    expires_at: new Date(now + AUTH_CONFIG.SESSION_TTL_SECONDS * 1000).toISOString(),
    session_version: AUTH_CONFIG.SESSION_VERSION
  };
  CacheService.getScriptCache().put(
    AUTH_CONFIG.SESSION_CACHE_PREFIX + sha256Hex_(token),
    JSON.stringify(payload),
    AUTH_CONFIG.SESSION_TTL_SECONDS
  );
  return { token: token, payload: payload };
}

function readSession_(sessionToken) {
  if (typeof sessionToken !== 'string' || !/^[A-Za-z0-9_-]{32,256}$/.test(sessionToken)) {
    return { ok: false, code: 'INVALID_SESSION' };
  }
  var key = AUTH_CONFIG.SESSION_CACHE_PREFIX + sha256Hex_(sessionToken);
  var raw = CacheService.getScriptCache().get(key);
  if (!raw) return { ok: false, code: 'INVALID_SESSION' };
  try {
    var payload = JSON.parse(raw);
    if (payload.session_version !== AUTH_CONFIG.SESSION_VERSION) {
      CacheService.getScriptCache().remove(key);
      return { ok: false, code: 'INVALID_SESSION' };
    }
    if (!payload.expires_at || new Date(payload.expires_at).getTime() <= new Date().getTime()) {
      CacheService.getScriptCache().remove(key);
      return { ok: false, code: 'SESSION_EXPIRED' };
    }
    return { ok: true, key: key, payload: payload };
  } catch (error) {
    CacheService.getScriptCache().remove(key);
    return { ok: false, code: 'INVALID_SESSION' };
  }
}

function validateSession(sessionToken) {
  var result = readSession_(sessionToken);
  if (!result.ok) return publicError_(result.code);
  return { ok: true, expires_at: result.payload.expires_at };
}

function getCurrentUser(sessionToken) {
  var result = readSession_(sessionToken);
  if (!result.ok) return publicError_(result.code);
  return { ok: true, user: minimumClientIdentity_(result.payload), expires_at: result.payload.expires_at };
}

function logout(sessionToken) {
  if (typeof sessionToken === 'string' && /^[A-Za-z0-9_-]{32,256}$/.test(sessionToken)) {
    CacheService.getScriptCache().remove(AUTH_CONFIG.SESSION_CACHE_PREFIX + sha256Hex_(sessionToken));
  }
  return { ok: true };
}
