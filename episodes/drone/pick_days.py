"""Выбирает 10 дней смены на город из почасового ERA5 за 2025 год (Open-Meteo, models=era5) и пишет world/<город>.json.
Смена 13:00–15:00 по местному времени, в файл идут часы 12:00–16:00 (запас на интерполяцию).
Дни выбираются по ветру на 100 м в часы смены: от штиля до ветра выше предела дрона, плюс крайние по температуре."""
import json, os
H = os.path.dirname(os.path.abspath(__file__)); E = os.path.join(H, "geo", "era5")
CITIES = {
    "almaty": {"file": "almaty", "name": {"ru": "Алматы", "en": "Almaty"}, "extreme": "cold"},
    "dubai": {"file": "dubai", "name": {"ru": "Дубай", "en": "Dubai"}, "extreme": "hot"},
    "rotterdam": {"file": "rotterdam", "name": {"ru": "Роттердам", "en": "Rotterdam"}, "extreme": "wind"},
}
VARS = ["temperature_2m", "wind_speed_10m", "wind_direction_10m", "wind_speed_100m", "wind_direction_100m", "wind_gusts_10m"]
for key, c in CITIES.items():
    d = json.load(open(os.path.join(E, c["file"] + ".json"))); h = d["hourly"]
    days = {}
    for i, t in enumerate(h["time"]):
        day, hh = t[:10], int(t[11:13])
        if 12 <= hh <= 16:
            days.setdefault(day, []).append(i)
    rows = []
    for day, idx in days.items():
        if len(idx) != 5 or any(h[v][i] is None for v in VARS for i in idx):
            continue
        sh = idx[1:4]
        rows.append({"day": day, "w100": sum(h["wind_speed_100m"][i] for i in sh) / 3, "gust": max(h["wind_gusts_10m"][i] for i in sh),
                     "t": sum(h["temperature_2m"][i] for i in sh) / 3, "idx": idx})
    rows.sort(key=lambda r: r["w100"])
    n = len(rows); pick = []
    for q in (0.05, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 0.97):  # ветер от штиля до сильного
        pick.append(rows[min(n - 1, int(q * n))])
    pick.append(max(rows, key=lambda r: r["w100"]))
    # крайние дни города: три самых холодных (Алматы), жарких (Дубай) или с сильнейшими порывами (Роттердам), не подряд
    keyf = {"cold": lambda r: r["t"], "hot": lambda r: -r["t"], "wind": lambda r: -r["gust"]}[c["extreme"]]
    ext = []
    for r in sorted(rows, key=keyf):
        if all(abs(int(r["day"][5:7]) * 31 + int(r["day"][8:]) - int(x["day"][5:7]) * 31 - int(x["day"][8:])) > 5 for x in ext):
            ext.append(r)
        if len(ext) == 3:
            break
    pick = pick[:6] + [pick[-1]] + ext
    for q in (0.42, 0.58, 0.72, 0.12):  # добрать до 10, если дни совпали
        if len({r["day"] for r in pick}) >= 10: break
        pick.append(rows[int(q * n)])
    seen = []; out = []
    for r in pick:
        if r["day"] in seen:
            continue
        seen.append(r["day"])
        out.append({"day": r["day"], "hours": [h["time"][i][11:16] for i in r["idx"]], **{v: [h[v][i] for i in r["idx"]] for v in VARS}})
    out = out[:10]
    out.sort(key=lambda r: r["day"])
    world = {"city": key, "name": c["name"], "lat": d["latitude"], "lon": d["longitude"], "elevation_m": d["elevation"], "timezone": d["timezone"],
             "shift": "13:00-15:00", "_tag": "И: ERA5 (Copernicus), почасовые данные через Open-Meteo Historical Weather API, models=era5, ячейка 0,25°",
             "_note": "ERA5 сглаживает ветер в горах и между домами: местные порывы и горный ветер в мире добавляются по зерну (О)", "days": out}
    json.dump(world, open(os.path.join(H, "world", key + ".json"), "w"), ensure_ascii=False, indent=0)
    print(c["name"]["ru"], len(out), "дней:", ", ".join("%s %.1f м/с %.0f°C" % (r["day"], sum(r["wind_speed_100m"][1:4]) / 3, sum(r["temperature_2m"][1:4]) / 3) for r in out))
