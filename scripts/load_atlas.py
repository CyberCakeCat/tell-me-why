import json, os, sys
from pymongo import MongoClient, GEOSPHERE
from urllib.parse import quote_plus
user = open('atlas_user.txt').read().strip(); pwd = open('atlas_password.txt').read().strip()
uri = f'mongodb+srv://{quote_plus(user)}:{quote_plus(pwd)}@cluster0.kkky9y1.mongodb.net/'
c = MongoClient(uri, serverSelectionTimeoutMS=15000)
c.admin.command('ping'); print('connected')
db = c['deadspot']
files = {'places':'fsa_places','google':'google_places','companies':'companies_dissolved','stations':'stations','areas':'areas'}
for coll, f in files.items():
    docs = json.load(open(f'data/{f}.json'))
    db[coll].drop(); db[coll].insert_many(docs)
    print(coll, db[coll].count_documents({}))
for coll in ['places','google','companies','stations']:
    db[coll].create_index([('location', GEOSPHERE)])
db.google.create_index('place_id'); db.companies.create_index('company_number'); db.areas.create_index('lsoa')
print(db.list_collection_names())
