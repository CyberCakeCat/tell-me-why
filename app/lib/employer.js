// Проверка работодателя: сигналы считаются кодом из cases.chain (Companies House + проверка Google/FSA).
// Работает и в браузере (window.Employer), и в Node (require) для /api.
(function (root) {
  const MONTH = 30.44 * 86400000;
  const norm = s => (s || '').toLowerCase().replace(/&/g, ' and ').replace(/\b(ltd|limited|llp|plc|london|shoreditch|hoxton|the|and)\b/g, ' ').replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
  const months = (a, b) => (new Date(b) - new Date(a)) / MONTH;

  function findCases(q, cases) {
    const n = norm(q); if (n.length < 3) return [];
    return cases.filter(c =>
      c.chain.some(x => norm(x.name).includes(n) || n.includes(norm(x.name))) ||
      (c.now_here || []).some(t => norm(t.name).includes(n)) ||
      norm(c.address).includes(n));
  }

  function signals(c) {
    const out = [], ch = [...c.chain].sort((a, b) => a.opened.localeCompare(b.opened));
    const operating = ch.filter(x => x.verification.verdict === 'operating_now');
    const closedOrGone = ch.filter(x => ['closed_google', 'no_trace', 'operating_now'].includes(x.verification.verdict));
    const traced = ch.filter(x => x.verification.verdict !== 'unclear');
    if (traced.length >= 2) out.push({ level: 'red', text: `${traced.length} venue companies have come and gone at this address (Companies House, checked against Google/FSA).`, source: 'Companies House' });
    else if (ch.length >= 2) out.push({ level: 'amber', text: `${ch.length} companies were registered and dissolved at this address; some may be registered-office only.`, source: 'Companies House' });
    if (operating.length) out.push({ level: 'red', text: `The company was dissolved but the venue is still trading (${operating.map(x => x.name.toLowerCase()).join(', ')}). For staff this is a risk of unpaid wages: ask who your employer is on paper.`, source: 'Companies House + ' + (operating[0].verification.note.startsWith('Google') ? 'Google' : 'FSA') });
    for (let i = 1; i < ch.length; i++) {
      const gap = months(ch[i - 1].closed, ch[i].opened);
      if (gap <= 3) out.push({ level: 'amber', text: `A new company (${ch[i].name.toLowerCase()}) was registered within 3 months of the previous one being dissolved.`, source: 'Companies House' });
    }
    const avg = ch.reduce((s, x) => s + x.months, 0) / ch.length;
    if (avg < 24) out.push({ level: 'amber', text: `Companies at this address last ${Math.round(avg)} months on average.`, source: 'Companies House' });
    if (c.closure_level === 'confirmed') out.push({ level: 'amber', text: 'Closure confirmed on Google (permanently or temporarily closed).', source: 'Google Places' });
    if (!out.length) out.push({ level: 'green', text: 'No signals in our data. This is not a guarantee: we only cover the area around Encode Hub.', source: 'our data' });
    return out;
  }

  function verdict(sigs) {
    return sigs.some(s => s.level === 'red') ? 'red' : sigs.some(s => s.level === 'amber') ? 'amber' : 'green';
  }

  function check(q, cases, venues) {
    const hits = findCases(q, cases);
    if (!hits.length) {
      const v = (venues || []).find(x => norm(x.name).includes(norm(q)));
      return { query: q, verdict: 'unknown', venue: v || null, cases: [], signals: [{ level: 'green', text: v ? 'Venue found (FSA/Google), but no company changes at this address in our data.' : 'Venue not found in our area (we currently cover the Encode Hub neighbourhood).', source: 'our data' }] };
    }
    const c = hits[0], s = signals(c);
    return { query: q, verdict: verdict(s), case_id: c.id, address: c.address, signals: s, chain: c.chain, now_here: c.now_here || [], others: hits.slice(1, 5).map(x => ({ id: x.id, address: x.address })) };
  }

  const api = { norm, findCases, signals, verdict, check };
  if (typeof module !== 'undefined') module.exports = api; else root.Employer = api;
})(typeof window !== 'undefined' ? window : globalThis);
