"""Причины закрытий: факты считаем кодом, Gemini только формулирует гипотезы со ссылками на факты."""
import json, math, re, statistics, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
from pymongo import MongoClient
K = open('gemini_key.txt').read().strip()
MODEL = 'gemini-4-argon'
u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']
stations = list(db.stations.find({}, {'_id': 0}))
fsa = list(db.places.find({}, {'_id': 0}))
ggl = [g for g in db.google.find({}, {'_id': 0}) if g.get('location')]

def xy(l): return l['coordinates'][1], l['coordinates'][0]
def dist(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*69400)

def late_open(hours):
    # открыто ли в будни после 21:00 / работает ли в воскресенье
    late = sun = False
    for h in hours or []:
        d, _, t = h.partition(': ')
        if d == 'Sunday' and 'Closed' not in t: sun = True
        if d in ('Monday','Tuesday','Wednesday','Thursday','Friday'):
            m = re.findall(r'(\d+):(\d+)\s*(AM|PM)\s*$', t.replace(' ',' ').strip())
            if m:
                hh, mm, ap = m[-1]; hh = int(hh) % 12 + (12 if ap == 'PM' else 0)
                if hh >= 21 or hh < 5 or 'Open 24' in t: late = True
    return late, sun

def facts(c):
    pt = xy(c['location'])
    st = sorted(((dist(pt, xy(s['location'])), s['name']) for s in stations))[0]
    near_f = [f for f in fsa if dist(pt, xy(f['location'])) <= 150]
    near_g = [g for g in ggl if dist(pt, xy(g['location'])) <= 150]
    late = [late_open(g.get('opening_hours')) for g in near_g if g.get('opening_hours')]
    rats = [g['rating'] for g in near_g if g.get('rating') and (g.get('rating_count') or 0) >= 20]
    hyg = [int(f['rating']) for f in near_f if str(f.get('rating')).isdigit()]
    return {
        'nearest_station': {'name': st[1], 'm': round(st[0])},
        'venues_within_150m_FSA': len(near_f),
        'google_venues_within_150m': len(near_g),
        'share_open_after_21_weekdays': round(sum(l for l, _ in late)/len(late), 2) if late else None,
        'share_open_sunday': round(sum(s for _, s in late)/len(late), 2) if late else None,
        'neighbour_google_rating_median': round(statistics.median(rats), 2) if rats else None,
        'neighbour_hygiene_median': statistics.median(hyg) if hyg else None,
        'share_price_range_known': round(sum(1 for g in near_g if g.get('price_range'))/len(near_g), 2) if near_g else None,
    }

SCHEMA = {'type': 'OBJECT', 'properties': {
    'concept_guess': {'type': 'STRING'},
    'headline': {'type': 'STRING'},
    'hypotheses': {'type': 'ARRAY', 'items': {'type': 'OBJECT', 'properties': {
        'reason': {'type': 'STRING'}, 'evidence': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
        'confidence': {'type': 'STRING', 'enum': ['low', 'medium', 'high']}, 'counter_argument': {'type': 'STRING'}},
        'required': ['reason', 'evidence', 'confidence', 'counter_argument']}},
    'chain_pattern': {'type': 'STRING'},
    'caveat': {'type': 'STRING'}},
    'required': ['concept_guess', 'headline', 'hypotheses', 'chain_pattern', 'caveat']}

PROMPT = """Ты аналитик по аренде помещений для общепита в Лондоне. Ниже ФАКТЫ по одному адресу, где закрылись юридические лица (Companies House) и текущая обстановка рядом.
Правила: используй ТОЛЬКО эти факты, ничего не выдумывай (отзывов закрывшихся мест у нас нет). Каждая гипотеза ссылается на конкретные факты (цитируй число/название). Причина = гипотеза, не установленный факт.
Юрадрес может принадлежать не заведению, а бухгалтеру: если сроки жизни выглядят шаблонно или названия не похожи на общепит, снижай уверенность и скажи об этом в caveat.
У каждой компании есть verification.verdict: operating_now = заведение работает, это СМЕНА ЮРЛИЦА, не закрытие (не считай в сроки провала, но можно отметить как признак живучести концепции); closed_google = подтверждённое закрытие; no_trace = вероятно закрыто; unclear = неясно, не называй закрытием. Уровень уверенности не выше medium, если нет closed_google.
Если в цепочке несколько закрытий, опиши повтор (chain_pattern). Дай 2-3 гипотезы, с контраргументом. Write all output fields in clear plain English (UK), short. confidence high только при нескольких независимых фактах.

ДАННЫЕ:
{data}"""

def gemini(prompt):
    body = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': SCHEMA, 'temperature': 0.3}}
    for _ in range(3):
        try:
            r = urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={K}',
                data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            out = json.loads(urllib.request.urlopen(r, timeout=120).read())
            parts = out['candidates'][0]['content']['parts']
            return json.loads(''.join(x.get('text', '') for x in parts))
        except Exception as e:
            err = repr(e)
    return {'error': err}

def work(c):
    f = facts(c)
    data = {'address': c['address'], 'dist_to_encode_hub_m': c['dist_hub_m'], 'closures_chain': c['chain'],
            'avg_lifespan_months': c['avg_months'], 'context': f,
            'who_is_nearby_now': c['now_here'][:6]}
    res = gemini(PROMPT.format(data=json.dumps(data, ensure_ascii=False, indent=1)))
    return c['id'], f, res

cases = list(db.cases.find({}))
with ThreadPoolExecutor(6) as ex:
    results = list(ex.map(work, cases))
ok = 0
for cid, f, res in results:
    if 'error' in res: print('ERR', cid, res['error'][:120]); continue
    db.cases.update_one({'id': cid}, {'$set': {'context': f, 'analysis': res, 'analysis_model': MODEL,
        'analysis_text': res['headline'] + '. ' + ' '.join(h['reason'] for h in res['hypotheses'])}})
    ok += 1
json.dump([{'id': i, 'context': f, 'analysis': r} for i, f, r in results], open('build/cases_analysis.json', 'w'), ensure_ascii=False, indent=1)
print('done', ok, '/', len(cases))
# выгрузка для фронта
json.dump(list(db.cases.find({}, {'_id': 0, 'analysis_text': 0})), open('app/data/cases.json', 'w'), ensure_ascii=False, indent=1)
print('exported app/data/cases.json')
