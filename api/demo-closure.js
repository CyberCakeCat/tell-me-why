// Stage demo: insert a closure event into `closure_events`. Atlas Stream Processing (scripts/stream_processor.json)
// finds case files within 150 m and writes signals to `alerts`. When the processor is not running
// (STREAM_PROCESSING != 'on') this function does the same calculation and labels it processed_by: 'api-fallback'.
// Protected by DEMO_KEY so that nobody else can insert events.
const { db } = require('./_db');
const PRESETS = {
  pitfield: { company_name: 'PITFIELD BAGEL CO LTD', address: '45 Pitfield Street, London N1 6DA', location: { type: 'Point', coordinates: [-0.08412, 51.52748] } },
  rivington: { company_name: 'RIVINGTON NOODLE BAR LTD', address: '18 Rivington Street, London EC2A 3DU', location: { type: 'Point', coordinates: [-0.08205, 51.52597] } },
};
const dist = ([x1, y1], [x2, y2]) => Math.hypot((y1 - y2) * 111320, (x1 - x2) * 111320 * Math.cos(y1 * Math.PI / 180));

module.exports = async (req, res) => {
  if (!process.env.DEMO_KEY || req.query.key !== process.env.DEMO_KEY) return res.status(403).json({ error: 'demo key required' });
  const p = PRESETS[req.query.preset] || PRESETS.pitfield;
  const d = await db();
  const event = { ...p, sic: '56101', dissolved_at: new Date().toISOString().slice(0, 10), source: 'demo', created_at: new Date() };
  const { insertedId } = await d.collection('closure_events').insertOne(event);
  let fallback = 0;
  if (process.env.STREAM_PROCESSING !== 'on') {
    const cases = await d.collection('cases').find({}, { projection: { id: 1, address: 1, location: 1 } }).toArray();
    const near = cases.map(c => ({ c, m: dist(c.location.coordinates, p.location.coordinates) })).filter(x => x.m <= 150);
    if (near.length) await d.collection('alerts').insertMany(near.map(({ c, m }) => ({ case_id: c.id, address: c.address, distance_m: Math.round(m),
      event: { company_name: p.company_name, address: p.address, location: p.location, dissolved_at: event.dissolved_at }, processed_by: 'api-fallback', at: new Date() })));
    fallback = near.length;
  }
  res.status(200).json({ ok: true, event_id: String(insertedId), processed_by: process.env.STREAM_PROCESSING === 'on' ? 'atlas-stream-processing' : 'api-fallback', alerts: fallback });
};
