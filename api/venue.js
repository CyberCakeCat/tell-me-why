// Full report for one venue, assembled from Atlas: the merged venue card, its Google listing (hours, reviews,
// attributes, customer segments), direct competitors and the neighbourhood mix ($geoNear), address histories
// nearby, and the street-by-the-hour / TfL / street-history context of the nearest address history.
const { db } = require('./_db');

module.exports = async (req, res) => {
  const id = String(req.query.id || '');
  const d = await db();
  const v = await d.collection('venues').findOne({ $or: [{ id }, { 'google.place_id': id }] }, { projection: { _id: 0 } });  // venue id or Google place id
  if (!v) return res.status(404).json({ error: 'venue not found' });
  const near = (coll, max, extra = [], query = {}) => d.collection(coll).aggregate([
    { $geoNear: { near: v.location, distanceField: 'd', maxDistance: max, spherical: true, query } }, ...extra]).toArray();

  const [g, competitors, mix, cases] = await Promise.all([
    v.google?.place_id ? d.collection('google').findOne({ place_id: v.google.place_id }, { projection: { _id: 0, opening_hours: 1, reviews: 1, attributes: 1, audience: 1, types: 1, review_summary: 1 } }) : null,
    near('venues', 300, [{ $match: { id: { $ne: v.id } } }, { $limit: 60 }, { $project: { _id: 0, id: 1, name: 1, d: 1, address: 1, google: { rating: 1, n: 1, price: 1, audience: 1 }, fsa: { hygiene: 1, status: 1, authority: 1, matched_by: 1 } } }], { concept: v.concept }),
    near('venues', 300, [{ $group: { _id: '$concept', n: { $sum: 1 } } }]),
    near('cases', 250, [{ $limit: 5 }, { $project: { _id: 0, id: 1, address: 1, closure_level: 1, d: 1, headline: '$analysis.headline', chain: { name: 1, months: 1, closed: 1 }, street_hours: 1, footfall_proxy: 1, street_history: 1 } }]),
  ]);
  const ctx = cases[0] || null;
  res.setHeader('Cache-Control', 's-maxage=300');
  res.status(200).json({
    venue: v,
    listing: g && { hours: g.opening_hours || [], attributes: g.attributes || {}, audience: g.audience || null, review_summary: g.review_summary || null,
      reviews: (g.reviews || []).filter(r => r.text).map(r => ({ rating: r.rating, time: r.time, text: r.text.length > 420 ? r.text.slice(0, 420).replace(/\s+\S*$/, '') + '…' : r.text })) },
    competitors, mix: Object.fromEntries(mix.map(x => [x._id, x.n])),
    cases: cases.map(({ street_hours, footfall_proxy, street_history, ...c }) => c),
    context: ctx && { from_case: ctx.id, distance_m: Math.round(ctx.d), street_hours: ctx.street_hours, footfall: ctx.footfall_proxy, street_history: ctx.street_history },
  });
};
