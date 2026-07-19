/** Minimal Sprint 1 web-app entry point. No operational data is exposed. */
function doGet() {
  return ContentService
    .createTextOutput(JSON.stringify(healthCheck()))
    .setMimeType(ContentService.MimeType.JSON);
}

function healthCheck() {
  return {
    ok: true,
    version: AUTH_CONFIG.VERSION,
    timestamp: new Date().toISOString()
  };
}
