const data = require('./_data'), Employer = require('../app/lib/employer.js');
// ?q=название или адрес; ?id=id дела (экран дизайна передаёт id выбранного адреса)
module.exports = (req, res) => {
  const { cases, venues } = data();
  const id = (req.query.id || '').toString(), q = (req.query.q || '').toString();
  let result;
  if (id) {
    const c = cases.find(x => x.id === id);
    if (!c) return res.status(404).json({ error: 'case not found' });
    result = Employer.checkCase(c);
  } else {
    if (q.trim().length < 3) return res.status(400).json({ error: 'q too short' });
    result = Employer.check(q, cases, venues);
  }
  res.status(200).json({ ...result, disclaimer: 'Signals from public records, not an accusation or legal advice.', checked_at: new Date().toISOString().slice(0, 10) });
};
