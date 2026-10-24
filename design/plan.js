// Стартовый экран «Что и где вы открываете?»: концепция + улица/адрес/индекс → конкуренты того же типа,
// уровень конкуренции, типичный чек, клиенты вокруг и дела закрытий рядом. Все числа считаются здесь из
// data/venues_all.json (склейка FSA + Google, scripts/build_venues.py); модель в этом экране не участвует.
const CONCEPTS = {
  coffee: ['Coffee shop', 'coffee shops'],
  bakery: ['Bakery or patisserie', 'bakeries and patisseries'],
  restaurant: ['Restaurant (hot kitchen)', 'restaurants'],
  takeaway: ['Takeaway or sandwich shop', 'takeaways'],
  bar: ['Bar or pub', 'bars and pubs'],
};
const STREET_EXAMPLES = ['Pitfield Street', 'Rivington Street', 'Great Eastern Street', 'Curtain Road', 'EC2A 3EP'];
let venuesAll = [];

function median(xs) { const s = xs.filter(x => x != null).sort((a, b) => a - b); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
const normStreet = s => String(s || '').toLowerCase().replace(/\bst\b\.?/g, 'street').replace(/\brd\b\.?/g, 'road').replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();

async function locate(q) {
  const pc = q.trim().toUpperCase().match(/^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$/);
  if (pc) {
    try { const r = await json(`https://api.postcodes.io/postcodes/${encodeURIComponent(q.trim())}`); return { at: [r.result.longitude, r.result.latitude], label: r.result.postcode, how: 'postcode' }; } catch { return null; }
  }
  const n = normStreet(q); if (n.length < 3) return null;
  const pts = [...venuesAll.map(v => ({ a: v.address, loc: v.loc })), ...cases.map(c => ({ a: c.address, loc: c.location.coordinates }))]
    .filter(x => normStreet(x.a).includes(n));
  if (!pts.length) return null;
  const at = [pts.reduce((s, x) => s + x.loc[0], 0) / pts.length, pts.reduce((s, x) => s + x.loc[1], 0) / pts.length];
  return { at, label: q.trim().replace(/\b\w/g, c => c.toUpperCase()), how: `${pts.length} addresses on this street` };
}

// Уровень конкуренции: сравниваем число конкурентов здесь с тем же числом вокруг каждого заведения района.
function competitionLevel(concept, at, r) {
  const mine = venuesAll.filter(v => v.concept === concept && gap({ coordinates: v.loc }, { coordinates: at }) <= r).length;
  const sample = venuesAll.filter((_, i) => i % 3 === 0).map(s => venuesAll.filter(v => v.concept === concept && gap({ coordinates: v.loc }, { coordinates: s.loc }) <= r).length);
  const below = sample.filter(x => x < mine).length / (sample.length || 1);
  const level = below >= 0.75 ? ['High', 'confirmed'] : below <= 0.35 ? ['Low', 'entity_change'] : ['Medium', 'probable'];
  return { mine, pct: Math.round(below * 100), level };
}

function planForm(concept, q, r) {
  return `<header class="page-heading"><div><p class="eyebrow">Before you sign</p><h1>What are you opening, and where?</h1><p>Tell us your plan. We'll show the competition, the prices people pay and what happened here before.</p></div></header>
  <form id="plan-form" class="panel"><p class="search-label">1 · Your concept</p><div class="filter-group" role="group" aria-label="Concept">${Object.entries(CONCEPTS).map(([k, [t]]) => `<button type="button" data-concept="${k}" aria-pressed="${k === concept}">${esc(t)}</button>`).join('')}</div>
  <label class="search-label" for="plan-q" style="margin-top:22px">2 · Street, address or postcode</label><div class="search-box"><input id="plan-q" value="${esc(q)}" placeholder="e.g. Pitfield Street or EC2A 3EP" autocomplete="off"><select id="plan-r" aria-label="Radius" style="border:0;background:none">${[200, 300, 500].map(x => `<option value="${x}" ${x === r ? 'selected' : ''}>within ${x} m</option>`).join('')}</select><button class="btn accent" type="submit">Show me ↗</button></div>
  <div class="examples"><span>Try</span>${STREET_EXAMPLES.map(s => `<a href="#" data-street="${esc(s)}">${esc(s)}</a>`).join('')}</div></form><div id="plan-result"></div>`;
}

function competitorCard(v) {
  const g = v.google || {}, f = v.fsa || {}, p = g.price;
  return `<article class="case-tile"><div class="tile-top"><span class="small muted">${Math.round(v.d)} m away</span>${g.audience ? `<span class="badge green">${esc(g.audience)}</span>` : ''}</div>
  <h3>${esc(v.name)}</h3><p>${esc(v.address || '')}</p>
  <div class="tile-bottom"><span>${g.rating != null ? `★ ${esc(g.rating)} · ${esc(g.n ?? '—')} reviews` : 'No Google rating found'}</span><span>${p ? `£${p[0] ?? '?'}–£${p[1] ?? '?'}` : 'Price not listed'}</span><span>${f.hygiene != null ? `Hygiene ${f.hygiene}/5` : 'No FSA match'}</span></div></article>`;
}

async function planResult(concept, q, r) {
  const box = $('#plan-result');
  if (!concept || !q) { box.innerHTML = ''; return; }
  box.innerHTML = '<div class="loading">Looking around…</div>';
  const where = await locate(q);
  if (!where) { box.innerHTML = `<div class="empty"><h2>We couldn't place “${esc(q)}”.</h2><p>Try a street name from the Shoreditch area (we cover about 900 m around Encode Hub) or a full postcode.</p></div>`; return; }
  const P = { coordinates: where.at };
  const around = venuesAll.map(v => ({ ...v, d: gap({ coordinates: v.loc }, P) })).filter(v => v.d <= r).sort((a, b) => a.d - b.d);
  const comp = around.filter(v => v.concept === concept);
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
   <section><div class="list-heading"><span>${comp.length} competitors · nearest first</span></div><div class="case-list">${comp.slice(0, 12).map(competitorCard).join('') || '<div class="empty"><h2>No direct competitors in this radius.</h2><p>That can be an opening — or a sign the street does not support this concept. Check the history below.</p></div>'}</div></section></div>
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

async function plan() {
  let concept = params.get('concept') || '', q = params.get('q') || '', r = Number(params.get('r')) || 300;
  $('#main').innerHTML = `<div class="wrap">${planForm(concept, q, r)}</div>`;
  try { venuesAll = await json('data/venues_all.json').catch(() => json('../app/data/venues_all.json')); } catch { $('#plan-result').innerHTML = '<div class="empty"><h2>Venue data unavailable.</h2></div>'; return; }
  const go = () => {
    q = $('#plan-q').value.trim(); r = Number($('#plan-r').value);
    const url = new URL(location.href); ['concept', 'q', 'r'].forEach(k => url.searchParams.delete(k));
    if (concept) url.searchParams.set('concept', concept); if (q) url.searchParams.set('q', q); url.searchParams.set('r', r);
    history.replaceState(null, '', url);
    if (!concept) { $('#plan-result').innerHTML = '<p class="small muted" style="margin-top:16px">Choose your concept first.</p>'; return; }
    planResult(concept, q, r);
  };
  document.querySelectorAll('[data-concept]').forEach(b => b.addEventListener('click', () => { concept = b.dataset.concept; document.querySelectorAll('[data-concept]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); if ($('#plan-q').value.trim()) go(); }));
  document.querySelectorAll('[data-street]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); $('#plan-q').value = a.dataset.street; go(); }));
  $('#plan-form').addEventListener('submit', e => { e.preventDefault(); go(); });
  $('#plan-r').addEventListener('change', () => { if ($('#plan-q').value.trim()) go(); });
  if (concept && q) planResult(concept, q, r);
}
