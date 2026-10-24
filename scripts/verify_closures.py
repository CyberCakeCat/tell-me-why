"""Проверка каждого закрытия: не сменилась ли просто компания. Для каждой компании цепочки:
1) ищем действующее заведение с тем же названием рядом (FSA + Google из базы);
2) спрашиваем Google Places по названию+адресу (businessStatus), результат кэшируем (build/verify_cache.json).
Вердикт: operating_now (смена юрлица, НЕ закрытие) / closed_google (подтверждено Google) / no_trace (следов нет, название похоже на заведение: вероятно закрыто) / unclear (следов нет, тип неясен: не считать закрытием).
Запуск повторно безопасен: кэш не тратит бюджет. --refresh перепроверяет Google заново."""
import json, math, os, re, sys, time, difflib, urllib.request
from urllib.parse import quote_plus
from pymongo import MongoClient
KEY = open('google_key.txt').read().strip()
u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']
CACHE = 'build/verify_cache.json'
cache = {} if '--refresh' in sys.argv or not os.path.exists(CACHE) else json.load(open(CACHE))
STOP = r'\b(ltd|limited|llp|plc|uk|london|shoreditch|hoxton|holdings|group|trading|hospitality|services|catering|operations|company|co|the|and)\b'
FOOD = r'(cafe|coffee|bar|pub|grill|kitchen|bakery|pizza|burger|chicken|kebab|mangal|food|eats|bagel|diner|restaurant|brew|wine|thai|sushi|noodle|curry|bistro|deli|dessert|pastry|fry|fish|taco|bbq)'
def norm(s): return re.sub(r'\s+', ' ', re.sub(STOP, ' ', re.sub(r'[^a-z0-9 ]', ' ', s.lower().replace('&', ' and ')))).strip()
def sim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b: return 0
    if a in b or b in a: return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()
def xy(l): return l['coordinates'][1], l['coordinates'][0]
def dist(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*69400)
fsa = list(db.places.find({}, {'_id': 0, 'name': 1, 'location': 1, 'rating': 1}))
ggl = [g for g in db.google.find({}, {'_id': 0, 'name': 1, 'location': 1, 'status': 1, 'rating': 1, 'rating_count': 1}) if g.get('location')]

def gsearch(name, pt):
    key = f'{norm(name)}|{pt[0]:.4f}|{pt[1]:.4f}'
    if key in cache: return cache[key]
    b = {'textQuery': name, 'pageSize': 5, 'locationBias': {'circle': {'center': {'latitude': pt[0], 'longitude': pt[1]}, 'radius': 80.0}}}
    req = urllib.request.Request('https://places.googleapis.com/v1/places:searchText', data=json.dumps(b).encode(), headers={
        'Content-Type': 'application/json', 'X-Goog-Api-Key': KEY,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.businessStatus,places.location,places.rating,places.userRatingCount,places.formattedAddress'})
    try: r = json.load(urllib.request.urlopen(req, timeout=40)).get('places', [])
    except Exception as e: r = [{'error': str(e)[:100]}]
    cache[key] = r; time.sleep(0.15); return r

def verify(company, pt):
    nm = company['name']
    local = [('FSA', f['name']) for f in fsa if dist(pt, xy(f['location'])) <= 45 and sim(nm, f['name']) >= 0.6] + \
            [('Google', g['name']) for g in ggl if dist(pt, xy(g['location'])) <= 45 and sim(nm, g['name']) >= 0.6]
    if local:
        return {'verdict': 'operating_now', 'note': f'A venue with the same name is trading now: {local[0][1]} ({local[0][0]}). Likely a change of company, not a closure.', 'evidence': local[:2]}
    res = gsearch(re.sub(r'\b(ltd|limited)\b', '', nm, flags=re.I).strip().title(), pt)
    hits = [x for x in res if 'error' not in x and sim(nm, x.get('displayName', {}).get('text', '')) >= 0.6
            and dist(pt, (x['location']['latitude'], x['location']['longitude'])) <= 120]
    for x in hits:
        st = x.get('businessStatus')
        if st in ('CLOSED_PERMANENTLY', 'CLOSED_TEMPORARILY'):
            return {'verdict': 'closed_google', 'note': f"Google: {x['displayName']['text']} is {st.replace('_', ' ').lower()}, rated {x.get('rating')} ({x.get('userRatingCount')} reviews).", 'evidence': [x['id']], 'rating': x.get('rating'), 'rating_count': x.get('userRatingCount')}
        if st == 'OPERATIONAL':
            return {'verdict': 'operating_now', 'note': f"Google: {x['displayName']['text']} is trading ({x.get('formattedAddress')}). Change of company, not a closure.", 'evidence': [x['id']]}
    if not re.search(FOOD, nm.lower()):
        return {'verdict': 'unclear', 'note': 'No trace on Google or FSA, and the name does not say whether a venue traded here (may be a registered-office address). Not counted as a closure.', 'evidence': []}
    return {'verdict': 'no_trace', 'note': 'No trace on FSA or Google: probably closed, not confirmed.', 'evidence': []}

stats = {}
for c in db.cases.find({}):
    pt = xy(c['location']); chain = c['chain']
    for ch in chain:
        ch['verification'] = verify({'name': ch['name']}, pt)
        stats[ch['verification']['verdict']] = stats.get(ch['verification']['verdict'], 0) + 1
    real = [x for x in chain if x['verification']['verdict'] in ('closed_google', 'no_trace')]
    vs = [x['verification']['verdict'] for x in chain]
    level = 'confirmed' if 'closed_google' in vs else ('probable' if 'no_trace' in vs else ('possible' if 'unclear' in vs else 'entity_change'))
    db.cases.update_one({'_id': c['_id']}, {'$set': {'chain': chain, 'real_closures': len(real), 'closure_level': level, 'verified_at': time.strftime('%Y-%m-%d %H:%M')}})
    json.dump(cache, open(CACHE, 'w'), ensure_ascii=False)
print(stats, 'google_calls_cached', len(cache))
json.dump(list(db.cases.find({}, {'_id': 0, 'analysis_text': 0})), open('app/data/cases.json', 'w'), ensure_ascii=False, indent=1)
