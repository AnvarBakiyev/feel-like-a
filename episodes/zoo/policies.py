"""Два тестовых игрока зоопарка. Не Extella: нужны, чтобы проверить экономику и зерно.

naive: смены по минимуму, разморозка ровно по норме, заказ одинаковый, карточки по умолчанию, ветеринара не зовёт.
careful: запас корма с покрытием до следующей поставки и двумя днями сверху, кассы и киоски по верхней границе прогноза,
         два кормления при публике, найм при нехватке часов, два визита ветеринара, карточки по простому правилу.
"""
import math

SECTIONS = ["pool", "cats", "birds", "yard", "tropic"]


def _ceil(x):
    return int(math.ceil(x - 1e-9))


def _gap(wd, days):
    return next(k for k in range(1, 8) if (wd + k) % 7 in days)


def naive(obs):
    dec = {"thaw": {"fish": obs["need_kg_per_day"]["fish"], "meat": obs["need_kg_per_day"]["meat"]}, "orders": {}}
    sup = obs["suppliers"]
    if sup["frozen"]["delivers_tomorrow"]:
        dec["orders"]["frozen"] = {"fish": 150, "meat": 10}
    if sup["hay"]["delivers_tomorrow"] and obs["stock"]["hay"] < 200:
        dec["orders"]["hay"] = {"hay": 500}
    dec["orders"]["produce"] = {"produce": 10}
    fz = obs["stock"]["freezer"]
    dec["thaw"] = {"fish": min(dec["thaw"]["fish"], fz["fish"] + obs["stock"]["thawed_for_tomorrow"]["fish"]),
                   "meat": min(dec["thaw"]["meat"], fz["meat"] + obs["stock"]["thawed_for_tomorrow"]["meat"])}
    return dec


def careful(obs):
    dec = {"orders": {}, "choices": {}}
    nd = obs["need_kg_per_day"]; st = obs["stock"]; sup = obs["suppliers"]; wd = obs["wd"]
    have = {k: st["freezer"][k] + st["thawed_for_tomorrow"][k] for k in ("fish", "meat")}
    dec["thaw"] = {k: min(nd[k], have[k]) for k in ("fish", "meat")}
    if sup["frozen"]["delivers_tomorrow"]:
        gap = _gap(wd, sup["frozen"]["days"])
        o = {}
        for k in ("fish", "meat"):
            want = nd[k] * (gap + 2) + nd[k] - (have[k] - nd[k])
            if want > 0:
                o[k] = 10 * _ceil(want / 10)
        if o:
            tot = sum(sup["frozen"]["prices_kg"][k] * q for k, q in o.items())
            while tot < sup["frozen"]["min_order"]:
                o["fish"] = o.get("fish", 0) + 10; tot += 10 * sup["frozen"]["prices_kg"]["fish"]
            dec["orders"]["frozen"] = o
    if sup["hay"]["delivers_tomorrow"] and st["hay"] < nd["hay"] * 12:
        dec["orders"]["hay"] = {"hay": 500}
    usable = sum(a for a, b in st["produce"] if b >= obs["day"])
    if usable < nd["produce"] * 1.5:
        dec["orders"]["produce"] = {"produce": max(10, _ceil(nd["produce"] * 2 - usable))}
    # смены на завтра
    f = obs["forecast"][0]; mn = obs["min_tomorrow"]
    kp = {s: list(mn[s]) for s in SECTIONS}
    kp["pool"] = [max(kp["pool"][h], 4) for h in range(2)]
    cards = {c["kind"]: c for c in obs["cards"]}
    if "school" in cards and cards["school"]["day"] == obs["day"]:
        kp["yard"][0] += 1
    gate = [_ceil(f["high"][h] * 0.75 / (100 * 3.5)) for h in range(2)]
    kiosk = [_ceil(f["high"][h] * 0.7 / (60 * 3.5)) for h in range(2)]
    row = {"keepers": kp, "cashiers": [max(1, min(8, x)) for x in gate], "kiosk": [min(8, x) for x in kiosk], "shows": 2}
    sch = {k: v for k, v in obs["schedule"].items()}
    sch[str(wd)] = row
    for w in range(7):
        r = sch[str(w)]
        if r.get("shows", 0) == 2:
            continue
        r = {"keepers": {s: list(r["keepers"][s]) for s in SECTIONS}, "cashiers": list(r["cashiers"]), "kiosk": list(r["kiosk"]), "shows": 2}
        r["keepers"]["pool"] = [max(x, 4) for x in r["keepers"]["pool"]]
        sch[str(w)] = r
    dec["schedule"] = sch
    week_h = sum(sum(sum(sch[str(w)]["keepers"][s]) for s in SECTIONS) for w in range(7)) * 3.5
    nb = len(obs["staff"])
    per_half = max(sum(sch[str(w)]["keepers"][s][h] for s in SECTIONS) for w in range(7) for h in range(2))
    need = max(_ceil(week_h / 40), per_half + 1)
    if need > nb and obs["day"] < obs["days_total"] - 8:
        dec["hire"] = min(3, need - nb)
    if obs["day"] in (8, 20):
        dec["vet_visit"] = True
    pick = {"heatwave": "shade", "cubs_press": "press", "cubs_watch": "keeper", "hpai": "vulnerable", "pump": "fast", "power": "generator",
            "sealion": "vet_full", "school": "accept", "donor": "tour", "sick": "ok"}
    for c in obs["cards"]:
        dec["choices"][c["id"]] = pick[c["kind"]]
        if c["kind"] == "donor" and c["day"] == obs["day"]:
            kp["cats"][0] = min(4, kp["cats"][0] + 2) if kp["cats"][0] < 4 else kp["cats"][0]
    return dec
