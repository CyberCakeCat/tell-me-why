// Сборка статики для Vercel: app/ и поверх него design/ → public/ (тот же порядок, что в dev-server).
const fs = require('fs'), path = require('path');
const { roots, hidden, alias } = require('../site.config');
const out = path.join(__dirname, '..', 'public');
fs.rmSync(out, { recursive: true, force: true });
function copy(src, dst) {
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, e.name), d = path.join(dst, e.name);
    if (e.isDirectory()) { fs.mkdirSync(d, { recursive: true }); copy(s, d); }
    else if (!hidden.test(e.name)) { fs.mkdirSync(dst, { recursive: true }); fs.copyFileSync(s, d); }
  }
}
[...roots].reverse().forEach(r => copy(r, out));
for (const [pre, dir] of Object.entries(alias)) copy(path.join(dir, 'data'), path.join(out, pre, 'data'));
console.log('built public/ from', roots.map(r => path.basename(r)).join(' + '));
