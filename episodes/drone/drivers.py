"""Простые диспетчеры без ИИ: ориентир для счёта и тест симулятора.
simple:  ближайший по времени заказ первому свободному дрону, быстро, 60 м, ветер и заряд не считает.
careful: то же, но заранее считает заряд на круг по прогнозу ветра и летит через площадку, если без неё не хватает."""
import math
import sim


def simple(o, g):
    for d in o["drones"]:
        if d["mode"] == "dock" and d["busy"] == 0:
            wait = [x for x in o["orders"] if x["status"] == "wait"]
            for x in wait:
                dec = {"drone": d["id"], "route": ["o%d" % x["id"]], "alt": 60, "speed": "fast"}
                if not g.check(dec):
                    return dec
    return None


def leg_wh(g, a, b, kg, alt, va, fc_hour):
    """Энергия плеча по прогнозу ветра (тот же расчёт, что в симуляторе, но по прогнозу)."""
    dx, dy = b["x"] - a["x"], b["y"] - a["y"]; dist = math.hypot(dx, dy)
    if dist == 0:
        return 0.0
    ex, ey = dx / dist, dy / dist; u, v = fc_hour["fc"][alt]
    wa = u * ex + v * ey; wc = -u * ey + v * ex
    gs = (math.sqrt(va * va - wc * wc) + wa) if wc * wc < va * va else wa
    if gs <= 0.5:
        return 1e9
    m = sim.D["empty_kg"] + kg; z = (a["z"] + b["z"]) / 2 + alt
    uu = va / 15.0
    return g.p_hover(m, z) * (1 + sim.CRUISE_A * uu + sim.CRUISE_B * uu * uu) * dist / gs / 3600.0


def careful(o, g):
    hr = g.hour(); cap = sim.D["battery_wh"] * hr["cap"]
    for d in o["drones"]:
        if d["mode"] != "dock" or d["busy"] != 0:
            continue
        for x in [x for x in o["orders"] if x["status"] == "wait"]:
            p = g.pts[x["point"]]; dep = g.M["depot"]
            for alt in (60, 30, 100):
                need = leg_wh(g, dep, p, x["kg"], alt, 12.0, hr) + leg_wh(g, p, dep, 0.0, alt, 12.0, hr) + 0.05 * cap
                if need < 0.8 * cap:
                    dec = {"drone": d["id"], "route": ["o%d" % x["id"]], "alt": alt, "speed": "eco"}
                    if not g.check(dec):
                        return dec
                # через площадку на обратном пути
                for pad in [q for q in g.M["points"] if q["pad"]]:
                    need1 = leg_wh(g, dep, p, x["kg"], alt, 12.0, hr) + leg_wh(g, p, pad, 0.0, alt, 12.0, hr) + 0.05 * cap
                    need2 = leg_wh(g, pad, dep, 0.0, alt, 12.0, hr) + 0.05 * cap
                    if need1 < 0.8 * cap and need2 < 0.8 * cap:
                        dec = {"drone": d["id"], "route": ["o%d" % x["id"], "p%d" % pad["id"]], "alt": alt, "speed": "eco"}
                        if not g.check(dec):
                            return dec
    return None


DRIVERS = {"simple": simple, "careful": careful}
