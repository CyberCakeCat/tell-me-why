"""Load a non-default area into Atlas next to Shoreditch: every document gets an `area` field.
Re-running replaces that area's documents only. Usage: python3 scripts/load_area.py richmond"""
import json, os
from urllib.parse import quote_plus
from pymongo import MongoClient, GEOSPHERE
from areas import current, data_path

AREA, CFG = current()
u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']

FILES = {'places': 'fsa_places.json', 'google': 'google_places.json', 'companies': 'companies_dissolved.json',
         'stations': 'stations.json', 'areas': 'areas.json'}
for coll, f in FILES.items():
    db[coll].update_many({'area': {'$exists': False}}, {'$set': {'area': 'shoreditch'}})
    path = data_path(AREA, f)
    if AREA == 'shoreditch' or not os.path.exists(path): continue
    docs = [{**d, 'area': AREA} for d in json.load(open(path)) if coll in ('areas',) or d.get('location')]
    db[coll].delete_many({'area': AREA})
    if docs: db[coll].insert_many(docs)
    print(coll, len(docs))
for coll in ('places', 'google', 'companies', 'stations'):
    db[coll].create_index([('location', GEOSPHERE)]); db[coll].create_index('area')
for coll in ('cases', 'venues'):
    db[coll].update_many({'area': {'$exists': False}}, {'$set': {'area': 'shoreditch'}})
