"""Create a browseable snapshot of operational hospitality venues; no entity inference."""
import json
from pathlib import Path
root=Path(__file__).resolve().parent
rows=json.loads((root.parent/'data/google_places.json').read_text())
types={'restaurant','cafe','coffee_shop','bakery','bar','meal_takeaway'}
keep=['name','address','primary_type','types','price_level','price_range','rating','rating_count','location','status']
result=[]
seen=set()
for r in rows:
 if r.get('status')!='OPERATIONAL' or not types.intersection(r.get('types',[])) or not r.get('location'):continue
 if r['place_id'] in seen:continue
 seen.add(r['place_id']);result.append({'id':r['place_id'],**{k:r.get(k) for k in keep},'source':'Google Places','observed_at':None})
(root.parent/'design/assets/active-venues.json').write_text(json.dumps(result,ensure_ascii=False))
print(len(result),'operational hospitality listings in source snapshot')
