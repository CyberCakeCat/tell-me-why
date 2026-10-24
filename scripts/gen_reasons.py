"""Closure hypotheses: facts are computed in code; Gemini only phrases hypotheses that cite those facts."""
import json, math, re, statistics, sys, urllib.request, urllib.error
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
    # open after 21:00 on weekdays / open on Sundays
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

PROMPT = """You analyse hospitality leases in London. Below are FACTS about one address where companies were dissolved (Companies House) and the current situation nearby.
Rules: use ONLY these facts, invent nothing (we have no reviews of the closed places). Every hypothesis cites specific facts (quote a number or a name). A reason is a hypothesis, not an established fact.
The registered address may belong to an accountant rather than a venue: if lifespans look templated or names don't look like food businesses, lower the confidence and say so in caveat.
Each company has verification.verdict: operating_now = the venue still trades, it is a CHANGE OF COMPANY, not a closure (don't count it as a failure, but it can show the concept survives); closed_google = confirmed closure; no_trace = probably closed; unclear = unknown, never call it a closure. Confidence no higher than medium without closed_google.
These are real, named businesses, some still trading: never suggest wrongdoing or financial trouble. Do not use the words phoenix, restructuring, thriving, debt, insolvency, liquidation, financial distress, tax, fraud, mismanagement or bankrupt. A change of company is just that; say it neutrally.
If the chain has several closures, describe the repetition (chain_pattern). Give 2-3 hypotheses, each with a counter-argument. Write all output fields in clear plain English (UK), short. Confidence high only with several independent facts.

DATA:
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

# Wording that would suggest wrongdoing by a real, named business. Checked in code after every answer.
BANNED = r'phoenix|restructur|thriving|tax liabilit|financial distress|fraud|insolven|\bdebts?\b|evasion|scam|mismanag|liquidat|bankrupt'

def work(c):
    f = facts(c)
    data = {'address': c['address'], 'dist_to_encode_hub_m': c['dist_hub_m'], 'closures_chain': c['chain'],
            'avg_lifespan_months': c['avg_months'], 'context': f,
            'who_is_nearby_now': c['now_here'][:6]}
    prompt = PROMPT.format(data=json.dumps(data, ensure_ascii=False, indent=1))
    for _ in range(3):  # the wording check runs in code; retry with the offending words named
        res = gemini(prompt)
        found = sorted(set(m.lower() for m in re.findall(BANNED, json.dumps(res), re.I)))
        if 'error' in res or not found: break
        prompt += f"\nYour previous answer used forbidden wording: {', '.join(found)}. Rewrite without it."
    if 'error' not in res and found:  # last resort: drop the hypotheses that still break the rule
        res['hypotheses'] = [h for h in res['hypotheses'] if not re.search(BANNED, json.dumps(h), re.I)]
    return c['id'], f, res

ONLY = next((a.split('=', 1)[1].split(',') for a in sys.argv if a.startswith('--ids=')), None)
cases = list(db.cases.find({'id': {'$in': ONLY}} if ONLY else {}))
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
# export for the front end
json.dump(list(db.cases.find({}, {'_id': 0, 'analysis_text': 0})), open('app/data/cases.json', 'w'), ensure_ascii=False, indent=1)
print('exported app/data/cases.json')
