def train_plan(text, seed, line_id, mode="check"):
    """Эпизод «машинист»: Проверка плана на языке поездки (mode=check) или рейс по плану в мире зерна (mode=run)."""
    if mode == "check":
        ok, errs, fc, plan = check(text, Game(seed, line_id))
        return {"ok": ok, "errors": errs, "forecast": fc}
    g = run(text, seed, line_id)
    return {"score": g.score(), "journal": g.journal, "decisions": g.decisions, "world": g.W}


import json, math, re

DATA = json.loads('{"lines": {"ch_gotthard": {"id": "ch_gotthard", "name": {"ru": "Швейцария: горная Готардская линия, Эрстфельд – Биаска", "en": "Switzerland: Gotthard mountain line, Erstfeld – Biasca"}, "_sources": "км и высоты станций, тоннель 15 003 м, уклоны до 26–28 ‰, мин. радиус 300 м: de.wikipedia Gotthardbahn (П); скорости О (не нашли)", "km_offset": 41.58, "protection": "О (не нашли)", "segments": [{"from_km": 41.58, "to_km": 46.55, "grade_permille": 14.5, "limit_kmh": 100, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 46.55, "to_km": 54.4, "grade_permille": 24.7, "limit_kmh": 80, "radius_m": 300, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 54.4, "to_km": 58.42, "grade_permille": 23.9, "limit_kmh": 80, "radius_m": 300, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 58.42, "to_km": 62.76, "grade_permille": 21.7, "limit_kmh": 80, "radius_m": 300, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 62.76, "to_km": 70.45, "grade_permille": 23.1, "limit_kmh": 80, "radius_m": 300, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 70.45, "to_km": 78.72, "grade_permille": 5.4, "limit_kmh": 125, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 78.72, "to_km": 86.2, "grade_permille": -1.2, "limit_kmh": 125, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 86.2, "to_km": 93.04, "grade_permille": -22.4, "limit_kmh": 80, "radius_m": 300, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 93.04, "to_km": 97.84, "grade_permille": -9.8, "limit_kmh": 100, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 97.84, "to_km": 106.0, "grade_permille": -22.9, "limit_kmh": 80, "radius_m": 300, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 106.0, "to_km": 112.6, "grade_permille": -21.2, "limit_kmh": 80, "radius_m": 300, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 112.6, "to_km": 121.12, "grade_permille": -22.9, "limit_kmh": 80, "radius_m": 300, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 121.12, "to_km": 125.5, "grade_permille": -20.3, "limit_kmh": 80, "radius_m": 300, "_tag": "уклон: из высот станций (П), скорость О"}, {"from_km": 125.5, "to_km": 131.8, "grade_permille": -6.0, "limit_kmh": 100, "_tag": "уклон: из высот станций (П), скорость О"}], "stations": [{"name": "Erstfeld", "km": 41.58}, {"name": "Göschenen", "km": 70.45, "dwell_s": 0, "pass": true}, {"name": "Biasca", "km": 131.8}], "timetable": [{"name": "Erstfeld", "arr_s": null, "dep_s": 0}, {"name": "Biasca", "arr_s": 5490.0, "dep_s": null, "tech_run_s": 5175.5}], "_timetable": "техническое время машиниста full на сухом рельсе × 1.06, вверх до 30 с (О)", "signal_sight_km": 2.5, "_signal": "видимость цели в кабине: LZB и ATC показывают цель за 10 км и больше (О); на горной линии сигнал за 2,5 км (О)", "ref_kwh": 2018.9, "_ref_kwh": "эталон энергии: тот же прогон машиниста full; в счёте ±4 очка за каждый процент к нему (О)"}, "de_koeln_frankfurt": {"id": "de_krm", "name": {"ru": "Германия: Кёльн – аэропорт Франкфурта", "en": "Germany: Cologne – Frankfurt Airport"}, "_sources": "станции, км, 300 км/ч, 40 ‰, ограничения 200 и 160: de.wikipedia Schnellfahrstrecke Köln–Rhein/Main (П); расстановка уклонов по км: О", "protection": "LZB", "segments": [{"from_km": 0, "to_km": 24.3, "grade_permille": 0, "limit_kmh": 200, "_tag": "скорость П (Porz–Siegburg 200), уклон О"}, {"from_km": 24.3, "to_km": 28, "grade_permille": 0, "limit_kmh": 300, "_tag": "О"}, {"from_km": 28, "to_km": 33, "grade_permille": 40, "limit_kmh": 300, "_tag": "О"}, {"from_km": 33, "to_km": 36, "grade_permille": 10, "limit_kmh": 300, "_tag": "О"}, {"from_km": 36, "to_km": 40, "grade_permille": -30, "limit_kmh": 300, "_tag": "О"}, {"from_km": 40, "to_km": 46, "grade_permille": 35, "limit_kmh": 300, "_tag": "О"}, {"from_km": 46, "to_km": 52, "grade_permille": 0, "limit_kmh": 300, "_tag": "О"}, {"from_km": 52, "to_km": 60, "grade_permille": -25, "limit_kmh": 300, "_tag": "О"}, {"from_km": 60, "to_km": 70, "grade_permille": 20, "limit_kmh": 300, "_tag": "О"}, {"from_km": 70, "to_km": 80, "grade_permille": -10, "limit_kmh": 300, "_tag": "О"}, {"from_km": 80, "to_km": 89.1, "grade_permille": 15, "limit_kmh": 300, "_tag": "О"}, {"from_km": 89.1, "to_km": 98, "grade_permille": -35, "limit_kmh": 300, "_tag": "О"}, {"from_km": 98, "to_km": 110.5, "grade_permille": -10, "limit_kmh": 300, "_tag": "О"}, {"from_km": 110.5, "to_km": 122, "grade_permille": 20, "limit_kmh": 300, "_tag": "О"}, {"from_km": 122, "to_km": 130, "grade_permille": 40, "limit_kmh": 300, "_tag": "О"}, {"from_km": 130, "to_km": 140, "grade_permille": -20, "limit_kmh": 300, "_tag": "О"}, {"from_km": 140, "to_km": 152.5, "grade_permille": -30, "limit_kmh": 300, "_tag": "О"}, {"from_km": 152.5, "to_km": 158, "grade_permille": -5, "limit_kmh": 160, "_tag": "скорость П (Breckenheim до 160), уклон О"}, {"from_km": 158, "to_km": 163, "grade_permille": 0, "limit_kmh": 160, "_tag": "скорость П (кривая у км 160), уклон О", "radius_m": 3348}, {"from_km": 163, "to_km": 170.5, "grade_permille": 0, "limit_kmh": 200, "_tag": "О"}], "stations": [{"name": "Köln Messe/Deutz", "km": 0}, {"name": "Siegburg/Bonn", "km": 24.3, "dwell_s": 60}, {"name": "Montabaur", "km": 89.1, "dwell_s": 60}, {"name": "Frankfurt Flughafen", "km": 169.3}], "check": {"ru": "Кёльн Hbf → аэропорт по расписанию 49 мин (П), с Кёльн Hbf на ~2 км дальше", "what": "nonstop"}, "timetable": [{"name": "Köln Messe/Deutz", "arr_s": null, "dep_s": 0}, {"name": "Siegburg/Bonn", "arr_s": 600.0, "dep_s": 660.0, "tech_run_s": 553.5}, {"name": "Montabaur", "arr_s": 1800.0, "dep_s": 1860.0, "tech_run_s": 1072.0}, {"name": "Frankfurt Flughafen", "arr_s": 3330.0, "dep_s": null, "tech_run_s": 1370.0}], "_timetable": "техническое время машиниста full на сухом рельсе × 1.06, вверх до 30 с (О)", "signal_sight_km": 10.0, "_signal": "видимость цели в кабине: LZB и ATC показывают цель за 10 км и больше (О); на горной линии сигнал за 2,5 км (О)", "ref_kwh": 3293.8, "_ref_kwh": "эталон энергии: тот же прогон машиниста full; в счёте ±4 очка за каждый процент к нему (О)"}, "jp_tokaido": {"id": "jp_tokaido", "name": {"ru": "Япония: Токайдо-синкансэн, Токио – Нагоя", "en": "Japan: Tokaido Shinkansen, Tokyo – Nagoya"}, "_sources": "км станций, 20 ‰ макс., ATC-NS: en.wikipedia Tokaido Shinkansen (П); 285 км/ч и средняя задержка 1,4 мин: годовой отчёт JR Central 2025 (И); ограничения кроме 285 и места уклонов: О", "protection": "ATC-NS", "segments": [{"from_km": 0, "to_km": 6.8, "grade_permille": 0, "limit_kmh": 110, "_tag": "О"}, {"from_km": 6.8, "to_km": 25.5, "grade_permille": 0, "limit_kmh": 160, "_tag": "О"}, {"from_km": 25.5, "to_km": 40, "grade_permille": 5, "limit_kmh": 255, "_tag": "О"}, {"from_km": 40, "to_km": 76.7, "grade_permille": 0, "limit_kmh": 285, "_tag": "285 И, уклон О"}, {"from_km": 76.7, "to_km": 95.4, "grade_permille": 15, "limit_kmh": 255, "_tag": "кривые R 2500 255 км/ч П, место О"}, {"from_km": 95.4, "to_km": 111.3, "grade_permille": -10, "limit_kmh": 270, "_tag": "О"}, {"from_km": 111.3, "to_km": 167.4, "grade_permille": 0, "limit_kmh": 285, "_tag": "285 И"}, {"from_km": 167.4, "to_km": 211.3, "grade_permille": 10, "limit_kmh": 270, "_tag": "О"}, {"from_km": 211.3, "to_km": 330, "grade_permille": 0, "limit_kmh": 285, "_tag": "285 И"}, {"from_km": 330, "to_km": 342, "grade_permille": 0, "limit_kmh": 170, "_tag": "О"}], "stations": [{"name": "Tokyo", "km": 0}, {"name": "Shinagawa", "km": 6.8, "dwell_s": 60}, {"name": "Shin-Yokohama", "km": 25.5, "dwell_s": 60}, {"name": "Nagoya", "km": 342.0}], "check": {"ru": "Токио → Нагоя самый быстрый 1:35 (П), с остановками Синагава и Син-Йокогама"}, "timetable": [{"name": "Tokyo", "arr_s": null, "dep_s": 0}, {"name": "Shinagawa", "arr_s": 300.0, "dep_s": 360.0, "tech_run_s": 276.5}, {"name": "Shin-Yokohama", "arr_s": 900.0, "dep_s": 960.0, "tech_run_s": 499.5}, {"name": "Nagoya", "arr_s": 5640.0, "dep_s": null, "tech_run_s": 4390.0}], "_timetable": "техническое время машиниста full на сухом рельсе × 1.06, вверх до 30 с (О)", "signal_sight_km": 10.0, "_signal": "видимость цели в кабине: LZB и ATC показывают цель за 10 км и больше (О); на горной линии сигнал за 2,5 км (О)", "ref_kwh": 12040.6, "_ref_kwh": "эталон энергии: тот же прогон машиниста full; в счёте ±4 очка за каждый процент к нему (О)"}}, "trains": {"ice3": {"id": "ice3", "name": "ICE 3 (BR 403)", "mass_t": 470, "_mass": "435 т порожний (bahn.de, И) + пассажиры О", "length_m": 200, "power_kW": 8000, "start_tractive_kN": 300, "powered_share": 0.5, "davis": [3.48, 0.0471, 0.000582], "_davis": "О: формула Peters для ICE 1 (Wende 2003, по диссертации TU Wien 2023) при 6 промежуточных вагонах", "brake": {"service_ms2": 0.6, "emergency_ms2": 1.0, "_tag": "О: не нашли"}, "regen_eff": 0.75, "_regen": "0,70–0,85 Fischer 2026 (И)", "adhesion": {"dry": 0.25, "_tag": "Curtius-Kniffler около 0,18–0,33 (И, учебный); среднее О"}, "vmax_kmh": 300}, "n700s": {"id": "n700s", "name": "N700S", "mass_t": 715, "_mass": "N700 около 715 т (П); у N700S не нашли", "length_m": 404.7, "power_kW": 17080, "_power": "56 × 305 кВт (О, расчёт)", "start_tractive_kN": 545, "_start": "О: из ускорения 2,6 км/ч/с (П)", "powered_share": 0.875, "davis": [4.9, 0.068, 0.000998], "_davis": "О: та же формула при 14 промежуточных вагонах", "brake": {"service_ms2": 0.7, "emergency_ms2": 1.1, "_tag": "О"}, "regen_eff": 0.75, "adhesion": {"dry": 0.25}, "vmax_kmh": 285}, "re66_freight": {"id": "re66_freight", "name": "Re 6/6 + 900 т", "mass_t": 1020, "_mass": "локомотив 120 т (П) + состав 900 т (О, ниже нормы 1300 т на 26 ‰, П)", "length_m": 520, "power_kW": 7237, "start_tractive_kN": 395, "powered_share": 0.1176, "resistance": "strahl", "_res": "улучшенная формула Strahl для грузовых (Wende 2003, по диссертации TU Wien, И вторичный)", "brake": {"service_ms2": 0.45, "emergency_ms2": 0.7, "_tag": "О"}, "regen_eff": 0.75, "adhesion": {"dry": 0.33}, "vmax_kmh": 100, "pusher": {"name": "Re 6/6 толкачом", "mass_t": 120, "power_kW": 7237, "start_tractive_kN": 395, "_tag": "данные Re 6/6 (П); толкач на всю поездку и цена 100 очков (О)"}}}}')


G = 9.81
DT = 0.5
LINES = {"de_krm": "de_koeln_frankfurt", "ch_gotthard": "ch_gotthard", "jp_tokaido": "jp_tokaido"}
TRAIN_OF = {"de_krm": "ice3", "ch_gotthard": "re66_freight", "jp_tokaido": "n700s"}

P = {  # параметры игры, метка О
    "sched_margin": 1.06,          # запас в расписании к техническому времени
    "late_free_s": 30,             # опоздание без штрафа
    "atp_service_over_kmh": 5,     # превышение, при котором защита тормозит
    "atp_emergency_over_kmh": 15,  # превышение, при котором защита даёт экстренный
    "atp_decel_share": 0.8,        # доля служебного замедления в кривой защиты
    "stop_window_m": 50,           # остановка засчитана в пределах ±50 м
    "sand_k": 1.25, "sand_s": 600, # песок: сцепление ×1,25, запас 600 с
    "slip_k": 0.85,                # при боксовании противобоксовочная защита держит 85 % сцепления
    "slide_k": 0.7,                # при юзе тормоз даёт 70 % сцепления
    "weather": {"dry": 1.0, "wet": 0.75, "leaves": 0.55},
    "weather_w": {"dry": 0.5, "wet": 0.35, "leaves": 0.15},
    "pusher_cost": 100,
    "score": {"base": 1000, "late_per_s": 2, "energy_per_pct": 4, "stop_per_m": 5, "stop_free_m": 2, "atp": 150, "emergency": 400,
              "missed_stop": 500, "harsh_per_s": 1, "harsh_ms2": 1.0},
}


def rej(field, code, ru, en):
    return {"field": field, "code": code, "ru": ru, "en": en}


def fnv(s):
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h


class Rng:  # mulberry32, как в кофейне
    def __init__(self, seed):
        self.a = seed & 0xFFFFFFFF

    def u(self):
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0


def load(kind, name):
    return json.loads(json.dumps(DATA[kind][name]))


def clock(t):
    t = int(t + 0.5)
    return "%02d:%02d:%02d" % (10 + t // 3600, (t // 60) % 60, t % 60)


# ---------- мир по зерну ----------
def make_world(seed, L):
    R = lambda label: Rng(fnv(str(seed) + ":" + L["id"] + ":" + label))
    r = R("weather"); u = r.u(); acc = 0.0; weather = "leaves"
    for k in ("dry", "wet", "leaves"):
        acc += P["weather_w"][k]
        if u < acc:
            weather = k; break
    adh = P["weather"][weather] * (0.95 + 0.1 * R("adh").u())  # настоящее сцепление: скрыто
    km0 = L["stations"][0]["km"]; km1 = L["stations"][-1]["km"]; span = km1 - km0
    temp = []
    rt = R("temp")
    if rt.u() < 0.6:
        segs = [s for s in L["segments"] if s["limit_kmh"] > 80 and s["to_km"] - s["from_km"] > 3]
        s = segs[int(rt.u() * len(segs))]
        a = s["from_km"] + (s["to_km"] - s["from_km"] - 2.0) * rt.u()
        temp.append({"from_km": round(a, 2), "to_km": round(a + 2.0, 2), "limit_kmh": max(40, int(s["limit_kmh"] * 0.5 / 10) * 10), "reason": "track_work"})
    rd = R("delay")
    delay = [0, 0, 60, 180][int(rd.u() * 4)]
    rs = R("signal")
    signal = None
    if rs.u() < 0.4:
        k = km0 + span * (0.3 + 0.4 * rs.u())
        signal = {"km": round(k, 2), "limit_kmh": 80 if L["id"] != "ch_gotthard" else 40, "length_km": 3.0,
                  "sight_km": L.get("signal_sight_km", 6.0)}
    return {"seed": seed, "weather": weather, "adhesion_factor": adh, "temp": temp, "depart_delay_s": delay, "signal": signal}


class Game:
    def __init__(self, seed, line_id, train_id=None, timetable=True, world=None):
        self.line_id = line_id
        self.L = load("lines", LINES[line_id]); self.T = dict(load("trains", train_id or TRAIN_OF[line_id]))
        self.W = world if world is not None else make_world(seed, self.L)
        self.seg = sorted(self.L["segments"], key=lambda s: s["from_km"])
        self.stations = [s for s in self.L["stations"] if not s.get("pass")]
        self.tt = self.L.get("timetable") if timetable else None  # [{name, arr_s, dep_s}] от 10:00:00
        self.t = 0.0; self.x = 1000.0 * self.stations[0]["km"]; self.v = 0.0; self.a = 0.0
        self.lever = 0.0; self.sand_on = False; self.sand_left = P["sand_s"]; self.pusher = False
        self.departed = False; self.stop_idx = 1; self.at_station = True; self.dwell_until = None
        self.atp = None; self.emerg = False; self.sig_seen = False
        self.E_in = 0.0; self.E_back = 0.0; self.harsh_s = 0.0
        self.counts = {"atp": 0, "emergency": 0, "missed_stops": 0, "slip_s": 0.0, "slide_s": 0.0}
        self.stops = []; self.journal = []; self.decisions = []; self.slip = False; self.slide = False
        self.dep_time = (self.tt[0]["dep_s"] if self.tt else 0) + self.W["depart_delay_s"]

    # --- профиль ---
    def at(self, x):
        km = x / 1000.0
        for s in self.seg:
            if s["from_km"] <= km < s["to_km"]:
                return s
        return self.seg[-1]

    def zones(self):
        """Ограничения, которые знает машинист: постоянные, временные (лист предупреждений), сигнал (если виден)."""
        z = [(1000.0 * s["from_km"], 1000.0 * s["to_km"], s["limit_kmh"]) for s in self.seg]
        z += [(1000.0 * t["from_km"], 1000.0 * t["to_km"], t["limit_kmh"]) for t in self.W["temp"]]
        sg = self.W["signal"]
        if sg and self.signal_visible():
            z.append((1000.0 * sg["km"], 1000.0 * (sg["km"] + sg["length_km"]), sg["limit_kmh"]))
        return z

    def signal_visible(self):
        """Цель сигнала видна за sight_km или раньше, если для торможения по кривой нужно больше (защита смотрит дальше, О)."""
        sg = self.W["signal"]
        if not sg:
            return False
        if self.sig_seen:
            return True
        dist = 1000.0 * sg["km"] - self.x
        vt = sg["limit_kmh"] / 3.6
        need = (self.v * self.v - vt * vt) / (2 * self.brake_curve_decel(1000.0 * sg["km"])) * 1.3 + 500.0
        if dist <= 1000.0 * sg["sight_km"] or dist <= need:
            self.sig_seen = True
        return self.sig_seen

    def limit_now(self):
        lo = self.x - self.T["length_m"]; v = 1e9
        for a, b, lim in self.zones():
            if b > lo and a <= self.x:
                v = min(v, lim)
        return v / 3.6

    def brake_curve_decel(self, to_x=None):
        """Замедление кривой защиты с поправкой на худший уклон до цели (как в ETCS: уклон входит в кривую)."""
        to_x = self.x if to_x is None else to_x
        gmin = self.at(self.x)["grade_permille"]
        for s in self.seg:
            if 1000.0 * s["to_km"] > self.x and 1000.0 * s["from_km"] < to_x and s["grade_permille"] < gmin:
                gmin = s["grade_permille"]
        d = self.T["brake"]["service_ms2"] * P["atp_decel_share"] + G * gmin / 1000.0
        return d if d > 0.1 else 0.1

    def permitted(self):
        lim = self.limit_now()
        for a, b, lk in self.zones():
            if a > self.x and a - self.x < 25000:
                vt = lk / 3.6
                lim = min(lim, math.sqrt(vt * vt + 2 * self.brake_curve_decel(a) * (a - self.x)))
        st = self.next_stop()
        if st is not None and not self.at_station:
            sx = 1000.0 * st["km"]
            dist = sx - self.x + P["stop_window_m"]
            lim = min(lim, math.sqrt(2 * self.brake_curve_decel(sx) * max(0.0, dist)) + 0.5)
        return lim

    def next_stop(self):
        return self.stations[self.stop_idx] if self.stop_idx < len(self.stations) else None

    def due(self):
        """Время, раньше которого нельзя трогаться со станции."""
        return self.dep_time if not self.departed else (self.dwell_until or 0.0)

    # --- силы ---
    def mass(self):
        return self.T["mass_t"] + (self.T["pusher"]["mass_t"] if self.pusher else 0)

    def mu(self, v):
        k = self.W["adhesion_factor"] * (P["sand_k"] if self.sand_on else 1.0)
        return (7.5 / (v * 3.6 + 44.0) + 0.161) * k

    def adh_force(self, v):
        pw = self.T["mass_t"] * self.T["powered_share"] + (self.T["pusher"]["mass_t"] if self.pusher else 0)
        return self.mu(v) * pw * 1000.0 * G

    def tractive_max(self, v):
        T = self.T; f0 = T["start_tractive_kN"] * 1000.0; p = T["power_kW"] * 1000.0
        if self.pusher:
            f0 += T["pusher"]["start_tractive_kN"] * 1000.0; p += T["pusher"]["power_kW"] * 1000.0
        return f0 if v < 1e-6 else min(f0, p / v)

    def resist(self, v):
        vk = v * 3.6; m = self.mass()
        if self.T.get("resistance") == "strahl":
            r = G * m * (2.2 + 80.0 / (vk + 38.0) + 0.00032 * vk * vk)
        else:
            A, B, C = self.T["davis"]
            r = (A + B * vk + C * vk * vk) * 1000.0
        s = self.at(self.x)
        grade = m * 1000.0 * G * s["grade_permille"] / 1000.0
        R = s.get("radius_m")
        curve = 0.0
        if R:
            curve = m * G * (650.0 / (R - 55.0) if R > 300 else 500.0 / (R - 30.0))
        return r + curve, grade

    # --- наблюдение: то, что видит машинист в кабине ---
    def observe(self):
        st = self.next_stop()
        ahead = []
        for a, b, lk in sorted(self.zones()):
            if b > self.x and a - self.x < 30000:
                ahead.append({"from_km": round(a / 1000, 3), "to_km": round(b / 1000, 3), "limit_kmh": lk})
        tt = self.tt[self.stop_idx] if (self.tt and st is not None) else None
        return {"t": self.t, "clock": clock(self.t), "km": round(self.x / 1000.0, 4), "v_kmh": round(self.v * 3.6, 2), "a_ms2": round(self.a, 3),
                "lever": self.lever, "limit_kmh": round(self.limit_now() * 3.6, 1), "permitted_kmh": round(self.permitted() * 3.6, 1),
                "grade_permille": self.at(self.x)["grade_permille"], "ahead": ahead[:10],
                "next_stop": None if st is None else {"name": st["name"], "km": st["km"], "dist_m": round(1000.0 * st["km"] - self.x, 1),
                                                      "arr_s": tt and tt["arr_s"], "arr_clock": tt and clock(tt["arr_s"])},
                "departed": self.departed, "due_s": self.due(), "due_clock": clock(self.due()), "at_station": self.at_station,
                "weather": self.W["weather"], "warnings": self.W["temp"], "depart_delay_s": self.W["depart_delay_s"],
                "signal": (self.W["signal"] if self.signal_visible() else None),
                "slip": self.slip, "slide": self.slide, "sand_on": self.sand_on, "sand_left_s": self.sand_left, "pusher": self.pusher,
                "pusher_available": "pusher" in self.T, "atp": self.atp, "emergency": self.emerg,
                "energy_kwh": round((self.E_in - self.E_back) / 3.6e6, 2), "stops": list(self.stops), "line": self.line_id}

    # --- Проверка ---
    def check(self, dec):
        out = []; ok = {}
        if "pusher" in dec:
            if self.departed:
                out.append(rej("pusher", "late", "Толкач ставят только до отправления.", "A banking engine is only added before departure."))
            elif "pusher" not in self.T:
                out.append(rej("pusher", "none", "На этом участке толкача нет.", "No banking engine on this line."))
            else:
                ok["pusher"] = bool(dec["pusher"])
        if "lever" in dec:
            lv = dec["lever"]
            if not isinstance(lv, (int, float)) or isinstance(lv, bool) or lv < -1 or lv > 1:
                out.append(rej("lever", "range", "Рычаг от −1 (тормоз) до 1 (тяга).", "Lever goes from −1 (brake) to 1 (power)."))
            elif lv > 0 and self.at_station and self.t < self.due():
                out.append(rej("lever", "early", "Отправление в %s, сейчас %s: раньше графика нельзя." % (clock(self.due()), clock(self.t)),
                               "Departure is at %s, it is %s: you cannot leave early." % (clock(self.due()), clock(self.t))))
            else:
                ok["lever"] = float(lv)
        if "sand" in dec:
            if dec["sand"] and self.sand_left <= 0:
                out.append(rej("sand", "empty", "Песок кончился.", "Out of sand."))
            else:
                ok["sand"] = bool(dec["sand"])
        if dec.get("emergency"):
            ok["emergency"] = True
        return out, ok

    def decide(self, dec):
        out, ok = self.check(dec)
        if "pusher" in ok:
            self.pusher = ok["pusher"]
        if "lever" in ok:
            self.lever = ok["lever"]
        if "sand" in ok:
            self.sand_on = ok["sand"]
        if ok.get("emergency") and not self.emerg:
            self.emerg = True; self.counts["emergency"] += 1
        if out or set(dec) - {"lever"}:
            self.decisions.append({"t": self.t, "dec": dec, "rej": out})
        return out

    # --- шаг 0,5 с ---
    def step(self):
        S = P
        if self.at_station and self.v < 0.01 and (self.lever <= 0 or self.t < self.due()):
            self.t += DT
            self._log()
            return
        if self.at_station and self.lever > 0:
            self.at_station = False; self.departed = True
        lever = self.lever
        perm = self.permitted(); over = (self.v - perm) * 3.6
        if over > S["atp_emergency_over_kmh"] and not self.emerg:
            self.emerg = True; self.counts["emergency"] += 1
        elif not self.emerg and (self.atp or over > S["atp_service_over_kmh"]):
            if not self.atp:
                self.atp = "service"; self.counts["atp"] += 1
            if over < -2:
                self.atp = None
            else:
                lever = -1.0
        m = self.mass() * 1000.0 * self.T.get("rot_mass", 1.06)
        r, grade = self.resist(self.v)
        self.slip = False; self.slide = False
        if self.sand_on:
            self.sand_left = max(0.0, self.sand_left - DT)
            if self.sand_left <= 0:
                self.sand_on = False
        if self.emerg:
            dec = min(self.T["brake"]["emergency_ms2"], self.mu(self.v) * G)
            acc = (-r - grade) / m - dec
        elif lever > 0:
            f = lever * self.tractive_max(self.v); adh = self.adh_force(self.v)
            if f > adh:
                self.slip = True; self.counts["slip_s"] += DT; f = adh * S["slip_k"]
            acc = (f - r - grade) / m
            self.E_in += f * self.v * DT / self.T.get("eff_traction", 0.85)
        else:
            dem = -lever * self.T["brake"]["service_ms2"]
            lim = self.mu(self.v) * G
            dec = dem
            if dem > lim:
                self.slide = True; self.counts["slide_s"] += DT; dec = lim * S["slide_k"]
            acc = (-r - grade) / m - dec
            if dec > 0:
                p = dec * m * self.v
                if p > self.T["power_kW"] * 1000.0:
                    p = self.T["power_kW"] * 1000.0
                self.E_back += p * DT * self.T.get("regen_eff", 0.0)
        if self.v <= 0.0 and acc < 0 and lever <= 0:
            acc = 0.0  # стоит на тормозе
        if abs(acc) > S["score"]["harsh_ms2"]:
            self.harsh_s += DT
        self.a = acc
        v_new = self.v + acc * DT
        if v_new < 0:
            v_new = 0.0
        self.x += (self.v + v_new) / 2.0 * DT
        self.v = v_new; self.t += DT
        if self.emerg and self.v < 0.01:
            self.emerg = False; self.atp = None; self.lever = 0.0
        st = self.next_stop()
        if st is not None:
            d = self.x - 1000.0 * st["km"]
            if self.v < 0.01 and abs(d) <= S["stop_window_m"]:
                tt = self.tt[self.stop_idx] if self.tt else None
                self.stops.append({"name": st["name"], "t": round(self.t, 1), "err_m": round(d, 2),
                                   "late_s": None if tt is None else round(self.t - tt["arr_s"], 1)})
                self.at_station = True; self.lever = 0.0
                dep = tt["dep_s"] if (tt and tt.get("dep_s") is not None) else self.t + st.get("dwell_s", 0)
                self.dwell_until = max(self.t + st.get("dwell_s", 0), dep)
                self.stop_idx += 1
            elif d > S["stop_window_m"]:
                self.counts["missed_stops"] += 1
                self.stops.append({"name": st["name"], "t": round(self.t, 1), "err_m": round(d, 2), "late_s": None, "missed": True})
                self.stop_idx += 1
        self._log()

    def _log(self):
        if int(self.t * 2 + 0.5) % 20 == 0:  # каждые 10 с
            self.journal.append({"t": self.t, "km": round(self.x / 1000.0, 4), "v": round(self.v * 3.6, 2), "a": round(self.a, 3), "lever": self.lever,
                                 "perm": round(self.permitted() * 3.6, 1), "lim": round(self.limit_now() * 3.6, 1), "atp": self.atp, "emerg": self.emerg,
                                 "slip": self.slip, "slide": self.slide, "sand": self.sand_on, "e": round((self.E_in - self.E_back) / 3.6e6, 2)})

    def done(self):
        return self.stop_idx >= len(self.stations) or self.t > 4 * 3600

    def score(self):
        Sc = P["score"]; parts = {}
        late = 0.0; stop_err = 0.0
        for s in self.stops:
            if s.get("missed"):
                continue
            if s["late_s"] is not None:
                late += max(0.0, s["late_s"] - P["late_free_s"])
            stop_err += max(0.0, abs(s["err_m"]) - Sc["stop_free_m"])
        unfinished = 0 if self.stop_idx >= len(self.stations) else 1
        kwh = (self.E_in - self.E_back) / 3.6e6
        parts["late"] = -Sc["late_per_s"] * late
        ref = self.L.get("ref_kwh")
        parts["energy"] = -Sc["energy_per_pct"] * (100.0 * kwh / ref - 100.0) if ref else 0.0  # ± за каждый процент к эталону участка
        parts["stop_precision"] = -Sc["stop_per_m"] * stop_err
        parts["protection"] = -Sc["atp"] * self.counts["atp"] - Sc["emergency"] * self.counts["emergency"]
        parts["missed_stops"] = -Sc["missed_stop"] * self.counts["missed_stops"]
        parts["comfort"] = -Sc["harsh_per_s"] * self.harsh_s
        parts["pusher"] = -P["pusher_cost"] if self.pusher else 0
        parts["unfinished"] = -1000 * unfinished
        sc = Sc["base"] + sum(parts.values())
        return {"score": round(sc, 1), "parts": {k: round(v, 1) for k, v in parts.items()}, "kwh": round(kwh, 1),
                "time_min": round(self.t / 60.0, 2), "stops": self.stops, "counts": dict(self.counts)}


def play(seed, line_id, driver, pre=None, **kw):
    g = Game(seed, line_id, **kw)
    if pre:
        g.decide(pre)
    while not g.done():
        d = driver(g.observe(), g)
        if d:
            g.decide(d)
        g.step()
    return g


LANG_VERSION = 2

KW = [
    (r"^(толкач|banker) (да|нет|yes|no)$", "pusher"),
    (r"^(разгон до|accelerate to) ([0-9]+)$", "accel"),
    (r"^(тише|slower) ([0-9]+) (с км|from km) ([0-9]+(?:[.,][0-9]+)?) (до км|to km) ([0-9]+(?:[.,][0-9]+)?)$", "slower"),
    (r"^(держать|hold) .*$", "old_hold"),
    (r"^(выбег с км|coast from km) ([0-9]+(?:[.,][0-9]+)?) (до км|to km) ([0-9]+(?:[.,][0-9]+)?)$", "coast"),
    (r"^(песок с км|sand from km) ([0-9]+(?:[.,][0-9]+)?) (до км|to km) ([0-9]+(?:[.,][0-9]+)?)$", "sand"),
    (r"^(по графику|to schedule)$", "schedule"),
]


def _f(s):
    return float(s.replace(",", "."))


def parse(text):
    """-> (план, ошибки). Ошибка: {line, ru, en}."""
    plan = {"pusher": False, "accel": None, "holds": [], "coasts": [], "sands": [], "schedule": False}
    errs = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip().lower()
        line = " ".join(line.split())
        if not line:
            continue
        for pat, kind in KW:
            m = re.match(pat, line)
            if m:
                break
        else:
            errs.append({"line": i, "ru": "строка %d: «%s» не команда языка поездки." % (i, raw.strip()), "en": "line %d: '%s' is not a command." % (i, raw.strip())})
            continue
        if kind == "pusher":
            plan["pusher"] = m.group(2) in ("да", "yes")
        elif kind == "accel":
            if plan["accel"]:
                errs.append({"line": i, "ru": "строка %d: «разгон до» пишется один раз (уже в строке %d). Чтобы ехать тише на отрезке, напиши «тише V с км A до км B»." % (i, plan["accel"][1]),
                             "en": "line %d: 'accelerate to' is written once (already on line %d). To go slower on a stretch, write 'slower V from km A to km B'." % (i, plan["accel"][1])})
                continue
            plan["accel"] = (int(m.group(2)), i)
        elif kind == "slower":
            plan["holds"].append((int(m.group(2)), _f(m.group(4)), _f(m.group(6)), i))
        elif kind == "old_hold":
            errs.append({"line": i, "ru": "строка %d: команды «держать» нет. Ограничения скорости и ремонт обработчик соблюдает сам; чтобы ехать тише допустимой, напиши «тише V с км A до км B»." % i,
                         "en": "line %d: there is no 'hold'. The handler keeps speed limits and track work itself; to go slower, write 'slower V from km A to km B'." % i})
        elif kind == "coast":
            plan["coasts"].append((_f(m.group(2)), _f(m.group(4)), i))
        elif kind == "sand":
            plan["sands"].append((_f(m.group(2)), _f(m.group(4)), i))
        elif kind == "schedule":
            plan["schedule"] = True
    return plan, errs


def sense(plan, g):
    """Здравый смысл плана без симуляции."""
    errs = []
    km0 = g.stations[0]["km"]; km1 = g.stations[-1]["km"]; vmax = g.T["vmax_kmh"]
    if plan["accel"] and plan["accel"][0] > vmax:
        errs.append(_e(plan["accel"][1], "разгон до %d км/ч: предельная скорость %s %d км/ч." % (plan["accel"][0], g.T["name"], vmax),
                       "accelerate to %d km/h: %s tops out at %d km/h." % (plan["accel"][0], g.T["name"], vmax)))
    for kind, zs in (("тише", [(a, b, i) for v, a, b, i in plan["holds"]]), ("выбег", plan["coasts"]), ("песок", plan["sands"])):
        for a, b, i in zs:
            if b <= a:
                errs.append(_e(i, "%s: конец км %s не дальше начала км %s." % (kind, _k(b), _k(a)), "%s: end km %s is not after start km %s." % (kind, _k(b), _k(a))))
            elif a < km0 or b > km1:
                errs.append(_e(i, "%s: км %s–%s вне участка (%s–%s)." % (kind, _k(a), _k(b), _k(km0), _k(km1)), "%s: km %s-%s is outside the line." % (kind, _k(a), _k(b))))
    if plan["pusher"] and "pusher" not in g.T:
        errs.append(_e(0, "толкача на этом участке нет.", "no banking engine on this line."))
    return errs


def _e(i, ru, en):
    return {"line": i, "ru": ("строка %d: " % i if i else "") + ru, "en": ("line %d: " % i if i else "") + en}


def _k(x):
    return ("%.1f" % x).replace(".", ",")


def speed_profile(plan, km0, km1):
    """Свои пределы скорости плана: «разгон до V» на весь рейс и отрезки «тише». -> [(от км, до км, V, строка)]."""
    out = []
    if plan["accel"]:
        out.append((km0, km1, plan["accel"][0], plan["accel"][1]))
    for v, a, b, i in plan["holds"]:
        if b > a:
            out.append((a, b, v, i))
    return out


class Driver:
    """Исполнение плана: целевая скорость по км, выбег и песок по зонам, торможение к станциям, отступ при боксовании."""

    def __init__(self, plan, km0=0.0, km1=1e9):
        self.p = plan; self.cap = 1.0; self.prof = speed_profile(plan, km0, km1)

    def target(self, km, o, g):
        v = o["limit_kmh"]
        for a, b, sv, _ in self.prof:
            if a <= km < b:
                v = min(v, sv)
        return min(v, o["permitted_kmh"] - 3, o["limit_kmh"] - 1)

    def __call__(self, o, g):
        self.cap = self.cap * 0.97 if o["slip"] else min(1.0, self.cap + 0.005)
        km = o["km"]
        d = {}
        if not o["departed"] and self.p["pusher"] and not o["pusher"] and o["pusher_available"]:
            d["pusher"] = True
        want_sand = any(a <= km <= b for a, b, _ in self.p["sands"]) and o["sand_left_s"] > 0
        if want_sand != o["sand_on"]:
            d["sand"] = want_sand
        if o["at_station"]:
            d["lever"] = self.cap if o["t"] >= o["due_s"] else 0.0
            return d
        v = o["v_kmh"]; tgt = self.target(km, o, g)
        lever = max(-1.0, min(self.cap, (tgt - v) / 4.0))
        coast = any(a <= km <= b for a, b, _ in self.p["coasts"])
        st = o["next_stop"]
        if self.p["schedule"] and st and st["arr_s"] is not None and v > 20 and lever >= 0:
            left = st["arr_s"] - o["t"]
            if left > 0 and st["dist_m"] / (v / 3.6) < 0.93 * left and o["grade_permille"] <= 5:
                coast = True
        if coast and lever >= 0 and v > 0.4 * o["limit_kmh"]:
            lever = 0.0
        d["lever"] = _stop(o, g, lever)
        return d


def _stop(o, g, lever):
    st = o["next_stop"]
    if st is None:
        return lever
    sv = g.T["brake"]["service_ms2"]; gr = G * o["grade_permille"] / 1000.0
    v = o["v_kmh"] / 3.6; dist = st["dist_m"]
    if dist > 0:
        need = v * v / (2 * dist)
        if need > 0.8 * sv + gr:
            lever = -min(1.0, (need - gr) / sv)
        if dist < 2 and v < 2:
            lever = -1.0
    else:
        lever = -1.0
    if v < 0.3 and dist > 2:
        lever = 0.6 if dist > 400 else 0.35
    return lever


EXPECT = {"dry": 1.0, "wet": 0.75, "leaves": 0.55}


def expected_world(g):
    """То, что машинист знает до отправления: погода (сцепление по прогнозу без разброса), лист предупреждений, задержка. Без сигнала."""
    W = g.W
    return {"seed": W["seed"], "weather": W["weather"], "adhesion_factor": EXPECT[W["weather"]], "temp": W["temp"], "depart_delay_s": W["depart_delay_s"], "signal": None}


def simulate(plan, g0):
    g = Game(g0.W["seed"], g0.line_id, world=expected_world(g0))
    drv = Driver(plan, g.stations[0]["km"], g.stations[-1]["km"])
    stall_km = None; slow_t = 0.0
    while not g.done():
        d = drv(g.observe(), g)
        if d:
            g.decide(d)
        g.step()
        if g.departed and not g.at_station and g.v < 0.5:
            slow_t += DT
            if slow_t > 120 and stall_km is None:
                stall_km = g.x / 1000.0
                break
        else:
            slow_t = 0.0
    return g, stall_km


def check(text, g0):
    """Полная Проверка плана до отправления: -> (ok, отказы, прогноз)."""
    plan, errs = parse(text)
    if errs:
        return False, errs, None, plan
    errs = sense(plan, g0)
    if errs:
        return False, errs, None, plan
    g, stall = simulate(plan, g0)
    sc = g.score()
    fc = {"stops": sc["stops"], "kwh": sc["kwh"], "energy_pct": round(100.0 * sc["kwh"] / g.L["ref_kwh"], 1), "atp": g.counts["atp"], "score": sc["score"]}
    if stall is not None:
        line = next((i for a, b, i in plan["sands"] if a <= stall <= b), 0)
        g1 = Game(g0.W["seed"], g0.line_id, world=expected_world(g0))
        gr = g1.at(stall * 1000.0)["grade_permille"]
        errs.append(_e(line, "поезд встанет на км %s (подъём %s ‰, %s): нужен песок или толкач." % (_k(stall), _k(gr), {"dry": "сухой рельс", "wet": "мокрый рельс", "leaves": "листопад"}[g0.W["weather"]]),
                       "the train stalls at km %s (%s ‰ climb, %s): add sand or a banking engine." % (_k(stall), _k(gr), g0.W["weather"])))
        return False, errs, fc, plan
    # опоздание по вине плана: сравнить с тем же планом без своих скоростей и без выбега
    if plan["accel"] or plan["holds"] or plan["coasts"]:
        free = dict(plan, holds=[], accel=None, coasts=[], schedule=False)
        gf, _ = simulate(free, g0)
        worse = sc["score"] < gf.score()["score"] - 30  # опоздание отказывает, только если план в итоге хуже по счёту
        for s, sf in zip(g.stops, gf.stops):
            if worse and s.get("late_s") is not None and sf.get("late_s") is not None and s["late_s"] > 30 and s["late_s"] - sf["late_s"] > 30:
                prof = speed_profile(plan, g.stations[0]["km"], g.stations[-1]["km"])
                worst = None
                for a, b, v, i in prof:
                    lim = max(z["limit_kmh"] for z in g.L["segments"] if z["to_km"] > a and z["from_km"] < b)
                    loss = (b - a) * (1.0 / max(v, 1) - 1.0 / lim) if v < lim else 0.0
                    if loss > 0 and (worst is None or loss > worst[0]):
                        worst = (loss, a, b, v, i)
                if worst:
                    _, a, b, v, i = worst
                    errs.append(_e(i, "%d км/ч с км %s до км %s: по прогнозу %s в %s, опоздание %d с (без ограничений плана было бы %d с)." % (
                        v, _k(a), _k(b), s["name"], clock(s["t"]), s["late_s"], max(0, sf["late_s"])),
                        "%d km/h from km %s to km %s: by the forecast %s at %s, %d s late (without the plan's limits %d s)." % (
                        v, _k(a), _k(b), s["name"], clock(s["t"]), s["late_s"], max(0, sf["late_s"]))))
                    break
    if plan["coasts"] and not errs:
        base = dict(plan, coasts=[])
        gb, _ = simulate(base, g0)
        for s, sb in zip(g.stops, gb.stops):
            if sc["score"] < gb.score()["score"] - 30 and s.get("late_s") is not None and sb.get("late_s") is not None and s["late_s"] > 30 and s["late_s"] - sb["late_s"] > 20:
                a, b, i = max(plan["coasts"], key=lambda c: c[1] - c[0])
                errs.append(_e(i, "выбег с км %s до км %s: прибытие %s в %s, график %s, опоздание %d с." % (_k(a), _k(b), s["name"], clock(s["t"]), clock(s["t"] - s["late_s"]), s["late_s"]),
                               "coast from km %s to km %s: arrival at %s %s, scheduled %s, %d s late." % (_k(a), _k(b), s["name"], clock(s["t"]), clock(s["t"] - s["late_s"]), s["late_s"])))
                break
    if g.counts["atp"]:
        errs.append(_e(0, "по прогнозу защита вмешается %d раз: план слишком близко к кривой торможения." % g.counts["atp"],
                       "by the forecast the protection system intervenes %d times: the plan runs too close to the braking curve." % g.counts["atp"]))
    return (not errs), errs, fc, plan


def run(text, seed, line_id):
    """Рейс по принятому плану в настоящем мире (со скрытым): то, что потом показывает призрак."""
    g = Game(seed, line_id)
    plan, errs = parse(text)
    drv = Driver(plan, g.stations[0]["km"], g.stations[-1]["km"])
    while not g.done():
        d = drv(g.observe(), g)
        if d:
            g.decide(d)
        g.step()
    return g
