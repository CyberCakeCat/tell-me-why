// Данные для функций: офлайн-снимок (страховка для демо). Подключение к Atlas добавляется позже через MONGODB_URI.
const path = require('path'), fs = require('fs');
const load = f => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'app', 'data', f), 'utf8'));
let cache;
module.exports = () => cache || (cache = { cases: load('cases.json'), venues: load('venues.json') });
