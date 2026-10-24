"""Street history: every food company opening and closing is an event in time (time-series collection
`occupancy_events`, metaField = street). A window aggregation ($setWindowFields) computes per street and year:
openings, closings, net and a rolling 3-year churn. Stored in cases.street_history
and app/data/cases.json. Registered-office addresses (more than 6 companies) are dropped, as in build_cases.py."""
import json, math, re
from collections import Counter
from datetime import datetime
from urllib.parse import quote_plus
from pymongo import MongoClient

from areas import AREAS
u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']

def dist(a, b): return math.hypot((a[1]-b[1])*111320, (a[0]-b[0])*111320*math.cos(math.radians(a[1])))
def street(addr):
    s = re.sub(r'^(flat|unit|office|suite)\s+\S+\s*', '', addr.split(',')[0].strip(), flags=re.I)
    m = re.search(r'\d+[a-z]?(?:\s*-\s*\d+)?\s+(.+)$', s, re.I)
    name = (m.group(1) if m else s).lower()
    name = re.sub(r'\bst\b\.?$', 'street', name); name = re.sub(r'\brd\b\.?$', 'road', name)
    return name.strip().title() if re.search(r'(street|road|square|lane|place|row|market|walk|yard|court|terrace|gardens|way|parade|grove)$', name) else None

companies = [c for c in db.companies.find({}, {'_id': 0}) if c.get('location') and any(
    c.get('area', 'shoreditch') == n and dist(c['location']['coordinates'], (a['center'][1], a['center'][0])) <= a['venues_radius'] for n, a in AREAS.items())]
per_addr = Counter((c['address'], c['postcode']) for c in companies)
events = []
for c in companies:
    if per_addr[(c['address'], c['postcode'])] > 6: continue
    st = street(c['address'])
    if not st: continue
    meta = {'street': st, 'postcode': c['postcode'], 'company_number': c['company_number']}
    if c.get('incorporated'): events.append({'at': datetime.fromisoformat(c['incorporated']), 'meta': meta, 'type': 'opened', 'name': c['name']})
    if c.get('dissolved'): events.append({'at': datetime.fromisoformat(c['dissolved']), 'meta': meta, 'type': 'closed', 'name': c['name'], 'months': c.get('lifespan_months')})

if 'occupancy_events' in db.list_collection_names(): db.occupancy_events.drop()
db.create_collection('occupancy_events', timeseries={'timeField': 'at', 'metaField': 'meta', 'granularity': 'hours'})
db.occupancy_events.insert_many(events)

pipeline = [
    {'$match': {'at': {'$gte': datetime(2012, 1, 1)}}},
    {'$group': {'_id': {'street': '$meta.street', 'year': {'$year': '$at'}},
                'opened': {'$sum': {'$cond': [{'$eq': ['$type', 'opened']}, 1, 0]}},
                'closed': {'$sum': {'$cond': [{'$eq': ['$type', 'closed']}, 1, 0]}},
                'median_life': {'$median': {'input': '$months', 'method': 'approximate'}}}},
    {'$setWindowFields': {'partitionBy': '$_id.street', 'sortBy': {'_id.year': 1}, 'output': {
        'closed_3y': {'$sum': '$closed', 'window': {'documents': [-2, 0]}},
        'opened_3y': {'$sum': '$opened', 'window': {'documents': [-2, 0]}},
        'cum_net': {'$sum': {'$subtract': ['$opened', '$closed']}, 'window': {'documents': ['unbounded', 'current']}}}}},
    {'$group': {'_id': '$_id.street', 'years': {'$push': {'year': '$_id.year', 'opened': '$opened', 'closed': '$closed', 'closed_3y': '$closed_3y', 'opened_3y': '$opened_3y', 'cum_net': '$cum_net', 'median_life': '$median_life'}},
                'total_closed': {'$sum': '$closed'}}},
    {'$match': {'total_closed': {'$gte': 3}}},
]
streets = {s['_id']: sorted(s['years'], key=lambda y: y['year']) for s in db.occupancy_events.aggregate(pipeline)}

n = 0
for c in db.cases.find({}, {'id': 1, 'address': 1}):
    st = street(c['address'])
    if st in streets:
        db.cases.update_one({'_id': c['_id']}, {'$set': {'street_history': {'street': st, 'years': streets[st],
            'source': 'Companies House food & drink companies (SIC 56), registered within 900 m; time-series collection occupancy_events'}}})
        n += 1
json.dump(list(db.cases.find({}, {'_id': 0, 'analysis_text': 0})), open('app/data/cases.json', 'w'), ensure_ascii=False, indent=1, default=str)
print('events', len(events), 'streets', len(streets), 'cases with history', n)
for s in ('Pitfield Street', 'Rivington Street', 'Great Eastern Street'):
    if s in streets: print(s, [(y['year'], y['opened'], y['closed']) for y in streets[s][-8:]])
