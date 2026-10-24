"""Competition around every venue, for the venue reports: how many venues of the same concept trade within
300 m, and what share of venues in the neighbourhood have fewer such neighbours (a percentile).
Writes `competition` to the `venues` collection in Atlas and to app/data/venues_all.json."""
import json
from urllib.parse import quote_plus
from pymongo import MongoClient

u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']
R = 300

counts = {}
for v in db.venues.find({}, {'id': 1, 'concept': 1, 'location': 1}):
    n = db.venues.count_documents({'concept': v['concept'], 'id': {'$ne': v['id']},
                                   'location': {'$geoWithin': {'$centerSphere': [v['location']['coordinates'], R / 6378137]}}})
    counts[v['id']] = (v['concept'], n)

by_concept = {}
for c, n in counts.values(): by_concept.setdefault(c, []).append(n)
for vid, (c, n) in counts.items():
    pct = round(100 * sum(1 for x in by_concept[c] if x < n) / len(by_concept[c]))
    level = 'high' if pct >= 75 else 'low' if pct <= 35 else 'medium'
    db.venues.update_one({'id': vid}, {'$set': {'competition': {'radius_m': R, 'same_concept': n, 'percentile': pct, 'level': level}}})

venues = list(db.venues.find({}, {'_id': 0, 'location': 0}))
json.dump(venues, open('app/data/venues_all.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('venues', len(venues), {c: (min(x), max(x)) for c, x in by_concept.items()})
