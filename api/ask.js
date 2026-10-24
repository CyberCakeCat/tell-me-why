// Ask the board: Gemini picks the tools itself; every fact comes from a MongoDB query.
// Tools: find_place (street / address / postcode → point), search_cases (Hybrid Search: $rankFusion of $search and
// $vectorSearch with Automated Embedding, plus a geo filter), area_stats ($geoNear + $group over merged venues).
// Response: text with [case:id] links and the list of steps — which MongoDB query ran and how long it took.
const { db, geminiKey } = require('./_db');
const MODEL = 'gemini-4-argon';
const CONCEPTS = ['coffee', 'bakery', 'restaurant', 'takeaway', 'bar'];
const R = 6378137;

const TOOLS = [{ functionDeclarations: [
  { name: 'find_place', description: 'Turn a street name, address or UK postcode in the Shoreditch / Hoxton area into coordinates.',
    parameters: { type: 'OBJECT', properties: { place: { type: 'STRING' } }, required: ['place'] } },
  { name: 'search_cases', description: 'Hybrid search (keywords + meaning) over closure case files: addresses where food businesses closed, with company chains, verdicts and hypotheses. Optionally limit to a radius around a point.',
    parameters: { type: 'OBJECT', properties: { query: { type: 'STRING' }, lng: { type: 'NUMBER' }, lat: { type: 'NUMBER' }, radius_m: { type: 'NUMBER' } }, required: ['query'] } },
  { name: 'area_stats', description: 'Count trading food & drink venues around a point by concept (coffee, bakery, restaurant, takeaway, bar), with median Google rating, typical price and hygiene for one concept.',
    parameters: { type: 'OBJECT', properties: { lng: { type: 'NUMBER' }, lat: { type: 'NUMBER' }, radius_m: { type: 'NUMBER' }, concept: { type: 'STRING', enum: CONCEPTS } }, required: ['lng', 'lat'] } },
] }];

const SYSTEM = `You are the analyst of "Tell Me WHY", helping someone decide on a hospitality lease in London. We cover Shoreditch & Hoxton (around Encode Hub) and Richmond & St Margarets.
Use the tools for every fact; never invent numbers, venues or reasons. Locate places with find_place before area questions.
Closure reasons are hypotheses: say "may", give the evidence. Company dates are registration/dissolution, not opening hours.
Answer in 3-6 short sentences in the user's language. Cite case files as [case:<id>] right after the fact they support.`;

const median = xs => { const s = xs.filter(x => x != null).sort((a, b) => a - b); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

async function findPlace(d, { place }) {
  const pc = String(place).trim().toUpperCase().match(/^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$/);
  if (pc) {
    const r = await fetch(`https://api.postcodes.io/postcodes/${encodeURIComponent(place)}`).then(r => r.json()).catch(() => null);
    if (r?.result) return { result: { lng: r.result.longitude, lat: r.result.latitude, label: r.result.postcode }, query: 'postcodes.io lookup' };
  }
  const n = String(place).toLowerCase().replace(/\bst\b\.?/g, 'street').replace(/\brd\b\.?/g, 'road').replace(/[^a-z0-9 ]/g, ' ').trim();
  const rx = new RegExp(n.split(/\s+/).map(w => w.replace(/street/, 'st(reet)?').replace(/road/, 'r(oa)?d')).join('\\s+'), 'i');
  const pipeline = [{ $match: { address: rx } }, { $group: { _id: null, n: { $sum: 1 }, lng: { $avg: { $arrayElemAt: ['$location.coordinates', 0] } }, lat: { $avg: { $arrayElemAt: ['$location.coordinates', 1] } } } }];
  const [r] = await d.collection('venues').aggregate(pipeline).toArray();
  if (!r) return { result: { error: 'not found in our area' }, query: `venues.aggregate($match address ~ /${rx.source}/i, $group avg coordinates)` };
  return { result: { lng: r.lng, lat: r.lat, label: place, addresses: r.n }, query: `venues.aggregate($match address ~ /${rx.source}/i, $group avg coordinates) → ${r.n} addresses` };
}

async function searchCases(d, { query, lng, lat, radius_m }) {
  const pipelines = {
    vector: [{ $vectorSearch: { index: 'cases_autoembed', path: 'analysis_text', query: { text: query }, numCandidates: 100, limit: 25 } }],
    text: [{ $search: { index: 'cases_text', text: { query, path: ['analysis_text', 'address', 'chain.name', 'analysis.headline', 'analysis.concept_guess'], fuzzy: {} } } }, { $limit: 25 }],
  };
  const pipe = [{ $rankFusion: { input: { pipelines }, combination: { weights: { vector: 1, text: 1 } }, scoreDetails: true } }];
  if (lng != null && lat != null) pipe.push({ $match: { location: { $geoWithin: { $centerSphere: [[lng, lat], (radius_m || 400) / R] } } } });
  pipe.push({ $limit: 6 }, { $project: { _id: 0, id: 1, address: 1, closure_level: 1, location: 1, headline: '$analysis.headline', chain: { name: 1, months: 1, opened: 1, closed: 1, 'verification.verdict': 1 }, score: { $meta: 'score' }, details: { $meta: 'scoreDetails' } } });
  const rows = await d.collection('cases').aggregate(pipe).toArray();
  return {
    result: rows.map(r => ({ id: r.id, address: r.address, level: r.closure_level, headline: r.headline,
      companies: r.chain.map(c => `${c.name} ${c.opened?.slice(0, 7)}→${c.closed?.slice(0, 7)} (${c.months} mo, ${c.verification?.verdict})`),
      ranks: Object.fromEntries((r.details?.details || []).map(x => [x.inputPipelineName, x.rank])) })),
    query: `cases.aggregate($rankFusion{ $vectorSearch(cases_autoembed, Automated Embedding, "${query}") + $search(cases_text) }${lng != null ? `, $match $geoWithin ${radius_m || 400} m` : ''})`,
  };
}

async function areaStats(d, { lng, lat, radius_m, concept }) {
  const r = radius_m || 300;
  const rows = await d.collection('venues').aggregate([
    { $geoNear: { near: { type: 'Point', coordinates: [lng, lat] }, distanceField: 'd', maxDistance: r, spherical: true } },
    { $group: { _id: '$concept', n: { $sum: 1 }, rating: { $median: { input: '$google.rating', method: 'approximate' } }, ratings: { $push: '$google.rating' },
      lo: { $push: { $arrayElemAt: ['$google.price', 0] } }, hi: { $push: { $arrayElemAt: ['$google.price', 1] } }, hygiene: { $push: '$fsa.hygiene' } } },
  ]).toArray();
  const by = Object.fromEntries(rows.map(x => [x._id, x.n]));
  const c = concept && rows.find(x => x._id === concept);
  return {
    result: { radius_m: r, counts: by, total: rows.reduce((s, x) => s + x.n, 0),
      ...(c ? { concept, median_rating: c.rating, typical_price_gbp: [median(c.lo), median(c.hi)], median_hygiene: median(c.hygiene), rated: c.ratings.filter(x => x != null).length } : {}) },
    query: `venues.aggregate($geoNear ${r} m, $group by concept with $median rating)`,
  };
}
const RUN = { find_place: findPlace, search_cases: searchCases, area_stats: areaStats };

async function gemini(contents) {
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${geminiKey()}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ systemInstruction: { parts: [{ text: SYSTEM }] }, contents, tools: TOOLS, generationConfig: { temperature: 0.2 } }),
  });
  if (r.status === 402 || r.status === 429) throw new Error('The analyst has run out of Gemini credits for now. The rest of the site works without it.');
  if (!r.ok) throw new Error(`Gemini ${r.status}`);
  return (await r.json()).candidates?.[0]?.content || { parts: [] };
}

module.exports = async (req, res) => {
  const q = String(req.query.q || '').trim().slice(0, 400);
  if (q.length < 3) return res.status(400).json({ error: 'question too short' });
  const d = await db();
  const contents = [{ role: 'user', parts: [{ text: q }] }], steps = [], cited = new Set();
  try {
    for (let turn = 0; turn < 5; turn++) {
      const content = await gemini(contents);
      contents.push(content);
      const calls = (content.parts || []).filter(p => p.functionCall);
      if (!calls.length) {
        const answer = (content.parts || []).map(p => p.text || '').join('').trim();
        (answer.match(/\[case:[^\]]+\]/g) || []).forEach(m => m.slice(1, -1).split(/,\s*/).forEach(x => cited.add(x.replace(/^case:/, '').trim())));
        return res.status(200).json({ question: q, answer, steps, cited: [...cited], model: MODEL });
      }
      const responses = [];
      for (const { functionCall: fc } of calls) {
        const t0 = Date.now();
        let out;
        try { out = await RUN[fc.name](d, fc.args || {}); } catch (e) { out = { result: { error: String(e.message).slice(0, 120) }, query: fc.name }; }
        steps.push({ tool: fc.name, args: fc.args, query: out.query, ms: Date.now() - t0, results: Array.isArray(out.result) ? out.result.length : undefined });
        responses.push({ functionResponse: { name: fc.name, response: { result: out.result } } });
      }
      contents.push({ role: 'user', parts: responses });
    }
    res.status(200).json({ question: q, answer: 'I could not finish the analysis in time. Try a more specific question.', steps, cited: [] });
  } catch (e) {
    res.status(502).json({ error: 'analysis failed', detail: String(e.message).slice(0, 120), steps });
  }
};
