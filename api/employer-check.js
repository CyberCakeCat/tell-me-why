const data = require('./_data'), Employer = require('../app/lib/employer.js');
module.exports = (req, res) => {
  const q = (req.query.q || '').toString();
  if (q.trim().length < 3) return res.status(400).json({ error: 'q too short' });
  const { cases, venues } = data();
  res.status(200).json({ ...Employer.check(q, cases, venues), disclaimer: 'Signals from public records, not an accusation or legal advice.', checked_at: new Date().toISOString().slice(0, 10) });
};
