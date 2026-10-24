import json
from urllib.parse import quote_plus
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
u=open('atlas_user.txt').read().strip(); p=open('atlas_password.txt').read().strip()
db=MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']
cases=json.load(open('build/cases_draft.json'))
db.cases.drop(); db.cases.insert_many(cases); print('cases',db.cases.count_documents({}))
from pymongo import GEOSPHERE
db.cases.create_index([('location',GEOSPHERE)])
def mk(coll,name,defn):
    try:
        print(coll,name,db[coll].create_search_index(SearchIndexModel(definition=defn,name=name)))
    except Exception as e: print(coll,name,'ERR',str(e)[:200])
mk('places','places_text',{'mappings':{'dynamic':False,'fields':{'name':{'type':'string'},'address':{'type':'string'},'business_type':{'type':'stringFacet'}}}})
mk('google','google_text',{'mappings':{'dynamic':False,'fields':{'name':{'type':'string'},'address':{'type':'string'},'reviews':{'type':'document','dynamic':True}}}})
mk('companies','companies_text',{'mappings':{'dynamic':False,'fields':{'name':{'type':'string'},'address':{'type':'string'}}}})
print([ (i['name'],i.get('status')) for c in ['places','google','companies'] for i in db[c].list_search_indexes()])
