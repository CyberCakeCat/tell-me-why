"""Улица по часам: сколько действующих заведений в 150 м открыто в каждый час (будни и выходные) — прокси того,
живое ли место вечером. Плюс часы прежних арендаторов, если Google их сохранил (у закрытых карточек обычно нет).
Пишет `street_hours` и `chain[].verification.hours` в Atlas (cases) и app/data/cases.json. Ответы Google кэшируются."""
import json, math, os, re, urllib.request
from urllib.parse import quote_plus
from pymongo import MongoClient

KEY = open('google_key.txt').read().strip()
u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']
CACHE = 'build/hours_cache.json'
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

def dist(a, b):
    (x1, y1), (x2, y2) = a['coordinates'], b['coordinates']
    return math.hypot((y1-y2)*111320, (x1-x2)*111320*math.cos(math.radians(y1)))

def open_hours(desc):
    """weekdayDescriptions → {день: множество часов 0..23, когда открыто}; ночные часы после полуночи идут на тот же день"""
    out = {}
    for line in desc or []:
        d, _, t = line.partition(': '); t = t.replace(' ', ' ').replace(' ', ' ')
        if d not in DAYS: continue
        hrs = set()
        if 'Open 24 hours' in t: hrs = set(range(24))
        elif 'Closed' not in t:
            for part in t.split(','):
                times = re.findall(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?', part)
                times = [x for x in times if x[0]]
                if len(times) < 2: continue
                ap_end = times[-1][2] or 'PM'
                def h(x, ap): return int(x[0]) % 12 + (12 if (x[2] or ap) == 'PM' else 0) + int(x[1] or 0) / 60
                o, c = h(times[0], ap_end), h(times[-1], ap_end)
                if c <= o: c += 24
                hrs |= {hh % 24 for hh in range(math.floor(o), math.ceil(c))}
        out[d] = hrs
    return out

def place_hours(pid):
    if pid in cache: return cache[pid]
    req = urllib.request.Request(f'https://places.googleapis.com/v1/places/{pid}', headers={
        'X-Goog-Api-Key': KEY, 'X-Goog-FieldMask': 'businessStatus,regularOpeningHours.weekdayDescriptions'})
    try: r = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e: r = {'error': str(e)[:80]}
    cache[pid] = r; return r

google = [g for g in db.google.find({'status': 'OPERATIONAL'}, {'_id': 0, 'location': 1, 'opening_hours': 1, 'name': 1}) if g.get('opening_hours') and g.get('location')]
parsed = [(g, open_hours(g['opening_hours'])) for g in google]
stats = {'cases': 0, 'prev_hours': 0}
for c in db.cases.find({}):
    near = [h for g, h in parsed if dist(g['location'], c['location']) <= 150]
    wk = [sum(hr in h.get(d, set()) for h in near for d in DAYS[:5]) / 5 for hr in range(24)]
    we = [sum(hr in h.get(d, set()) for h in near for d in DAYS[5:]) / 2 for hr in range(24)]
    n = len(near)
    street = {'n': n, 'weekday': [round(x, 1) for x in wk], 'weekend': [round(x, 1) for x in we],
              'share_open_21_weekday': round(wk[21] / n, 2) if n else None,
              'share_open_13_weekday': round(wk[13] / n, 2) if n else None,
              'source': 'Google Places opening hours of trading venues within 150 m'}
    chain = c['chain']
    for x in chain:
        ev = (x.get('verification') or {}).get('evidence') or []
        if ev and str(ev[0]).startswith('ChIJ'):
            r = place_hours(ev[0]); d = (r.get('regularOpeningHours') or {}).get('weekdayDescriptions')
            if d: x['verification']['hours'] = d; stats['prev_hours'] += 1
    db.cases.update_one({'_id': c['_id']}, {'$set': {'street_hours': street, 'chain': chain}})
    stats['cases'] += 1
json.dump(cache, open(CACHE, 'w'), ensure_ascii=False)
json.dump(list(db.cases.find({}, {'_id': 0, 'analysis_text': 0})), open('app/data/cases.json', 'w'), ensure_ascii=False, indent=1)
print(stats)
x = db.cases.find_one({'id': '14-rivington-st-EC2A3DU'})['street_hours']
print('14 Rivington: n', x['n'], 'open at 13:', x['weekday'][13], 'at 21:', x['weekday'][21], 'at 23:', x['weekday'][23])
x = db.cases.find_one({'id': '57-pitfield-st-N16BU'})['street_hours']
print('57 Pitfield: n', x['n'], 'open at 13:', x['weekday'][13], 'at 21:', x['weekday'][21], 'at 23:', x['weekday'][23])
