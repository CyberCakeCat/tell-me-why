// Локальный сервер: статика из app/ + /api/*. Запуск: npm run dev (порт 3000)
const http = require('http'), fs = require('fs'), path = require('path'), url = require('url');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
http.createServer((req, res) => {
  const u = url.parse(req.url, true);
  if (u.pathname.startsWith('/api/')) {
    const f = path.join(__dirname, 'api', u.pathname.slice(5) + '.js');
    if (!fs.existsSync(f)) { res.writeHead(404); return res.end('{}'); }
    res.status = c => (res.statusCode = c, res); res.json = o => (res.setHeader('Content-Type', 'application/json'), res.end(JSON.stringify(o)));
    req.query = u.query; return require(f)(req, res);
  }
  let p = path.join(__dirname, 'app', u.pathname === '/' ? 'index.html' : u.pathname);
  if (!p.startsWith(path.join(__dirname, 'app')) || !fs.existsSync(p)) { res.writeHead(404); return res.end('not found'); }
  res.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(res);
}).listen(3000, () => console.log('http://localhost:3000'));
