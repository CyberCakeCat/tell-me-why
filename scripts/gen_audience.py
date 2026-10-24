"""Customer segments per venue: code computes the signals, Gemini only finds supporting quotes in reviews.
1) Code: opening hours (weekdays only, closed in the evening, open late), Google attributes, price, ONS Census 2021 area.
2) Gemini: which guest groups each venue's reviews mention, with a VERBATIM quote.
   Every quote is checked by code; if it is not in the review text, it is dropped.
3) Result: segments with score, evidence and confidence (high only when code and reviews agree).
Output: design/assets/venue-audience.json (by place_id) and the `audience` field in Atlas (google).
Re-runs reuse Gemini answers from build/audience_cache.json (--refresh to ask again)."""
import json, math, os, re, sys, statistics, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

K = open('gemini_key.txt').read().strip()
MODEL = 'gemini-4-argon'
SEGMENTS = {
    'office_workers': 'Office workers',
    'families': 'Families with children',
    'students': 'Students',
    'evening_crowd': 'Evening & nightlife crowd',
    'visitors': 'Tourists & visitors',
    'locals': 'Neighbourhood regulars',
    'remote_workers': 'Laptop & remote workers',
}
CACHE = 'build/audience_cache.json'
cache = {} if '--refresh' in sys.argv or not os.path.exists(CACHE) else json.load(open(CACHE))

google = [g for g in json.load(open('data/google_places.json')) if g.get('location')]
postcodes = json.load(open('data/postcode_lsoa.json'))
areas = {a['lsoa']: a for a in json.load(open('data/areas.json'))}
MED = {k: statistics.median(a[k] for a in areas.values()) for k in ('student_share', 'employed_share')}
MED_U20 = statistics.median(a['age_share']['under_20'] for a in areas.values())
MED_2034 = statistics.median(a['age_share']['20_34'] for a in areas.values())

def dist(lat1, lon1, lat2, lon2): return math.hypot((lat1-lat2)*111320, (lon1-lon2)*111320*math.cos(math.radians(lat1)))

def area_for(g):
    m = re.search(r'\b([A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})\b', g.get('address', ''))
    pc = m and m.group(1).replace('  ', ' ')
    if pc and pc in postcodes: return areas.get(postcodes[pc]['lsoa'])
    lon, lat = g['location']['coordinates']
    best = min(postcodes.values(), key=lambda p: dist(lat, lon, p['lat'], p['lng']))
    return areas.get(best['lsoa'])

def hours(g):
    """(open on Saturday, open on Sunday, latest weekday closing as hour 0-29, earliest weekday opening)"""
    sat = sun = None; closes = []; opens = []
    for h in g.get('opening_hours') or []:
        d, _, t = h.partition(': '); t = t.replace(' ', ' ').replace(' ', ' ')
        closed = 'Closed' in t
        if d == 'Saturday': sat = not closed
        if d == 'Sunday': sun = not closed
        if d in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday') and not closed:
            if 'Open 24 hours' in t: closes.append(24); opens.append(0); continue
            times = re.findall(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM)', t)
            if len(times) >= 2:
                def h24(x):
                    hh = int(x[0]) % 12 + (12 if x[2] == 'PM' else 0); return hh + int(x[1] or 0) / 60
                o, c = h24(times[0]), h24(times[-1])
                if c <= o: c += 24
                opens.append(o); closes.append(c)
    return sat, sun, (max(closes) if closes else None), (min(opens) if opens else None)

def code_signals(g):
    """Code signals: {segment: [(weight, evidence text, source)]}"""
    s = {k: [] for k in SEGMENTS}; a = g.get('attributes') or {}
    sat, sun, close, open_ = hours(g)
    if sat is False and sun is False: s['office_workers'].append((2, 'Closed at weekends, open on weekdays', 'Google hours'))
    if close is not None and close <= 17.5: s['office_workers'].append((1, f'Closes by {int(close)}:{int(close%1*60):02d} on weekdays', 'Google hours'))
    if open_ is not None and open_ <= 8: s['office_workers'].append((1, f'Opens at {int(open_)}:{int(open_%1*60):02d} on weekdays', 'Google hours'))
    if close is not None and close >= 23: s['evening_crowd'].append((2, f'Open until {int(close)%24}:{int(close%1*60):02d} on weekdays', 'Google hours'))
    if a.get('servesBeer') and a.get('servesWine') and a.get('servesDinner'): s['evening_crowd'].append((1, 'Serves dinner, beer and wine', 'Google attributes'))
    if a.get('goodForChildren'): s['families'].append((2, 'Listed as good for children', 'Google attributes'))
    if a.get('goodForChildren') is False: s['families'].append((-1, 'Listed as not good for children', 'Google attributes'))
    if a.get('servesBrunch') and sat and sun: s['locals'].append((1, 'Weekend brunch', 'Google attributes + hours'))
    if a.get('allowsDogs'): s['locals'].append((1, 'Dog-friendly', 'Google attributes'))
    if a.get('takeout') and a.get('servesLunch') and sat is False: s['office_workers'].append((1, 'Weekday lunch with takeaway', 'Google attributes'))
    if a.get('servesCoffee') and (g.get('primary_type') in ('cafe', 'coffee_shop')) and open_ is not None and open_ <= 8: s['remote_workers'].append((1, 'Coffee shop open early', 'Google type + hours'))
    pr = g.get('price_range') or {}
    hi = (pr.get('endPrice') or {}).get('units') if isinstance(pr, dict) else None
    if hi and int(hi) <= 15: s['students'].append((1, f'Budget prices (up to £{hi} per person)', 'Google price range'))
    ar = area_for(g)
    if ar:
        if ar['student_share'] >= 2 * MED['student_share']: s['students'].append((1, f"{ar['student_share']}% of residents nearby are students (area median {MED['student_share']}%)", 'ONS Census 2021'))
        if ar['age_share']['under_20'] >= MED_U20 + 5: s['families'].append((1, f"{ar['age_share']['under_20']}% of residents nearby are under 20 (area median {MED_U20}%)", 'ONS Census 2021'))
        if ar['age_share']['20_34'] >= MED_2034 + 10: s['evening_crowd'].append((1, f"{ar['age_share']['20_34']}% of residents nearby are 20–34 (area median {MED_2034}%)", 'ONS Census 2021'))
    return s, ar

SCHEMA = {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {
    'id': {'type': 'STRING'},
    'mentions': {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {
        'segment': {'type': 'STRING', 'enum': list(SEGMENTS)},
        'quote': {'type': 'STRING'}}, 'required': ['segment', 'quote']}}},
    'required': ['id', 'mentions']}}
PROMPT = """For each venue below, find guests' own words in its reviews that show WHO comes there.
Segments: office_workers (colleagues, work lunch, team, after work), families (kids, children, family), students, evening_crowd (night out, drinks, late, party, date night),
visitors (tourists, visiting London, first time in London), locals (regular, neighbourhood, local, every week), remote_workers (laptop, working from here, wifi).
Rules: quote must be copied EXACTLY from one review (5-20 words, no changes). Only include clear evidence; most venues have 0-2 mentions. Do not guess from food or prices.
Return JSON array: [{{"id": ..., "mentions": [{{"segment": ..., "quote": ...}}]}}].

VENUES:
{data}"""

def gemini(batch):
    key = '|'.join(g['place_id'] for g in batch)
    if key in cache: return cache[key]
    data = [{'id': g['place_id'], 'name': g['name'], 'reviews': [r['text'] for r in g['reviews'][:5] if r.get('text')]} for g in batch]
    body = {'contents': [{'parts': [{'text': PROMPT.format(data=json.dumps(data, ensure_ascii=False))}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': SCHEMA, 'temperature': 0.1}}
    for _ in range(3):
        try:
            r = urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={K}',
                                       data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            out = json.loads(urllib.request.urlopen(r, timeout=180).read())
            res = json.loads(''.join(p.get('text', '') for p in out['candidates'][0]['content']['parts']))
            cache[key] = res; return res
        except Exception as e:
            err = repr(e)
    print('gemini failed', err[:120]); return []

def norm_q(s): s = s or ''; return re.sub(r'\s+', ' ', s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')).strip().lower()

with_reviews = [g for g in google if g.get('reviews')]
batches = [with_reviews[i:i+10] for i in range(0, len(with_reviews), 10)]
with ThreadPoolExecutor(6) as ex:
    results = [m for res in ex.map(gemini, batches) for m in res]
json.dump(cache, open(CACHE, 'w'), ensure_ascii=False)
by_id = {g['place_id']: g for g in google}
quotes, rejected = {}, 0
for item in results:
    g = by_id.get(item.get('id'))
    if not g: continue
    texts = [norm_q(r['text']) for r in g['reviews']]
    for m in item.get('mentions', []):
        q = m.get('quote', '').strip().strip('"')
        if m.get('segment') in SEGMENTS and len(q) >= 12 and any(norm_q(q) in t for t in texts):
            quotes.setdefault(g['place_id'], {}).setdefault(m['segment'], []).append(q)
        else:
            rejected += 1

out = {}
for g in google:
    sig, ar = code_signals(g); q = quotes.get(g['place_id'], {})
    segs = []
    for k, label in SEGMENTS.items():
        code_pts = sum(w for w, _, _ in sig[k]); rev = q.get(k, [])[:2]
        score = code_pts + 2 * len(rev)
        if score < 2: continue
        independent = len({src.split(' ')[0] for w, _, src in sig[k] if w > 0}) + (1 if rev else 0)
        conf = 'high' if (code_pts > 0 and rev and independent >= 2) else 'medium' if score >= 3 else 'low'
        segs.append({'segment': k, 'label': label, 'score': score, 'confidence': conf,
                     'evidence': [{'text': t, 'source': src} for w, t, src in sig[k] if w > 0],
                     'quotes': rev})
    segs.sort(key=lambda x: -x['score'])
    out[g['place_id']] = {'name': g['name'], 'loc': g['location']['coordinates'], 'segments': segs[:3],
                          'area': ar and {'lsoa': ar['lsoa'], 'name': ar['name'], 'student_share': ar['student_share'], 'employed_share': ar['employed_share'], 'age_share': ar['age_share']},
                          'note': 'Hypothesis from opening hours, Google attributes, ONS Census 2021 and review quotes. Census counts residents, not daytime workers.'}

json.dump(out, open('design/assets/venue-audience.json', 'w'), ensure_ascii=False, separators=(',', ':'))
c = sum(1 for v in out.values() if v['segments'])
print(f'venues {len(out)}, with audience {c}, quotes kept {sum(len(x) for v in quotes.values() for x in v.values())}, rejected {rejected}')
from collections import Counter
print(Counter(v['segments'][0]['segment'] for v in out.values() if v['segments']))
print(Counter(s['confidence'] for v in out.values() for s in v['segments']))
