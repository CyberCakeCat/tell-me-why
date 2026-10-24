// The site is assembled from two folders: design/ (the screens) and app/ (data and shared logic).
// If a file exists in both, design/ wins. Design working files are not served.
const path = require('path');
module.exports = {
  roots: ['design', 'app'].map(d => path.join(__dirname, d)),
  // design/app.js reads '../app/data/cases.json', which resolves to /app/data/… from the site root.
  alias: { '/app/': path.join(__dirname, 'app') },
  hidden: /\.(md|py)$|^\/?serve\.py$/i,
};
