// Read-only snapshot of the case files and venues for the employer check (the demo keeps working without Atlas).
const path = require('path'), fs = require('fs');
const load = f => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'app', 'data', f), 'utf8'));
let cache;
module.exports = () => cache || (cache = { cases: load('cases.json'), venues: load('venues.json') });
