const data = require('./_data');
module.exports = (req, res) => {
  const { cases } = data();
  const level = req.query.level;
  res.setHeader('Cache-Control', 's-maxage=300');
  res.status(200).json(level ? cases.filter(c => c.closure_level === level) : cases);
};
