from urllib.parse import quote_plus
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
u=open('atlas_user.txt').read().strip(); p=open('atlas_password.txt').read().strip()
db=MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']
for name,defn in [
 ('cases_autoembed',{'fields':[{'type':'autoEmbed','modality':'text','path':'analysis_text','model':'voyage-4'},{'type':'filter','path':'postcode'}]}),
]:
    try:
        print(db.cases.create_search_index(SearchIndexModel(definition=defn,name=name,type='vectorSearch')))
    except Exception as e: print('ERR',str(e)[:400])
print([(i['name'],i.get('status')) for i in db.cases.list_search_indexes()])
