// Tiny upload server — receives screenshots from the browser and saves them.
// Usage:  node screenshot_server.js
// Listens on http://localhost:5555  ;  POST /upload?name=foo.png  body = raw image bytes

const http = require('http');
const fs = require('fs');
const path = require('path');

const OUT_DIR = path.join(__dirname, 'screenshots');
if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

const server = http.createServer((req, res) => {
  // CORS — browser POSTs from localhost:4173 to localhost:5555
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  if (req.method === 'GET' && req.url === '/') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('screenshot_server up on :5555\nPOST /upload?name=foo.png with raw bytes\n');
    return;
  }

  if (req.method === 'POST' && req.url.startsWith('/upload')) {
    const url = new URL(req.url, 'http://localhost:5555');
    const name = url.searchParams.get('name') || ('shot_' + Date.now() + '.png');
    const safe = name.replace(/[^a-zA-Z0-9_.-]/g, '_');
    const out = path.join(OUT_DIR, safe);
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
      const buf = Buffer.concat(chunks);
      fs.writeFile(out, buf, err => {
        if (err) { res.writeHead(500); res.end(err.message); return; }
        console.log('saved', safe, '(' + buf.length + ' bytes)');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, path: out, bytes: buf.length, name: safe }));
      });
    });
    req.on('error', e => { res.writeHead(500); res.end(e.message); });
    return;
  }

  res.writeHead(404); res.end('not found');
});

server.listen(5555, '127.0.0.1', () => {
  console.log('screenshot_server listening on http://127.0.0.1:5555');
  console.log('saving to:', OUT_DIR);
});
