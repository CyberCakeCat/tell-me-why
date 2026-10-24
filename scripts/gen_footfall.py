"""Замена footfall из открытых данных TfL (честно: это люди на станциях, а не поток мимо двери).
1) TfL Annual Station Counts 2025 (data/tfl/AC2025.xlsx): входы+выходы в типичный будний день, субботу, воскресенье и за год.
2) TfL Crowding API: типичная загрузка ближайшей станции метро по часам (будни/суббота), % от базового уровня.
Для каждого дела: станции в 800 м (~10 минут пешком) и профиль по часам ближайшей станции метро.
Пишет `footfall_proxy` в Atlas (cases) и app/data/cases.json. Ответы API кэшируются в build/crowding_cache.json."""
import json, math, os, re, urllib.request
from urllib.parse import quote_plus
import openpyxl
from pymongo import MongoClient

u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']
CACHE = 'build/crowding_cache.json'
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

def num(x): return x if isinstance(x, (int, float)) else 0

def norm(s): return re.sub(r'\b(underground|rail|station|dlr|overground)\b', '', s.lower()).replace('&', 'and').replace(' ', '').replace('-', '').replace("'", '')

counts = {}
ws = openpyxl.load_workbook('data/tfl/AC2025.xlsx', read_only=True, data_only=True).worksheets[0]
for r in ws.iter_rows(min_row=8, values_only=True):
    if not r[3] or r[6] is None: continue
    k = norm(r[3]); prev = counts.get(k, {'modes': [], 'weekday': 0, 'saturday': 0, 'sunday': 0, 'annual': 0})
    prev['modes'].append(r[0]); prev['name'] = r[3]
    prev['weekday'] += num(r[7]) + num(r[12]); prev['saturday'] += num(r[9]) + num(r[14])
    prev['sunday'] += num(r[10]) + num(r[15]); prev['annual'] += num(r[18])
    counts[k] = prev

def crowding(naptan, day):
    key = f'{naptan}/{day}'
    if key not in cache:
        req = urllib.request.Request(f'https://api.tfl.gov.uk/crowding/{naptan}/{day}', headers={'User-Agent': 'tell-me-why/1.0'})
        try: cache[key] = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e: cache[key] = {'error': str(e)[:80]}
    bands = cache[key].get('timeBands') or []
    hours = [0.0] * 24
    for b in bands:
        hours[int(b['timeBand'][:2])] += b['percentageOfBaseLine'] / 4
    return [round(h, 2) for h in hours] if bands else None

def dist(a, b):
    (x1, y1), (x2, y2) = a['coordinates'], b['coordinates']
    return math.hypot((y1-y2)*111320, (x1-x2)*111320*math.cos(math.radians(y1)))

stations = list(db.stations.find({}, {'_id': 0}))
for s in stations:
    s['counts'] = counts.get(norm(s['name']))
matched = sum(1 for s in stations if s['counts'])

for c in db.cases.find({}):
    near = sorted(((dist(c['location'], s['location']), s) for s in stations), key=lambda x: x[0])
    within = [(d, s) for d, s in near if d <= 800]
    seen, out = set(), []
    for d, s in within:
        k = s['counts'] and s['counts']['name']
        if not k or k in seen: continue
        seen.add(k)
        out.append({'name': s['counts']['name'], 'modes': sorted(set(s['counts']['modes'])), 'walk_m': round(d),
                    'weekday_taps': round(s['counts']['weekday']), 'saturday_taps': round(s['counts']['saturday']),
                    'sunday_taps': round(s['counts']['sunday']), 'annual_taps': round(s['counts']['annual'])})
    tube = next((s for d, s in near if s['naptan'].startswith('940G')), None)
    profile = None
    if tube:
        wk, sat = crowding(tube['naptan'], 'TUE'), crowding(tube['naptan'], 'SAT')
        if wk: profile = {'station': tube['name'], 'walk_m': round(dist(c['location'], tube['location'])), 'weekday': wk, 'saturday': sat}
    fp = {'stations': out[:4], 'hourly': profile,
          'note': 'People entering and leaving stations (TfL, 2025), not people walking past this door.',
          'sources': ['TfL Annual Station Counts 2025', 'TfL Crowding API (typical busyness by hour)']}
    db.cases.update_one({'_id': c['_id']}, {'$set': {'footfall_proxy': fp}})
json.dump(cache, open(CACHE, 'w'))
json.dump(list(db.cases.find({}, {'_id': 0, 'analysis_text': 0})), open('app/data/cases.json', 'w'), ensure_ascii=False, indent=1)
print('stations matched to counts', matched, '/', len(stations))
x = db.cases.find_one({'id': '57-pitfield-st-N16BU'})['footfall_proxy']
print(json.dumps(x['stations'], ensure_ascii=False)[:500])
h = x['hourly']; print(h and (h['station'], 'weekday 13h', h['weekday'][13], '18h', h['weekday'][18], '21h', h['weekday'][21]))
