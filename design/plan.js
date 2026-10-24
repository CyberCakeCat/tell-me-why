// Plan a venue: concept + street / address / postcode → direct competitors, competition level,
// typical price, customers around and closure case files nearby. Every number is computed here from
// data/venues_all.json (FSA + Google merged by scripts/build_venues.py); no model is involved on this screen.
const CONCEPTS = {
  coffee: ['Coffee shop', 'coffee shops'],
  bakery: ['Bakery or patisserie', 'bakeries and patisseries'],
  restaurant: ['Restaurant (hot kitchen)', 'restaurants'],
  takeaway: ['Takeaway or sandwich shop', 'takeaways'],
  bar: ['Bar or pub', 'bars and pubs'],
};
let venuesAll = [];

function median(xs) { const s = xs.filter(x => x != null).sort((a, b) => a - b); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
const normStreet = s => String(s || '').toLowerCase().replace(/\bst\b\.?/g, 'street').replace(/\brd\b\.?/g, 'road').replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();

async function locate(q) {
  const pc = q.trim().toUpperCase().match(/^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$/);
  if (pc) {
    try { const r = await json(`https://api.postcodes.io/postcodes/${encodeURIComponent(q.trim())}`); return { at: [r.result.longitude, r.result.latitude], label: r.result.postcode, how: 'postcode' }; } catch { return null; }
  }
  const n = normStreet(q); if (n.length < 3) return null;
  const pts = venuesAll.map(v => ({ a: v.address, loc: v.loc })).filter(x => normStreet(x.a).includes(n));  // same rule as find_place in /api/ask
  if (!pts.length) return null;
  const at = [pts.reduce((s, x) => s + x.loc[0], 0) / pts.length, pts.reduce((s, x) => s + x.loc[1], 0) / pts.length];
  return { at, label: q.trim().replace(/\b\w/g, c => c.toUpperCase()), how: `${pts.length} addresses on this street` };
}

// Competition level: competitors here compared with the same count around every venue in the neighbourhood.
function competitionLevel(concept, at, r) {
  const mine = venuesAll.filter(v => v.concept === concept && gap({ coordinates: v.loc }, { coordinates: at }) <= r).length;
  const sample = venuesAll.filter((_, i) => i % 3 === 0).map(s => venuesAll.filter(v => v.concept === concept && gap({ coordinates: v.loc }, { coordinates: s.loc }) <= r).length);
  const below = sample.filter(x => x < mine).length / (sample.length || 1);
  const level = below >= 0.75 ? ['High', 'confirmed'] : below <= 0.35 ? ['Low', 'entity_change'] : ['Medium', 'probable'];
  return { mine, pct: Math.round(below * 100), level };
}

// The form a first-time visitor sees: three friendly steps, big concept tiles, two areas with their streets,
// and the radius expressed as a walk. The ids (#plan-q, #plan-r, [data-concept]) are what plan() wires up.
const CONCEPT_HINT = {
  coffee: ['☕', 'Espresso, pastries, a laptop or two'], bakery: ['🥐', 'Bread, cakes, coffee to go'],
  restaurant: ['🍝', 'A proper kitchen and table service'], takeaway: ['🥪', 'Quick lunches, sandwiches, delivery'], bar: ['🍷', 'Drinks first, evenings and weekends'],
};
const AREA_STREETS = {
  'Shoreditch & Hoxton': ['Pitfield Street', 'Rivington Street', 'Curtain Road', 'Great Eastern Street'],
  'Richmond & St Margarets': ['George Street, Richmond', 'Hill Street, Richmond', 'Kew Road, Richmond', 'Crown Road, Twickenham'],
};
const WALKS = [[200, '2–3 min walk'], [300, '4 min walk'], [500, '6–7 min walk']];
function planForm(concept, q, r) {
  return `<header class="page-heading plan-hero"><div><p class="eyebrow">Open a venue</p><h1>Thinking of opening somewhere?</h1>
   <p>Pick what you'd like to open and the street you have in mind. In a few seconds you'll see who is already trading there, what people pay, and what happened to the businesses that came before you.</p></div></header>
  <form id="plan-form" class="plan-steps">
   <section class="plan-step"><div class="step-num">1</div><div class="step-body"><h2>What would you like to open?</h2>
    <div class="concept-grid" role="group" aria-label="Concept">${Object.entries(CONCEPTS).map(([k, [t]]) => `<button type="button" class="concept-tile" data-concept="${k}" aria-pressed="${k === concept}"><span class="concept-icon" aria-hidden="true">${CONCEPT_HINT[k][0]}</span><b>${esc(t)}</b><small>${esc(CONCEPT_HINT[k][1])}</small></button>`).join('')}</div></div></section>
   <section class="plan-step"><div class="step-num">2</div><div class="step-body"><h2>Where are you looking?</h2>
    <p class="step-hint">Type a street, an address or a postcode — or tap one of the streets below. We cover two parts of London for now.</p>
    <div class="search-box"><input id="plan-q" value="${esc(q)}" placeholder="e.g. Pitfield Street, or TW9 1JY" autocomplete="off"></div>
    <div class="area-grid">${Object.entries(AREA_STREETS).map(([area, streets]) => `<div class="area-card"><b>${esc(area)}</b><div class="street-chips">${streets.map(st => `<a href="#" class="street-chip" data-street="${esc(st)}">${esc(st.replace(/, (Richmond|Twickenham)$/, ''))}</a>`).join('')}</div></div>`).join('')}</div></div></section>
   <section class="plan-step"><div class="step-num">3</div><div class="step-body"><h2>How far would your customers walk?</h2>
    <input type="hidden" id="plan-r" value="${r}"><div class="walk-group" role="radiogroup" aria-label="Distance">${WALKS.map(([m, t]) => `<button type="button" class="walk" data-walk="${m}" role="radio" aria-checked="${m === r}"><b>${t}</b><small>about ${m} m</small></button>`).join('')}</div>
    <button class="btn accent big-cta" type="submit">Show me what's around →</button>
    <p class="step-hint" style="margin-top:14px">You'll see: the venues like yours nearby · what they charge · how well they're rated · who eats around there · what closed nearby and why. Prefer to just ask? <a class="text-link" href="ask.html">Ask the analyst ↗</a></p></div></section>
  </form><div id="plan-result"></div>`;
}

function competitorCard(v) {
  const g = v.google || {}, f = v.fsa || {}, p = g.price;
  return `<article class="case-tile"><div class="tile-top"><span class="small muted">${Math.round(v.d)} m away</span>${g.audience ? `<span class="badge green">${esc(g.audience)}</span>` : ''}</div>
  <h3><a href="venue.html?id=${encodeURIComponent(v.id)}">${esc(v.name)} ↗</a></h3><p>${esc(v.address || '')}</p>
  ${(() => { const facts = [g.rating != null ? `★ ${esc(g.rating)} · ${esc(g.n ?? '—')} reviews` : '', p ? esc(money(p)) : '', f.hygiene != null || f.status ? hygiene(v).short : ''].filter(Boolean); return facts.length ? `<div class="tile-bottom">${facts.map(x => `<span>${x}</span>`).join('')}</div>` : ''; })()}</article>`;
}

async function planResult(concept, q, r) {
  const box = $('#plan-result');
  if (!concept || !q) { box.innerHTML = ''; return; }
  box.innerHTML = '<div class="loading">Looking around…</div>';
  const where = await locate(q);
  if (!where) { box.innerHTML = `<div class="empty"><h2>We couldn't place “${esc(q)}”.</h2><p>Try a street in Shoreditch & Hoxton or Richmond & St Margarets, or a full postcode.</p></div>`; return; }
  const P = { coordinates: where.at };
  const around = venuesAll.map(v => ({ ...v, d: gap({ coordinates: v.loc }, P) })).filter(v => v.d <= r).sort((a, b) => a.d - b.d);
  const comp = around.filter(v => v.concept === concept).sort(byInfo);
  const lvl = competitionLevel(concept, where.at, r);
  const priced = comp.filter(v => v.google?.price);
  const lo = median(priced.map(v => v.google.price[0])), hi = median(priced.map(v => v.google.price[1]));
  const rated = comp.filter(v => v.google?.rating != null && (v.google.n || 0) >= 20);
  const medRating = median(rated.map(v => v.google.rating)), strong = rated.filter(v => v.google.rating >= 4.5).length;
  const hyg = median(comp.map(v => v.fsa?.hygiene));
  const tally = {}; around.forEach(v => { if (v.google?.audience) tally[v.google.audience] = (tally[v.google.audience] || 0) + 1; });
  const crowd = Object.entries(tally).sort((a, b) => b[1] - a[1]).slice(0, 3), crowdN = Object.values(tally).reduce((s, x) => s + x, 0);
  const near = cases.map(c => ({ c, d: gap(c.location, P) })).filter(x => x.d <= Math.max(r, 300)).sort((a, b) => a.d - b.d);
  const name = CONCEPTS[concept][1];

  box.innerHTML = `<section class="panel" style="margin-top:24px"><p class="eyebrow">Your plan · ${esc(CONCEPTS[concept][0])} · ${esc(where.label)}</p>
   <h2>${comp.length} ${esc(name)} within ${r} m.</h2><p class="panel-intro">Placed by ${esc(where.how)}. ${around.length} food & drink venues in total around this point.</p>
   <div class="how-grid" style="border:0;padding-top:0">
    <article><span class="badge ${lvl.level[1]}">${lvl.level[0]} competition</span><h3>${lvl.mine} direct competitors</h3><p>${lvl.pct}% of spots in this neighbourhood have fewer ${esc(name)} within ${r} m.</p></article>
    <article><span class="badge">Typical price per person</span><h3>${lo == null ? 'Not enough price data' : lo <= 1 ? `Under £${hi}` : `£${lo}–£${hi}`}</h3><p>${priced.length ? `Median of the price ranges listed by ${priced.length} of ${comp.length} competitors on Google.` : 'Google lists no prices for these competitors.'}</p></article>
    <article><span class="badge">The bar you'd have to clear</span><h3>${medRating != null ? `★ ${medRating} median` : 'Few rated competitors'}</h3><p>${rated.length ? `${strong} of ${rated.length} rated competitors have 4.5★ or more.` : ''}${hyg != null ? ` Median hygiene score ${hyg}/5.` : ''}</p></article>
   </div>
   <div class="sources">${source('Google Places')}${source('FSA Food Hygiene')}<small>Venues counted only if they look like ${esc(name)} by Google category, FSA type or name</small></div></section>
   <div class="board-grid"><div class="map-panel"><div class="map" id="plan-map" role="region" aria-label="Competitors on the map"></div><div class="map-legend"><span><i class="dot confirmed"></i>${esc(CONCEPTS[concept][0])}</span><span><i class="dot"></i>Other venues</span><span><i class="dot entity_change"></i>Your spot</span></div></div>
   <section><div class="list-heading"><span>${comp.length} competitors · most reviewed first</span></div><div class="case-list">${comp.slice(0, 12).map(competitorCard).join('') || '<div class="empty"><h2>No direct competitors in this radius.</h2><p>That can be an opening — or a sign the street does not support this concept. Check the history below.</p></div>'}</div></section></div>
   ${crowdN ? `<section class="panel" style="margin-top:24px"><p class="eyebrow">Who eats around here</p><h2>Main customers of ${crowdN} venues nearby</h2>${crowd.map(([l, n]) => `<div class="metric"><strong>${Math.round(n / crowdN * 100)}%</strong><p>${esc(l)} · ${n} venues</p></div>`).join('')}<p class="disclaimer">From opening hours, Google attributes and review quotes. A hypothesis, not a survey.</p></section>` : ''}
   <section class="panel"><p class="eyebrow">What happened here before</p><h2>${near.length ? `${near.length} addresses with closures nearby` : 'No closure records nearby'}</h2><p class="panel-intro">Company records checked against Google and FSA. Open a case file for the timeline, possible reasons and the street by the hour.</p><div class="case-list">${near.slice(0, 6).map(x => tile(x.c)).join('')}</div>${near.length > 6 ? `<a class="btn secondary" href="board.html?q=${encodeURIComponent(q)}" style="margin-top:16px">See all ${near.length} ↗</a>` : ''}</section>`;

  if (window.L) {
    const m = L.map('plan-map', { scrollWheelZoom: false }).setView([where.at[1], where.at[0]], r <= 200 ? 17 : 16);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(m);
    L.circle([where.at[1], where.at[0]], { radius: r, color: '#365e48', weight: 1, fillOpacity: .04 }).addTo(m);
    L.circleMarker([where.at[1], where.at[0]], { radius: 8, color: '#fff', weight: 2, fillColor: '#365e48', fillOpacity: 1 }).bindTooltip('Your spot').addTo(m);
    around.filter(v => v.concept !== concept).forEach(v => L.circleMarker([v.loc[1], v.loc[0]], { radius: 4, color: '#8b9286', weight: 0, fillOpacity: .6 }).bindTooltip(esc(v.name)).addTo(m));
    comp.forEach(v => L.circleMarker([v.loc[1], v.loc[0]], { radius: 7, color: '#fff', weight: 2, fillColor: '#c34d36', fillOpacity: 1 }).bindTooltip(`${esc(v.name)}${v.google?.rating ? ' · ★ ' + v.google.rating : ''}`).addTo(m));
  }
}

// Without a concept the user still gets an answer: what trades around the place, one button per concept.
async function overview(q, r) {
  const box = $('#plan-result');
  if (!q) { box.innerHTML = ''; return; }
  const where = await locate(q);
  if (!where) { box.innerHTML = `<div class="empty"><h2>We couldn't place “${esc(q)}”.</h2><p>Try a street name from the Shoreditch area or a full postcode.</p></div>`; return; }
  const around = venuesAll.filter(v => gap({ coordinates: v.loc }, { coordinates: where.at }) <= r);
  const count = k => around.filter(v => v.concept === k).length;
  box.innerHTML = `<section class="panel" style="margin-top:24px"><p class="eyebrow">${esc(where.label)} · within ${r} m</p><h2>${around.length} food & drink venues trade here.</h2>
   <p class="panel-intro">Pick what you're planning to open to see your direct competitors, the competition level and typical prices.</p>
   <div class="filter-group">${Object.entries(CONCEPTS).map(([k, [t]]) => `<button type="button" data-pick="${k}"><b>${count(k)}</b>&nbsp;${esc(t)}</button>`).join('')}</div></section>`;
  box.querySelectorAll('[data-pick]').forEach(b => b.addEventListener('click', () => document.querySelector(`[data-concept="${b.dataset.pick}"]`).click()));
}

async function plan() {
  let concept = params.get('concept') || '', q = params.get('q') || '', r = Number(params.get('r')) || 300;
  $('#main').innerHTML = `<div class="wrap">${planForm(concept, q, r)}</div>`;
  try { venuesAll = await json('data/venues_all.json').catch(() => json('../app/data/venues_all.json')); } catch { $('#plan-result').innerHTML = '<div class="empty"><h2>Venue data unavailable.</h2></div>'; return; }
  const go = () => {
    q = $('#plan-q').value.trim(); r = Number($('#plan-r').value);
    const url = new URL(location.href); ['concept', 'q', 'r'].forEach(k => url.searchParams.delete(k));
    if (concept) url.searchParams.set('concept', concept); if (q) url.searchParams.set('q', q); url.searchParams.set('r', r);
    history.replaceState(null, '', url);
    const show = () => setTimeout(() => $('#plan-result').scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);  // bring the answer into view
    if (!concept) return overview(q, r).then(show);
    planResult(concept, q, r).then(show);
  };
  document.querySelectorAll('[data-concept]').forEach(b => b.addEventListener('click', () => { concept = b.dataset.concept; document.querySelectorAll('[data-concept]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); if ($('#plan-q').value.trim()) go(); }));
  document.querySelectorAll('[data-street]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); $('#plan-q').value = a.dataset.street; go(); }));
  $('#plan-form').addEventListener('submit', e => { e.preventDefault(); go(); });
  document.querySelectorAll('[data-walk]').forEach(b => b.addEventListener('click', () => { $('#plan-r').value = b.dataset.walk; document.querySelectorAll('[data-walk]').forEach(x => x.setAttribute('aria-checked', String(x === b))); if ($('#plan-q').value.trim()) go(); }));
  if (q) concept ? planResult(concept, q, r) : overview(q, r);
}

// Ask the board: the question goes to /api/ask (Gemini + MongoDB tools). We show the answer and every step —
// which Atlas query the analyst ran — so it is clear the facts come from the database, not the model.
const ASK_EXAMPLES = ['I want to open a coffee shop on Pitfield Street. How many competitors, what do they charge, what closed nearby?',
  'Which fried chicken places closed fast near Old Street, and why might that be?',
  'Is Rivington Street busy with bars? What happened to restaurants there?'];
// Plain-language description of each lookup the analyst made (no tool names or database jargon).
function stepText(s) {
  const a = s.args || {}, place = a.place || (a.lat ? 'the area' : '');
  if (s.tool === 'find_place') return `Located <b>${esc(place)}</b>${/→ (\d+)/.test(s.query || '') ? ` across ${s.query.match(/→ (\d+)/)[1]} venue addresses` : ''}.`;
  if (s.tool === 'area_stats') return `Counted the food & drink venues trading within ${a.radius_m || 300} m${a.concept ? `, with prices, ratings and hygiene for ${esc(a.concept)}` : ''}.`;
  if (s.tool === 'search_cases') return `Searched ${cases.length} address histories for “${esc(a.query || '')}”${a.lat ? ` within ${a.radius_m || 400} m` : ''} — ${s.results ?? 0} relevant.`;
  return '';
}
async function ask() {
  const q0 = params.get('q') || '';
  $('#main').innerHTML = `<div class="wrap"><header class="page-heading"><div><p class="eyebrow">Ask the analyst</p><h1>Ask in your own words.</h1><p>The analyst looks things up in our database and shows every query it ran. It never answers from memory.</p></div></header>
  <form id="ask-form" class="panel"><label class="search-label" for="ask-q">Your question</label><div class="search-box"><input id="ask-q" value="${esc(q0)}" placeholder="e.g. Is Pitfield Street good for a bakery?" autocomplete="off"><button class="btn accent" type="submit">Ask ↗</button></div>
  <div class="examples" style="flex-direction:column;gap:6px">${ASK_EXAMPLES.map(x => `<a href="#" data-ask="${esc(x)}">${esc(x)}</a>`).join('')}</div></form><div id="ask-result"></div></div>`;
  const run = async q => {
    const url = new URL(location.href); url.searchParams.set('q', q); history.replaceState(null, '', url);
    $('#ask-result').innerHTML = '<div class="loading">Searching the case files and the neighbourhood…</div>';
    let r; try { r = await fetch(`/api/ask?q=${encodeURIComponent(q)}`).then(x => x.json()); } catch { r = { error: 'network' }; }
    if (r.error) { $('#ask-result').innerHTML = `<div class="empty"><h2>The analyst couldn't answer.</h2><p>${esc(r.detail || r.error)}</p></div>`; return; }
    const html = esc(r.answer).replace(/\[(case:[^\]]+)\]/g, (_, ids) => ids.split(/,\s*/).map(x => x.replace(/^case:/, '').trim()).map(id => { const c = cases.find(x => x.id === id); return c ? `<a class="text-link" href="${path('case', id)}">${esc(c.address.replace(/, London$/, ''))} ↗</a>` : ''; }).join(' '));
    $('#ask-result').innerHTML = `<section class="panel"><p class="eyebrow">Answer · ${esc(r.model || '')}</p><p style="font-size:1.05rem;line-height:1.6">${html.replace(/\n+/g, '<br>')}</p><p class="disclaimer" style="margin-top:14px">Reasons for closures are hypotheses. Check the case files and sources.</p></section>
    <section class="panel"><p class="eyebrow">What we checked</p><ul class="checked-list">${r.steps.map(stepText).filter(Boolean).map(t => `<li>${t}</li>`).join('')}</ul><p class="disclaimer">Every number in the answer comes from our records: Companies House, the FSA hygiene register, Google listings and TfL, checked ${esc(CHECKED || 'recently')}.</p></section>
    ${r.cited?.length ? `<section class="panel"><p class="eyebrow">Case files cited</p><div class="case-list">${r.cited.map(id => cases.find(c => c.id === id)).filter(Boolean).map(tile).join('')}</div></section>` : ''}`;
  };
  $('#ask-form').addEventListener('submit', e => { e.preventDefault(); const q = $('#ask-q').value.trim(); if (q.length >= 3) run(q); });
  document.querySelectorAll('[data-ask]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); $('#ask-q').value = a.dataset.ask; run(a.dataset.ask); }));
  if (q0) run(q0);
}

// Live signals on the map: /api/live holds a Change Stream on `alerts`. A new closure near a case file
// turns its pin red and pulsing, marks the event on the map and shows a notification.
// The demo button only appears with ?demo=<key>.
function liveAlert(a) {
  toast(`Simulated closure (demo), ${a.distance_m} m from ${a.address.replace(/, London.*$/, '')}: ${a.event.company_name.toLowerCase()} (${a.processed_by === 'atlas-stream-processing' ? 'Atlas Stream Processing' : 'API fallback'})`);
  if (window.L && typeof map !== 'undefined' && map && typeof pins !== 'undefined' && pins) {
    pins.eachLayer(m => { if (m.options.title === a.address) m.setIcon(L.divIcon({ className: 'map-marker', html: '<div class="pin confirmed live"></div>', iconSize: [20, 20], iconAnchor: [10, 10] })); });
    const [lng, lat] = a.event.location.coordinates;
    L.circleMarker([lat, lng], { radius: 10, color: '#c34d36', weight: 3, fillColor: '#fff', fillOpacity: 1, className: 'live-ring' }).bindTooltip(`Just closed: ${esc(a.event.company_name)}`).addTo(pins);
  }
  const box = $('#live-feed'); if (box) box.insertAdjacentHTML('afterbegin', `<div class="signal-row"><span class="badge confirmed">Live · ${new Date(a.at).toLocaleTimeString('en-GB')}</span><p>${esc(a.event.company_name)} at ${esc(a.event.address)} — ${a.distance_m} m from <a class="text-link" href="${path('case', a.case_id)}">${esc(a.address)}</a></p></div>`);
}
async function startLive() {
  // Only the stage screen listens: a room full of phones should not each hold a Change Stream open.
  const demo = params.get('demo');
  if (!demo || !['board', 'home', 'case'].includes(document.body.dataset.screen)) return;
  {
    const bar = document.createElement('div'); bar.className = 'panel'; bar.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:9000;max-width:320px;padding:16px';
    bar.innerHTML = `<p class="eyebrow" style="margin-bottom:8px">Stage demo</p><button class="btn accent" id="demo-close">Simulate a closure on Pitfield St</button><p class="small muted" style="margin-top:6px">Demo event, not a real company.</p><div id="live-feed" style="margin-top:10px;max-height:200px;overflow:auto"></div>`;
    document.body.appendChild(bar);
    $('#demo-close').addEventListener('click', async () => { const r = await fetch(`/api/demo-closure?preset=pitfield&key=${encodeURIComponent(demo)}`).then(x => x.json()).catch(() => ({})); toast(r.ok ? `Event sent · processed by ${r.processed_by}` : 'Demo key rejected'); });
  }
  let after = new Date().toISOString();
  for (;;) {
    try {
      const r = await fetch(`/api/live?after=${encodeURIComponent(after)}`).then(x => x.json());
      for (const a of r.alerts || []) { liveAlert(a); if (a.at > after) after = a.at; }
    } catch { await new Promise(s => setTimeout(s, 5000)); }
  }
}
window.addEventListener('load', () => startLive());

// Street history (time-series `occupancy_events` + $setWindowFields): food companies opened and closed per year.
function streetHistoryPanel(c) {
  const h = c.street_history; if (!h?.years?.length) return '';
  // Our Companies House extract holds only companies that were later dissolved, so we count dissolutions only.
  const from = 2014, to = new Date().getFullYear(), by = Object.fromEntries(h.years.map(y => [y.year, y]));
  const yrs = []; for (let y = from; y <= to; y++) yrs.push(by[y] || { year: y, closed: 0 });
  const max = Math.max(1, ...yrs.map(y => y.closed));
  const closed = yrs.reduce((s, y) => s + y.closed, 0), worst = yrs.reduce((a, b) => (b.closed > a.closed ? b : a)), last3 = yrs.slice(-3).reduce((s, y) => s + y.closed, 0);
  return `<section class="panel"><p class="eyebrow">The street over the years</p><h2>${esc(h.street)}: ${closed} food companies dissolved since ${from}</h2>
  ${h.verdict ? `<div class="verdict ${h.verdict}"><b>${{ high: 'More churn than most streets here', typical: 'About as much churn as a typical street here', low: 'Less churn than most streets here' }[h.verdict]}.</b> ${h.closed_since_2014} dissolved companies against ${h.trading_now} venues trading today: ${h.per_10_venues} per 10 venues, where a typical street in this area has ${h.area_typical_per_10}. ${{ high: 'Businesses here change hands often — ask the landlord why the last tenants left.', typical: 'Normal turnover for this part of London: no red flag on its own.', low: 'Businesses here tend to last — a good sign for the location.' }[h.verdict]}</div>` : ''}
  <p class="panel-intro">Food & drink companies registered on this street that were later dissolved, by year of dissolution. The busiest year was ${worst.year} (${worst.closed}); ${last3} in the last three years.</p>
  <div class="year-chart">${yrs.map(y => `<div class="year-col" title="${y.year}: ${y.closed} dissolved"><span class="yc" style="height:${Math.round(y.closed / max * 60)}px"></span><small>${String(y.year).slice(2)}</small></div>`).join('')}</div>
  <div class="sources">${source('Companies House')}<small>Company paperwork, not venue openings · MongoDB time series + window functions</small></div></section>`;
}

// QR landing page for the room: no typing, everything within a short walk of Encode Hub.
async function here() {
  const HUB = { coordinates: [-0.083849, 51.527626] };
  const near = cases.map(c => ({ c, d: gap(c.location, HUB) })).filter(x => x.d <= 400);
  const rank = { confirmed: 0, probable: 1, entity_change: 2, possible: 3 };
  const top = near.sort((a, b) => rank[a.c.closure_level] - rank[b.c.closure_level] || b.c.chain.length - a.c.chain.length || a.d - b.d).slice(0, 6);
  const confirmed = near.filter(x => x.c.closure_level === 'confirmed').length, churn = near.filter(x => x.c.chain.length >= 2).length;
  $('#main').innerHTML = `<div class="wrap"><header class="page-heading"><div><p class="eyebrow">Within a 5-minute walk of this room</p><h1>Who closed here before you, and why?</h1>
  <p>${near.length} addresses around Encode Hub where food companies were dissolved. ${confirmed} closures confirmed on Google; ${churn} addresses saw two or more companies come and go.</p></div></header>
  <div class="button-row" style="margin-bottom:24px"><a class="btn accent" href="plan.html">Open a venue →</a><a class="btn secondary" href="employer.html">Take a job →</a></div>
  <div class="case-list">${top.map(x => tile(x.c)).join('')}</div><p style="margin-top:20px"><a class="text-link" href="board.html">See all ${near.length} on the map ↗</a></p></div>`;
}

// Venue report: everything we know about one café, restaurant or bar, from /api/venue (Atlas).
const ATTR = { dineIn: 'Dine-in', takeout: 'Takeaway', delivery: 'Delivery', outdoorSeating: 'Outdoor seating', goodForChildren: 'Good for children', goodForGroups: 'Good for groups',
  allowsDogs: 'Dogs allowed', servesBreakfast: 'Breakfast', servesBrunch: 'Brunch', servesLunch: 'Lunch', servesDinner: 'Dinner', servesCoffee: 'Coffee', servesBeer: 'Beer', servesWine: 'Wine' };
const CONCEPT_LABEL = { coffee: 'Coffee shop', bakery: 'Bakery / patisserie', restaurant: 'Restaurant', takeaway: 'Takeaway', bar: 'Bar / pub' };
const stars = n => n == null ? '' : '★'.repeat(Math.round(n)) + '☆'.repeat(5 - Math.round(n));
const money = p => p ? (p[0] <= 1 ? `Under £${p[1]}` : `£${p[0]}–£${p[1] ?? '?'}`) : null;

async function venue() {
  $('#main').innerHTML = '<div class="loading">Putting the report together…</div>';
  let r; try { r = await json(`/api/venue?id=${encodeURIComponent(params.get('id') || '')}`); } catch { r = null; }
  if (!r || r.error) { $('#main').innerHTML = '<div class="empty"><h1>Venue not found.</h1><p>Pick a venue from the map or search.</p><a class="btn secondary" href="plan.html">Open a venue</a></div>'; return; }
  const v = r.venue, g = v.google || {}, f = v.fsa || {}, L = r.listing || {}, comp = v.competition || {}, rs = L.review_summary;
  r.competitors.sort(byInfo); const segs = L.audience?.segments || [], rated = r.competitors.filter(x => x.google?.rating != null);
  const medRating = median(rated.map(x => x.google.rating)), medLo = median(r.competitors.map(x => x.google?.price?.[0])), medHi = median(r.competitors.map(x => x.google?.price?.[1]));
  const attrs = Object.entries(L.attributes || {}).filter(([k, val]) => val === true && ATTR[k]).map(([k]) => ATTR[k]);
  const mixTotal = Object.values(r.mix).reduce((a, b) => a + b, 0) || 1, mixMax = Math.max(1, ...Object.values(r.mix));
  const levelBadge = { high: 'confirmed', medium: 'probable', low: 'entity_change' }[comp.level] || '';
  const ctx = r.context;
  $('#main').innerHTML = `<div class="wrap">
  <div class="breadcrumb"><a href="plan.html">Open a venue</a><span>/</span><span>Venue report</span></div>
  <header class="page-heading"><div><p class="eyebrow">${esc(CONCEPT_LABEL[v.concept] || v.concept)} · venue report</p><h1>${esc(v.name)}</h1><p>${esc(v.address || '')}</p>
   <div class="sources">${g.place_id ? source('Google', `https://www.google.com/maps/search/?api=1&query=venue&query_place_id=${encodeURIComponent(g.place_id)}`) : ''}${v.fsa ? source('FSA hygiene') : ''}${source('MongoDB Atlas')}</div></div>
   ${g.place_id ? `<a class="btn secondary" href="employer.html?venue=${encodeURIComponent(g.place_id)}">Working here? →</a>` : ''}</header>

  <section class="report-tiles">
   ${g.rating != null ? `<div class="panel"><p class="eyebrow">Google</p><strong class="big">★ ${g.rating}</strong><p>${g.n != null ? `${Number(g.n).toLocaleString('en-GB')} reviews` : ''}</p></div>` : ''}
   ${f.hygiene != null || f.status ? `<div class="panel"><p class="eyebrow">Food hygiene · FSA</p><strong class="big">${hygiene(v).big}</strong><p>${hygiene(v).note}</p></div>` : ''}
   ${g.price ? `<div class="panel"><p class="eyebrow">Price per person</p><strong class="big">${money(g.price)}</strong><p>Listed on Google${medLo != null ? ` · nearby ${esc(money([medLo, medHi]))}` : ''}</p></div>` : ''}
   <div class="panel"><p class="eyebrow">Competition · 300 m</p><strong class="big">${comp.same_concept ?? '—'}</strong><p><span class="badge ${levelBadge}">${esc(comp.level || '')} competition</span> ${comp.percentile != null ? `· ${comp.percentile}% of similar venues have fewer competitors` : ''}</p></div>
  </section>

  <div class="case-layout"><div>
  ${rs ? `<section class="panel"><p class="eyebrow">What guests say · from ${rs.reviews_read} recent reviews</p><h2>${esc(rs.summary)}</h2>
   <div class="two-col">${rs.praise.length ? `<div><h3>Praised</h3>${rs.praise.map(x => `<div class="quote-row good"><b>${esc(x.point)}</b><p>“${esc(x.quote)}”</p></div>`).join('')}</div>` : ''}
   ${rs.complaints.length ? `<div><h3>Criticised</h3>${rs.complaints.map(x => `<div class="quote-row bad"><b>${esc(x.point)}</b><p>“${esc(x.quote)}”</p></div>`).join('')}</div>` : ''}</div>
   <p class="disclaimer">Points summarised by Gemini; every quote is checked word for word against the review text.</p></section>` : ''}

  ${segs.length ? `<section class="panel"><p class="eyebrow">Who comes here · a hypothesis</p><h2>${segs[0].confidence === 'low' ? 'Only weak signals so far' : esc(segs[0].label) + (segs[1] && segs[1].confidence !== 'low' ? ` and ${esc(segs[1].label.toLowerCase())}` : '')}</h2>${segs.map(s => `<div class="signal-row"><div class="tile-top"><h3>${esc(s.label)}</h3><span class="badge">${esc({ high: 'we are fairly sure', medium: 'plausible', low: 'weak signal' }[s.confidence])}</span></div>${s.evidence.map(e => `<p class="small">${esc(e.text)} <span class="source">${esc(e.source)}</span></p>`).join('')}${s.quotes.map(q => `<p class="small"><i>“${esc(q)}”</i> <span class="source">Google review</span></p>`).join('')}</div>`).join('')}</section>` : ''}

  <section class="panel"><p class="eyebrow">Competition within 300 m</p><h2>${comp.same_concept ?? 0} other ${esc((CONCEPT_LABEL[v.concept] || 'venues').toLowerCase())}s nearby</h2>
   <p class="panel-intro">${medRating != null ? `Their median Google rating is ★ ${medRating}${g.rating != null ? ` — this venue is ${g.rating >= medRating ? 'at or above' : 'below'} it` : ''}.` : ''} ${medLo != null ? `Typical price nearby: ${esc(money([medLo, medHi]))}.` : ''}</p>
   <div class="map-panel" style="height:320px;position:relative;margin-bottom:16px"><div class="map" id="venue-map"></div></div>
   <div class="filter-group" style="margin-bottom:10px"><button type="button" data-sort="info" aria-pressed="true">Most reviewed</button><button type="button" data-sort="near" aria-pressed="false">Nearest</button></div><table class="report-table" id="comp-table"><thead><tr><th>Venue</th><th>Distance</th><th>Google</th><th>Price</th><th>Hygiene</th></tr></thead><tbody>
   ${r.competitors.slice(0, 15).map(x => `<tr><td><a class="text-link" href="venue.html?id=${encodeURIComponent(x.id)}">${esc(x.name)}</a>${x.google?.audience ? `<br><small class="muted">${esc(x.google.audience)}</small>` : ''}</td><td>${Math.round(x.d)} m</td><td>${x.google?.rating != null ? `★ ${x.google.rating} <small class="muted">(${x.google.n ?? '—'})</small>` : '—'}</td><td>${money(x.google?.price) || '—'}</td><td>${hygiene(x).short}</td></tr>`).join('')}</tbody></table></section>

  ${ctx?.street_hours ? streetHoursPanel({ street_hours: ctx.street_hours, footfall_proxy: ctx.footfall || {}, chain: [] }).replace('02b / Day or evening?', 'Day or evening?') : ''}
  ${ctx?.street_history ? streetHistoryPanel({ street_history: ctx.street_history }) : ''}

  ${(L.reviews || []).length ? `<section class="panel"><p class="eyebrow">Recent Google reviews</p><h2>In guests' own words</h2>${L.reviews.map(x => `<div class="signal-row"><div class="tile-top"><span class="stars">${stars(x.rating)}</span><small class="muted">${x.time ? esc(new Date(x.time).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })) : ''}</small></div><p>${esc(x.text)}</p></div>`).join('')}</section>` : ''}
  </div>
  <aside>
   ${(L.hours || []).length || attrs.length ? `<section class="panel">${(L.hours || []).length ? `<p class="eyebrow">Opening hours</p><table class="report-table hours">${L.hours.map(h => { const [d, t] = h.split(': '); return `<tr><td>${esc(d.slice(0, 3))}</td><td>${esc((t || '').replace(/ | /g, ' '))}</td></tr>`; }).join('')}</table>` : ''}
   ${attrs.length ? `<h3 style="margin-top:18px">Offers</h3><div class="sources">${attrs.map(a => `<span class="source">${esc(a)}</span>`).join('')}</div>` : ''}</section>` : ''}
   <section class="panel"><p class="eyebrow">What trades within 300 m</p>${Object.entries(r.mix).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<div class="mix-row"><span>${esc(CONCEPT_LABEL[k] || k)}</span><span class="mix-bar"><i style="width:${Math.round(n / mixMax * 100)}%" class="${k === v.concept ? 'mine' : ''}"></i></span><b>${n}</b></div>`).join('')}<p class="small muted" style="margin-top:8px">${mixTotal} food &amp; drink venues in total.</p></section>
   <div id="council-venue"></div>
   ${r.cases.length ? `<section class="panel"><p class="eyebrow">What happened nearby</p>${r.cases.map(c => `<div class="signal-row"><span class="badge ${esc(c.closure_level)}">${esc(labels[c.closure_level] || '')}</span><p style="margin-top:8px"><a class="text-link" href="${path('case', c.id)}">${esc(c.address.replace(/, London$/, ''))}</a> · ${Math.round(c.d)} m</p><p class="small muted">${esc(c.chain.map(x => `${x.name.toLowerCase()} (${x.months} mo)`).join(' → '))}</p></div>`).join('')}</section>` : ''}
  </aside></div></div>`;
  councilLinks($('#council-venue'), (String(v.address || '').match(/[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}/) || [])[0] || v.fsa?.postcode);
  const rowsFor = list => list.slice(0, 15).map(x => `<tr><td><a class="text-link" href="venue.html?id=${encodeURIComponent(x.id)}">${esc(x.name)}</a>${x.google?.audience ? `<br><small class="muted">${esc(x.google.audience)}</small>` : ''}</td><td>${Math.round(x.d)} m</td><td>${x.google?.rating != null ? `★ ${x.google.rating} <small class="muted">(${x.google.n ?? '—'})</small>` : '—'}</td><td>${money(x.google?.price) || '—'}</td><td>${hygiene(x).short}</td></tr>`).join('');
  document.querySelectorAll('[data-sort]').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('[data-sort]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    $('#comp-table tbody').innerHTML = rowsFor([...r.competitors].sort(b.dataset.sort === 'near' ? (a, c) => a.d - c.d : byInfo));
  }));
  if (window.L) {
    const [lng, lat] = v.loc, m = window.L.map('venue-map', { scrollWheelZoom: false }).setView([lat, lng], 17);
    window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(m);
    window.L.circle([lat, lng], { radius: 300, color: '#365e48', weight: 1, fillOpacity: .03 }).addTo(m);
    window.L.circleMarker([lat, lng], { radius: 9, color: '#fff', weight: 2, fillColor: '#365e48', fillOpacity: 1 }).bindTooltip(esc(v.name)).addTo(m);
    const byId = Object.fromEntries((venuesAll.length ? venuesAll : await json('data/venues_all.json').catch(() => [])).map(x => [x.id, x]));
    r.competitors.forEach(x => { const p = byId[x.id]?.loc; if (p) window.L.circleMarker([p[1], p[0]], { radius: 6, color: '#fff', weight: 2, fillColor: '#c34d36', fillOpacity: 1 }).bindTooltip(esc(x.name)).addTo(m); });
  }
}

// Food hygiene shown everywhere the same way: score, FSA status, or a link to look it up on the FSA site.
function hygiene(v) {
  const f = v.fsa || {}, pc = (String(v.address || '').match(/[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}/) || [''])[0];
  const search = `https://ratings.food.gov.uk/business-search?business-name-search=${encodeURIComponent(v.name || '')}&address-search=${encodeURIComponent(pc.split(' ')[0] || '')}`;
  if (f.hygiene != null) return { big: `${f.hygiene}/5`, note: `${f.date ? `Inspected ${esc(f.date)}` : 'FSA'}${/registered with/.test(f.matched_by || '') ? ` · registered with ${esc(f.authority)}` : ''}`, short: `Hygiene ${f.hygiene}/5` };
  if (f.status) return { big: esc(f.status), note: `FSA${f.authority ? ` · ${esc(f.authority)}` : ''}`, short: esc(f.status) };
  return { big: '—', note: `<a class="text-link" href="${search}" target="_blank" rel="noopener">Check on the FSA site ↗</a>`, short: `<a class="text-link" href="${search}" target="_blank" rel="noopener">Check FSA ↗</a>` };
}
// Most informative first: many reviews, then a rating, price and hygiene on record; distance breaks ties.
const infoScore = v => Math.log10((v.google?.n || 0) + 1) * 3 + (v.google?.rating != null) + (v.google?.price ? 1 : 0) + (v.fsa?.hygiene != null);
const byInfo = (a, b) => infoScore(b) - infoScore(a) || a.d - b.d;

// Planning history and licences live on each council's own portal; we link to it with the postcode to search.
const COUNCILS = {
  'Hackney': ['https://planningapps.hackney.gov.uk/planning/search-applications', 'https://hackney.gov.uk'],
  'Islington': ['https://www.islington.gov.uk/planning', 'https://www.islington.gov.uk/business/licensing'],
  'City of London': ['https://www.planning2.cityoflondon.gov.uk/online-applications/', 'https://www.cityoflondon.gov.uk/services/licensing'],
  'Tower Hamlets': ['https://development.towerhamlets.gov.uk/online-applications/', 'https://www.towerhamlets.gov.uk/lgnl/business/licences/licences.aspx'],
  'Richmond upon Thames': ['https://www2.richmond.gov.uk/lbrplanning/Planning_Search.aspx', 'https://www.richmond.gov.uk/licensing'],
  'Hounslow': ['https://www.hounslow.gov.uk', 'https://www.hounslow.gov.uk/licensing'],
};
async function councilLinks(el, postcode) {
  if (!el || !postcode) return;
  let d; try { d = (await json(`https://api.postcodes.io/postcodes/${encodeURIComponent(postcode)}`)).result; } catch { return; }
  const council = d?.admin_district, links = COUNCILS[council];
  el.innerHTML = `<section class="panel"><p class="eyebrow">Before you sign · council records</p><h3>${esc(council || 'Council')} planning history</h3>
   <p class="small">Search the council's planning portal for <b>${esc(d.postcode)}</b> to see every application at this address: change of use, extraction and ventilation, signs, late hours — and which were refused.</p>
   ${links ? `<div class="help-links"><a href="${links[0]}" target="_blank" rel="noopener">Planning applications · ${esc(council)} ↗</a><a href="${links[1]}" target="_blank" rel="noopener">Licensing (alcohol, late hours) · ${esc(council)} ↗</a></div>` : ''}
   <p class="disclaimer" style="margin-top:12px">Council portals don't publish open data we can store, so we link to them.</p></section>`;
}

// Motion: panels, tiles and cards rise in as they enter the viewport (skipped for reduced-motion users);
// big numbers count up once. Works on every screen because the content is rendered after load.
(function motion() {
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const seen = new WeakSet();
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); countUp(e.target); } }), { rootMargin: '0px 0px -8% 0px' });
  function countUp(el) {
    el.querySelectorAll('strong.big, .metric strong').forEach(n => {
      const m = n.textContent.match(/^([^\d]*)(\d[\d,]*)(.*)$/s); if (!m || n.dataset.counted) return; n.dataset.counted = 1;
      const end = Number(m[2].replace(/,/g, '')), t0 = performance.now();
      const tick = t => { const k = Math.min(1, (t - t0) / 700); n.textContent = m[1] + Math.round(end * (1 - Math.pow(1 - k, 3))).toLocaleString('en-GB') + m[3]; if (k < 1) requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
    });
  }
  const scan = () => document.querySelectorAll('main .panel, main .case-tile, main .report-tiles .panel, main .scenario, main .status-panel').forEach((el, i) => {
    if (seen.has(el)) return; seen.add(el); el.classList.add('reveal'); el.style.transitionDelay = `${Math.min(i % 6, 5) * 60}ms`; io.observe(el);
  });
  let queued = false;  // map tiles mutate the DOM constantly: rescan at most once per frame
  new MutationObserver(() => { if (!queued) { queued = true; requestAnimationFrame(() => { queued = false; scan(); }); } }).observe(document.body, { childList: true, subtree: true });
  scan();
})();
