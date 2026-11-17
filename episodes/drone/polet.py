"""Язык полёта и его обработчик: модель пишет замысел смены, обработчик считает заряд по прогнозу и ведёт смену сам.

Строки (русский или английский, по одной команде в строке, # комментарий):
  высота 60                                  altitude 60
  скорость эконом | быстро                   speed eco | fast
  груз до 20 кг                              load up to 20 kg
  заказов за рейс 2                          orders per flight 2
  запас 20                                   reserve 20            (сколько процентов заряда должно остаться на складе)
  зарядка на площадке 6 если заряд меньше 35 pad 6 if charge below 35
  сначала срочные | близкие | тяжёлые        first urgent | near | heavy
  не лететь дальше 8 км                      no farther than 8 km
  точка 3 груз до 12 кг                      point 3 load up to 12 kg   (предел груза на одной точке)
  точку 5 пропускать                         skip point 5               (эту точку не обслуживать)

Чего в языке нет: отдельного рейса по секундам и приказа «лети, даже если не вернёшься». Кому лететь и когда,
обработчик решает сам по замыслу, и перед каждым взлётом считает круг по прогнозу ветра: рейс, который по прогнозу
не возвращается с запасом, не начинается. Правила профессии (ветер выше 12 м/с, масса, запретные зоны, мощность
батареи в жару) держит Проверка игры в sim.Game.check, и обойти её языком нельзя.

Проверка до взлёта: разбор (строка и причина), здравый смысл (высота не из списка, груз больше 40 кг),
затем прогон всей смены на прогнозе ветра этого дня и типовой ленте заказов. Отказ выдаётся только тогда,
когда план по прогнозу хуже по счёту, чем он же без этой строки, и в отказе стоит строка, причина и цифры.
Настоящие заказы приходят в течение смены, поэтому Проверка берёт типовую ленту (та же рука, что в мире:
12-16 заказов, груз 2-30 кг, точки города), а не будущее.
"""
import math
import re
import sim

LANG_VERSION = 4

DEFAULT = {"alt": 60, "speed": "eco", "load_kg": 40.0, "per_flight": 1, "reserve": 15,
           "pad": None, "pad_below": None, "first": "urgent", "max_km": None, "pt_load": {}, "skip": []}

KW = [
    (r"^(высота|altitude) ([0-9]+)$", "alt"),
    (r"^(скорость|speed) (эконом|быстро|eco|fast)$", "speed"),
    (r"^(груз до|load up to) ([0-9]+(?:[.,][0-9]+)?)( кг| kg)?$", "load"),
    (r"^(заказов за рейс|orders per flight) ([0-9]+)$", "per_flight"),
    (r"^(запас|reserve) ([0-9]+)( %|%)?$", "reserve"),
    (r"^(зарядка на площадке|pad) ([0-9]+) (если заряд меньше|if charge below) ([0-9]+)( %|%)?$", "pad"),
    (r"^(сначала|first) (срочные|близкие|тяжёлые|urgent|near|heavy)$", "first"),
    (r"^(не лететь дальше|no farther than) ([0-9]+(?:[.,][0-9]+)?)( км| km)?$", "max_km"),
    (r"^(?:точка|point) (?P<pid>[0-9]+) (?:груз до|load up to) (?P<kg>[0-9]+(?:[.,][0-9]+)?)(?: кг| kg)?$", "pt_load"),
    (r"^(?:точку (?P<pid2>[0-9]+) пропускать|skip point (?P<pid3>[0-9]+))$", "skip"),
]
FIRST = {"срочные": "urgent", "urgent": "urgent", "близкие": "near", "near": "near", "тяжёлые": "heavy", "heavy": "heavy"}
SPEED = {"эконом": "eco", "eco": "eco", "быстро": "fast", "fast": "fast"}


def _f(s):
    return float(s.replace(",", "."))


def _n(x):
    return ("%.1f" % x).replace(".", ",")


def _e(i, ru, en):
    return {"line": i, "ru": ("строка %d: " % i if i else "") + ru, "en": ("line %d: " % i if i else "") + en}


def parse(text):
    """-> (план, ошибки). Ошибка: {line, ru, en}."""
    plan = dict(DEFAULT); plan["lines"] = {}; plan["pt_load"] = {}; plan["skip"] = []
    errs = []
    for i, raw in enumerate(str(text).splitlines(), start=1):
        line = raw.split("#", 1)[0].strip().lower()
        line = " ".join(line.split())
        if not line:
            continue
        for pat, kind in KW:
            m = re.match(pat, line)
            if m:
                break
        else:
            errs.append(_e(i, "«%s» не команда языка полёта." % raw.strip(), "'%s' is not a command of the flight language." % raw.strip()))
            continue
        pid = None
        if kind in ("pt_load", "skip"):
            g = m.groupdict()
            pid = int(g.get("pid") or g.get("pid2") or g.get("pid3"))
            key = kind + ":" + str(pid)       # строка про точку пишется для каждой точки своя
        else:
            key = kind
        if key in plan["lines"]:
            errs.append(_e(i, "такая строка уже есть (строка %d): команда пишется один раз." % plan["lines"][key],
                           "this command is already on line %d: write it once." % plan["lines"][key]))
            continue
        plan["lines"][key] = i
        if kind == "alt":
            plan["alt"] = int(m.group(2))
        elif kind == "speed":
            plan["speed"] = SPEED[m.group(2)]
        elif kind == "load":
            plan["load_kg"] = _f(m.group(2))
        elif kind == "per_flight":
            plan["per_flight"] = int(m.group(2))
        elif kind == "reserve":
            plan["reserve"] = int(m.group(2))
        elif kind == "pad":
            plan["pad"] = int(m.group(2)); plan["pad_below"] = int(m.group(4))
        elif kind == "first":
            plan["first"] = FIRST[m.group(2)]
        elif kind == "max_km":
            plan["max_km"] = _f(m.group(2))
        elif kind == "pt_load":
            plan["pt_load"][pid] = _f(m.group("kg"))
        elif kind == "skip":
            plan["skip"] = sorted(set(plan["skip"] + [pid]))
    return plan, errs


def sense(plan, g):
    """Здравый смысл замысла без прогона."""
    errs = []; L = plan["lines"]
    if plan["alt"] not in sim.ALTS:
        errs.append(_e(L.get("alt", 0), "высота %d м: дрон летит на 30, 60, 100 или 120 м." % plan["alt"],
                       "altitude %d m: the drone flies at 30, 60, 100 or 120 m." % plan["alt"]))
    if plan["load_kg"] > sim.D["payload_max"]:
        errs.append(_e(L.get("load", 0), "груз до %s кг: дрон берёт не больше 40 кг." % _n(plan["load_kg"]),
                       "load up to %s kg: the drone takes at most 40 kg." % _n(plan["load_kg"])))
    if plan["load_kg"] < 2:
        errs.append(_e(L.get("load", 0), "груз до %s кг: самый легкий заказ 2 кг, с таким пределом не полетит ни один." % _n(plan["load_kg"]),
                       "load up to %s kg: the lightest order is 2 kg, nothing would fly." % _n(plan["load_kg"])))
    if plan["per_flight"] < 1 or plan["per_flight"] > 3:
        errs.append(_e(L.get("per_flight", 0), "заказов за рейс %d: за рейс берут от 1 до 3 заказов." % plan["per_flight"],
                       "orders per flight %d: a flight takes 1 to 3 orders." % plan["per_flight"]))
    if plan["reserve"] < 5 or plan["reserve"] > 60:
        errs.append(_e(L.get("reserve", 0), "запас %d %%: запас на складе от 5 до 60 процентов (ниже 8 %% дрон садится сам)." % plan["reserve"],
                       "reserve %d%%: keep 5 to 60 percent (below 8%% the autopilot lands)." % plan["reserve"]))
    if plan["pad"] is not None:
        p = g.pts.get(plan["pad"])
        if p is None or not p["pad"]:
            pads = ", ".join(str(q["id"]) for q in g.M["points"] if q["pad"])
            errs.append(_e(L.get("pad", 0), "точка %d не площадка зарядки; площадки: %s." % (plan["pad"], pads),
                           "point %d is not a charging pad; pads: %s." % (plan["pad"], pads)))
    ids = ", ".join(str(q["id"]) for q in g.M["points"])
    for pid, kg in sorted(plan["pt_load"].items()):
        i = L.get("pt_load:" + str(pid), 0)
        if pid not in g.pts:
            errs.append(_e(i, "точки %d в этом городе нет; точки: %s." % (pid, ids),
                           "there is no point %d in this city; points: %s." % (pid, ids)))
        elif kg > sim.D["payload_max"]:
            errs.append(_e(i, "точка %d груз до %s кг: дрон берёт не больше 40 кг." % (pid, _n(kg)),
                           "point %d load up to %s kg: the drone takes at most 40 kg." % (pid, _n(kg))))
        elif kg < 2:
            errs.append(_e(i, "точка %d груз до %s кг: самый легкий заказ 2 кг, на эту точку не полетит ни один." % (pid, _n(kg)),
                           "point %d load up to %s kg: the lightest order is 2 kg, nothing would fly there." % (pid, _n(kg))))
        elif pid in plan["skip"]:
            errs.append(_e(i, "точка %d и пропускается, и с пределом груза: оставь одну из двух строк." % pid,
                           "point %d is both skipped and load limited: keep one of the two lines." % pid))
    for pid in plan["skip"]:
        if pid not in g.pts:
            errs.append(_e(L.get("skip:" + str(pid), 0), "точки %d в этом городе нет; точки: %s." % (pid, ids),
                           "there is no point %d in this city; points: %s." % (pid, ids)))
    if plan["skip"] and len([q for q in g.M["points"] if q["id"] not in plan["skip"]]) == 0:
        errs.append(_e(L.get("skip:" + str(plan["skip"][-1]), 0), "пропущены все точки города: везти будет некуда.",
                       "every point of the city is skipped: there would be nowhere to fly."))
    if plan["max_km"] is not None:
        near = min(math.sqrt(p["x"] * p["x"] + p["y"] * p["y"]) for p in g.M["points"]) / 1000.0
        if plan["max_km"] < near:
            errs.append(_e(L.get("max_km", 0), "не лететь дальше %s км: ближняя точка города в %s км от склада, летать будет некуда." % (_n(plan["max_km"]), _n(near)),
                           "no farther than %s km: the nearest point is %s km from the depot, nothing would fly." % (_n(plan["max_km"]), _n(near))))
    return errs


# ---------- расчёт круга по прогнозу ----------
def fc_wind(g, t, alt):
    """Прогноз ветра на высоте alt в момент t: вектор «куда», м/с."""
    hs = g.W["hours"]; f = t / 3600.0 + 1.0
    i = int(f)
    i = 0 if i < 0 else (len(hs) - 2 if i > len(hs) - 2 else i)
    a = f - i
    a = 0.0 if a < 0 else (1.0 if a > 1 else a)
    u = hs[i]["fc"][alt][0] * (1 - a) + hs[i + 1]["fc"][alt][0] * a
    v = hs[i]["fc"][alt][1] * (1 - a) + hs[i + 1]["fc"][alt][1] * a
    return u, v


WIND_K = 1.18   # объявленная в правилах ошибка прогноза по силе ветра: обработчик считает круг по худшему краю


def ground_speed(va, u, v, ex, ey, k=1.0):
    """Путевая скорость и встречная составляющая ветра на курсе.

    k > 1: считать по худшему краю прогноза. Попутный ветер берётся слабее, встречный и боковой сильнее:
    ошибка прогноза объявлена в правилах (±18 % по силе), и дрон не должен зависеть от того, в какую сторону она легла.
    """
    wa = u * ex + v * ey; wc = -u * ey + v * ex
    wa = wa / k if wa > 0 else wa * k
    wc = wc * k
    gs = (math.sqrt(va * va - wc * wc) + wa) if wc * wc < va * va else wa
    return (0.0 if gs < 0 else gs), -wa


def flight(g, stops, kgs, alt, va, t0, soc0, cap):
    """Круг по прогнозу: склад -> stops -> склад. Фазы как в симуляторе (подъём, полёт, спуск, выгрузка).

    stops: [(точка карты, вид)], вид «order» (груз опускают тросом с 20 м) или «pad» (садится и меняет батарею);
    kgs: груз на борту на каждом плече (кг).
    -> {ok, soc, t, legs}: legs = [{from, to, dist, gs, head, wh, soc, km_left}]
    """
    pts = [(g.M["depot"], "depot")] + list(stops) + [(g.M["depot"], "depot")]
    e = sim.D["battery_wh"] * cap
    t = t0; soc = soc0; legs = []; pneed = 0.0
    for k in range(len(pts) - 1):
        (a, _), (b, kind) = pts[k], pts[k + 1]
        kg = kgs[k] if k < len(kgs) else 0.0
        m = sim.D["empty_kg"] + kg
        ph_mid = sim.D["hover_c"] * m * math.sqrt(math.sqrt(m)) * g.dens((a["z"] + b["z"]) / 2.0 + alt)
        ph_a = sim.D["hover_c"] * m * math.sqrt(math.sqrt(m)) * g.dens(a["z"] + alt / 2.0)
        low = 20.0 if kind == "order" else 0.0
        pneed = max(pneed, ph_a * sim.D["climb_k"])   # подъём стоит на 15 % больше висения: в жару упирается в батарею
        wh = ph_a * sim.D["climb_k"] * (alt / sim.D["climb_ms"]) / 3600.0          # подъём
        wh += ph_a * sim.D["descend_k"] * ((alt - low) / sim.D["climb_ms"]) / 3600.0  # спуск
        dx, dy = b["x"] - a["x"], b["y"] - a["y"]
        dist = math.sqrt(dx * dx + dy * dy)
        ex, ey = (dx / dist, dy / dist) if dist > 0 else (0.0, 0.0)
        u, v = fc_wind(g, t + alt / sim.D["climb_ms"], alt)
        gs, head = ground_speed(va, u, v, ex, ey, WIND_K)
        uu = va / 15.0
        p_cr = ph_mid * (1 + sim.CRUISE_A * uu + sim.CRUISE_B * uu * uu)
        if gs < 0.5:
            cr_s = 1e9; wh += 1e9
        else:
            cr_s = dist / gs; wh += p_cr * cr_s / 3600.0
        if low > 0:
            wh += ph_a * sim.D["service_s"] / 3600.0                                # выгрузка с висения
        soc_a = soc; soc = soc - wh / e
        km_left = 0.0
        if soc_a > 0 and wh > 0 and dist > 0 and gs >= 0.5:
            share = (soc_a - sim.D["reserve"]) * e / wh
            share = 0.0 if share < 0 else (1.0 if share > 1 else share)
            km_left = dist * share / 1000.0
        legs.append({"from": a, "to": b, "dist": dist, "gs": gs, "head": head, "wh": wh, "soc": soc, "km_left": km_left})
        t += alt / sim.D["climb_ms"] + (alt - low) / sim.D["climb_ms"] + (cr_s if cr_s < 1e8 else 0.0) + (sim.D["service_s"] if low > 0 else 0.0)
        if kind == "pad":
            soc = 1.0; t += sim.D["swap_pad_s"]
    return {"ok": soc > 0, "soc": soc, "t": t, "legs": legs, "pneed": pneed}


def fc_pmax(g, t0, t1):
    """Наименьшая мощность батареи по прогнозу на часы рейса."""
    hs = g.W["hours"]; out = None
    for k, h in enumerate(hs):
        a0 = (k - 1) * 3600.0; a1 = a0 + 3600.0
        if a1 > t0 and a0 < t1 + 1:
            out = h["pmax"] if out is None else min(out, h["pmax"])
    return out if out is not None else hs[min(len(hs) - 1, 1)]["pmax"]


def fc_wind_max(g, t0, t1, alt):
    """Наибольшая сила ветра по прогнозу на высоте полёта, по худшему краю прогноза (×1,18).

    Ступень 3 языка (14.11, по ошибке прогона ступени 2): обработчик закладывал запас только на заряд.
    В Дубае 07.05 прогноз давал 13-15 м/с в 13 часов и 9-10 в 14 часов. Проверка игры смотрит настоящий
    ветер у склада в миг взлёта; в 14 часов он оказался ниже 12 м/с, дроны ушли, а в воздухе порыв перешёл
    15 м/с, и автопилот посадил три рейса вне площадки.

    Поэтому смотрим не только часы рейса, но и всю смену: ветер ходит порывами и шквалами, и день, в который
    прогноз хоть в один час выходит за предел дрона (12 м/с, цифра DJI), диспетчер считает штормовым -
    между шквалами дрон не посылают. Такой день обработчик просто не летает.
    """
    hs = g.W["hours"]; out = 0.0
    for k, h in enumerate(hs):
        a0 = (k - 1) * 3600.0; a1 = a0 + 3600.0
        shift_hour = a1 > 0 and a0 < sim.SHIFT_S          # час попадает в смену
        if shift_hour or (a1 > t0 and a0 < t1 + 1):
            u, v = h["fc"][alt]
            sp = math.sqrt(u * u + v * v) * WIND_K
            out = sp if sp > out else out
    return out


class Dispatcher:
    """Обработчик: ведёт смену по замыслу. Каждые 5 с смотрит свободные дроны и считает круг по прогнозу."""

    def __init__(self, plan):
        self.p = plan; self.refused = {}; self.launched = 0

    @property
    def refusals(self):
        return list(self.refused.values())

    def _cands(self, g):
        out = []
        for o in g.orders:
            if o["status"] != "wait" or o["t"] > g.t:
                continue
            p = g.pts[o["point"]]
            d = math.sqrt(p["x"] * p["x"] + p["y"] * p["y"])
            if self.p["max_km"] is not None and d > 1000.0 * self.p["max_km"]:
                continue
            if o["kg"] > self.p["load_kg"]:
                continue
            if p["id"] in (self.p.get("skip") or []):
                continue
            lim = (self.p.get("pt_load") or {}).get(p["id"])
            if lim is not None and o["kg"] > lim:
                continue
            out.append((o, p, d))
        if self.p["first"] == "near":
            out.sort(key=lambda r: (r[2], r[0]["id"]))
        elif self.p["first"] == "heavy":
            out.sort(key=lambda r: (-r[0]["kg"], r[0]["id"]))
        else:
            out.sort(key=lambda r: (r[0]["due"], r[0]["id"]))
        return out

    def _try(self, g, dr, picked, cap):
        """Собрать рейс из выбранных заказов: с площадкой, если так сказано, и без неё. -> (decision, расчёт) или (None, расчёт)."""
        alt = self.p["alt"]; va = sim.SPEEDS[self.p["speed"]]
        stops = [(p, "order") for _, p, _ in picked]
        kgs = []
        total = sum(o["kg"] for o, _, _ in picked)
        left = total
        kgs.append(left)
        for o, _, _ in picked:
            left -= o["kg"]; kgs.append(left)
        f = flight(g, stops, kgs, alt, va, g.t, dr["soc"], g.hour()["cap"])
        need = self.p["reserve"] / 100.0
        route = ["o%d" % o["id"] for o, _, _ in picked]
        f["pmax"] = fc_pmax(g, g.t, f["t"])
        if f["pneed"] > f["pmax"]:        # подъём с таким грузом в такую жару батарея не даёт
            return None, f
        f["wind_fc"] = fc_wind_max(g, g.t, f["t"], alt)
        if f["wind_fc"] > sim.D["wind_max"]:   # по прогнозу ветер за пределом дрона: рейс не начинается
            return None, f
        if f["soc"] >= need:
            return {"drone": dr["id"], "route": route, "alt": alt, "speed": self.p["speed"]}, f
        pad = g.pts.get(self.p["pad"]) if self.p["pad"] is not None else None
        if pad is not None and pad["pad"] and f["soc"] < self.p["pad_below"] / 100.0:
            f2 = flight(g, stops + [(pad, "pad")], kgs + [0.0], alt, va, g.t, dr["soc"], g.hour()["cap"])
            if f2["soc"] >= need and all(l["soc"] > sim.D["reserve"] for l in f2["legs"]):
                return {"drone": dr["id"], "route": route + ["p%d" % pad["id"]], "alt": alt, "speed": self.p["speed"]}, f2
            f = f2 if f2["soc"] > f["soc"] else f
        return None, f

    def tick(self, g):
        """-> список решений на этот шаг."""
        if int(g.t) % 5:
            return []
        out = []
        for dr in g.drones:
            if dr["mode"] != "dock" or dr["busy"] > 0 or dr["route"]:
                continue
            cands = self._cands(g)
            if not cands:
                continue
            taken = set()
            for d in out:
                for tok in d["route"]:
                    if tok[0] == "o":
                        taken.add(int(tok[1:]))
            cands = [c for c in cands if c[0]["id"] not in taken]
            if not cands:
                continue
            flew = False
            for head in cands:          # заказ, который не закрывается по прогнозу, не держит остальную ленту
                group = [head]
                for _ in range(self.p["per_flight"] - 1):
                    rest = [c for c in cands if c not in group and sum(o["kg"] for o, _, _ in group) + c[0]["kg"] <= self.p["load_kg"]]
                    if not rest:
                        break
                    lp = group[-1][1]
                    rest.sort(key=lambda c: ((c[1]["x"] - lp["x"]) ** 2 + (c[1]["y"] - lp["y"]) ** 2, c[0]["id"]))
                    group.append(rest[0])
                while group:
                    dec, f = self._try(g, dr, group, g.hour()["cap"])
                    if dec is not None and not g.check(dec):
                        out.append(dec); self.launched += 1; flew = True
                        break
                    if len(group) == 1:
                        self._refuse(g, dr, group, f, dec)
                        break
                    group = group[:-1]
                if flew:
                    break
        return out

    def _refuse(self, g, dr, group, f, dec):
        """Записать, почему один заказ не взлетел: встречный ветер обратного плеча и где кончится заряд."""
        o, p, d = group[0]
        why = "charge"
        if f.get("pneed", 0.0) > f.get("pmax", 1e9):
            why = "heat"
        elif f.get("wind_fc", 0.0) > sim.D["wind_max"]:
            why = "wind_fc"
        if dec is not None:
            r = g.check(dec)
            why = r[0]["code"] if r else "charge"
        back = f["legs"][-1] if f["legs"] else None
        self.refused[o["id"]] = ({"t": g.t, "order": o["id"], "point": p["id"], "point_ru": p["ru"], "point_en": p["en"],
                              "kg": o["kg"], "km": d / 1000.0, "why": why, "soc": f["soc"],
                              "head": (back["head"] if back else 0.0), "km_left": (back["km_left"] if back else 0.0),
                              "dist_back": (back["dist"] / 1000.0 if back else 0.0)})


# ---------- мир по прогнозу ----------
def typical_orders(city, points):
    """Типовая лента заказов города: та же рука, что в мире, но не те заказы, что придут (их до смены никто не знает)."""
    ro = sim.Rng(sim.fnv("typical:" + city)); orders = []
    n = 12 + int(ro.u() * 5)
    for i in range(n):
        t = int(ro.u() * 5400)
        p = points[int(ro.u() * len(points))]
        kg = round(2 + 28 * ro.u() * ro.u(), 1)
        orders.append({"t": t, "point": p["id"], "kg": kg, "due": t + 1500 + int(ro.u() * 1500)})
    orders.sort(key=lambda o: (o["t"], o["point"]))
    for i, o in enumerate(orders):
        o["id"] = i
    return orders


def expected_world(g, k=1.0):
    """То, что известно до смены: прогноз ветра и температуры этого дня, без порывов, типовая лента заказов.

    k > 1: худший край прогноза, ветер сильнее на объявленную ошибку. Прогноз в этом мире остаётся прежним:
    обработчик видит то же, что видел бы в смену, а мир идёт по худшему краю.
    """
    W = g.W; zc = W["map"]["depot"]["z"]; hours = []
    for h in W["hours"]:
        t2 = h["t_fc"]; dens = []
        for z in range(0, 3100, 100):
            T = t2 + 273.15 - 0.0065 * (z - zc)
            pr = 101325.0 * (1 - 2.25577e-5 * z) ** 5.25588
            dens.append(math.sqrt(1.225 / (pr / (287.05 * T))))
        cap = 1.0 if t2 >= 15 else (0.85 + 0.15 * t2 / 15.0 if t2 >= 0 else (0.85 + 0.015 * t2 if t2 >= -20 else 0.55))
        pmax = sim.D["pmax_w"] if t2 <= sim.D["pmax_hot_c"] else max(
            sim.D["pmax_46_w"], sim.D["pmax_w"] - (t2 - sim.D["pmax_hot_c"]) * (sim.D["pmax_w"] - sim.D["pmax_46_w"]) / 6.0)
        truth = h["fc"] if k == 1.0 else {a: [k * h["fc"][a][0], k * h["fc"][a][1]] for a in h["fc"]}
        hours.append({"truth": truth, "fc": h["fc"], "t": t2, "t_fc": t2, "dens": dens, "cap": cap, "pmax": pmax, "gust_k": 0.0})
    return {"seed": W["seed"], "city": W["city"], "day": W["day"], "hours": hours,
            "gust": [1.0] * len(W["gust"]), "orders": typical_orders(W["city"], W["map"]["points"]), "map": W["map"]}


def simulate(plan, g0, world=None):
    """Прогон смены по замыслу. -> (игра, обработчик)."""
    g = sim.Game(g0.W["seed"], g0.city, world=world if world is not None else expected_world(g0))
    disp = Dispatcher(plan)
    while not g.done():
        for dec in disp.tick(g):
            g.decide(dec)
        g.step()
    return g, disp


def _fc(g, disp):
    sc = g.score(); c = sc["counts"]
    return {"score": sc["score"], "delivered": c["delivered"], "orders": c["orders"], "forced": c["forced"], "lost": c["lost"],
            "pads": c["pads"], "kwh": c["kwh"], "ref_kwh": c["ref_kwh"], "flights": disp.launched, "refused": len(disp.refusals)}


LINE_RU = {"alt": "высота", "speed": "скорость", "load": "груз до", "per_flight": "заказов за рейс", "reserve": "запас",
           "pad": "зарядка на площадке", "first": "сначала", "max_km": "не лететь дальше"}
LINE_EN = {"alt": "altitude", "speed": "speed", "load": "load up to", "per_flight": "orders per flight", "reserve": "reserve",
           "pad": "pad", "first": "first", "max_km": "no farther than"}
MARGIN = 30.0
GAIN = 60.0     # совет по строке показывается, когда одна строка даёт столько очков по прогнозу


def _with(d, k, v):
    out = dict(d or {}); out[k] = v; return out


def variants(plan, g):
    """Что стоит попробовать: замена или добавление одной строки. -> [(строка ru, строка en, план, (поле, значение))].

    Ступень 2 языка (13.11, по ошибкам прогона ступени 1): модель написала один и тот же осторожный замысел
    во все 30 смен, и Проверка молчала, потому что отказывает только на замысле, который хуже. Теперь Проверка
    вместе с прогнозом отдаёт разницу в счёте от одной строки, и модель получает её до смены.
    """
    out = []
    pads = [q["id"] for q in g.M["points"] if q["pad"]]

    def mk(**kw):
        p = dict(plan); p["lines"] = dict(plan["lines"])
        p["pt_load"] = dict(plan.get("pt_load") or {}); p["skip"] = list(plan.get("skip") or [])
        p.update(kw); return p

    out.append(("со строкой «скорость быстро»", "with the line 'speed fast'", mk(speed="fast"), ("speed", "fast")) if plan["speed"] != "fast"
               else ("со строкой «скорость эконом»", "with the line 'speed eco'", mk(speed="eco"), ("speed", "eco")))
    out.append(("со строкой «заказов за рейс 2»", "with the line 'orders per flight 2'", mk(per_flight=2), ("per_flight", 2)) if plan["per_flight"] != 2
               else ("со строкой «заказов за рейс 3»", "with the line 'orders per flight 3'", mk(per_flight=3), ("per_flight", 3)))
    for a in (30, 60):
        if plan["alt"] != a:
            out.append(("со строкой «высота %d»" % a, "with the line 'altitude %d'" % a, mk(alt=a), ("alt", a)))
    for f, ru, en in (("near", "близкие", "near"), ("heavy", "тяжёлые", "heavy"), ("urgent", "срочные", "urgent")):
        if plan["first"] != f:
            out.append(("со строкой «сначала %s»" % ru, "with the line 'first %s'" % en, mk(first=f), ("first", f)))
    if plan["reserve"] > 10:
        out.append(("со строкой «запас 10»", "with the line 'reserve 10'", mk(reserve=10), ("reserve", 10)))
    if plan["max_km"] is not None:
        out.append(("без строки «не лететь дальше %s км»" % _n(plan["max_km"]),
                    "without the line 'no farther than %s km'" % _n(plan["max_km"]), mk(max_km=None), ("max_km", None)))
    if plan["load_kg"] < sim.D["payload_max"]:
        out.append(("со строкой «груз до 40 кг»", "with the line 'load up to 40 kg'", mk(load_kg=sim.D["payload_max"]), ("load_kg", sim.D["payload_max"])))
    if plan["pad"] is None and pads:
        out.append(("со строкой «зарядка на площадке %d если заряд меньше 45»" % pads[0],
                    "with the line 'pad %d if charge below 45'" % pads[0], mk(pad=pads[0], pad_below=45), ("pad", pads[0])))
    elif plan["pad"] is not None:
        out.append(("без строки «зарядка на площадке %d»" % plan["pad"],
                    "without the line 'pad %d'" % plan["pad"], mk(pad=None, pad_below=None), ("pad", None)))
    # ступень 4 языка: предел по точке. Дальняя точка съедает смену целиком, и пока дрон идёт туда с тяжёлым
    # заказом, ближние заказы просрочиваются. Проверка считает, что дала бы одна такая строка на самой дальней точке.
    far = sorted(g.M["points"], key=lambda q: -(q["x"] * q["x"] + q["y"] * q["y"]))
    free = [q for q in far if q["id"] not in (plan.get("skip") or []) and q["id"] not in (plan.get("pt_load") or {})][:2]
    for q in free:
        d = math.sqrt(q["x"] * q["x"] + q["y"] * q["y"]) / 1000.0
        out.append(("со строкой «точку %d пропускать» (%s, %s км от склада)" % (q["id"], q["ru"], _n(d)),
                    "with the line 'skip point %d' (%s, %s km from the depot)" % (q["id"], q["en"], _n(d)),
                    mk(skip=sorted(set((plan.get("skip") or []) + [q["id"]]))), ("skip", q["id"])))
        out.append(("со строкой «точка %d груз до 10 кг» (%s, %s км от склада)" % (q["id"], q["ru"], _n(d)),
                    "with the line 'point %d load up to 10 kg' (%s, %s km from the depot)" % (q["id"], q["en"], _n(d)),
                    mk(pt_load=_with(plan.get("pt_load"), q["id"], 10.0)), ("pt_load", [q["id"], 10.0])))
    for pid in (plan.get("skip") or []):
        out.append(("без строки «точку %d пропускать»" % pid, "without the line 'skip point %d'" % pid,
                    mk(skip=[x for x in plan["skip"] if x != pid]), ("skip_off", pid)))
    for pid in sorted(plan.get("pt_load") or {}):
        out.append(("без строки «точка %d груз до %s кг»" % (pid, _n(plan["pt_load"][pid])),
                    "without the line 'point %d load up to %s kg'" % (pid, _n(plan["pt_load"][pid])),
                    mk(pt_load={k: v for k, v in plan["pt_load"].items() if k != pid}), ("pt_load_off", pid)))
    return out


def used(plan, field, value):
    """Применена ли советованная строка в присланном замысле (поля плана и строки про точку)."""
    if field == "skip":
        return int(value) in [int(x) for x in (plan.get("skip") or [])]
    if field == "skip_off":
        return int(value) not in [int(x) for x in (plan.get("skip") or [])]
    if field == "pt_load":
        pid, kg = value
        got = (plan.get("pt_load") or {}).get(int(pid))
        return got is not None and abs(float(got) - float(kg)) < 1e-9
    if field == "pt_load_off":
        return int(value) not in [int(k) for k in (plan.get("pt_load") or {})]
    return plan.get(field) == value


CHAIN = 3   # ступень 4: Проверка набирает цепочку строк, пока каждая следующая даёт ещё GAIN очков


def _one(plan, g0, worlds, mine, mine18):
    """Лучшая одна строка поверх этого замысла: ранжир по прогнозу, проверка по худшему краю. -> (dict, план) или None."""
    cand = []
    for ru, en, p, key in variants(plan, g0):
        got = _fc(*simulate(p, g0, worlds[0]))
        if got["score"] > mine["score"] + GAIN:
            cand.append((got["score"], ru, en, p, key, got))
    cand.sort(key=lambda r: -r[0])
    for _, ru, en, p, key, got in cand:          # худший край считаем только для лучших, по порядку
        got18 = _fc(*simulate(p, g0, worlds[1]))
        if got18["score"] <= mine18["score"] + GAIN:
            continue
        return ({"line_ru": ru, "line_en": en, "field": key[0], "value": key[1],
                 "score": got["score"], "delivered": got["delivered"], "forced": got["forced"]}, p, got, got18)
    return None


def advice(plan, g0, worlds, mine, mine18, chain=CHAIN):
    """Цепочка строк, которая по прогнозу даёт больше всех очков. -> dict или None.

    Ступень 4 языка (14.11, по прогону ступени 3): совет был одной строкой, и выигрыш обрывался на первой.
    По прогнозу цепочка из двух-трёх строк давала в Дубае ещё 300 очков поверх одной. Каждая строка цепочки
    обязана дать GAIN очков и на прогнозе, и на худшем крае прогноза (ветер ×1,18), иначе цепочка кончается.
    """
    cur = plan; m, m18 = mine, mine18; steps = []
    for _ in range(max(1, chain)):
        got = _one(cur, g0, worlds, m, m18)
        if got is None:
            break
        step, cur, m, m18 = got
        steps.append(step)
    if not steps:
        return None
    last = steps[-1]
    best = {"steps": steps, "line_ru": last["line_ru"], "line_en": last["line_en"], "field": last["field"], "value": last["value"],
            "score": last["score"], "delivered": last["delivered"], "forced": last["forced"],
            "base_score": mine["score"], "base_delivered": mine["delivered"], "orders": mine["orders"]}
    def _join(parts, last_word):
        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + " " + last_word + " " + parts[-1]

    join_ru = _join([st["line_ru"] for st in steps], "и")
    join_en = _join([st["line_en"] for st in steps], "and")
    best["lines_ru"] = join_ru; best["lines_en"] = join_en
    best["ru"] = ("по прогнозу этот замысел даёт %s очков (доставлено %d из %d); %s вышло бы %s (доставлено %d)."
                  % (_n(best["base_score"]), best["base_delivered"], best["orders"], join_ru, _n(best["score"]), best["delivered"]))
    best["en"] = ("by the forecast this plan scores %s (%d of %d delivered); %s it would score %s (%d delivered)."
                  % (_n(best["base_score"]), best["base_delivered"], best["orders"], join_en, _n(best["score"]), best["delivered"]))
    return best


def _wind_shift(g, alt):
    """Наибольшая сила ветра по прогнозу на этой высоте за часы смены."""
    out = 0.0
    for t in range(0, sim.SHIFT_S + 1, 600):
        u, v = fc_wind(g, t, alt)
        s = math.sqrt(u * u + v * v)
        out = s if s > out else out
    return out


def _reason(kind, plan, g, disp, mine, base, hint):
    """Отказ по строке: причина с цифрами. hint = худший отказ взлёта на прогоне плана."""
    i = plan["lines"][kind]; d = mine["delivered"]; db = base["delivered"]
    pid = int(kind.split(":")[1]) if ":" in kind else None
    tail_ru = "по прогнозу доставлено %d из %d против %d без этой строки, счёт %s против %s" % (d, mine["orders"], db, _n(mine["score"]), _n(base["score"]))
    tail_en = "by the forecast %d of %d delivered against %d without this line, score %s against %s" % (d, mine["orders"], db, _n(mine["score"]), _n(base["score"]))
    if pid is not None:
        q = g.pts.get(pid); name = q["ru"] if q else str(pid)
        dist = _n(math.sqrt(q["x"] * q["x"] + q["y"] * q["y"]) / 1000.0) if q else "?"
        name_en = q["en"] if q else str(pid)
        if kind.startswith("skip:"):
            return _e(i, "точку %d (%s, %s км) пропускать не стоит: %s." % (pid, name, dist, tail_ru),
                      "point %d (%s, %s km) is worth serving: %s." % (pid, name_en, dist, tail_en))
        return _e(i, "предел груза на точке %d (%s, %s км) по прогнозу отрезает заказы без выигрыша: %s." % (
            pid, name, dist, tail_ru),
            "the load limit on point %d (%s, %s km) cuts orders without a gain by the forecast: %s." % (
                pid, name_en, dist, tail_en))
    if kind == "reserve":
        return _e(i, "запас %d %% не даёт взлететь: по прогнозу %d заказов из %d остаются на складе, %s." % (plan["reserve"], mine["orders"] - mine["delivered"], mine["orders"], tail_ru),
                  "the %d%% reserve blocks take-offs: by the forecast %d orders of %d stay at the depot, %s." % (plan["reserve"], mine["orders"] - mine["delivered"], mine["orders"], tail_en))
    if kind == "alt":
        w_plan = _wind_shift(g, plan["alt"]); w_def = _wind_shift(g, DEFAULT["alt"])
        zc = g.M["depot"]["z"]
        ph = sim.D["hover_c"] * sim.D["empty_kg"] * math.sqrt(math.sqrt(sim.D["empty_kg"])) * g.dens(zc + plan["alt"] / 2.0)
        dz = (plan["alt"] - DEFAULT["alt"]) / sim.D["climb_ms"]
        dwh = ph * (sim.D["climb_k"] + sim.D["descend_k"]) * dz / 3600.0
        return _e(i, "на %d м ветер по прогнозу %s м/с (на %d м %s м/с), а подъём и спуск стоят на %s Вт·ч за остановку больше: %s." % (
            plan["alt"], _n(w_plan), DEFAULT["alt"], _n(w_def), _n(dwh), tail_ru),
            "at %d m the forecast wind is %s m/s (at %d m it is %s m/s) and climb plus descent cost %s Wh more per stop: %s." % (
                plan["alt"], _n(w_plan), DEFAULT["alt"], _n(w_def), _n(dwh), tail_en))
    if hint is not None and hint["head"] > 3.0 and kind in ("load", "per_flight", "speed"):
        pads = [q for q in g.M["points"] if q["pad"]]
        low_ru = "лети ниже" if plan["alt"] > 30 else "лети быстро"
        low_en = "fly lower" if plan["alt"] > 30 else "fly fast"
        pad_ru = (" или садись на зарядку на площадке %d" % pads[0]["id"]) if (plan["pad"] is None and pads) else ""
        pad_en = (" or recharge on pad %d" % pads[0]["id"]) if (plan["pad"] is None and pads) else ""
        if kind == "load":
            add_ru = "подними предел груза, " + low_ru + pad_ru; add_en = "raise the load limit, " + low_en + pad_en
        elif kind == "per_flight":
            add_ru = "бери по одному заказу, " + low_ru + pad_ru; add_en = "take one order per flight, " + low_en + pad_en
        else:
            add_ru = "лети быстро: времени в воздухе меньше" + pad_ru; add_en = "fly fast: less time in the air" + pad_en
        return _e(i, "на обратном плече встречный ветер %s м/с, заряда хватит до %s км от склада (%s в %s км, груз %s кг): %s. Иначе %s." % (
            _n(hint["head"]), _n(hint["km_left"]), hint["point_ru"], _n(hint["km"]), _n(hint["kg"]), add_ru, tail_ru),
            "headwind %s m/s on the leg home, the charge lasts %s km from the depot (%s at %s km, load %s kg): %s. Otherwise %s." % (
                _n(hint["head"]), _n(hint["km_left"]), hint["point_en"], _n(hint["km"]), _n(hint["kg"]), add_en, tail_en))
    if kind == "max_km":
        return _e(i, "предел %s км оставляет без доставки дальние точки: %s." % (_n(plan["max_km"]), tail_ru),
                  "the %s km limit leaves the far points undelivered: %s." % (_n(plan["max_km"]), tail_en))
    if kind == "speed" and plan["speed"] == "fast":
        return _e(i, "быстро стоит энергии: %s кВт·ч против %s кВт·ч без этой строки, %s." % (_n(mine["kwh"]), _n(base["kwh"]), tail_ru),
                  "fast costs energy: %s kWh against %s kWh without this line, %s." % (_n(mine["kwh"]), _n(base["kwh"]), tail_en))
    if kind == "pad":
        return _e(i, "зарядка на площадке %d не нужна по этому прогнозу: %s." % (plan["pad"], tail_ru),
                  "recharging on pad %d is not needed by this forecast: %s." % (plan["pad"], tail_en))
    if mine["forced"] > base["forced"] or mine["lost"] > base["lost"]:
        return _e(i, "вынужденных посадок %d и потерь %d против %d и %d без этой строки: %s." % (
            mine["forced"], mine["lost"], base["forced"], base["lost"], tail_ru),
            "%d forced landings and %d losses against %d and %d without this line: %s." % (
                mine["forced"], mine["lost"], base["forced"], base["lost"], tail_en))
    return _e(i, "строка «%s» по прогнозу хуже: %s." % (LINE_RU[kind], tail_ru), "the line '%s' is worse by the forecast: %s." % (LINE_EN[kind], tail_en))


def check(text, g0):
    """Полная Проверка замысла до взлёта: -> (ok, отказы, прогноз, план)."""
    plan, errs = parse(text)
    if errs:
        return False, errs, None, plan
    errs = sense(plan, g0)
    if errs:
        return False, errs, None, plan
    worlds = [expected_world(g0), expected_world(g0, WIND_K)]
    g, disp = simulate(plan, g0, worlds[0])
    mine = _fc(g, disp)
    mine18 = _fc(*simulate(plan, g0, worlds[1]))
    base = _fc(*simulate(dict(DEFAULT, lines={}), g0, worlds[0]))
    base18 = _fc(*simulate(dict(DEFAULT, lines={}), g0, worlds[1]))
    if not plan["lines"] or mine["score"] >= base["score"] - MARGIN or mine18["score"] >= base18["score"] - MARGIN:
        mine["advice"] = advice(plan, g0, worlds, mine, mine18)   # замысел принят, но Проверка говорит, что даёт одна строка
        return True, [], mine, plan        # хуже только на одном краю прогноза: это выбор замысла, а не ошибка
    hint = None
    if disp.refusals:
        hint = max(disp.refusals, key=lambda r: r["head"])
    worst = None
    for kind in plan["lines"]:
        cut = dict(plan); cut["lines"] = {k: v for k, v in plan["lines"].items() if k != kind}
        cut["pt_load"] = dict(plan.get("pt_load") or {}); cut["skip"] = list(plan.get("skip") or [])
        for key, val in (("alt", "alt"), ("speed", "speed"), ("load", "load_kg"), ("per_flight", "per_flight"),
                         ("reserve", "reserve"), ("first", "first"), ("max_km", "max_km")):
            if kind == key:
                cut[val] = DEFAULT[val]
        if kind == "pad":
            cut["pad"] = None; cut["pad_below"] = None
        if ":" in kind:
            pid = int(kind.split(":")[1])
            if kind.startswith("skip:"):
                cut["skip"] = [x for x in cut["skip"] if x != pid]
            else:
                cut["pt_load"] = {k: v for k, v in cut["pt_load"].items() if k != pid}
        got = _fc(*simulate(cut, g0, worlds[0]))
        got18 = _fc(*simulate(cut, g0, worlds[1]))
        if got["score"] > mine["score"] + MARGIN and got18["score"] > mine18["score"] + MARGIN and (worst is None or got["score"] > worst[1]["score"]):
            worst = (kind, got)
    if worst is None:
        mine["advice"] = advice(plan, g0, worlds, mine, mine18)
        return True, [], mine, plan
    errs.append(_reason(worst[0], plan, g0, disp, mine, worst[1], hint))
    return False, errs, mine, plan


def run(text, seed, city):
    """Смена по принятому замыслу в настоящем мире (со скрытым ветром и порывами)."""
    g = sim.Game(seed, city)
    plan, _ = parse(text)
    disp = Dispatcher(plan)
    decisions = []; n = 0
    while not g.done():
        for dec in disp.tick(g):
            if not g.decide(dec):
                decisions.append([n, dec])
        g.step(); n += 1
    return g, disp, decisions
