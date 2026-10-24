"""Group Companies House closures by address into chains; add current occupants (FSA / Google) and neighbours."""
import json, math, re, collections
H = (51.527626, -0.083849)
R_DEMO = 400
def xy(loc): lon, lat = loc['coordinates']; return lat, lon
def dist(a, b):
    return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*69400)
def norm(s): return re.sub(r'[^a-z0-9 ]', '', s.lower().replace('street','st')).strip()
def key(c):
    m = re.search(r'(\d+[a-z]?(?:-\d+)?)\s+([A-Za-z ]+?)(?:,|$)', c['address'])
    return (m.group(1)+' '+norm(m.group(2)), c['postcode']) if m else (norm(c['address']), c['postcode'])

co = json.load(open('data/companies_dissolved.json'))
fsa = json.load(open('data/fsa_places.json'))
ggl = json.load(open('data/google_places.json'))
per_addr = collections.Counter(key(c) for c in co)
cand = [c for c in co if per_addr[key(c)] <= 6 and c['dissolved'] >= '2018'
        and dist(xy(c['location']), H) <= R_DEMO and 'Flat' not in c['address'] and 'Floor' not in c['address']]
groups = collections.defaultdict(list)
for c in cand: groups[key(c)].append(c)

def tenant(pt):
    out = []
    for p in fsa:
        if dist(xy(p['location']), pt) < 25:
            out.append({'src': 'FSA', 'name': p['name'], 'type': p['business_type'], 'hygiene': p['rating'], 'rating_date': p['rating_date'][:10]})
    for p in ggl:
        if p.get('location') and dist(xy(p['location']), pt) < 25:
            out.append({'src': 'Google', 'name': p['name'], 'rating': p.get('rating'), 'n': p.get('rating_count'), 'price_range': p.get('price_range')})
    return out

cases = []
for k, cs in groups.items():
    cs.sort(key=lambda c: c['incorporated'])
    pt = xy(cs[0]['location'])
    cases.append({
        'id': re.sub(r'\W+', '-', k[0]) + '-' + k[1].replace(' ', ''),
        'address': cs[0]['address'], 'postcode': cs[0]['postcode'], 'location': cs[0]['location'],
        'dist_hub_m': round(dist(pt, H)),
        'chain_len': len(cs),
        'chain': [{'name': c['name'], 'opened': c['incorporated'], 'closed': c['dissolved'], 'months': c['lifespan_months'],
                   'company_number': c['company_number'], 'sic': c['sic_codes']} for c in cs],
        'avg_months': round(sum(c['lifespan_months'] for c in cs)/len(cs), 1),
        'now_here': tenant(pt),
        'confirmation': 'Companies House (registered office, not confirmed by Google)',
    })
cases.sort(key=lambda c: (-c['chain_len'], c['dist_hub_m']))
json.dump(cases, open('build/cases_draft.json', 'w'), ensure_ascii=False, indent=1)
print(len(cases), 'addresses;', sum(1 for c in cases if c['chain_len'] > 1), 'chains')
for c in cases[:14]:
    print(c['dist_hub_m'], c['address'], c['chain_len'], [x['name'].title()+f" ({x['months']} mo)" for x in c['chain']], '=> now:', [t['name'] for t in c['now_here']][:3])
