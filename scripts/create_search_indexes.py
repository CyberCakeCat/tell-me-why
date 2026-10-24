"""Atlas Search and Vector Search indexes used by the app.
- cases_text: full-text index over case files (address, company names, Gemini analysis) — the keyword half of Hybrid Search.
- cases_autoembed: Vector Search with Automated Embedding (Voyage) on `analysis_text` — the meaning half of Hybrid Search.
- google_text: full-text index over venue names, addresses and review text.
Existing indexes with the same name are left as they are."""
from urllib.parse import quote_plus
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

u = open('atlas_user.txt').read().strip(); p = open('atlas_password.txt').read().strip()
db = MongoClient(f'mongodb+srv://{quote_plus(u)}:{quote_plus(p)}@cluster0.kkky9y1.mongodb.net/')['deadspot']

INDEXES = [
    ('cases', 'cases_text', 'search', {'mappings': {'dynamic': False, 'fields': {
        'address': {'type': 'string'}, 'analysis_text': {'type': 'string'}, 'closure_level': {'type': 'token'},
        'chain': {'type': 'document', 'fields': {'name': {'type': 'string'}}},
        'analysis': {'type': 'document', 'fields': {'concept_guess': {'type': 'string'}, 'headline': {'type': 'string'}}}}}}),
    ('cases', 'cases_autoembed', 'vectorSearch', {'fields': [
        {'type': 'autoEmbed', 'modality': 'text', 'path': 'analysis_text', 'model': 'voyage-4'},
        {'type': 'filter', 'path': 'postcode'}]}),
    ('google', 'google_text', 'search', {'mappings': {'dynamic': False, 'fields': {
        'name': {'type': 'string'}, 'address': {'type': 'string'},
        'reviews': {'type': 'document', 'fields': {'text': {'type': 'string'}}}}}}),
]
for coll, name, kind, definition in INDEXES:
    existing = {i['name'] for i in db[coll].list_search_indexes()}
    if name in existing:
        print(coll, name, 'exists'); continue
    db[coll].create_search_index(SearchIndexModel(name=name, type=kind, definition=definition))
    print(coll, name, 'created')
