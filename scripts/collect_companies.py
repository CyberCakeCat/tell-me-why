"""Ликвидированные компании общепита в районе из Companies House (нужен ключ в ch_key.txt, LIVE-приложение).
Результат: data/companies_dissolved.json (GeoJSON-точка по почтовому индексу). Адрес = юридический (может быть бухгалтерским)."""
import json, re, time, base64, urllib.request, urllib.parse
from datetime import date

KEY = open("ch_key.txt").read().strip()
AUTH = "Basic " + base64.b64encode((KEY + ":").encode()).decode()
SICS = "56101,56102,56103,56302,10710"
OUTWARD = {"E1", "E2", "E8", "N1", "EC2"}
UA = {"User-Agent": "Mozilla/5.0"}

def ch(params):
    r = urllib.request.Request("https://api.company-information.service.gov.uk/advanced-search/companies?" +
                               urllib.parse.urlencode(params), headers={"Authorization": AUTH})
    with urllib.request.urlopen(r, timeout=90) as f:
        return json.load(f)

def district(pc):
    m = re.match(r"^([A-Z]{1,2}\d{1,2})[A-Z]?\s*\d[A-Z]{2}$", (pc or "").upper().strip())
    return m.group(1) if m else None

def months(a, b):
    try:
        y1, m1, _ = map(int, a.split("-")); y2, m2, _ = map(int, b.split("-"))
        return (y2 - y1) * 12 + (m2 - m1)
    except Exception:
        return None

found = {}
for loc in ["E1", "E2", "E8", "N1", "EC2A", "EC2M", "EC2Y", "EC2R", "EC2V", "EC2N"]:
    idx = 0
    while True:
        r = ch({"company_status": "dissolved", "sic_codes": SICS, "location": loc,
                "dissolved_from": "2016-01-01", "size": 1000, "start_index": idx})
        items = r.get("items", [])
        for i in items:
            ra = i.get("registered_office_address", {})
            if district(ra.get("postal_code")) in OUTWARD:
                found[i["company_number"]] = i
        idx += len(items)
        print(loc, idx, "/", r.get("hits"), "kept", len(found))
        if not items or idx >= r.get("hits", 0):
            break
        time.sleep(1)

# геокодирование по почтовому индексу
pcs = sorted({i["registered_office_address"]["postal_code"] for i in found.values()})
geo = {}
for k in range(0, len(pcs), 100):
    req = urllib.request.Request("https://api.postcodes.io/postcodes", data=json.dumps({"postcodes": pcs[k:k+100]}).encode(),
                                 headers={"Content-Type": "application/json", **UA})
    for x in json.load(urllib.request.urlopen(req, timeout=60))["result"]:
        if x["result"]:
            geo[x["query"]] = (x["result"]["longitude"], x["result"]["latitude"], x["result"]["codes"]["lsoa"])

docs = []
for i in found.values():
    ra = i["registered_office_address"]; pc = ra["postal_code"]
    if pc not in geo: continue
    lng, lat, lsoa = geo[pc]
    docs.append({"source": "companies_house", "company_number": i["company_number"], "name": i["company_name"],
                 "sic_codes": i.get("sic_codes", []), "incorporated": i.get("date_of_creation"),
                 "dissolved": i.get("date_of_cessation"), "lifespan_months": months(i.get("date_of_creation", ""), i.get("date_of_cessation", "")),
                 "address": ", ".join(x for x in [ra.get("address_line_1"), ra.get("address_line_2"), ra.get("locality")] if x),
                 "postcode": pc, "outward": district(pc), "lsoa": lsoa, "status": "dissolved",
                 "address_note": "registered office (may differ from trading address)",
                 "location": {"type": "Point", "coordinates": [lng, lat]}})
json.dump(docs, open("data/companies_dissolved.json", "w", encoding="utf-8"), ensure_ascii=False)
from collections import Counter
ls = [d["lifespan_months"] for d in docs if d["lifespan_months"] is not None]
print("итого", len(docs), Counter(d["outward"] for d in docs), "медиана жизни, мес.", sorted(ls)[len(ls)//2] if ls else None)
