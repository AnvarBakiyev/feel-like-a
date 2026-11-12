"""Эпизод «Почувствуй себя машинистом»: симулятор рейса по договору ../EPISODE.md §2.

g = Game(seed, line_id)
до отправления: g.decide({"pusher": True}) (толкач только где есть)
каждый шаг 0,5 с: obs = g.observe(); rej = g.decide({"lever": x, "sand": bool, "emergency": bool}); g.step()
g.done(); g.score()

Детерминирован по зерну. Только стандартная библиотека, в цикле только + − × / и sqrt (перенос на JS).
Скрыто от игрока: настоящее сцепление (видна погода), поезд впереди (виден, когда сигнал в зоне видимости).
"""
import json, math, os

G = 9.81
DT = 0.5
HERE = os.path.dirname(os.path.abspath(__file__))
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
    return json.load(open(os.path.join(HERE, kind, name + ".json"), encoding="utf-8"))


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
        if unfinished and parts["energy"] > 0:
            parts["energy"] = 0.0  # недоехавший поезд не получает бонус за сэкономленную энергию
        parts["stop_precision"] = -Sc["stop_per_m"] * stop_err
        parts["protection"] = -Sc["atp"] * self.counts["atp"] - Sc["emergency"] * self.counts["emergency"]
        parts["missed_stops"] = -Sc["missed_stop"] * self.counts["missed_stops"]
        parts["comfort"] = -Sc["harsh_per_s"] * self.harsh_s
        parts["pusher"] = -P["pusher_cost"] if self.pusher else 0
        parts["unfinished"] = -1000 * unfinished
        sc = Sc["base"] + sum(parts.values())
        return {"score": round(sc, 1), "raw": sc, "parts": {k: round(v, 1) for k, v in parts.items()}, "kwh": round(kwh, 1),
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
