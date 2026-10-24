const data = require('./_data');
module.exports = (req, res) => {
  const c = data().cases.find(x => x.id === req.query.id);
  c ? res.status(200).json(c) : res.status(404).json({ error: 'not found' });
};
