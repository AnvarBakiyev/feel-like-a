"""Тестовые машинисты. Не Extella: нужны, чтобы проверить физику, расписание и счёт.

Видят только наблюдение (то же, что игрок) и паспорт поезда (открытые данные).
full: полная тяга до допустимой скорости, тормоз к станции по расчёту.
careful: то же, плюс выбег, когда идёт с опережением графика, песок при боксовании, толкач на мокром Готарде.
"""


def _brake_to_stop(o, g, lever):
    st = o["next_stop"]
    if st is None or o["at_station"]:
        return lever
    sv = g.T["brake"]["service_ms2"]; gr = 9.81 * min(o["grade_permille"], 0.0) / 1000.0
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


_CAP = {}


def full(o, g):
    """При боксовании сбрасывает рычаг на 3 % за шаг, потом понемногу добавляет: так держит тягу у предела сцепления."""
    cap = _CAP.get(id(g), 1.0)
    cap = cap * 0.97 if o["slip"] else min(1.0, cap + 0.005)
    _CAP[id(g)] = cap
    if o["at_station"]:
        return {"lever": cap} if o["t"] >= o["due_s"] else None
    tgt = min(o["permitted_kmh"] - 3, o["limit_kmh"] - 1)
    v = o["v_kmh"]
    lever = max(-1.0, min(cap, (tgt - v) / 4.0))
    return {"lever": _brake_to_stop(o, g, lever)}


def careful(o, g):
    if o["at_station"]:
        d = {"lever": 1.0} if o["t"] >= o["due_s"] else {"lever": 0.0}
        if not o["departed"] and o["pusher_available"] and o["weather"] != "dry" and not o["pusher"]:
            d["pusher"] = True
        return d
    d = full(o, g)
    st = o["next_stop"]; v = o["v_kmh"] / 3.6
    if st and st["arr_s"] is not None and v > 5 and d["lever"] >= 0:
        left = st["arr_s"] - o["t"]
        if left > 0 and st["dist_m"] / v < 0.92 * left and o["v_kmh"] > 0.6 * o["limit_kmh"] and o["grade_permille"] <= 5:
            d["lever"] = 0.0
    if o["slip"]:
        if o["sand_left_s"] > 0:
            d["sand"] = True
    elif o["sand_on"] and o["v_kmh"] > 30:
        d["sand"] = False
    return d
