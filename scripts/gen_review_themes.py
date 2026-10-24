"""What guests say about each venue: Gemini reads its Google reviews and returns what is praised and what is
criticised, each point with a VERBATIM quote. Code drops any quote that is not in the review text.
Writes `review_summary` to the `google` collection. Answers are cached in build/review_themes_cache.json."""
import json, os, re, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
from pymongo import MongoClient

K = open('gemini_key.txt').read().strip()
MODEL = 'gemini-4-argon'
CACHE = 'build/review_themes_cache.json'
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']

POINT = {'type': 'OBJECT', 'properties': {'point': {'type': 'STRING'}, 'quote': {'type': 'STRING'}}, 'required': ['point', 'quote']}
SCHEMA = {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {
    'id': {'type': 'STRING'}, 'summary': {'type': 'STRING'},
    'praise': {'type': 'ARRAY', 'items': POINT}, 'complaints': {'type': 'ARRAY', 'items': POINT}},
    'required': ['id', 'summary', 'praise', 'complaints']}}
PROMPT = """For each venue, read its guest reviews and report what guests praise and what they criticise.
Rules: points are short (3-8 words, e.g. "huge portions", "slow service at peak times"). Each point has a quote copied EXACTLY from one review (5-25 words).
Up to 3 praise points and up to 3 complaints; an empty list is fine if nobody complains. summary: one neutral sentence about the overall picture.
Plain UK English. Do not invent anything beyond the reviews.
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
            res = json.loads(''.join(x.get('text', '') for x in out['candidates'][0]['content']['parts']))
            cache[key] = res; return res
        except Exception as e:
            err = repr(e)
    print('gemini failed', err[:100]); return []

def norm(s): return re.sub(r'\s+', ' ', (s or '').replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')).strip().lower()

venues = [g for g in db.google.find({'reviews.0': {'$exists': True}}, {'_id': 0, 'place_id': 1, 'name': 1, 'reviews': 1})]
batches = [venues[i:i + 10] for i in range(0, len(venues), 10)]
with ThreadPoolExecutor(6) as ex:
    results = [x for res in ex.map(gemini, batches) for x in res]
json.dump(cache, open(CACHE, 'w'), ensure_ascii=False)

by_id = {g['place_id']: g for g in venues}
kept = dropped = 0
for item in results:
    g = by_id.get(item.get('id'))
    if not g: continue
    texts = [norm(r.get('text')) for r in g['reviews']]
    def ok(pt):
        nonlocal_ok = len(pt.get('quote', '')) >= 12 and any(norm(pt['quote'].strip('"')) in t for t in texts)
        return nonlocal_ok
    praise = [x for x in item.get('praise', []) if ok(x)]; complaints = [x for x in item.get('complaints', []) if ok(x)]
    dropped += len(item.get('praise', [])) + len(item.get('complaints', [])) - len(praise) - len(complaints); kept += len(praise) + len(complaints)
    db.google.update_one({'place_id': g['place_id']}, {'$set': {'review_summary': {
        'summary': item.get('summary', ''), 'praise': praise, 'complaints': complaints, 'reviews_read': len(texts), 'model': MODEL}}})
print('venues', len(venues), 'quotes kept', kept, 'dropped', dropped)
