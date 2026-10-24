"""Find an FSA food hygiene record for every venue that has none yet.
1) FSA establishments within ~150 m of the venue (no name filter), matched by name here — covers postcodes we never downloaded.
2) The venue's name anywhere in the country — market and street traders register at their home kitchen in another borough
   (e.g. a Richmond market stall rated in Merton). Accepted only for a close name match, and labelled with that authority.
3) FSA statuses that are not a score ("Awaiting Inspection", "Exempt") are kept and shown as such.
Writes `fsa` on the `venues` collection and app/data/venues_all.json. FSA answers are cached in build/hygiene_cache.json."""
import json, math, os, re, time, difflib, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
from pymongo import MongoClient

CACHE = 'build/hygiene_cache.json'
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']

STOP = r'\b(ltd|limited|the|and|london|shoreditch|hoxton|richmond|twickenham|restaurant|cafe|café|bar|kitchen|uk|co|coffee)\b'
def words(s): return ' '.join(re.sub(STOP, ' ', re.sub(r'[^a-z0-9é ]', ' ', (s or '').lower().replace('&', ' and '))).split())
def sim(a, b):
    a, b = words(a), words(b)
    if not a or not b: return 0
    if a == b: return 1.0
    if len(min(a, b, key=len)) >= 5 and (a in b or b in a): return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()
def dist(a, b): return math.hypot((a[1]-b[1])*111320, (a[0]-b[0])*111320*math.cos(math.radians(a[1])))

def fsa(url):
    if url not in cache:  # errors (rate limits) are retried, never cached
        req = urllib.request.Request(url, headers={'x-api-version': '2', 'accept': 'application/json', 'User-Agent': 'tell-me-why/1.0'})
        for wait in (0, 2, 5, 10):
            time.sleep(wait)
            try: cache[url] = json.load(urllib.request.urlopen(req, timeout=40)).get('establishments', []); break
            except Exception: continue
        else: return []
    return cache[url]

def record(e, how):
    rv = str(e.get('RatingValue'))
    return {'name': e['BusinessName'], 'hygiene': int(rv) if rv.isdigit() else None,
            'status': None if rv.isdigit() else {'AwaitingInspection': 'Awaiting inspection', 'Exempt': 'Exempt', 'AwaitingPublication': 'Awaiting publication'}.get(rv, rv),
            'date': (e.get('RatingDate') or '')[:10], 'type': e.get('BusinessType'), 'authority': e.get('LocalAuthorityName'),
            'postcode': e.get('PostCode'), 'fhrsid': e.get('FHRSID'), 'matched_by': how}

def find(v):
    lng, lat = v['loc']
    near = fsa(f"https://api.ratings.food.gov.uk/Establishments?latitude={lat}&longitude={lng}&maxDistanceLimit=0.1&sortOptionKey=distance&pageSize=40")
    best = max(((sim(v['name'], e['BusinessName']), e) for e in near), key=lambda t: t[0], default=(0, None))
    if best[0] >= 0.75: return record(best[1], 'FSA, within 150 m')
    q = ' '.join(words(v['name']).split()[:3])
    if len(q) < 4: return None
    anywhere = fsa(f"https://api.ratings.food.gov.uk/Establishments?name={quote_plus(q)}&pageSize=10")
    hits = [e for e in anywhere if sim(v['name'], e['BusinessName']) >= 0.9]
    if len(hits) == 1: return record(hits[0], f"FSA, registered with {hits[0].get('LocalAuthorityName')}")
    return None

todo = [v for v in db.venues.find({}, {'_id': 0, 'id': 1, 'name': 1, 'loc': 1, 'fsa': 1}) if not v.get('fsa') or v['fsa'].get('hygiene') is None]
with ThreadPoolExecutor(2) as ex:
    found = list(ex.map(find, todo))
json.dump(cache, open(CACHE, 'w'))
n = {'score': 0, 'status': 0, 'elsewhere': 0, 'none': 0}
for v, rec in zip(todo, found):
    if not rec: n['none'] += 1; continue
    n['score' if rec['hygiene'] is not None else 'status'] += 1
    if 'registered with' in rec['matched_by']: n['elsewhere'] += 1
    db.venues.update_one({'id': v['id']}, {'$set': {'fsa': rec}})
venues = list(db.venues.find({}, {'_id': 0, 'location': 0}))
json.dump(venues, open('app/data/venues_all.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('checked', len(todo), n, '· venues with a score now', sum(1 for v in venues if (v.get('fsa') or {}).get('hygiene') is not None), 'of', len(venues))
