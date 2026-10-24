"""Who runs each venue: food & drink companies (active and dissolved) from Companies House matched to every venue.
- Address match: same postcode and the same house number as the venue.
- Name match: a company whose name equals or contains the venue's trading name (see venue_companies_lib.close), registered in the same area,
  or elsewhere in London (build/ch_names.json from name_companies.py) when nothing local carries the name; those are
  listed as history only, since common names ('The Sun Inn') belong to unrelated companies.
The likely operator is an active company matched by name in the area (best: name and address). Addresses where more than six
companies are registered are flagged as registered-office addresses (accountants, formation agents), not venues.
Writes `companies` on the `venues` collection and app/data/venues_all.json."""
import json, os
from collections import Counter, defaultdict
from urllib.parse import quote_plus
from pymongo import MongoClient, UpdateOne
from areas import AREAS, data_path
from venue_companies_lib import postcode, number, words, close, LONDON

u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']

companies = []
for area in AREAS:
    for f, status in (('companies_active.json', 'active'), ('companies_dissolved.json', 'dissolved')):
        try: rows = json.load(open(data_path(area, f)))
        except FileNotFoundError: continue
        companies += [{**c, 'status': status, 'area': area} for c in rows]
by_pc, by_area = defaultdict(list), defaultdict(list)
for c in companies:
    c['words'] = words(c['name'])
    by_pc[c['postcode']].append(c); by_area[c['area']].append(c)
per_address = Counter((c['postcode'], number(c['address'])) for c in companies)
national = json.load(open('build/ch_names.json')) if os.path.exists('build/ch_names.json') else {}

def record(c, how):
    return {'name': c['name'], 'number': c['company_number'], 'status': c['status'], 'incorporated': c.get('incorporated'),
            'dissolved': c.get('dissolved'), 'match': how, 'address': c['address'], 'postcode': c['postcode']}

stats = Counter()
updates = []
for v in db.venues.find({}, {'id': 1, 'name': 1, 'address': 1, 'area': 1, 'fsa': 1}):
    pc = postcode(v.get('address')) or (v.get('fsa') or {}).get('postcode'); num = number(v.get('address'))
    found = {}
    if pc:
        for c in by_pc.get(pc, []):
            same_addr = num and number(c['address']) == num
            named = close(words(v['name']), c['words']) > 0
            if same_addr or named:
                found[c['company_number']] = record(c, 'name and address' if same_addr and named else 'address' if same_addr else 'name')
    vw = words(v['name'])
    for c in by_area[v.get('area', 'shoreditch')]:  # same trading name elsewhere in the area: registered office at an accountant, typically
        if c['company_number'] not in found and close(vw, c['words']):
            found[c['company_number']] = record(c, 'name')
    if not any(r['status'] == 'active' and 'name' in r['match'] for r in found.values()):
        for c in national.get(vw, []):  # registered elsewhere in London under the same name
            if c['company_number'] not in found and c['status'] in ('active', 'dissolved') and LONDON.match(c['postcode'] or '') and close(vw, words(c['name'])) == 1.0:
                found[c['company_number']] = record(c, 'name, registered elsewhere')
    rows = sorted(found.values(), key=lambda r: (r['incorporated'] or ''), reverse=True)
    named_active = [r for r in rows if r['status'] == 'active' and r['match'] in ('name and address', 'name')]
    # name and address beats name only; among equals, the newest company (rows are newest first)
    operator = next((r for r in named_active if r['match'] == 'name and address'), named_active[0] if named_active else None)
    busy = bool(pc and num and per_address[(pc, num)] > 6)
    stats['venues'] += 1; stats['with_companies'] += bool(rows); stats['with_operator'] += bool(operator)
    keep = ([operator] if operator else []) + [r for r in rows if r is not operator][:11]
    updates.append((v['id'], {'records': sorted(keep, key=lambda r: r['incorporated'] or '', reverse=True), 'operator': operator and operator['number'], 'registered_office_address': busy}))

db.venues.bulk_write([UpdateOne({'id': i}, {'$set': {'companies': c}}) for i, c in updates])
venues = list(db.venues.find({}, {'_id': 0, 'location': 0}))
json.dump(venues, open('app/data/venues_all.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(dict(stats), 'companies loaded', len(companies))
for name in ('Ottolenghi Richmond', 'Schnitzel Heaven', 'Knoops', 'Best Mangal Bar & Restaurant'):
    v = next((x for x in venues if x['name'] == name), None)
    if v: print(name, '→', v['companies']['operator'], [(r['name'], r['status'], r['match']) for r in v['companies']['records'][:4]])
