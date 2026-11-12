"""Язык поездки и его обработчик: модель пишет замысел, обработчик ведёт поезд и проверяет план до отправления.

Строки (русский или английский, по одной команде в строке, # комментарий):
  толкач да | нет                         banker yes | no
  разгон до 280                           accelerate to 280    (один раз: предел скорости на весь рейс)
  тише 250 с км 100 до км 120             slower 250 from km 100 to km 120   (ехать тише допустимой на отрезке)
  выбег с км 140 до км 150                coast from km 140 to km 150
  песок с км 42 до км 70                  sand from km 42 to km 70
  по графику                              to schedule      (выбег там, где поезд идёт с опережением)

Ограничения скорости и остановки на станциях обработчик соблюдает сам: в языке нет слов, которыми можно их нарушить.
Проверка до отправления: разбор (строка и причина), здравый смысл (км вне участка, скорость выше предельной для поезда),
затем симуляция плана на ожидаемом мире (погода по прогнозу, лист предупреждений, без скрытого сигнала):
опоздание больше 30 с из-за плана, остановка поезда на подъёме, вмешательство защиты отказывают с километром и причиной.

Версия 2 (12.11, по ошибкам модели в прогоне H1): «держать V до км K» убрано. Модель переписывала им профиль и занижала скорость
(28 из 35 отказов). Ограничения обработчик соблюдает сам; ехать тише допустимой можно только явно, словом «тише» с отрезком.
"""
import re
import sim

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
    sv = g.T["brake"]["service_ms2"]; gr = sim.G * o["grade_permille"] / 1000.0
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
    g = sim.Game(g0.W["seed"], g0.line_id, world=expected_world(g0))
    drv = Driver(plan, g.stations[0]["km"], g.stations[-1]["km"])
    stall_km = None; slow_t = 0.0
    while not g.done():
        d = drv(g.observe(), g)
        if d:
            g.decide(d)
        g.step()
        if g.departed and not g.at_station and g.v < 0.5:
            slow_t += sim.DT
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
        g1 = sim.Game(g0.W["seed"], g0.line_id, world=expected_world(g0))
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
                        v, _k(a), _k(b), s["name"], sim.clock(s["t"]), s["late_s"], max(0, sf["late_s"])),
                        "%d km/h from km %s to km %s: by the forecast %s at %s, %d s late (without the plan's limits %d s)." % (
                        v, _k(a), _k(b), s["name"], sim.clock(s["t"]), s["late_s"], max(0, sf["late_s"]))))
                    break
    if plan["coasts"] and not errs:
        base = dict(plan, coasts=[])
        gb, _ = simulate(base, g0)
        for s, sb in zip(g.stops, gb.stops):
            if sc["score"] < gb.score()["score"] - 30 and s.get("late_s") is not None and sb.get("late_s") is not None and s["late_s"] > 30 and s["late_s"] - sb["late_s"] > 20:
                a, b, i = max(plan["coasts"], key=lambda c: c[1] - c[0])
                errs.append(_e(i, "выбег с км %s до км %s: прибытие %s в %s, график %s, опоздание %d с." % (_k(a), _k(b), s["name"], sim.clock(s["t"]), sim.clock(s["t"] - s["late_s"]), s["late_s"]),
                               "coast from km %s to km %s: arrival at %s %s, scheduled %s, %d s late." % (_k(a), _k(b), s["name"], sim.clock(s["t"]), sim.clock(s["t"] - s["late_s"]), s["late_s"])))
                break
    if g.counts["atp"]:
        errs.append(_e(0, "по прогнозу защита вмешается %d раз: план слишком близко к кривой торможения." % g.counts["atp"],
                       "by the forecast the protection system intervenes %d times: the plan runs too close to the braking curve." % g.counts["atp"]))
    return (not errs), errs, fc, plan


def run(text, seed, line_id):
    """Рейс по принятому плану в настоящем мире (со скрытым): то, что потом показывает призрак."""
    g = sim.Game(seed, line_id)
    plan, errs = parse(text)
    drv = Driver(plan, g.stations[0]["km"], g.stations[-1]["km"])
    while not g.done():
        d = drv(g.observe(), g)
        if d:
            g.decide(d)
        g.step()
    return g
