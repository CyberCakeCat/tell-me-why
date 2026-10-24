const LEVEL = { confirmed: ['Confirmed closed (Google)', 'var(--red)'], probable: ['Probably closed', 'var(--amber)'], possible: ['Unclear', '#8a867d'], entity_change: ['Company changed, venue open', 'var(--green)'] };
const VERDICT = { closed_google: ['Closed on Google', ''], no_trace: ['No trace found, probably closed', 'unk'], unclear: ['Unclear, not counted as a closure', 'unk'], operating_now: ['Venue still trading: company changed', 'ok'] };
const CONF = { low: 'low confidence', medium: 'medium confidence', high: 'high confidence' };
const $ = s => document.querySelector(s), esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
let cases = [], venues = [], map, markers = {}, filter = 'all', query = '', selected = null;

const badge = l => `<span class="badge b-${l}">${LEVEL[l][0]}</span>`;
const fmt = d => d ? d.slice(0, 7) : '?';

function timeline(chain) {
  return `<ul class="tl">${chain.map(x => { const v = x.verification, m = VERDICT[v.verdict];
    return `<li class="${m[1]}"><b>${esc(x.name.toLowerCase().replace(/(^|\s)\S/g, c => c.toUpperCase()))}</b> · ${fmt(x.opened)} → ${fmt(x.closed)} (${x.months} mo)
    <small>${m[0]}<span class="src">${v.verdict === 'closed_google' ? 'Google' : v.verdict === 'operating_now' ? 'Google/FSA' : 'Companies House'}</span></small>
    <small>${esc(v.note)}</small></li>`; }).join('')}</ul>`;
}

function visible() {
  const base = query ? Employer.findCases(query, cases) : cases;
  return base.filter(c => filter === 'all' || c.closure_level === filter);
}

function renderList() {
  const v = visible();
  $('#list').innerHTML = v.length ? v.map(c => `<div class="card ${selected === c.id ? 'sel' : ''}" data-id="${c.id}">
    <h3>${esc(c.address.replace(', London', ''))}</h3>${badge(c.closure_level)}
    <div style="color:var(--muted);margin-top:6px">${c.chain.length} compan${c.chain.length > 1 ? 'ies' : 'y'} · ${c.dist_hub_m} m from Encode Hub</div></div>`).join('')
    : '<p class="sub">Nothing found. Try “Pitfield”, “Rivington” or “Great Eastern”.</p>';
  Object.entries(markers).forEach(([id, m]) => v.some(c => c.id === id) ? m.addTo(map) : m.remove());
}

function showCase(id, pan = true) {
  const c = cases.find(x => x.id === id); if (!c) return; selected = id; renderList();
  if (pan) map.flyTo([c.location.coordinates[1], c.location.coordinates[0]], 17, { duration: .6 });
  const a = c.analysis || {}, x = c.context || {};
  $('#detail').innerHTML = `<div class="panel"><h2>${esc(c.address.replace(', London', ''))}</h2>${badge(c.closure_level)}
    <h4>Who was here (company records, checked against Google and FSA)</h4>${timeline(c.chain)}
    ${a.headline ? `<h4>Why it may have failed — hypotheses, not facts</h4><p>${esc(a.headline)}</p>${(a.hypotheses || []).map(h => `<div class="hyp"><b>${esc(h.reason)}</b>
      <div class="conf">${CONF[h.confidence] || ''} · evidence: ${(h.evidence || []).map(esc).join('; ')}</div>
      <div class="conf">Counter-argument: ${esc(h.counter_argument)}</div></div>`).join('')}` : ''}
    <h4>Around it</h4><p>${x.nearest_station ? `${esc(x.nearest_station.name)} ${x.nearest_station.m} m · ` : ''}${x.venues_within_150m_FSA ?? '?'} food venues within 150 m (FSA)${x.neighbour_google_rating_median ? ` · neighbours' median Google rating ${x.neighbour_google_rating_median}` : ''}</p>
    ${(c.now_here || []).length ? `<h4>Trading here now</h4><p>${c.now_here.slice(0, 5).map(t => esc(t.name)).join(', ')}</p>` : ''}
    <p class="disc">Signals from public records (Companies House, Google, FSA). Hypotheses, not accusations or advice. Company changes can have ordinary reasons. Checked ${esc(c.verified_at || '')}.</p></div>`;
  $('#detail').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function initMap() {
  map = L.map('map').setView([51.5265, -0.0838], 16);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors', maxZoom: 19, className: 'tiles' }).addTo(map);
  L.marker([51.527626, -0.083849], { title: 'Encode Hub' }).addTo(map).bindTooltip('Encode Hub');
  cases.forEach(c => {
    const m = L.circleMarker([c.location.coordinates[1], c.location.coordinates[0]], { radius: 8, color: '#fff', weight: 2, fillColor: getComputedStyle(document.documentElement).getPropertyValue(LEVEL[c.closure_level][1].slice(4, -1)) || LEVEL[c.closure_level][1], fillOpacity: .95 });
    m.on('click', () => showCase(c.id, false)); m.bindTooltip(c.address.replace(', London', '')); markers[c.id] = m;
  });
}

const HELP = [['Acas — free workplace advice', 'https://www.acas.org.uk'], ['HMRC — report unpaid minimum wage', 'https://www.gov.uk/pay-and-work-rights-complaints'], ['Redundancy Payments Service — if your employer is insolvent', 'https://www.gov.uk/claim-redundancy/if-your-employer-is-insolvent'], ['Citizens Advice', 'https://www.citizensadvice.org.uk']];
const ASK = ['Who is my employer on the contract (exact company name and number)?', 'Will I get payslips and a written contract before my first shift?', 'How and when is pay and tips paid? Is it through PAYE?', 'Has the company or owner changed in the last 2 years?'];

function runCheck(q) {
  const r = Employer.check(q, cases, venues), label = { red: 'Insolvency confirmed', amber: 'Needs verification', green: 'No signals found', unknown: 'No data' }[r.verdict];
  $('#worker-result').innerHTML = `<div class="panel"><div class="light ${r.verdict}"><div class="dot"></div><div><b style="font-size:18px">${label}</b><br>${esc(r.address || (r.venue && r.venue.address) || q)}</div></div>
    ${r.signals.map(s => `<div class="sig ${s.level}"><i></i><div>${esc(s.text)}<span class="src">${esc(s.source)}</span></div></div>`).join('')}
    ${r.chain ? `<h4>Companies at this address</h4>${timeline(r.chain)}` : ''}
    <h4>Ask before you start</h4><ul>${ASK.map(a => `<li>${a}</li>`).join('')}</ul>
    <h4>If something has already gone wrong</h4><ul>${HELP.map(h => `<li><a href="${h[1]}" target="_blank" rel="noopener">${h[0]}</a></li>`).join('')}</ul>
    <p class="disc">Signals from public records (Companies House, Google, FSA). Not an accusation and not legal advice. Company changes can have ordinary reasons.</p></div>`;
}

function setMode(m) {
  document.querySelectorAll('.modes button').forEach(b => b.classList.toggle('on', b.dataset.mode === m));
  $('#owner').classList.toggle('hidden', m !== 'owner'); $('#worker').classList.toggle('hidden', m !== 'worker');
  if (m === 'owner') setTimeout(() => map.invalidateSize(), 50);
}

(async () => {
  [cases, venues] = await Promise.all([fetch('data/cases.json').then(r => r.json()), fetch('data/venues.json').then(r => r.json())]);
  cases.sort((a, b) => ['confirmed', 'probable', 'entity_change', 'possible'].indexOf(a.closure_level) - ['confirmed', 'probable', 'entity_change', 'possible'].indexOf(b.closure_level) || b.chain.length - a.chain.length);
  initMap();
  $('#levels').innerHTML = [['all', 'All']].concat(Object.entries(LEVEL).map(([k, v]) => [k, v[0]])).map(([k, t]) => `<button class="chip ${k === 'all' ? 'on' : ''}" data-l="${k}">${t}</button>`).join('');
  $('#levels').onclick = e => { const b = e.target.closest('[data-l]'); if (!b) return; filter = b.dataset.l; document.querySelectorAll('#levels .chip').forEach(x => x.classList.toggle('on', x === b)); renderList(); };
  $('#list').onclick = e => { const c = e.target.closest('.card'); if (c) showCase(c.dataset.id); };
  $('#owner-form').onsubmit = e => { e.preventDefault(); query = $('#owner-q').value.trim(); renderList(); const v = visible(); if (v.length) map.fitBounds(v.map(c => [c.location.coordinates[1], c.location.coordinates[0]]), { maxZoom: 17, padding: [30, 30] }); };
  const ex = ['Schnitzel Heaven', 'Best Mangal', 'Nanashi', 'Gundiburger'];
  $('#examples').innerHTML = ex.map(x => `<button class="chip">${x}</button>`).join('');
  $('#examples').onclick = e => { if (e.target.classList.contains('chip')) { $('#worker-q').value = e.target.textContent; runCheck(e.target.textContent); } };
  $('#worker-form').onsubmit = e => { e.preventDefault(); const q = $('#worker-q').value.trim(); if (q.length >= 3) runCheck(q); };
  document.querySelector('.modes').onclick = e => { const b = e.target.closest('button'); if (b) setMode(b.dataset.mode); };
  renderList();
})();
