"""Станции метро/железной дороги рядом с районом из TfL API (ключ не нужен).
Результат: data/stations.json"""
import json, urllib.request
URL = ("https://api.tfl.gov.uk/StopPoint?lat=51.5246&lon=-0.0786&radius=3000"
       "&stopTypes=NaptanMetroStation,NaptanRailStation")
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
data = json.load(urllib.request.urlopen(req, timeout=60))
out = [{"source": "tfl", "naptan": s["naptanId"], "name": s["commonName"], "modes": s.get("modes", []),
        "location": {"type": "Point", "coordinates": [s["lon"], s["lat"]]}} for s in data["stopPoints"]]
json.dump(out, open("data/stations.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(out), [s["name"] for s in out][:12])
