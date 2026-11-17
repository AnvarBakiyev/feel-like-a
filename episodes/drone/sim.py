"""Симулятор эпизода «Почувствуй себя курьером дронов» (договор CONTRACT.md в корне репозитория).

Смена 2 часа, шаг 1 с, парк из 3 грузовых октокоптеров (цифры DJI FlyCart 30, без бренда), заказы приходят в течение смены.
Мир по зерну: город и настоящий день из world/<город>.json (ERA5), ошибка прогноза, порывы, заказы. Скрыто: настоящий ветер
впереди по времени и порывы; игрок видит прогноз по часам и ветер там, где сейчас дроны.

В шаге только + − × / и sqrt, всё с pow, log, exp, sin, cos считается при постройке мира (страница берёт миры готовыми).
"""
import json, math, os

H = os.path.dirname(os.path.abspath(__file__))
DT = 1.0
SHIFT_S = 7200
END_S = 9000            # после конца смены дроны ещё возвращаются; дольше 2,5 часа мир не идёт
CITIES = ("almaty", "dubai", "rotterdam")
ALTS = (30, 60, 100, 120)
SPEEDS = {"eco": 12.0, "fast": 18.0}

D = {  # дрон: цифры DJI FlyCart 30 (И) и пересчёт из них (П), остальное оценка (О)
    "empty_kg": 65.0,           # И: с двумя батареями DB2000
    "mtow_kg": 95.0,            # И
    "payload_max": 40.0,        # И: груз в кейсе 0–40 кг
    "battery_wh": 3968.8,       # И: 2 × 1 984,4 Вт·ч
    "hover_c": 8211.0 / (65.0 ** 1.25),  # П: висение пустым 29 мин → 8,2 кВт; P ~ m^1,25 (с 30 кг 18 мин → 13,2 кВт, сходится)
    "wind_max": 12.0,           # И: предел ветра
    "wind_abort": 15.0,         # О: выше этого автопилот сажает дрон
    "climb_ms": 3.0, "climb_k": 1.15, "descend_k": 0.9,  # О
    "service_s": 40.0,          # О: груз опускают тросом с висения
    "swap_depot_s": 90.0, "swap_pad_s": 120.0,  # О: замена батарей
    "reserve": 0.08,            # О: ниже 8 % автопилот садится там, где он есть
    "pmax_w": 16000.0, "pmax_hot_c": 40.0, "pmax_46_w": 12000.0,  # О: выше +40 °C батарея ограничивает мощность, предел DJI +45 °C
}
CRUISE_A, CRUISE_B = -0.32, 0.32  # О: P(V)/P_висения = 1 − 0,32·u + 0,32·u², u = V/15 м/с (на 15 м/с как висение: DJI 16 км за 18 мин с 30 кг)
SC = {"base": 1000, "delivered": 40, "late_per_s": 0.1, "undelivered": 60, "forced": 250, "lost": 600, "pad": 10,
      "energy_per_pct": 2, "energy_min": -200, "energy_max": 100}


def rej(field, code, ru, en):
    return {"field": field, "code": code, "ru": ru, "en": en}


def fnv(s):
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h


class Rng:  # mulberry32, как у кофейни и машиниста
    def __init__(self, seed):
        self.a = seed & 0xFFFFFFFF

    def u(self):
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0


def clock(t):
    t = int(t + 0.5)
    return "%02d:%02d:%02d" % (13 + t // 3600, (t // 60) % 60, t % 60)


def load(city):
    w = json.load(open(os.path.join(H, "world", city + ".json"), encoding="utf-8"))
    m = json.load(open(os.path.join(H, "world", city + "_map.json"), encoding="utf-8"))
    return w, m


# ---------- мир по зерну: всё с тригонометрией и степенями здесь ----------
def make_world(seed, city):
    W, M = load(city)
    day = W["days"][(seed - 1) % len(W["days"])]
    R = lambda label: Rng(fnv(str(seed) + ":" + city + ":" + label))
    zc = M["depot"]["z"]
    hours = []      # часы 12..16, смена с 13:00 (индекс 1)
    re = R("forecast")
    for k in range(len(day["hours"])):
        w10, w100 = day["wind_speed_10m"][k], day["wind_speed_100m"][k]
        d10, d100 = day["wind_direction_10m"][k], day["wind_direction_100m"][k]
        t2 = day["temperature_2m"][k]
        truth, fc = {}, {}
        es, ed = 1.0 + 0.36 * (re.u() - 0.5), 36.0 * (re.u() - 0.5)  # О: ошибка прогноза ±18 % по силе, ±18° по направлению
        for a in ALTS:
            s = w10 + (w100 - w10) * math.log(a / 10.0) / math.log(10.0)  # логарифмический профиль между 10 и 100 м
            s = max(0.0, s)
            dr = d10 if a < 60 else d100
            # направление «откуда дует» → вектор «куда»: x на восток, y на север
            truth[a] = [-s * math.sin(math.radians(dr)), -s * math.cos(math.radians(dr))]
            sf, df = s * es, dr + ed
            fc[a] = [-sf * math.sin(math.radians(df)), -sf * math.cos(math.radians(df))]
        # плотность по высоте над уровнем моря: множитель мощности sqrt(ρ0/ρ) через каждые 100 м от 0 до 3 000 м
        dens = []
        for z in range(0, 3100, 100):
            T = t2 + 273.15 - 0.0065 * (z - zc)
            p = 101325.0 * (1 - 2.25577e-5 * z) ** 5.25588
            rho = p / (287.05 * T)
            dens.append(math.sqrt(1.225 / rho))
        cap = 1.0 if t2 >= 15 else (0.85 + 0.15 * t2 / 15.0 if t2 >= 0 else (0.85 + 0.015 * t2 if t2 >= -20 else 0.55))  # О: −15 % при 0 °C, −30 % при −10 °C
        pmax = D["pmax_w"] if t2 <= D["pmax_hot_c"] else max(D["pmax_46_w"], D["pmax_w"] - (t2 - D["pmax_hot_c"]) * (D["pmax_w"] - D["pmax_46_w"]) / 6.0)
        gust_k = max(0.0, day["wind_gusts_10m"][k] / max(0.5, w10) - 1.0)
        hours.append({"truth": truth, "fc": fc, "t": t2, "t_fc": round(t2 + 2.0 * (re.u() - 0.5), 1), "dens": dens, "cap": cap, "pmax": pmax, "gust_k": gust_k})
    # порывы: на каждые 10 с множитель силы ветра 1 + k·r², r случайно (скрыто)
    rg = R("gust"); gust = []
    for i in range(END_S // 10 + 1):
        hk = hours[min(len(hours) - 1, 1 + i * 10 // 3600)]["gust_k"]
        r = rg.u(); gust.append(1.0 + 0.6 * hk * r * r)
    # заказы
    ro = R("orders"); pts = M["points"]; orders = []
    n = 12 + int(ro.u() * 5)
    for i in range(n):
        t = int(ro.u() * 5400)
        p = pts[int(ro.u() * len(pts))]
        kg = round(2 + 28 * ro.u() * ro.u(), 1)
        orders.append({"t": t, "point": p["id"], "kg": kg, "due": t + 1500 + int(ro.u() * 1500)})
    orders.sort(key=lambda o: (o["t"], o["point"]))
    for i, o in enumerate(orders):
        o["id"] = i
    return {"seed": seed, "city": city, "day": day["day"], "hours": hours, "gust": gust, "orders": orders,
            "map": {"depot": M["depot"], "points": pts, "nofly": M["nofly"], "terrain": M["terrain"]}}


def seg_circle(ax, ay, bx, by, cx, cy, r):
    """Проходит ли отрезок AB через круг (центр C, радиус r)."""
    dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else ((cx - ax) * dx + (cy - ay) * dy) / L2
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    px, py = ax + t * dx - cx, ay + t * dy - cy
    return px * px + py * py < r * r


class Game:
    def __init__(self, seed, city, world=None):
        self.city = city
        self.W = world if world is not None else make_world(seed, city)
        self.M = self.W["map"]; self.pts = {p["id"]: p for p in self.M["points"]}
        self.t = 0.0
        self.drones = [{"id": i, "mode": "dock", "x": 0.0, "y": 0.0, "agl": 0.0, "soc": 1.0, "load": [], "route": [], "wp": 0,
                        "phase": "", "alt": 60, "va": 12.0, "busy": 0.0, "gs": 0.0, "wh": 0.0, "pads": 0} for i in range(3)]
        self.orders = [dict(o, status="wait", drone=None, at=None) for o in self.W["orders"]]
        self.counts = {"delivered": 0, "late_s": 0.0, "forced": 0, "lost": 0, "pads": 0, "wh": 0.0, "ref_wh": 0.0}
        self.journal = []; self.events = []

    # ---------- окружение ----------
    def hour(self):
        return self.W["hours"][min(len(self.W["hours"]) - 1, 1 + int(self.t) // 3600)]

    def ground(self, x, y):
        T = self.M["terrain"]; fx = (x - T["x0"]) / T["step"]; fy = (y - T["y0"]) / T["step"]
        i = int(fx); j = int(fy)
        i = 0 if i < 0 else (T["nx"] - 2 if i > T["nx"] - 2 else i); j = 0 if j < 0 else (T["ny"] - 2 if j > T["ny"] - 2 else j)
        ax, ay = fx - i, fy - j; ax = 0.0 if ax < 0 else (1.0 if ax > 1 else ax); ay = 0.0 if ay < 0 else (1.0 if ay > 1 else ay)
        z = T["z"]; n = T["nx"]
        return (z[j * n + i] * (1 - ax) * (1 - ay) + z[j * n + i + 1] * ax * (1 - ay) + z[(j + 1) * n + i] * (1 - ax) * ay + z[(j + 1) * n + i + 1] * ax * ay)

    def wind(self, alt, truth=True):
        """Ветер на высоте полёта сейчас: линейно между часами, с порывом (скрыто). Вектор «куда», м/с."""
        hs = self.W["hours"]; f = self.t / 3600.0 + 1.0; i = int(f); i = len(hs) - 2 if i > len(hs) - 2 else i; a = f - i
        key = "truth" if truth else "fc"
        u = hs[i][key][alt][0] * (1 - a) + hs[i + 1][key][alt][0] * a; v = hs[i][key][alt][1] * (1 - a) + hs[i + 1][key][alt][1] * a
        if truth:
            g = self.W["gust"][int(self.t) // 10]; u *= g; v *= g
        return u, v

    def dens(self, z):
        d = self.hour()["dens"]; f = z / 100.0; i = int(f); i = 0 if i < 0 else (len(d) - 2 if i > len(d) - 2 else i); a = f - i
        a = 0.0 if a < 0 else (1.0 if a > 1 else a)
        return d[i] * (1 - a) + d[i + 1] * a

    def mass(self, dr):
        return D["empty_kg"] + sum(self.orders[o]["kg"] for o in dr["load"])

    def p_hover(self, m, z):
        return D["hover_c"] * m * math.sqrt(math.sqrt(m)) * self.dens(z)

    def target(self, tok):
        if tok == "depot":
            return self.M["depot"]
        if tok[0] == "o":
            return self.pts[self.orders[int(tok[1:])]["point"]]
        return self.pts[int(tok[1:])]

    # ---------- Проверка игры ----------
    def check(self, dec):
        out = []
        i = dec.get("drone")
        if not isinstance(i, int) or i < 0 or i > 2:
            return [rej("drone", "unknown", "Дронов три: 0, 1 и 2.", "There are three drones: 0, 1 and 2.")]
        dr = self.drones[i]
        if dec.get("recall"):
            if dr["mode"] != "air":
                out.append(rej("recall", "not_air", "Дрон %d не в воздухе." % i, "Drone %d is not in the air." % i))
            return out
        route = dec.get("route")
        if dr["mode"] != "dock":
            return [rej("drone", "busy", "Дрон %d сейчас не на складе." % i, "Drone %d is not at the depot." % i)]
        if dr["busy"] > 0:
            return [rej("drone", "swap", "Дрон %d меняет батарею, ещё %d с." % (i, int(dr["busy"] + 0.999)), "Drone %d is swapping its battery, %d s more." % (i, int(dr["busy"] + 0.999)))]
        if not isinstance(route, list) or not route or len(route) > 5:
            return [rej("route", "len", "Маршрут: от 1 до 5 остановок.", "A route has 1 to 5 stops.")]
        if dec.get("alt", 60) not in ALTS:
            out.append(rej("alt", "alt", "Высота полёта: 30, 60, 100 или 120 м.", "Altitude: 30, 60, 100 or 120 m."))
        if dec.get("speed", "eco") not in SPEEDS:
            out.append(rej("speed", "speed", "Скорость: эконом или быстро.", "Speed: eco or fast."))
        kg = 0.0; seen = set(); pts = [self.M["depot"]]
        for tok in route:
            if not isinstance(tok, str) or len(tok) < 2 or tok[0] not in "op" or not tok[1:].isdigit():
                out.append(rej("route", "token", "Остановка «%s» не заказ (o…) и не площадка (p…)." % tok, "Stop '%s' is neither an order (o…) nor a pad (p…)." % tok)); continue
            n = int(tok[1:])
            if tok[0] == "o":
                if n >= len(self.orders) or self.orders[n]["t"] > self.t:
                    out.append(rej("route", "no_order", "Заказа %d ещё нет." % n, "Order %d does not exist yet." % n)); continue
                o = self.orders[n]
                if o["status"] != "wait" or n in seen:
                    out.append(rej("route", "taken", "Заказ %d уже доставлен или в пути." % n, "Order %d is already delivered or on its way." % n)); continue
                seen.add(n); kg += o["kg"]
            else:
                if n not in self.pts or not self.pts[n]["pad"]:
                    out.append(rej("route", "no_pad", "Точка %d не площадка зарядки." % n, "Point %d is not a charging pad." % n)); continue
            pts.append(self.target(tok))
        if out:
            return out
        if kg > D["payload_max"] or D["empty_kg"] + kg > D["mtow_kg"]:
            out.append(rej("route", "mass", "Груз %.1f кг: дрон берёт не больше 40 кг, взлётная масса до 95 кг." % kg, "Load %.1f kg: the drone takes at most 40 kg, take-off mass up to 95 kg." % kg))
        pts.append(self.M["depot"])
        for a, b in zip(pts, pts[1:]):
            for nf in self.M["nofly"]:
                if seg_circle(a["x"], a["y"], b["x"], b["y"], nf["x"], nf["y"], nf["r"]):
                    out.append(rej("route", "nofly", "Плечо %s → %s проходит через зону «%s»." % (a["ru"], b["ru"], nf["ru"]), "Leg %s → %s crosses the zone '%s'." % (a["en"], b["en"], nf["en"])))
        u, v = self.wind(30)
        w = math.sqrt(u * u + v * v)
        if w > D["wind_max"]:
            out.append(rej("drone", "wind", "Ветер у склада %.1f м/с, предел дрона 12 м/с." % w, "Wind at the depot %.1f m/s, the drone's limit is 12 m/s." % w))
        p = self.p_hover(D["empty_kg"] + kg, self.M["depot"]["z"]); hr = self.hour()
        if p > hr["pmax"]:
            out.append(rej("route", "heat", "При %.0f °C батарея даёт %.1f кВт, а висение с грузом %.1f кг требует %.1f кВт." % (hr["t"], hr["pmax"] / 1000, kg, p / 1000),
                           "At %.0f °C the battery gives %.1f kW, hovering with %.1f kg needs %.1f kW." % (hr["t"], hr["pmax"] / 1000, kg, p / 1000)))
        return out

    def decide(self, dec):
        r = self.check(dec)
        if r:
            return r
        dr = self.drones[dec["drone"]]
        if dec.get("recall"):
            dr["route"] = dr["route"][:dr["wp"]] + ["depot"]
            if dr["phase"] == "service":
                dr["phase"] = "climb"
            return []
        dr.update(mode="air", route=list(dec["route"]) + ["depot"], wp=0, phase="climb", alt=dec.get("alt", 60), va=SPEEDS[dec.get("speed", "eco")], busy=0.0)
        dr["load"] = [int(t[1:]) for t in dec["route"] if t[0] == "o"]
        for o in dr["load"]:
            self.orders[o].update(status="air", drone=dr["id"])
        self.events.append([self.t, "takeoff", dr["id"]])
        return []

    # ---------- шаг ----------
    def step(self):
        hr = self.hour()
        for dr in self.drones:
            if dr["mode"] == "dock" or dr["mode"] == "pad":
                if dr["busy"] > 0:
                    dr["busy"] -= DT
                    if dr["busy"] <= 0:
                        dr["busy"] = 0.0; dr["soc"] = 1.0
                        if dr["mode"] == "pad":
                            dr["mode"] = "air"; dr["phase"] = "climb"; dr["wp"] += 1
                continue
            if dr["mode"] != "air":
                continue
            m = self.mass(dr); zg = self.ground(dr["x"], dr["y"]); ph = self.p_hover(m, zg + dr["agl"])
            u, v = self.wind(dr["alt"])
            w = math.sqrt(u * u + v * v)
            P = ph
            if dr["phase"] == "climb":
                P = ph * D["climb_k"]; dr["agl"] += D["climb_ms"] * DT
                if dr["agl"] >= dr["alt"]:
                    dr["agl"] = float(dr["alt"]); dr["phase"] = "cruise"
            elif dr["phase"] == "cruise":
                tg = self.target(dr["route"][dr["wp"]]); dx, dy = tg["x"] - dr["x"], tg["y"] - dr["y"]
                dist = math.sqrt(dx * dx + dy * dy)
                ex, ey = (dx / dist, dy / dist) if dist > 0 else (0.0, 0.0)
                wa = u * ex + v * ey; wc = -u * ey + v * ex; va = dr["va"]
                gs = (math.sqrt(va * va - wc * wc) + wa) if wc * wc < va * va else wa
                gs = 0.0 if gs < 0 else gs
                dr["gs"] = gs
                uu = va / 15.0
                P = ph * (1 + CRUISE_A * uu + CRUISE_B * uu * uu)
                step = gs * DT
                if step >= dist:
                    dr["x"], dr["y"] = tg["x"], tg["y"]; dr["phase"] = "descend"
                else:
                    dr["x"] += ex * step; dr["y"] += ey * step
            elif dr["phase"] == "descend":
                P = ph * D["descend_k"]; dr["gs"] = 0.0
                tok = dr["route"][dr["wp"]]; low = 0.0 if tok == "depot" or tok[0] == "p" else 20.0  # заказ опускают тросом с 20 м
                dr["agl"] -= D["climb_ms"] * DT
                if dr["agl"] <= low:
                    dr["agl"] = low
                    if tok == "depot":
                        dr.update(mode="dock", phase="", busy=D["swap_depot_s"], route=[], wp=0)
                        for o in dr["load"]:
                            self.orders[o].update(status="wait", drone=None)  # недоставленное возвращается в очередь
                        dr["load"] = []
                        self.events.append([self.t, "dock", dr["id"]])
                    elif tok[0] == "p":
                        dr.update(mode="pad", busy=D["swap_pad_s"]); self.counts["pads"] += 1; dr["pads"] += 1
                        self.events.append([self.t, "pad", dr["id"], int(tok[1:])])
                    else:
                        dr["phase"] = "service"; dr["busy"] = D["service_s"]
            elif dr["phase"] == "service":
                dr["busy"] -= DT
                if dr["busy"] <= 0:
                    o = int(dr["route"][dr["wp"]][1:]); dr["busy"] = 0.0
                    if o in dr["load"]:
                        dr["load"].remove(o); od = self.orders[o]
                        od.update(status="done", at=self.t + DT)
                        self.counts["delivered"] += 1
                        late = self.t + DT - od["due"]; self.counts["late_s"] += late if late > 0 else 0.0
                        self.events.append([self.t, "deliver", dr["id"], o])
                    dr["wp"] += 1; dr["phase"] = "climb"
            if dr["mode"] != "air":
                continue
            # батарея: ёмкость меньше на морозе, мощность ограничена в жару
            used = P * DT / 3600.0
            dr["wh"] += used; self.counts["wh"] += used
            dr["soc"] -= used / (D["battery_wh"] * hr["cap"])
            if dr["soc"] <= 0:
                self._down(dr, "lost"); continue
            if P > hr["pmax"] or w > D["wind_abort"] or (dr["soc"] < D["reserve"] and dr["phase"] != "descend"):
                self._forced(dr)
        self.t += DT
        if int(self.t) % 10 == 0:
            self._log()

    def _forced(self, dr):
        """Автопилот сажает дрон там, где он есть: у точки, на площадке или на складе это не вынужденная посадка."""
        here = None
        for p in [self.M["depot"]] + self.M["points"]:
            dx, dy = p["x"] - dr["x"], p["y"] - dr["y"]
            if dx * dx + dy * dy < 50 * 50:
                here = p
        if here is self.M["depot"]:
            dr["route"] = dr["route"][:dr["wp"]] + ["depot"]; dr["phase"] = "descend"; return
        if here is not None and here.get("pad"):  # над площадкой: садится на неё и меняет батарею
            if dr["route"][dr["wp"]] != "p%d" % here["id"]:
                dr["route"].insert(dr["wp"], "p%d" % here["id"])
            dr["phase"] = "descend"; return
        self._down(dr, "forced")

    def _down(self, dr, kind):
        dr["mode"] = kind; dr["phase"] = ""; dr["gs"] = 0.0
        self.counts[kind] += 1
        for o in dr["load"]:
            self.orders[o].update(status="lost" if kind == "lost" else "stuck")
        self.events.append([self.t, kind, dr["id"], round(dr["x"]), round(dr["y"])])

    def _log(self):
        self.journal.append({"t": self.t, "d": [[round(d["x"]), round(d["y"]), round(d["agl"]), round(d["soc"] * 1000) / 10, d["mode"], len(d["load"])] for d in self.drones]})

    def done(self):
        if self.t >= END_S:
            return True
        return self.t >= SHIFT_S and all(d["mode"] != "air" and d["mode"] != "pad" for d in self.drones)

    # ---------- что видит игрок ----------
    def observe(self):
        hr = self.hour(); out_d = []
        for d in self.drones:
            u, v = self.wind(d["alt"]) if d["mode"] == "air" else (None, None)
            out_d.append({"id": d["id"], "mode": d["mode"], "phase": d["phase"], "x": d["x"], "y": d["y"], "agl": d["agl"], "soc": d["soc"],
                          "load": list(d["load"]), "load_kg": round(self.mass(d) - D["empty_kg"], 1), "route": d["route"][d["wp"]:], "gs": d["gs"],
                          "busy": d["busy"], "wind_here": None if u is None else [round(u, 2), round(v, 2)]})
        u, v = self.wind(30)
        return {"t": self.t, "clock": clock(self.t), "city": self.city, "drones": out_d,
                "orders": [{"id": o["id"], "point": o["point"], "kg": o["kg"], "due": o["due"], "status": o["status"]} for o in self.orders if o["t"] <= self.t],
                "depot_wind": [round(u, 2), round(v, 2)], "temp_now": hr["t"], "cap_now": hr["cap"], "pmax_now": hr["pmax"],
                "forecast": [{"hour": 12 + k, "t": h["t_fc"], "wind": {a: h["fc"][a] for a in ALTS}} for k, h in enumerate(self.W["hours"])],
                "map": {"depot": self.M["depot"], "points": self.M["points"], "nofly": self.M["nofly"]}}

    # ---------- счёт ----------
    def ref_wh(self, o):
        """Эталон энергии заказа: туда и обратно по прямой в штиль, эконом, 60 м, с грузом туда и пустым обратно."""
        p = self.pts[o["point"]]; d = math.sqrt(p["x"] * p["x"] + p["y"] * p["y"])
        c = 1 + CRUISE_A * 0.8 + CRUISE_B * 0.64
        hl = D["hover_c"] * (D["empty_kg"] + o["kg"]) * math.sqrt(math.sqrt(D["empty_kg"] + o["kg"])); he = D["hover_c"] * D["empty_kg"] * math.sqrt(math.sqrt(D["empty_kg"]))
        return (hl + he) * c * d / 12.0 / 3600.0

    def score(self):
        parts = {}; c = self.counts
        undelivered = sum(1 for o in self.orders if o["status"] != "done")
        ref = sum(self.ref_wh(o) for o in self.orders if o["status"] == "done")
        parts["delivered"] = SC["delivered"] * c["delivered"]
        parts["late"] = -SC["late_per_s"] * c["late_s"]
        parts["undelivered"] = -SC["undelivered"] * undelivered
        parts["forced"] = -SC["forced"] * c["forced"]
        parts["lost"] = -SC["lost"] * c["lost"]
        parts["pads"] = -SC["pad"] * c["pads"]
        e = 0.0
        if ref > 0:
            e = -SC["energy_per_pct"] * (100.0 * c["wh"] / ref - 100.0)
            e = SC["energy_min"] if e < SC["energy_min"] else (SC["energy_max"] if e > SC["energy_max"] else e)
        parts["energy"] = e
        sc = 0.0
        for k in ("delivered", "late", "undelivered", "forced", "lost", "pads", "energy"):
            sc += parts[k]
        sc = SC["base"] + sc
        return {"score": round(sc, 1), "raw": sc, "parts": {k: round(v, 1) for k, v in parts.items()},
                "counts": {"delivered": c["delivered"], "orders": len(self.orders), "late_s": round(c["late_s"]), "forced": c["forced"], "lost": c["lost"],
                           "pads": c["pads"], "kwh": round(c["wh"] / 1000, 2), "ref_kwh": round(ref / 1000, 2)}}


def replay(seed, settings, decisions):
    """Пересчёт смены по журналу решений [[шаг, решение], ...] для таблицы рекордов."""
    city = settings.get("city")
    if city not in CITIES:
        raise ValueError("неизвестный город: %r" % city)
    clean = sorted([(int(s), d) for s, d in decisions], key=lambda x: x[0])
    g = Game(int(seed), city); i = 0; n = 0
    while not g.done():
        while i < len(clean) and clean[i][0] <= n:
            g.decide(clean[i][1]); i += 1
        g.step(); n += 1
    sc = g.score()
    return {"score": sc["score"], "parts": sc["parts"], "counts": sc["counts"], "steps": n}
