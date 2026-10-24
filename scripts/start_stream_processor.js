// mongosh script: (re)creates and starts the Atlas Stream Processing processor `closures_to_alerts`
// from scripts/stream_processor.json. Idempotent: stops and drops an existing processor of the same name first.
//
// Run from the project folder (the workspace URL comes from Atlas: Stream Processing -> Connect -> Shell tab;
// only the mongodb://... part is needed, it holds no password):
//   SP_URI="mongodb://atlas-stream-....mongodb.net/" mongosh --nodb scripts/start_stream_processor.js
//
// Credentials are read from the git-ignored atlas_user.txt / atlas_password.txt (the user needs the atlasAdmin role)
// and are never printed. Prerequisite in the workspace's Connection Registry: an Atlas Database connection to
// Cluster0 named exactly `deadspot`.
const fs = require('fs');
const path = require('path');

const root = typeof __dirname !== 'undefined' ? path.join(__dirname, '..') : process.cwd();
const read = f => fs.readFileSync(path.join(root, f), 'utf8').trim();
const spec = JSON.parse(read('scripts/stream_processor.json'));
const NAME = spec.name;

const raw = (process.env.SP_URI || '').trim().replace(/^mongosh\s+/, '').replace(/^"|"$/g, '').split(/\s/)[0];
if (!/^mongodb(\+srv)?:\/\//.test(raw)) {
  print('Set SP_URI to the workspace connection string (mongodb://atlas-stream-...). Nothing was changed.');
  quit(1);
}
const url = new URL(raw);
url.username = encodeURIComponent(read('atlas_user.txt'));
url.password = encodeURIComponent(read('atlas_password.txt'));
if (!url.searchParams.has('tls')) url.searchParams.set('tls', 'true');
if (!url.searchParams.has('authSource')) url.searchParams.set('authSource', 'admin');

try {
  db = connect(url.toString()); // re-binds the global `sp` helper to the workspace
} catch (e) {
  print('Could not connect to the workspace: ' + String(e.message).replace(/\/\/[^@]*@/g, '//***@'));
  quit(1);
}

const conns = sp.listConnections();
const names = ((conns && conns.connections) || []).map(c => c.name);
if (!names.includes('deadspot')) {
  print('Connection Registry has no connection named "deadspot" (found: ' + (names.join(', ') || 'none') + '). Add it in Atlas first.');
  quit(1);
}

const existing = sp.listStreamProcessors({ name: NAME });
if (Array.isArray(existing) && existing.length) {
  try { sp[NAME].stop(); } catch (e) { /* already stopped */ }
  sp[NAME].drop();
  print('Dropped the previous ' + NAME);
}

sp.createStreamProcessor(NAME, spec.pipeline);
sp[NAME].start();
const st = sp[NAME].stats();
print(NAME + ' status: ' + ((st && st.stats && st.stats.status) || JSON.stringify(st)));
print('Next: set STREAM_PROCESSING=on in Vercel and redeploy, so the API stops writing fallback alerts.');
