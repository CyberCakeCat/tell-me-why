"""Build a small read-only design enrichment from supplied source records."""
import json, math, re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
load=lambda f:json.loads((ROOT.parent/f).read_text())
cases=load('app/data/cases.json'); google=load('data/google_places.json'); cache=load('build/verify_cache.json')
norm=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
def distance(a,b):
 if not a or not b:return 1e10
 return math.hypot((a[0]-b[0])*math.cos(math.radians(a[1])),a[1]-b[1])*111320
byid={r['place_id']:r for r in google}
for values in cache.values():
 if not isinstance(values,list):continue
 for r in values:
  if not isinstance(r,dict) or not r.get('id'):continue
  byid.setdefault(r['id'],{'place_id':r['id'],'name':r.get('displayName',{}).get('text'),'rating':r.get('rating'),'rating_count':r.get('userRatingCount'),'status':r.get('businessStatus'),'address':r.get('formattedAddress')})
def compact(r):return {k:r[k] for k in ['place_id','name','address','primary_type','types','price_level','price_range','rating','rating_count','status'] if k in r}
result={'by_place_id':{},'by_case_listing':{}}
for c in cases:
 for entity in c.get('chain',[]):
  for ident in entity.get('verification',{}).get('evidence',[]):
   if isinstance(ident,str) and ident in byid:result['by_place_id'][ident]=compact(byid[ident])
 for row in c.get('now_here',[]):
  hits=[r for r in google if norm(r['name'])==norm(row['name']) and distance(r.get('location',{}).get('coordinates'),c.get('location',{}).get('coordinates'))<=200]
  if len(hits)==1:result['by_case_listing'][c['id']+'|'+row['src']+'|'+row['name']]=compact(hits[0])
(ROOT/'assets/venue-details.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('Venue enrichment:',len(result['by_place_id']),'historical source IDs;',len(result['by_case_listing']),'exact-name local listing matches')
