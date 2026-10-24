// Local server: screens from design/, data and logic from app/, plus /api/*. Run: npm run dev (port 3000)
const http = require('http'), fs = require('fs'), path = require('path');
const { roots, hidden, alias } = require('./site.config');
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.txt': 'text/plain' };

function resolve(p) {
  if (p.endsWith('/')) p += 'index.html';
  if (hidden.test(p)) return null;
  for (const [pre, dir] of Object.entries(alias)) if (p.startsWith(pre)) {
    const f = path.join(dir, p.slice(pre.length));
    return f.startsWith(dir + path.sep) && fs.existsSync(f) && fs.statSync(f).isFile() ? f : null;
  }
  for (const root of roots) {
    const f = path.join(root, p);
    if (f.startsWith(root + path.sep) && fs.existsSync(f) && fs.statSync(f).isFile()) return f;
  }
  return null;
}

http.createServer((req, res) => {
  const u = new URL(req.url, 'http://localhost');
  if (u.pathname.startsWith('/api/')) {
    const f = path.join(__dirname, 'api', path.basename(u.pathname) + '.js');
    if (!fs.existsSync(f)) { res.writeHead(404); return res.end('{}'); }
    res.status = c => (res.statusCode = c, res); res.json = o => (res.setHeader('Content-Type', 'application/json'), res.end(JSON.stringify(o)));
    req.query = Object.fromEntries(u.searchParams);
    try { return require(f)(req, res); } catch (e) { console.error(e); res.statusCode = 500; return res.end('{"error":"server error"}'); }
  }
  const f = resolve(decodeURIComponent(u.pathname));
  if (!f) { res.writeHead(404); return res.end('not found'); }
  res.writeHead(200, { 'Content-Type': types[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
}).listen(3000, () => console.log('http://localhost:3000'));
