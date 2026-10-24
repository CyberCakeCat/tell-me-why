"""Companies registered anywhere in the UK under a venue's trading name (food & drink SIC codes), for venues whose
company is not registered in the area: chains and groups often keep their registered office in central London.
Needs ch_key.txt. Cached per venue in build/ch_names.json; venue_companies.py merges the result."""
import json, os, time, base64, urllib.request, urllib.parse
from urllib.parse import quote_plus
from pymongo import MongoClient
from venue_companies_lib import words, distinctive

KEY = open('ch_key.txt').read().strip()
AUTH = 'Basic ' + base64.b64encode((KEY + ':').encode()).decode()
SICS = '56101,56102,56103,56302,10710'
CACHE = 'build/ch_names.json'

u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

def search(name):
    q = urllib.parse.urlencode({'company_name_includes': name, 'sic_codes': SICS, 'size': 50})
    r = urllib.request.Request('https://api.company-information.service.gov.uk/advanced-search/companies?' + q, headers={'Authorization': AUTH})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(r, timeout=60) as f: return json.load(f).get('items', [])
        except urllib.error.HTTPError as e:
            if e.code == 404: return []
            if e.code == 429: time.sleep(60); continue
            raise
    return []

todo = [v for v in db.venues.find({'companies.operator': None}, {'id': 1, 'name': 1}) if distinctive(words(v['name']))]
print('venues to look up', len(todo))
for k, v in enumerate(todo):
    w = words(v['name'])
    if w in cache: continue
    cache[w] = [{'company_number': i['company_number'], 'name': i['company_name'], 'status': i.get('company_status'),
                 'incorporated': i.get('date_of_creation'), 'dissolved': i.get('date_of_cessation'),
                 'address': ', '.join(filter(None, [(i.get('registered_office_address') or {}).get(x) for x in ('address_line_1', 'locality')])),
                 'postcode': (i.get('registered_office_address') or {}).get('postal_code')} for i in search(w)]
    if k % 50 == 0:
        json.dump(cache, open(CACHE, 'w')); print(k, v['name'], len(cache[w]))
    time.sleep(0.55)  # Companies House allows 600 requests per 5 minutes
json.dump(cache, open(CACHE, 'w'))
print('done', len(cache))
