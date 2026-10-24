"""Who lives in the area: postcodes.io (postcode -> LSOA) + Census 2021 (Nomis / ONS).
No keys needed. Output: data/areas.json and data/postcode_lsoa.json."""
import json, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0"}

def jget(url, data=None, headers=None):
    h = dict(UA); h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

places = json.load(open("data/fsa_places.json", encoding="utf-8"))
postcodes = sorted({p["postcode"] for p in places})

# 1. postcode -> LSOA
pc_map = {}
for i in range(0, len(postcodes), 100):
    chunk = postcodes[i:i + 100]
    res = jget("https://api.postcodes.io/postcodes", json.dumps({"postcodes": chunk}).encode(),
               {"Content-Type": "application/json"})["result"]
    for x in res:
        r = x["result"]
        if r:
            pc_map[x["query"]] = {"lsoa": r["codes"]["lsoa"], "lsoa_name": r["lsoa"], "msoa": r["codes"]["msoa"],
                                  "borough": r["admin_district"], "lat": r["latitude"], "lng": r["longitude"]}
    time.sleep(0.3)
json.dump(pc_map, open("data/postcode_lsoa.json", "w", encoding="utf-8"), ensure_ascii=False)
lsoas = sorted({v["lsoa"] for v in pc_map.values()})
print("postcodes", len(pc_map), "LSOA", len(lsoas))

# 2. Census 2021 by LSOA
def nomis(ds):
    out = {}
    for i in range(0, len(lsoas), 40):
        g = ",".join(lsoas[i:i + 40])
        j = jget(f"https://www.nomisweb.co.uk/api/v01/dataset/{ds}.data.json?geography={g}&measures=20100")
        for o in j["obs"]:
            dim = next(k for k in o if k.startswith("c2021_"))
            out.setdefault(o["geography"]["geogcode"], {})[o[dim]["description"]] = o["obs_value"]["value"]
        time.sleep(0.5)
    return out

age, eco, ten = nomis("NM_2020_1"), nomis("NM_2083_1"), nomis("NM_2072_1")

def pct(a, b): return round(100 * a / b, 1) if b else None

areas = []
for code in lsoas:
    a, e, t = age.get(code, {}), eco.get(code, {}), ten.get(code, {})
    tot = a.get("Total") or 0
    band = lambda *names: sum(a.get(n, 0) for n in names)
    u20 = band("Aged 4 years and under", "Aged 5 to 9 years", "Aged 10 to 14 years", "Aged 15 to 19 years")
    y2034 = band("Aged 20 to 24 years", "Aged 25 to 29 years", "Aged 30 to 34 years")
    m3549 = band("Aged 35 to 39 years", "Aged 40 to 44 years", "Aged 45 to 49 years")
    o50 = tot - u20 - y2034 - m3549
    e_tot = e.get("Total: All usual residents aged 16 years and over") or 0
    emp = e.get("Economically active (excluding full-time students):In employment", 0) + \
          e.get("Economically active and a full-time student:In employment", 0)
    students = e.get("Economically active and a full-time student", 0) + \
               sum(v for k, v in e.items() if k.startswith("Economically inactive") and k.rstrip().endswith("Student"))
    h_tot = t.get("Total: All households") or 0
    names = [v for v in pc_map.values() if v["lsoa"] == code]
    areas.append({
        "lsoa": code, "name": names[0]["lsoa_name"], "borough": names[0]["borough"], "msoa": names[0]["msoa"],
        "population": tot, "households": h_tot,
        "age_share": {"under_20": pct(u20, tot), "20_34": pct(y2034, tot), "35_49": pct(m3549, tot), "50_plus": pct(o50, tot)},
        "employed_share": pct(emp, e_tot), "student_share": pct(students, e_tot),
        "tenure_share": {"owned": pct(t.get("Owned", 0) + t.get("Shared ownership", 0), h_tot),
                         "social_rented": pct(t.get("Social rented", 0), h_tot),
                         "private_rented": pct(t.get("Private rented", 0), h_tot)},
        "source": "ONS Census 2021",
    })
json.dump(areas, open("data/areas.json", "w", encoding="utf-8"), ensure_ascii=False)
print("areas", len(areas))
print(json.dumps(areas[0], ensure_ascii=False))
