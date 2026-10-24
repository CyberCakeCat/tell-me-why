"""Trading food businesses in the area from the FSA Food Hygiene API (no key needed).
Output: data/fsa_places.json."""
import json, re, time, urllib.request

CENTER = (51.5246, -0.0786)          # Shoreditch, next to Encode Hub
RADIUS_MILES = 3
OUTWARD = {"E1", "E2", "E8", "N1", "EC2"}
URL = ("https://api.ratings.food.gov.uk/Establishments?latitude={lat}&longitude={lng}"
       "&maxDistanceLimit={r}&pageSize=5000&pageNumber={p}")

def get(page):
    req = urllib.request.Request(
        URL.format(lat=CENTER[0], lng=CENTER[1], r=RADIUS_MILES, p=page),
        headers={"x-api-version": "2", "accept": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def outward(pc):
    m = re.match(r"^([A-Z]{1,2}\d[A-Z\d]?)\s*\d[A-Z]{2}$", (pc or "").strip().upper())
    if not m:
        return None
    d = re.match(r"^[A-Z]{1,2}\d{1,2}", m.group(1))   # E1W -> E1, EC2A -> EC2, E14 stays E14
    return d.group(0) if d else None

docs, page, total_pages = [], 1, 1
while page <= total_pages:
    data = get(page)
    total_pages = data["meta"]["totalPages"]
    for e in data["establishments"]:
        oc = outward(e.get("PostCode"))
        g = e.get("geocode") or {}
        if oc not in OUTWARD or not g.get("longitude"):
            continue
        addr = ", ".join(x for x in [e.get(f"AddressLine{i}") for i in range(1, 5)] if x)
        docs.append({
            "source": "fsa", "fhrsid": e["FHRSID"], "name": e["BusinessName"],
            "business_type": e["BusinessType"], "address": addr, "postcode": e["PostCode"],
            "outward": oc, "rating": e["RatingValue"], "rating_date": e.get("RatingDate"),
            "scores": e.get("scores"), "status": "open",
            "location": {"type": "Point", "coordinates": [float(g["longitude"]), float(g["latitude"])]},
        })
    print(f"page {page}/{total_pages}: kept {len(docs)}")
    page += 1
    time.sleep(1)

with open("data/fsa_places.json", "w", encoding="utf-8") as f:
    json.dump(docs, f, ensure_ascii=False)
from collections import Counter
print("total", len(docs), Counter(d["outward"] for d in docs), Counter(d["business_type"] for d in docs).most_common(5))
