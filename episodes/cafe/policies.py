"""Тестовые игроки. Не Extella: нужны, чтобы проверить экономику и зерно,
и чтобы игроку было с кем себя сравнить, кроме Extella.

naive:   ничего не планирует, держит стартовые смены, заказывает одинаково.
careful: заказывает по прогнозу с запасом, смены под прогноз, найм при нехватке,
         карточки решает по простому правилу ожидаемой выгоды.
plenty:  тот же расчёт, но с избытком: запас в полтора раза, смены по верхней границе прогноза.
thrifty: тот же расчёт, но людей меньше и никого не нанимает.
bare:    тот же расчёт, но заказ ровно по прогнозу, без запаса.

Четыре последних — одна функция _plan с разными числами, и каждый отличается
от careful ровно одним: запасом, сменой или заказом. Так видно, что чего стоит.
"""
import math

DRINKS = ["latte", "cold_brew", "drip", "tea"]


def _ceil(x):
    return int(math.ceil(x - 1e-9))


def naive(obs):
    dec = {"orders": {}}
    sup = obs["suppliers"]
    if sup["dairy"]["delivers_tomorrow"]:
        dec["orders"]["dairy"] = {"milk": 40}
    if sup["roaster"]["delivers_tomorrow"]:
        dec["orders"]["roaster"] = {"beans": 30, "cups": 2}
    dec["orders"]["bakery"] = {"croissant": 60}
    return dec


def _need(obs, C=None):
    """Ожидаемый расход по дням прогноза: латте-молоко л, зерно г, стаканы, круассаны."""
    M = {"latte": (18, 0.24), "cold_brew": (22, 0), "drip": (20, 0), "tea": (0, 0)}
    share = {"latte": 0.45, "cold_brew": 0.10, "drip": 0.30, "tea": 0.15}
    rows = []
    for f in obs["forecast"]:
        g = sum(f["guests"])
        milk = g * share["latte"] * M["latte"][1]
        beans = sum(g * share[k] * M[k][0] for k in DRINKS)
        rows.append({"day": f["day"], "wd": f["wd"], "g": g, "milk": milk, "beans": beans, "cups": g, "dp": f["guests"], "high": f["high"]})
    return rows


CAREFUL = {"milk_k": 1.15, "dry_k": 1.10, "croissant_k": 1.05, "staff_k": 1.10, "use_high": False, "hire_cap": 3, "cards": "careful"}
PLENTY = dict(CAREFUL, milk_k=1.50, dry_k=1.35, croissant_k=1.35, staff_k=1.00, use_high=True)
THRIFTY = dict(CAREFUL, staff_k=0.95, hire_cap=0, cards="default")
BARE = dict(CAREFUL, milk_k=1.00, dry_k=0.95, croissant_k=0.80)


def careful(obs):
    return _plan(obs, CAREFUL)


def plenty(obs):
    return _plan(obs, PLENTY)


def thrifty(obs):
    return _plan(obs, THRIFTY)


def bare(obs):
    return _plan(obs, BARE)


def _plan(obs, p):
    dec = {"orders": {}, "choices": {}}
    rows = _need(obs)
    if not rows:
        return dec
    sup = obs["suppliers"]; st = obs["stock"]
    avg = sum(r["g"] for r in rows) / len(rows)
    # молоко: если завтра привоз, покрыть до следующего привоза включительно с запасом 15 %
    if sup["dairy"]["delivers_tomorrow"]:
        days = sup["dairy"]["days"]; wd = rows[0]["wd"]
        gap = next(k for k in range(1, 8) if (wd + k) % 7 in days)
        cover = sum(r["milk"] for r in rows[:gap]) + max(0, gap - len(rows)) * rows[-1]["milk"]
        have = sum(a for a, b in st["milk_l"] if b >= rows[0]["day"])
        need_l = cover * p["milk_k"] - have
        if need_l > 0:
            gal = max(_ceil(need_l / 3.785), _ceil(sup["dairy"]["min_order"] / sup["dairy"]["prices"]["milk"]))
            dec["orders"]["dairy"] = {"milk": gal}
    if sup["roaster"]["delivers_tomorrow"]:
        need_lb = (avg * 16.3 * 5 * p["dry_k"]) / 453.6 - st["beans_lb"]
        need_cups = avg * 5 * p["dry_k"] - st["cups"]
        o = {}
        if need_lb > 0:
            o["beans"] = _ceil(need_lb)
        if need_cups > 0:
            o["cups"] = _ceil(need_cups / 500)
        if o:
            tot = o.get("beans", 0) * 12 + o.get("cups", 0) * 75
            if tot < sup["roaster"]["min_order"]:
                o["beans"] = o.get("beans", 0) + _ceil((sup["roaster"]["min_order"] - tot) / 12)
            dec["orders"]["roaster"] = o
    croissant = max(12, int(round(rows[0]["g"] * 0.35 * p["croissant_k"])))
    dec["orders"]["bakery"] = {"croissant": croissant}
    # смены на завтрашний день недели под прогноз
    sch = obs["schedule"]
    wd = str(rows[0]["wd"])
    nb = sum(1 for s in obs["staff"] if s["role"] == "barista")
    b = []
    for dp, g in enumerate(rows[0]["high"] if p["use_high"] else rows[0]["dp"]):
        cap_per = 12 * 4
        need = _ceil(g * p["staff_k"] / cap_per - (0.5 if dp == 0 else 0))
        b.append(max(1, min(need, 6 - (1 if dp == 0 else 0))))
    if max(b) > nb and p["hire_cap"]:
        dec["hire"] = min(p["hire_cap"], max(b) - nb)
    b = [min(x, nb + dec.get("hire", 0)) for x in b]
    new = {k: {"barista": list(v["barista"]), "lead": list(v["lead"])} for k, v in sch.items()}
    new[wd] = {"barista": b, "lead": [1, 0, 0]}
    dec["schedule"] = new
    # карточки
    for c in obs["cards"]:
        k = c["kind"]
        pick = c["default"] if p["cards"] == "default" else {"blogger": "accept", "repair": "sign", "inspection": "clean", "breakdown": "fast", "sick": "agency",
                "catering": "accept", "blizzard": "open", "competitor": "loyalty", "complaint": "coupons"}.get(k, c["default"])
        dec["choices"][c["id"]] = pick
    return dec
