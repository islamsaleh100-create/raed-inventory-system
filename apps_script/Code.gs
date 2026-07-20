/** Web UI entry point. Use ?format=json to retain the existing health endpoint. */
function doGet(event) {
  if (event && event.parameter && String(event.parameter.format).toLowerCase() === 'json') {
    return ContentService
      .createTextOutput(JSON.stringify(healthCheck()))
      .setMimeType(ContentService.MimeType.JSON);
  }
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('عمليات فروع رائد')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function include_(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

function healthCheck() {
  return {
    ok: true,
    version: AUTH_CONFIG.VERSION,
    timestamp: new Date().toISOString()
  };
}
