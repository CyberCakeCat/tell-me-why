"""One card per venue: FSA (hygiene) and Google (rating, price, hours) merged, plus a concept.
1) Merge by similar name within 60 m.
2) FSA venues without a match: search Google Places by name near the point (cache build/fill_cache.json).
   If nothing is found, the venue honestly stays without a rating (`google: null`).
3) Concept (coffee / bakery / restaurant / takeaway / bar) from the primary Google category, FSA type and name.
4) Google-only venues: hygiene score from the free FSA API (by name and nearby, match within 60 m; cache build/fsa_fill_cache.json).
Output: app/data/venues_all.json (Plan a venue screen) and the `venues` collection in Atlas (2dsphere)."""
import json, math, os, re, sys, time, difflib, urllib.request
from urllib.parse import quote_plus
from pymongo import MongoClient, GEOSPHERE

from areas import AREAS, data_path
KEY = open('google_key.txt').read().strip()
CACHE = 'build/fill_cache.json'
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
FILL = '--no-fill' not in sys.argv

def dist(a, b): return math.hypot((a[1]-b[1])*111320, (a[0]-b[0])*111320*math.cos(math.radians(a[1])))
STOP = r'\b(ltd|limited|the|and|london|shoreditch|hoxton|restaurant|cafe|café|bar|kitchen|uk|co)\b'
def words(s): return ' '.join(re.sub(STOP, ' ', re.sub(r'[^a-z0-9é ]', ' ', (s or '').lower().replace('&', ' and '))).split())
def sim(a, b):
    a, b = words(a), words(b)
    if not a or not b: return 0
    if a in b or b in a: return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()

FOOD_FSA = {'Restaurant/Cafe/Canteen', 'Takeaway/sandwich shop', 'Pub/bar/nightclub', 'Other catering premises', 'Hotel/bed & breakfast/guest house', 'Mobile caterer'}
COFFEE_W = r'coffee|espresso|roast|caff[eè]|\bcafe\b|café|brew|matcha|tea room'
BAKERY_W = r'bak(er|ing|e)|patisser|p[aâ]tisserie|boulanger|cake|bread|croissant|donut|doughnut|bun\b|pastr|dessert|gelato'
PRIMARY = {'coffee_shop': 'coffee', 'cafe': 'coffee', 'tea_house': 'coffee', 'bakery': 'bakery', 'dessert_shop': 'bakery', 'confectionery': 'bakery',
           'donut_shop': 'bakery', 'cake_shop': 'bakery', 'bar': 'bar', 'pub': 'bar', 'cocktail_bar': 'bar', 'wine_bar': 'bar', 'night_club': 'bar',
           'sports_bar': 'bar', 'beer_hall': 'bar', 'meal_takeaway': 'takeaway', 'fast_food_restaurant': 'takeaway', 'sandwich_shop': 'takeaway', 'kebab_shop': 'takeaway'}
NOT_FOOD = {'movie_theater', 'hotel', 'event_venue', 'gym', 'store', 'supermarket', 'grocery_store', 'convenience_store', 'clothing_store', 'art_gallery', 'tourist_attraction'}
def concept(types, fsa_type, name, primary=None):
    t = set(types or []); n = (name or '').lower()
    primary = primary or (types[0] if types else None)
    if primary in NOT_FOOD: return None
    if primary in PRIMARY: return PRIMARY[primary]
    if primary and (primary == 'restaurant' or primary.endswith('_restaurant')):
        return 'bakery' if re.search(BAKERY_W, n) else 'coffee' if re.search(r'coffee|espresso', n) else 'restaurant'
    if t & {'bakery', 'dessert_shop', 'confectionery', 'donut_shop', 'cake_shop'} or re.search(BAKERY_W, n): return 'bakery'
    if t & {'coffee_shop', 'cafe', 'tea_house'} or re.search(COFFEE_W, n): return 'coffee'
    if t & {'bar', 'pub', 'cocktail_bar', 'wine_bar', 'night_club', 'beer_hall', 'sports_bar'} or fsa_type == 'Pub/bar/nightclub': return 'bar'
    if t & {'meal_takeaway', 'fast_food_restaurant', 'sandwich_shop', 'kebab_shop'} or fsa_type == 'Takeaway/sandwich shop': return 'takeaway'
    if any(x == 'restaurant' or x.endswith('_restaurant') for x in t) or fsa_type == 'Restaurant/Cafe/Canteen': return 'restaurant'
    return None

def price(pr):
    if not isinstance(pr, dict): return None
    lo = (pr.get('startPrice') or {}).get('units'); hi = (pr.get('endPrice') or {}).get('units')
    return [int(lo) if lo else None, int(hi) if hi else None] if (lo or hi) else None

fsa, goo = [], []
for name, cfg in AREAS.items():  # every covered area, each within its own radius
    hub = (cfg['center'][1], cfg['center'][0])
    fsa += [{**f, 'area': name} for f in json.load(open(data_path(name, 'fsa_places.json'))) if dist(f['location']['coordinates'], hub) <= cfg['venues_radius']]
    goo += [{**g, 'area': name} for g in json.load(open(data_path(name, 'google_places.json'))) if g.get('location') and g.get('status') == 'OPERATIONAL' and dist(g['location']['coordinates'], hub) <= cfg['venues_radius']]
aud = json.load(open('design/assets/venue-audience.json'))

def google_part(g, how):
    segs = (aud.get(g['place_id']) or {}).get('segments') or []
    return {'place_id': g['place_id'], 'name': g['name'], 'primary': g.get('primary_type'), 'rating': g.get('rating'), 'n': g.get('rating_count'),
            'price': price(g.get('price_range')), 'types': g.get('types') or [], 'address': g.get('address'),
            'audience': segs[0]['label'] if segs and segs[0]['confidence'] != 'low' else None, 'matched_by': how}

def fill(f):
    """Look up an FSA venue on Google by name near its point."""
    lng, lat = f['location']['coordinates']; key = f"{f['fhrsid']}"
    if key not in cache:
        body = {'textQuery': f"{f['name']} {f.get('postcode', '')}", 'pageSize': 3,
                'locationBias': {'circle': {'center': {'latitude': lat, 'longitude': lng}, 'radius': 80.0}}}
        req = urllib.request.Request('https://places.googleapis.com/v1/places:searchText', data=json.dumps(body).encode(), headers={
            'Content-Type': 'application/json', 'X-Goog-Api-Key': KEY,
            'X-Goog-FieldMask': 'places.id,places.displayName,places.businessStatus,places.location,places.rating,places.userRatingCount,places.priceRange,places.types,places.formattedAddress'})
        try: cache[key] = json.load(urllib.request.urlopen(req, timeout=30)).get('places', [])
        except Exception as e: cache[key] = [{'error': str(e)[:80]}]
        time.sleep(0.1)
    for x in cache[key]:
        if 'error' in x or x.get('businessStatus') not in (None, 'OPERATIONAL'): continue
        loc = [x['location']['longitude'], x['location']['latitude']]
        if sim(f['name'], x['displayName']['text']) >= 0.6 and dist(loc, f['location']['coordinates']) <= 80:
            return {'place_id': x['id'], 'name': x['displayName']['text'], 'rating': x.get('rating'), 'n': x.get('userRatingCount'),
                    'price': price(x.get('priceRange')), 'types': x.get('types') or [], 'address': x.get('formattedAddress'),
                    'audience': None, 'matched_by': 'Google search by name'}
    return None

venues, used, stats = [], set(), {'merged': 0, 'filled': 0, 'fsa_only': 0, 'google_only': 0, 'calls': 0}
for f in fsa:
    if f['business_type'] not in FOOD_FSA and not re.search(COFFEE_W + '|' + BAKERY_W, f['name'].lower()): continue
    cands = [(sim(f['name'], g['name']), g) for g in goo if g['place_id'] not in used and dist(f['location']['coordinates'], g['location']['coordinates']) <= 60]
    best = max(cands, key=lambda t: t[0], default=(0, None))
    if best[0] >= 0.7:
        gp = google_part(best[1], 'name + distance ≤ 60 m'); used.add(best[1]['place_id']); stats['merged'] += 1
    elif FILL:
        before = len(cache); gp = fill(f); stats['calls'] += len(cache) - before
        if gp: used.add(gp['place_id']); stats['filled'] += 1
        else: stats['fsa_only'] += 1
    else:
        gp = None; stats['fsa_only'] += 1
    c = concept(gp and gp['types'], f['business_type'], (gp and gp['name']) or f['name'], gp and gp.get('primary'))
    if not c: continue
    venues.append({'id': f"fsa-{f['fhrsid']}", 'name': (gp and gp['name']) or f['name'].title(), 'address': (gp and gp['address']) or f['address'].title(),
                   'loc': f['location']['coordinates'], 'concept': c, 'area': f['area'],
                   'fsa': {'name': f['name'], 'hygiene': int(f['rating']) if str(f['rating']).isdigit() else None, 'date': (f.get('rating_date') or '')[:10], 'type': f['business_type']},
                   'google': gp})
FCACHE = 'build/fsa_fill_cache.json'
fcache = json.load(open(FCACHE)) if os.path.exists(FCACHE) else {}
def fsa_fill(g):
    lng, lat = g['location']['coordinates']; key = g['place_id']
    if key not in fcache:
        name = ' '.join(words(g['name']).split()[:3]) or g['name']
        url = f"https://api.ratings.food.gov.uk/Establishments?name={quote_plus(name)}&latitude={lat}&longitude={lng}&maxDistanceLimit=1&pageSize=5"
        req = urllib.request.Request(url, headers={'x-api-version': '2', 'accept': 'application/json'})
        try: fcache[key] = json.load(urllib.request.urlopen(req, timeout=30)).get('establishments', [])
        except Exception as e: fcache[key] = [{'error': str(e)[:80]}]
    near_key = key + '|near'
    if near_key not in fcache:  # fallback: every FSA venue within ~80 m, matched by name here
        url = f"https://api.ratings.food.gov.uk/Establishments?latitude={lat}&longitude={lng}&maxDistanceLimit=0.05&sortOptionKey=distance&pageSize=15"
        req = urllib.request.Request(url, headers={'x-api-version': '2', 'accept': 'application/json'})
        try: fcache[near_key] = json.load(urllib.request.urlopen(req, timeout=30)).get('establishments', [])
        except Exception as e: fcache[near_key] = [{'error': str(e)[:80]}]
    for e in fcache[key] + fcache[near_key]:
        if 'error' in e or not (e.get('geocode') or {}).get('longitude'): continue
        loc = [float(e['geocode']['longitude']), float(e['geocode']['latitude'])]
        if sim(e['BusinessName'], g['name']) >= 0.7 and dist(loc, g['location']['coordinates']) <= 60:
            return {'name': e['BusinessName'], 'hygiene': int(e['RatingValue']) if str(e['RatingValue']).isdigit() else None,
                    'date': (e.get('RatingDate') or '')[:10], 'type': e.get('BusinessType'), 'matched_by': 'FSA API by name'}
    return None

stats['fsa_filled'] = 0
for g in goo:
    if g['place_id'] in used: continue
    c = concept(g.get('types'), None, g['name'], g.get('primary_type'))
    if not c: continue
    stats['google_only'] += 1
    fp = fsa_fill(g) if FILL else None
    if fp: stats['fsa_filled'] += 1
    venues.append({'id': g['place_id'], 'name': g['name'], 'address': g['address'], 'loc': g['location']['coordinates'], 'concept': c, 'area': g['area'],
                   'fsa': fp, 'google': google_part(g, 'Google listing')})
json.dump(fcache, open(FCACHE, 'w'), ensure_ascii=False)
json.dump(cache, open(CACHE, 'w'), ensure_ascii=False)
json.dump(venues, open('app/data/venues_all.json', 'w'), ensure_ascii=False, separators=(',', ':'))

u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']
db.venues.drop(); db.venues.insert_many([{**v, 'location': {'type': 'Point', 'coordinates': v['loc']}} for v in venues])
db.venues.create_index([('location', GEOSPHERE)]); db.venues.create_index('concept')

from collections import Counter
print(stats, 'venues', len(venues))
print(Counter(v['concept'] for v in venues))
print('with Google rating', sum(1 for v in venues if v['google'] and v['google']['rating']), '· with FSA hygiene', sum(1 for v in venues if v['fsa'] and v['fsa']['hygiene'] is not None), '· with both', sum(1 for v in venues if v['fsa'] and v['google'] and v['google']['rating']))
