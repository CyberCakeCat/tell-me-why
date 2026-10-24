"""Действующие заведения у хаба из Google Places (New): цена, часы, отзывы, рейтинг. Ключ в google_key.txt.
Запускается порциями (сохраняет прогресс в data/google_progress.json). Результат: data/google_places.json.
Стоимость ~ $0.04 за запрос (до 20 мест в запросе); жёсткий лимит MAX_REQUESTS."""
import json, math, os, sys, time, urllib.request

KEY = open("google_key.txt").read().strip()
HUB = (51.527626, -0.083849)
RADIUS_M, STEP_M = 900, 400
QUERIES = ["cafe", "restaurant", "bakery", "bar", "pub", "takeaway"]
MAX_REQUESTS, BUDGET_S = 260, int(sys.argv[1]) if len(sys.argv) > 1 else 140
FIELDS = ",".join("places." + f for f in [
    "id", "displayName", "formattedAddress", "location", "businessStatus", "primaryType", "types", "priceLevel", "priceRange",
    "rating", "userRatingCount", "regularOpeningHours.weekdayDescriptions", "reviews.text", "reviews.rating",
    "reviews.publishTime", "servesBreakfast", "servesBrunch", "servesLunch", "servesDinner", "servesCoffee", "servesBeer",
    "servesWine", "dineIn", "takeout", "delivery", "outdoorSeating", "goodForGroups", "goodForChildren", "allowsDogs"]) + ",nextPageToken"

P = "data/google_progress.json"
st = json.load(open(P)) if os.path.exists(P) else {"requests": 0, "done": [], "places": {}}

def cells():
    out = []
    n = RADIUS_M // STEP_M
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            dy, dx = i * STEP_M, j * STEP_M
            if math.hypot(dx, dy) <= RADIUS_M:
                out.append((HUB[0] + dy / 110540, HUB[1] + dx / (111320 * math.cos(math.radians(HUB[0])))))
    return out

def search(q, c, token=None):
    half = STEP_M / 2
    dlat, dlng = half / 110540, half / (111320 * math.cos(math.radians(HUB[0])))
    b = {"textQuery": q, "pageSize": 20, "locationRestriction": {"rectangle": {
        "low": {"latitude": c[0] - dlat, "longitude": c[1] - dlng}, "high": {"latitude": c[0] + dlat, "longitude": c[1] + dlng}}}}
    if token: b["pageToken"] = token
    req = urllib.request.Request("https://places.googleapis.com/v1/places:searchText", data=json.dumps(b).encode(),
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": KEY, "X-Goog-FieldMask": FIELDS})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

t0 = time.time()
jobs = [(q, c) for c in cells() for q in QUERIES]
for q, c in jobs:
    tag = f"{q}|{c[0]:.5f}|{c[1]:.5f}"
    if tag in st["done"]: continue
    if st["requests"] >= MAX_REQUESTS or time.time() - t0 > BUDGET_S: break
    token = None
    for page in range(3):
        try:
            r = search(q, c, token); st["requests"] += 1
        except Exception as e:
            print("ошибка", str(e)[:120]); break
        for p in r.get("places", []): st["places"][p["id"]] = p
        token = r.get("nextPageToken")
        if not token or st["requests"] >= MAX_REQUESTS: break
        time.sleep(0.4)
    st["done"].append(tag)
    json.dump(st, open(P, "w"), ensure_ascii=False)
json.dump(st, open(P, "w"), ensure_ascii=False)
print(f"запросов {st['requests']}/{MAX_REQUESTS} (~${st['requests']*0.04:.1f}), задач {len(st['done'])}/{len(jobs)}, мест {len(st['places'])}")
