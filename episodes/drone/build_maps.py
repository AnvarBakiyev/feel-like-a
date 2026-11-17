"""Карты городов для курьера дронов: склад, точки заказов, площадки зарядки, запретные зоны и сетка рельефа.
Координаты точек выбраны вручную по карте (П), высоты из Copernicus DEM GLO-30 (И), запретные круги у аэропортов (О: радиус).
Пишет world/<город>_map.json. Локальные координаты: x на восток, y на север, метры от склада."""
import json, math, os
import numpy as np
from PIL import Image

H = os.path.dirname(os.path.abspath(__file__))
DEM = os.path.join(H, "geo", "dem")
STEP = 250.0  # шаг сетки рельефа, м

CITIES = {
    "almaty": {
        "depot": ("Склад «Сайран»", "Sairan depot", 43.236, 76.866),
        "points": [
            ("Ботанический сад", "Botanical Garden", 43.215, 76.913),
            ("Есентай", "Esentai", 43.218, 76.929),
            ("Самал-2", "Samal-2", 43.227, 76.953),
            ("Кок-Тобе", "Kok-Tobe", 43.231, 76.976),
            ("Горный Гигант", "Gorny Gigant", 43.196, 76.968),
            ("Медеу", "Medeu", 43.157, 77.059),
            ("Шымбулак", "Shymbulak", 43.128, 77.081),
            ("Орбита", "Orbita", 43.205, 76.861),
            ("Айнабулак", "Ainabulak", 43.283, 76.902),
            ("Алатау", "Alatau", 43.222, 76.85),
        ],
        "pads": [3, 4],  # Кок-Тобе и Горный Гигант: площадки зарядки на пути в горы
        "nofly": [("Аэропорт Алматы", "Almaty Airport", 43.352, 77.040, 5000)],
    },
    "dubai": {
        "depot": ("Склад Аль-Куоз", "Al Quoz depot", 25.140, 55.230),
        "points": [
            ("Дубай Марина", "Dubai Marina", 25.080, 55.140),
            ("Даунтаун", "Downtown", 25.197, 55.274),
            ("Джумейра", "Jumeirah", 25.210, 55.250),
            ("Бизнес-Бей", "Business Bay", 25.185, 55.268),
            ("Аль-Барша", "Al Barsha", 25.110, 55.200),
            ("DIFC", "DIFC", 25.213, 55.282),
            ("Пальма", "The Palm", 25.112, 55.139),
            ("Аль-Карама", "Al Karama", 25.245, 55.300),
            ("Аль-Сафа", "Al Safa", 25.170, 55.240),
            ("Мотор-Сити", "Motor City", 25.045, 55.235),
        ],
        "pads": [3, 6],
        "nofly": [("Аэропорт Дубай", "Dubai International Airport", 25.253, 55.365, 6000),
                  ("Аэропорт Аль-Мактум", "Al Maktoum Airport", 24.896, 55.161, 6000)],
    },
    "rotterdam": {
        "depot": ("Склад Ваалхафен", "Waalhaven depot", 51.885, 4.440),
        "points": [
            ("Центр", "Centrum", 51.922, 4.479),
            ("Коп-ван-Зёйд", "Kop van Zuid", 51.906, 4.488),
            ("Кралинген", "Kralingen", 51.925, 4.510),
            ("Делфсхафен", "Delfshaven", 51.909, 4.445),
            ("Схидам", "Schiedam", 51.917, 4.400),
            ("Оверсхи", "Overschie", 51.940, 4.430),
            ("Фейеноорд", "Feijenoord", 51.894, 4.500),
            ("Ахой", "Ahoy", 51.884, 4.488),
            ("Барендрехт", "Barendrecht", 51.856, 4.535),
            ("Капелле", "Capelle", 51.930, 4.580),
        ],
        "pads": [1, 6],
        "nofly": [("Аэропорт Роттердам", "Rotterdam The Hague Airport", 51.957, 4.437, 4000)],
    },
}


def tiles():
    out = {}
    for f in os.listdir(DEM):
        if f.endswith(".tif"):
            p = f.split("_")  # Copernicus_DSM_COG_10_N43_00_E076_00_DEM.tif
            lat = int(p[4][1:]) * (1 if p[4][0] == "N" else -1); lon = int(p[6][1:]) * (1 if p[6][0] == "E" else -1)
            out[(lat, lon)] = os.path.join(DEM, f)
    return out


TILES = tiles(); CACHE = {}


def elev(lat, lon):
    k = (math.floor(lat), math.floor(lon))
    if k not in CACHE:
        CACHE[k] = np.array(Image.open(TILES[k]), dtype=np.float64)
    a = CACHE[k]; rows, cols = a.shape
    r = (k[0] + 1 - lat) * rows; c = (lon - k[1]) * cols
    r0 = min(max(int(r), 0), rows - 2); c0 = min(max(int(c), 0), cols - 2); fr = r - r0; fc = c - c0
    return float(a[r0, c0] * (1 - fr) * (1 - fc) + a[r0, c0 + 1] * (1 - fr) * fc + a[r0 + 1, c0] * fr * (1 - fc) + a[r0 + 1, c0 + 1] * fr * fc)


for key, c in CITIES.items():
    lat0, lon0 = c["depot"][2], c["depot"][3]
    kx = 111320.0 * math.cos(math.radians(lat0)); ky = 110540.0
    xy = lambda la, lo: (round((lo - lon0) * kx, 1), round((la - lat0) * ky, 1))
    pts = []
    for i, p in enumerate(c["points"]):
        x, y = xy(p[2], p[3])
        pts.append({"id": i, "ru": p[0], "en": p[1], "lat": p[2], "lon": p[3], "x": x, "y": y, "z": round(elev(p[2], p[3]), 1), "pad": i in c["pads"]})
    dz = round(elev(lat0, lon0), 1)
    xs = [0.0] + [p["x"] for p in pts]; ys = [0.0] + [p["y"] for p in pts]
    x0 = math.floor((min(xs) - 2000) / STEP) * STEP; x1 = math.ceil((max(xs) + 2000) / STEP) * STEP
    y0 = math.floor((min(ys) - 2000) / STEP) * STEP; y1 = math.ceil((max(ys) + 2000) / STEP) * STEP
    nx = int((x1 - x0) / STEP) + 1; ny = int((y1 - y0) / STEP) + 1
    grid = []
    for j in range(ny):
        for i in range(nx):
            x = x0 + i * STEP; y = y0 + j * STEP
            grid.append(round(elev(lat0 + y / ky, lon0 + x / kx)))
    nofly = []
    for n in c["nofly"]:
        x, y = xy(n[2], n[3]); nofly.append({"ru": n[0], "en": n[1], "x": x, "y": y, "r": n[4]})
    out = {"city": key, "_tag": "точки: П (выбраны по карте), высоты: И (Copernicus DEM GLO-30), радиусы запретных зон: О",
           "depot": {"ru": c["depot"][0], "en": c["depot"][1], "lat": lat0, "lon": lon0, "x": 0.0, "y": 0.0, "z": dz},
           "points": pts, "nofly": nofly, "terrain": {"x0": x0, "y0": y0, "step": STEP, "nx": nx, "ny": ny, "z": grid}}
    json.dump(out, open(os.path.join(H, "world", key + "_map.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    far = max(math.hypot(p["x"], p["y"]) for p in pts)
    print(key, "склад", dz, "м; точек", len(pts), "дальняя", round(far / 1000, 1), "км; высоты", min(p["z"] for p in pts), "–", max(p["z"] for p in pts),
          "; сетка", nx, "×", ny)
