// Сайт собирается из двух папок: design/ (экраны от ChatGPT, правятся отдельно) и app/ (данные, общая логика, классический вид).
// Если файл есть в обеих, побеждает design/. Служебные файлы дизайна наружу не отдаются.
const path = require('path');
module.exports = {
  roots: ['design', 'app'].map(d => path.join(__dirname, d)),
  // design/app.js читает '../app/data/cases.json': с корня сайта это /app/data/…, поэтому app/ доступен и по /app/
  alias: { '/app/': path.join(__dirname, 'app') },
  hidden: /\.(md|py)$|^\/?serve\.py$/i,
};
