// Live signals: long-poll over a Change Stream on `alerts`. The client sends ?after=<ISO time>;
// signals already waiting are returned at once, otherwise we wait up to ~20 s for the next one.
const { db } = require('./_db');
const shape = a => ({ id: String(a._id), case_id: a.case_id, address: a.address, distance_m: a.distance_m, event: a.event, processed_by: a.processed_by, at: a.at });

module.exports = async (req, res) => {
  const d = await db(), alerts = d.collection('alerts');
  const after = new Date(req.query.after || Date.now() - 60000);
  const recent = await alerts.find({ at: { $gt: after } }).sort({ at: 1 }).limit(50).toArray();
  if (recent.length) return res.status(200).json({ alerts: recent.map(shape), via: 'query' });
  const stream = alerts.watch([{ $match: { operationType: 'insert' } }], { maxAwaitTimeMS: 20000 });
  try {
    const timer = setTimeout(() => stream.close().catch(() => {}), 20000);
    const change = await stream.tryNext().then(c => c || stream.tryNext()).catch(() => null);
    clearTimeout(timer);
    res.status(200).json({ alerts: change ? [shape(change.fullDocument)] : [], via: 'change stream' });
  } finally { stream.close().catch(() => {}); }
};
