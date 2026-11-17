"""Эпизод «Зоопарк»: симулятор месяца без интерфейса, по договору CONTRACT.md.

Детерминирован по зерну (det.py). Скрытое (посетители, исходы событий)
наружу через observe() не выходит.

    g = Game(seed, place, team, scenario)     # place: park / waterfront / subway; team: small / mid / large; scenario: heat / spring / flu
    while not g.done():
        obs = g.observe(); rej = g.decide({...}); g.step()
    g.score()
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from det import Rng, fnv, rnd, cents, clamp, split_lr, days_in_month, weekday  # noqa: E402

SECTIONS = ["pool", "cats", "birds", "yard", "tropic"]
HALF_N = 2
WD_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HALF_RU = ["утро", "день"]
HALF_EN = ["morning", "afternoon"]
FEEDS = ["fish", "meat", "hay", "produce"]


def load_world(name="ny"):
    with open(os.path.join(HERE, "world_" + name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def rej(field, code, ru, en):
    return {"field": field, "code": code, "ru": ru, "en": en}


def card_options(kind):
    return {
        "heatwave": ["shade", "close_midday", "none"], "cubs_press": ["press", "quiet"], "cubs_watch": ["keeper", "camera", "none"],
        "hpai": ["all_indoor", "vulnerable", "none"], "pump": ["fast", "slow"], "power": ["generator", "move", "none"],
        "sealion": ["vet_now", "vet_full", "wait"], "school": ["accept", "decline"], "donor": ["tour", "decline"], "sick": ["ok"],
    }[kind]


DEFAULT = {"heatwave": "close_midday", "cubs_press": "quiet", "cubs_watch": "none", "hpai": "none", "pump": "slow", "power": "none",
           "sealion": "vet_now", "school": "decline", "donor": "decline", "sick": "ok"}

# Варианты, которые запрещает закон: Проверка отказывает
FORBIDDEN = {
    ("heatwave", "none"): ("Морские млекопитающие не остаются на улице при Heat Advisory без тени и укрытия (9 CFR 3.103, пороги NWS): нужно «тень» или «закрыть днём».",
                           "Marine mammals cannot stay outdoors in a Heat Advisory without shade and shelter (9 CFR 3.103, NWS thresholds): choose shade or close midday."),
    ("sealion", "wait"): ("Морской лев не ест больше 24 часов: по 9 CFR 3.105 нужно сразу сообщить ветеринару, ждать нельзя.",
                          "A sea lion off food for more than 24 hours must be reported to the vet at once (9 CFR 3.105); waiting is not allowed."),
}


# ---------- мир ----------
def make_world(seed, place, team, scenario, W):
    sc = W["scenarios"][scenario]
    y, m, d0 = sc["start"]
    n = W["days"]
    R = lambda label: Rng(fnv(str(seed) + ":" + label))
    dim = days_in_month(y, m)
    wx = W["weather"][sc["weather"]]
    wd0 = weekday(y, m, d0)
    rw = R("weather")
    days = []
    for i in range(n):
        date = "%04d-%02d-%02d" % (y, m, d0 + i)
        u = rw.u()
        p_hot = wx["hot_days"] / dim; p_rain = wx["rain_days"] / dim
        w = "hot" if u < p_hot else "rain" if u < p_hot + p_rain else "clear"
        days.append({"date": date, "wd": (wd0 + i) % 7, "weather": w, "holiday": W["holidays"].get(date, 1.0)})
    rn = R("noise")
    noise = [[1 + W["noise"] * (2 * rn.u() - 1) for _ in range(HALF_N)] for _ in range(n)]
    re = R("events")
    used = set()
    E = W["events"]

    def free_day(lo, hi, pred=lambda d: True):
        cand = [d for d in range(lo, hi + 1) if d not in used and pred(d)] or [d for d in range(lo, hi + 1) if pred(d)] or list(range(lo, hi + 1))
        d = cand[re.int(0, len(cand) - 1)]
        used.add(d)
        return d

    events = []
    for k, kind in enumerate(sc["events"]):
        ev = {"id": kind + "_" + str(k), "kind": kind}
        if kind == "heatwave":
            d = free_day(10, 20)
            for j in range(E["heatwave"]["days"]):
                days[d + j]["weather"] = "advisory"; used.add(d + j)
            ev.update({"day": d, "show": d - E["heatwave"]["notice"],
                       "hidden": {}})
        elif kind == "cubs":
            d = free_day(6, 14)
            ev.update({"day": d, "show": None, "hidden": {"boost": E["cubs"]["boost"][re.int(0, 2)], "u_loss": re.u()}})
            events.append(ev)
            events.append({"id": "cubs_press_" + str(k), "kind": "cubs_press", "day": d + 1, "show": d + 1, "parent": ev["id"]})
            events.append({"id": "cubs_watch_" + str(k), "kind": "cubs_watch", "day": d + 1, "show": d + 1, "parent": ev["id"]})
            continue
        elif kind == "hpai":
            d = free_day(4, 9)
            ev.update({"day": d, "show": d, "hidden": {"u": re.u()}})
        elif kind == "inspection":
            ev.update({"day": free_day(6, 27), "show": None})
        elif kind == "pump":
            d = free_day(3, 26)
            ev.update({"day": d, "show": d + 1})        # сломался в день d, карточка вечером дня d про день d+1
        elif kind == "power":
            d = free_day(5, 26)
            ev.update({"day": d, "show": d - E["power"]["notice"], "hidden": {"u": re.u()}})
        elif kind == "sealion":
            d = free_day(3, 26)
            ev.update({"day": d, "show": d + 1, "hidden": {"u": re.u()}})
        elif kind == "school":
            d = free_day(2, 27, lambda x: days[x]["wd"] < 5)
            ev.update({"day": d, "show": d - 3})
        elif kind == "donor":
            d = free_day(5, 25)
            ev.update({"day": d, "show": d - 2, "hidden": {"amount": E["donor"]["amounts"][re.pick_w([0.4, 0.4, 0.2])]}})
        elif kind == "sick":
            d = free_day(1, 27)
            ev.update({"day": d, "show": d})
        elif kind == "no_show":
            ev.update({"day": free_day(2, 27, lambda x: days[x]["wd"] in W["suppliers"]["frozen"]["days"]), "show": None})
        events.append(ev)
    events.sort(key=lambda e: (e["day"], e["id"]))
    return {"seed": seed, "place": place, "team": team, "scenario": scenario, "days": days, "noise": noise, "events": events}


def default_schedule(W):
    row = {"keepers": {s: list(W["sections"][s]["min"]) for s in SECTIONS}, "cashiers": [2, 3], "kiosk": [2, 3], "shows": 0}
    return {str(w): json.loads(json.dumps(row)) for w in range(7)}


class Game:
    def __init__(self, seed, place, team, scenario, world="ny"):
        self.Wd = W = load_world(world)
        self.X = make_world(seed, place, team, scenario, W)
        self.t = 0
        sc = W["scenarios"][scenario]
        y, m, _ = sc["start"]
        self.base_day = W["visitors_year"] * W["places"][place]["mult"] * sc["month_share"] / days_in_month(y, m)
        self.staff = [{"id": "k" + str(i + 1), "start": 0} for i in range(W["teams"][team])]
        self.next_id = W["teams"][team] + 1
        S = W["start_stock"]
        self.freezer = dict(S["freezer"]); self.thawed_next = dict(S["thawed"])
        self.hay = float(S["hay"]); self.produce = [list(x) for x in S["produce"]]
        self.schedule = default_schedule(W)
        self.price = W["prices"]["adult"]; self.free_wed = False
        self.orders = {}
        self.vet_tomorrow = False; self.vet_visits = 0
        self.choices = {}
        self.rep = W["reputation"]["start"]
        self.week_hours = 0.0
        self.violations = []          # (день, секция, причина)
        self.dead = []                # (день, что)
        self.flags = {}               # долгие последствия: hpai_hit_from, cubs_lost
        self.totals = {k: 0.0 for k in ["tickets", "food", "souvenirs", "donations", "school", "cogs", "card_fees", "wages", "feed", "refunds", "electricity", "vet", "event_costs"]}
        self.counts = {"visitors": 0, "demand": 0, "queue_lost": 0, "section_violation_days": 0, "inspection_findings": 0, "deaths": 0, "thaw_waste_kg": 0.0, "produce_waste_kg": 0.0, "shows": 0}
        self.journal = []
        self.last_report = None
        self.pending_rejections = []; self.pending_decisions = []

    # --- служебное ---
    def done(self):
        return self.t >= self.Wd["days"]

    def ev(self, kind):
        return [e for e in self.X["events"] if e["kind"] == kind]

    def choice(self, e):
        return self.choices.get(e["id"], DEFAULT.get(e["kind"]))

    def headcount(self, day, include_pending=False):
        return sum(1 for s in self.staff if include_pending or s["start"] <= day)

    def sick_out(self, day):
        return sum(1 for e in self.ev("sick") if e["day"] <= day < e["day"] + self.Wd["events"]["sick"]["days"])

    def extra_min(self, day):
        """Добавки к минимуму смены от событий: перевод животных при отключении света, экскурсия донора."""
        add = {s: [0, 0] for s in SECTIONS}
        for e in self.ev("power"):
            if e["day"] == day and self.choice(e) == "move":
                add["tropic"] = [1, 1]
        for e in self.ev("donor"):
            if e["day"] == day and self.choice(e) == "tour":
                add["cats"] = [self.Wd["events"]["donor"]["cats_halves"], 0]
        return add

    # --- спрос ---
    def demand_mult(self, day, hidden):
        W = self.Wd; D = self.X["days"][day]
        m = W["weekday_mult"][D["wd"]] * D["holiday"] * W["weather_mult"][D["weather"]]
        notes = []; extra = 0.0
        if D["weather"] == "advisory":
            notes.append("advisory")
        E = W["events"]
        for e in self.X["events"]:
            k = e["kind"]
            if k == "heatwave" and e["day"] <= day < e["day"] + E["heatwave"]["days"] and self.choice(e) == "close_midday":
                m *= E["heatwave"]["close_mult"]; notes.append("closed_midday")
            elif k == "cubs_press" and day >= e["day"] + 1:
                parent = next(x for x in self.X["events"] if x["id"] == e["parent"])
                if self.flags.get("cubs_lost_from") is not None and day >= self.flags["cubs_lost_from"]:
                    continue
                if self.choice(e) == "press":
                    if hidden:
                        m *= 1 + parent["hidden"]["boost"]
                    else:
                        b = E["cubs"]["boost"]; m *= 1 + sum(b) / len(b); extra += 0.1
                else:
                    m *= 1 + E["cubs"]["quiet_boost"]
                notes.append("cubs")
            elif k == "hpai" and day >= e["day"]:
                m *= E["hpai"]["mult"][self.choice(e)]
                if hidden and self.flags.get("hpai_hit_from") is not None and day >= self.flags["hpai_hit_from"]:
                    m *= E["hpai"]["hit_mult"]
                if not hidden and self.choice(e) != "all_indoor":
                    extra += 0.05
                notes.append("hpai")
            elif k == "pump" and day == e["day"] + 1 and self.choice(e) == "slow":
                m *= E["pump"]["slow_mult"]; notes.append("pool_closed_pm")
            elif k == "power" and day == e["day"] and self.choice(e) == "move":
                m *= E["power"]["move_mult"]; notes.append("tropic_closed")
        if not hidden and self.flags.get("hpai_hit_from") is not None and day >= self.flags["hpai_hit_from"]:
            m *= E["hpai"]["hit_mult"]
        if not hidden and self.flags.get("cubs_lost_from") is not None and day >= self.flags["cubs_lost_from"]:
            notes.append("cubs_lost")
        # цена
        pi = self.price / W["prices"]["adult"]
        m *= pi ** (W["elasticity"]["up"] if pi > 1 else W["elasticity"]["down"])
        return m * self.rep, notes, extra

    def expected(self, day, hidden):
        m, notes, extra = self.demand_mult(day, hidden)
        W = self.Wd; D = self.X["days"][day]
        out = []
        for h in range(HALF_N):
            v = self.base_day * W["halves"]["share"][h] * m
            if h == 1 and D["wd"] == 2 and self.free_wed:
                v *= W["free_wed"]["afternoon_mult"]
            out.append(v)
        return out, notes, extra

    # --- наблюдение ---
    def open_cards(self):
        ev_ = self.t - 1
        cards = []
        for e in self.X["events"]:
            if e.get("show") is None or e["kind"] in ("cubs", "inspection", "no_show"):
                continue
            k = e["kind"]
            deadline = e["day"] - 1 if k in ("heatwave", "power", "school", "donor", "hpai", "sick") else e["day"] - 1
            first = e["show"] - 1
            if k in ("pump", "sealion"):
                first = e["day"]; deadline = e["day"]
            if k in ("cubs_press", "cubs_watch"):
                first = e["day"] - 1; deadline = e["day"] - 1
            if first <= ev_ <= deadline:
                c = {"id": e["id"], "kind": k, "day": e["day"] if k not in ("pump", "sealion") else e["day"] + 1, "options": card_options(k),
                     "chosen": self.choices.get(e["id"]), "default": DEFAULT[k], "decide_by_evening_of": deadline}
                cards.append(c)
        return cards

    def observe(self):
        W = self.Wd; t = self.t; n = W["days"]
        fc = []
        for d in range(t, min(t + 3, n)):
            g, notes, extra = self.expected(d, hidden=False)
            band = W["noise"] + extra
            D = self.X["days"][d]
            fc.append({"day": d, "date": D["date"], "wd": D["wd"], "weather": D["weather"], "notes": notes,
                       "visitors": [rnd(x) for x in g], "low": [rnd(x * (1 - band)) for x in g], "high": [rnd(x * (1 + band)) for x in g]})
        nxt = self.X["days"][t] if t < n else None
        sup = {}
        for s, S in W["suppliers"].items():
            sup[s] = {"days": S["days"], "delivers_tomorrow": nxt is not None and nxt["wd"] in S["days"],
                      "prices_kg": {k: v["price_kg"] for k, v in S["items"].items()},
                      "min_order": S.get("min_order"), "min_kg": S.get("min_kg"), "case_kg": S.get("case_kg"), "bale_kg": S.get("bale_kg")}
        return {
            "day": t, "date": nxt["date"] if nxt else None, "wd": nxt["wd"] if nxt else None, "days_total": n,
            "reputation": round(self.rep, 3),
            "stock": {"freezer": {k: cents(v) for k, v in self.freezer.items()}, "thawed_for_tomorrow": {k: cents(v) for k, v in self.thawed_next.items()},
                      "hay": cents(self.hay), "produce": [[cents(a), b] for a, b in self.produce], "freezer_kg": W["freezer_kg"], "hay_store_kg": W["hay_store_kg"]},
            "need_kg_per_day": {"fish": W["sections"]["pool"]["need_kg"], "meat": W["sections"]["cats"]["need_kg"], "hay": W["sections"]["yard"]["need_kg"],
                                "produce": W["sections"]["birds"]["need_kg"] + W["sections"]["tropic"]["need_kg"]},
            "staff": [dict(s) for s in self.staff], "sick_tomorrow": self.sick_out(t) if t < n else 0,
            "schedule": json.loads(json.dumps(self.schedule)), "min_tomorrow": self.min_for(t) if t < n else None,
            "price": self.price, "free_wed": self.free_wed, "suppliers": sup, "forecast": fc, "cards": self.open_cards(),
            "vet_visits": self.vet_visits, "vet_visits_min": W["vet_visits_min"],
            "yesterday": self.last_report, "totals": {k: cents(v) for k, v in self.totals.items()}, "counts": dict(self.counts),
            "violations": len(self.violations),
        }

    def min_for(self, day):
        add = self.extra_min(day)
        return {s: [self.Wd["sections"][s]["min"][h] + add[s][h] for h in range(HALF_N)] for s in SECTIONS}

    # --- Проверка ---
    def check(self, dec):
        W = self.Wd; t = self.t
        out = []
        ok = {"orders": {}, "choices": {}, "hire": 0, "fire": 0}
        if t >= W["days"]:
            return [rej("day", "over", "Месяц закончился.", "The month is over.")], ok
        nxt = self.X["days"][t]; wd = nxt["wd"]
        cards = {c["id"]: c for c in self.open_cards()}
        # что прислано не в той форме, отклоняется с причиной, а не роняет Проверку
        if not isinstance(dec, dict):
            return [rej("decision", "form", "Решение должно быть объектом.", "A decision must be an object.")], ok
        dec = dict(dec)
        for k in ("choices", "thaw", "orders", "schedule"):
            if dec.get(k) is not None and not isinstance(dec[k], dict):
                out.append(rej(k, "form", "Поле «" + k + "» должно быть объектом.", "Field '" + k + "' must be an object."))
                dec.pop(k)
        # карточки
        for cid, opt in (dec.get("choices") or {}).items():
            if cid not in cards:
                out.append(rej("choices." + cid, "no_card", "Карточки «" + cid + "» сейчас нет.", "There is no card '" + cid + "' now.")); continue
            if opt not in cards[cid]["options"]:
                out.append(rej("choices." + cid, "option", "Нет варианта «" + str(opt) + "».", "No option '" + str(opt) + "'.")); continue
            fb = FORBIDDEN.get((cards[cid]["kind"], opt))
            if fb:
                out.append(rej("choices." + cid, "law", fb[0], fb[1])); continue
            ok["choices"][cid] = opt
        # найм
        hire = dec.get("hire", 0) or 0; fire = dec.get("fire", 0) or 0
        hb = self.headcount(t, include_pending=True)
        if not isinstance(hire, int) or isinstance(hire, bool) or hire < 0 or hire > 3:
            out.append(rej("hire", "range", "Нанять можно от 0 до 3 смотрителей за вечер.", "You can hire 0 to 3 keepers per evening.")); hire = 0
        if not isinstance(fire, int) or isinstance(fire, bool) or fire < 0 or fire > hb:
            out.append(rej("fire", "range", "Уволить можно не больше, чем есть смотрителей (" + str(hb) + ").", "You cannot let go more keepers than you have (" + str(hb) + ").")); fire = 0
        ok["hire"] = hire; ok["fire"] = fire
        hb_after = hb + hire - fire
        # смены
        if "schedule" in dec:
            sch = dec["schedule"]; good = True; S = W["staff"]
            for w in range(7):
                r = sch.get(str(w)) if isinstance(sch, dict) else None
                kp = (r or {}).get("keepers") if isinstance(r, dict) else None
                if not isinstance(kp, dict) or any(not isinstance(kp.get(s), list) or len(kp[s]) != 2 or any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in kp[s]) for s in SECTIONS) \
                        or any(not isinstance(r.get(f), list) or len(r[f]) != 2 or any(not isinstance(x, int) or x < 0 or x > 8 for x in r[f]) for f in ("cashiers", "kiosk")) \
                        or not isinstance(r.get("shows", 0), int) or not 0 <= r.get("shows", 0) <= W["shows"]["max"]:
                    out.append(rej("schedule." + str(w), "form", WD_RU[w] + ": нужны смотрители по пяти секциям на утро и день, кассиры и киоск по два числа (0–8), шоу 0–2.",
                                   WD_EN[w] + ": need keepers for five sections for morning and afternoon, cashiers and kiosk as two numbers (0-8), shows 0-2.")); good = False; continue
                for h in range(HALF_N):
                    if kp["cats"][h] > 0 and kp["cats"][h] < 2 and h == 0:
                        out.append(rej("schedule." + str(w), "two_keepers", WD_RU[w] + " " + HALF_RU[h] + ": в вольер барсов входят вдвоём, а в смене " + str(kp["cats"][h]) + ".",
                                       WD_EN[w] + " " + HALF_EN[h] + ": two keepers enter the snow leopard enclosure together, the shift has " + str(kp["cats"][h]) + ".")); good = False
                    if kp["cats"][0] == 0 and h == 0:
                        out.append(rej("schedule." + str(w), "two_keepers", WD_RU[w] + " утро: вольер барсов убирают утром вдвоём, а в смене никого.",
                                       WD_EN[w] + " morning: the snow leopard enclosure is cleaned in the morning by two keepers, the shift has none.")); good = False
                    if kp["pool"][h] < 1:
                        out.append(rej("schedule." + str(w), "water", WD_RU[w] + " " + HALF_RU[h] + ": в бассейне никого, а хлор и pH воды проверяют каждый день (9 CFR 3.106).",
                                       WD_EN[w] + " " + HALF_EN[h] + ": nobody at the pool, while chlorine and pH are checked daily (9 CFR 3.106).")); good = False
                    if kp["yard"][h] < 1:
                        out.append(rej("schedule." + str(w), "contact", WD_RU[w] + " " + HALF_RU[h] + ": в контактном дворе посетители, а смотрителя в смене нет.",
                                       WD_EN[w] + " " + HALF_EN[h] + ": visitors are in the petting yard, but no keeper is on shift.")); good = False
                    tot = sum(kp[s][h] for s in SECTIONS)
                    if tot > hb_after:
                        out.append(rej("schedule." + str(w), "headcount", WD_RU[w] + " " + HALF_RU[h] + ": " + str(tot) + " смотрителей в смене, а в штате " + str(hb_after) + ".",
                                       WD_EN[w] + " " + HALF_EN[h] + ": " + str(tot) + " keepers on shift, but you employ " + str(hb_after) + ".")); good = False
                    if any(kp[s][h] > S["max_per_half"] for s in SECTIONS):
                        out.append(rej("schedule." + str(w), "space", WD_RU[w] + " " + HALF_RU[h] + ": в одной секции не больше " + str(S["max_per_half"]) + " смотрителей.",
                                       WD_EN[w] + " " + HALF_EN[h] + ": at most " + str(S["max_per_half"]) + " keepers per section.")); good = False
                    if r["cashiers"][h] < 1:
                        out.append(rej("schedule." + str(w), "gate", WD_RU[w] + " " + HALF_RU[h] + ": на кассе никого, вход не откроется.",
                                       WD_EN[w] + " " + HALF_EN[h] + ": nobody at the gate, the zoo cannot open.")); good = False
                sh = r.get("shows", 0)
                for h in range(sh):
                    if kp["pool"][h] < W["shows"]["pool_keepers_needed"]:
                        out.append(rej("schedule." + str(w), "show", WD_RU[w] + ": кормление при публике (" + HALF_RU[h] + ") ведут двое, а бассейн не остаётся без смотрителя: нужно " + str(W["shows"]["pool_keepers_needed"]) + " в бассейне.",
                                       WD_EN[w] + ": a public feeding (" + HALF_EN[h] + ") takes two keepers and the pool is never left alone: need " + str(W["shows"]["pool_keepers_needed"]) + " at the pool.")); good = False
            if good:
                ok["schedule"] = {str(w): {"keepers": {s: list(sch[str(w)]["keepers"][s]) for s in SECTIONS}, "cashiers": list(sch[str(w)]["cashiers"]),
                                            "kiosk": list(sch[str(w)]["kiosk"]), "shows": sch[str(w)].get("shows", 0)} for w in range(7)}
        # разморозка: из того, что в морозилке сейчас
        if "thaw" in dec:
            th = dec["thaw"] or {}; okth = {}
            for k in ("fish", "meat"):
                q = th.get(k, 0)
                have = self.freezer.get(k, 0) + self.thawed_next.get(k, 0)
                if not isinstance(q, (int, float)) or isinstance(q, bool) or q < 0:
                    out.append(rej("thaw." + k, "qty", "Разморозка: нужно число килограммов.", "Thawing: need a number of kilograms.")); continue
                if q > have + 1e-9:
                    out.append(rej("thaw." + k, "stock", "Разморозить " + str(q) + " кг нельзя: в морозилке " + ("%.1f" % have) + " кг.",
                                   "Cannot thaw " + str(q) + " kg: the freezer holds " + ("%.1f" % have) + " kg.")); continue
                okth[k] = float(q)
            ok["thaw"] = okth
        # заказы
        new_thaw = {k: (ok.get("thaw") or {}).get(k, self.thawed_next.get(k, 0.0)) for k in ("fish", "meat")}
        freezer_after = sum(self.freezer.values()) + sum(self.thawed_next.values()) - sum(new_thaw.values())
        for s, items in (dec.get("orders") or {}).items():
            if s not in W["suppliers"]:
                out.append(rej("orders." + s, "no_supplier", "Нет поставщика «" + s + "».", "No supplier '" + s + "'.")); continue
            S = W["suppliers"][s]
            if items is not None and not isinstance(items, dict):
                out.append(rej("orders." + s, "form", S["ru"] + ": заказ пишется как «товар: килограммы».",
                               S["en"] + ": an order is written as 'item: kilograms'.")); continue
            bad = False
            for it, q in (items or {}).items():
                if it not in S["items"]:
                    out.append(rej("orders." + s, "no_item", S["ru"] + " не возит «" + it + "».", S["en"] + " does not carry '" + it + "'.")); bad = True
                elif not isinstance(q, (int, float)) or isinstance(q, bool) or q < 0:
                    out.append(rej("orders." + s, "qty", "Количество должно быть числом килограммов.", "Quantity must be kilograms.")); bad = True
                elif S.get("case_kg") and q % S["case_kg"]:
                    out.append(rej("orders." + s, "case", S["ru"] + ": мороженое идёт коробками по " + str(S["case_kg"]) + " кг, а заказано " + str(q) + ".",
                                   S["en"] + ": frozen feed comes in " + str(S["case_kg"]) + " kg cases, ordered " + str(q) + ".")); bad = True
                elif S.get("bale_kg") and q % S["bale_kg"]:
                    out.append(rej("orders." + s, "bale", S["ru"] + ": сено тюками по " + str(S["bale_kg"]) + " кг.", S["en"] + ": hay comes in " + str(S["bale_kg"]) + " kg bales.")); bad = True
            if bad:
                continue
            items = {k: v for k, v in (items or {}).items() if v > 0}
            if not items:
                continue
            if wd not in S["days"]:
                out.append(rej("orders." + s, "day", S["ru"] + " возит только " + ", ".join(WD_RU[x] for x in S["days"]) + ", а завтра " + WD_RU[wd] + ".",
                               S["en"] + " delivers only " + ", ".join(WD_EN[x] for x in S["days"]) + "; tomorrow is " + WD_EN[wd] + ".")); continue
            total = cents(sum(S["items"][k]["price_kg"] * q for k, q in items.items()))
            kg = sum(items.values())
            if S.get("min_order") and total < S["min_order"]:
                out.append(rej("orders." + s, "min", S["ru"] + ": заказ $" + ("%.2f" % total) + " меньше минимума $" + str(S["min_order"]) + ".",
                               S["en"] + ": order $" + ("%.2f" % total) + " is below the $" + str(S["min_order"]) + " minimum.")); continue
            if S.get("min_kg") and kg < S["min_kg"]:
                out.append(rej("orders." + s, "min", S["ru"] + ": меньше " + str(S["min_kg"]) + " кг не возит.", S["en"] + ": minimum " + str(S["min_kg"]) + " kg.")); continue
            if s == "frozen" and freezer_after + kg > W["freezer_kg"] + 1e-9:
                out.append(rej("orders.frozen", "freezer", "Морозилка вмещает " + str(W["freezer_kg"]) + " кг, а с заказом выйдет " + str(rnd(freezer_after + kg)) + ".",
                               "The freezer holds " + str(W["freezer_kg"]) + " kg; with this order it would be " + str(rnd(freezer_after + kg)) + ".")); continue
            if s == "hay" and self.hay + kg > W["hay_store_kg"] + 1e-9:
                out.append(rej("orders.hay", "store", "Сенник вмещает " + str(W["hay_store_kg"]) + " кг, а с заказом выйдет " + str(rnd(self.hay + kg)) + ".",
                               "The hay store holds " + str(W["hay_store_kg"]) + " kg; with this order it would be " + str(rnd(self.hay + kg)) + ".")); continue
            ok["orders"][s] = {"items": items, "total": total}
        # цена
        if "price" in dec:
            p = dec["price"]; lo, hi = W["prices"]["bounds"]; base = W["prices"]["adult"]
            if not isinstance(p, (int, float)) or isinstance(p, bool) or p < base * lo or p > base * hi:
                out.append(rej("price", "bounds", "Взрослый билет от $" + ("%.2f" % (base * lo)) + " до $" + ("%.2f" % (base * hi)) + ".",
                               "Adult ticket between $" + ("%.2f" % (base * lo)) + " and $" + ("%.2f" % (base * hi)) + "."))
            else:
                ok["price"] = cents(p)
        if "free_wed" in dec:
            if isinstance(dec["free_wed"], bool):
                ok["free_wed"] = dec["free_wed"]
            else:
                out.append(rej("free_wed", "form", "Бесплатные часы в среду: да или нет.", "Free Wednesday hours: true or false."))
        if "vet_visit" in dec:
            if isinstance(dec["vet_visit"], bool):
                ok["vet_visit"] = dec["vet_visit"]
            else:
                out.append(rej("vet_visit", "form", "Визит ветеринара: да или нет.", "Vet visit: true or false."))
        return out, ok

    def decide(self, dec):
        out, ok = self.check(dec)
        t = self.t
        for s, o in ok["orders"].items():
            if s in self.orders:
                self.totals["feed"] -= self.orders[s]["total"]
            self.orders[s] = o
            self.totals["feed"] += o["total"]
        if "thaw" in ok:
            for k, q in ok["thaw"].items():
                self.freezer[k] += self.thawed_next.get(k, 0.0)
                self.thawed_next[k] = q
                self.freezer[k] -= q
        for _ in range(ok["hire"]):
            self.staff.append({"id": "k" + str(self.next_id), "start": t + self.Wd["staff"]["hire_delay_days"]}); self.next_id += 1
        for _ in range(ok["fire"]):
            ks = sorted(self.staff, key=lambda s: (-s["start"], -int(s["id"][1:])))
            self.staff.remove(ks[0])
        if "schedule" in ok:
            self.schedule = ok["schedule"]
        if "price" in ok:
            self.price = ok["price"]
        if "free_wed" in ok:
            self.free_wed = ok["free_wed"]
        if "vet_visit" in ok:
            self.vet_tomorrow = ok["vet_visit"]
        self.choices.update(ok["choices"])
        self.pending_rejections += out
        self.pending_decisions.append(json.loads(json.dumps(dec)))  # копия: журнал не меняется, если игрок потом правит свой dict
        return out

    # --- день ---
    def step(self):
        W = self.Wd; t = self.t; X = self.X; E = W["events"]; S = W["staff"]
        D = X["days"][t]
        rep = {"day": t, "date": D["date"], "wd": D["wd"], "weather": D["weather"], "events": []}
        costs_ev = 0.0; vet_cost = 0.0
        viol = {s: [] for s in SECTIONS}
        # карточки с ценой
        for e in X["events"]:
            k = e["kind"]; ch = self.choice(e) if k in DEFAULT else None
            if k == "heatwave" and e["day"] == t and ch == "shade":
                costs_ev += E["heatwave"]["shade_cost"]; rep["events"].append("shade")
            if k == "cubs_press" and e["day"] == t and ch == "press":
                costs_ev += E["cubs"]["press_cost"]; rep["events"].append("press")
            if k == "cubs_watch" and e["day"] <= t < e["day"] + E["cubs"]["watch_days"]:
                if ch == "keeper":
                    costs_ev += E["cubs"]["watch_cost_night"]
                elif ch == "camera" and e["day"] == t:
                    costs_ev += E["cubs"]["cam_cost"]
            if k == "pump" and e["day"] + 1 == t:
                costs_ev += E["pump"]["fast_cost"] if ch == "fast" else E["pump"]["slow_cost"]
            if k == "power" and e["day"] == t and ch == "generator":
                costs_ev += E["power"]["generator_cost"]
            if k == "sealion" and e["day"] + 1 == t:
                vet_cost += E["sealion"]["vet_full_cost"] if ch == "vet_full" else S["vet"]["emergency"]
        # поставки утром
        delivered = {}
        no_show = any(e["day"] == t for e in self.ev("no_show"))
        for s, o in self.orders.items():
            if s == "frozen" and no_show:
                self.totals["refunds"] += o["total"]; rep["events"].append("no_delivery_frozen"); continue
            for it, q in o["items"].items():
                if it in ("fish", "meat"):
                    self.freezer[it] += q
                elif it == "hay":
                    self.hay += q
                elif it == "produce":
                    self.produce.append([float(q), t + W["suppliers"]["produce"]["shelf_days"] - 1])
            delivered[s] = o["items"]
        self.orders = {}
        rep["delivered"] = delivered
        # люди
        row = self.schedule[str(D["wd"])]
        avail = max(0, self.headcount(t) - self.sick_out(t))
        on = {s: [0, 0] for s in SECTIONS}
        cut_order = ["birds", "tropic", "yard", "cats", "pool"]
        for h in range(HALF_N):
            want = {s: row["keepers"][s][h] for s in SECTIONS}
            over = sum(want.values()) - avail
            for s in cut_order:
                while over > 0 and want[s] > 0:
                    want[s] -= 1; over -= 1
            for s in SECTIONS:
                on[s][h] = want[s]
        mins = self.min_for(t)
        for s in SECTIONS:
            for h in range(HALF_N):
                if on[s][h] < mins[s][h]:
                    viol[s].append("care")
        shows = 0
        for h in range(min(row.get("shows", 0), HALF_N)):
            if on["pool"][h] >= W["shows"]["pool_keepers_needed"] and not any(e["kind"] == "pump" and e["day"] + 1 == t and self.choice(e) == "slow" for e in X["events"]):
                shows += 1
        # экскурсия донора
        donation_extra = 0.0
        for e in self.ev("donor"):
            if e["day"] == t and self.choice(e) == "tour":
                if on["cats"][0] >= W["sections"]["cats"]["min"][0] + E["donor"]["cats_halves"]:
                    donation_extra += e["hidden"]["amount"]; rep["events"].append("donor_" + str(e["hidden"]["amount"]))
                else:
                    self.rep = clamp(self.rep - 0.02, W["reputation"]["min"], W["reputation"]["max"]); rep["events"].append("donor_cancelled")
        # корм
        fed = {}
        need = {s: W["sections"][s]["need_kg"] for s in SECTIONS}
        th = self.thawed_next
        for feed, s in (("fish", "pool"), ("meat", "cats")):
            given = min(th.get(feed, 0.0), need[s])
            waste = th.get(feed, 0.0) - given
            self.counts["thaw_waste_kg"] = cents(self.counts["thaw_waste_kg"] + waste)
            fed[s] = given / need[s]
        self.thawed_next = {"fish": 0.0, "meat": 0.0}
        h_given = min(self.hay, need["yard"]); self.hay -= h_given; fed["yard"] = h_given / need["yard"]
        p_need = need["birds"] + need["tropic"]; p_left = p_need
        self.produce.sort(key=lambda x: x[1])
        for lot in self.produce:
            if lot[1] >= t and p_left > 0:
                use = min(lot[0], p_left); lot[0] -= use; p_left -= use
        p_ratio = (p_need - p_left) / p_need
        fed["birds"] = fed["tropic"] = p_ratio
        for s in SECTIONS:
            if fed[s] < W["fed_ok"]:
                viol[s].append("underfed")
        # морской лев: без полного обследования болезнь возвращается
        for e in self.ev("sealion"):
            if t == e["day"] + 4 and self.choice(e) == "vet_now" and e["hidden"]["u"] < E["sealion"]["relapse_risk"]:
                viol["pool"].append("sealion_relapse"); vet_cost += S["vet"]["emergency"]; rep["events"].append("sealion_relapse")
        # свет в тропическом доме
        for e in self.ev("power"):
            if e["day"] == t and self.choice(e) == "none":
                viol["tropic"].append("cold"); rep["events"].append("tropic_cold")
                if e["hidden"]["u"] < E["power"]["death_risk"]:
                    self.dead.append((t, "tropic")); rep["events"].append("death_tropic")
        # птичий грипп
        for e in self.ev("hpai"):
            if t == e["day"] + 4 and e["hidden"]["u"] < E["hpai"]["risk"][self.choice(e)] and self.flags.get("hpai_hit_from") is None:
                self.flags["hpai_hit_from"] = t + 1; self.dead.append((t, "birds")); rep["events"].append("hpai_hit")
                self.rep = clamp(self.rep + E["hpai"]["hit_rep"], W["reputation"]["min"], W["reputation"]["max"])
        # котята
        for e in self.ev("cubs"):
            if t == e["day"]:
                rep["events"].append("cubs_born")
            if t == e["day"] + 3 and self.flags.get("cubs_lost_from") is None:
                watch = next((x for x in self.X["events"] if x["kind"] == "cubs_watch" and x.get("parent") == e["id"]), None)
                ch = self.choice(watch) if watch else "none"
                risk = {"keeper": 0.0, "camera": 0.05, "none": E["cubs"]["loss_risk"]}[ch]
                if e["hidden"]["u_loss"] < risk:
                    self.flags["cubs_lost_from"] = t + 1; self.dead.append((t, "cubs")); rep["events"].append("cubs_lost")
        # посетители
        exp, notes, _ = self.expected(t, hidden=True)
        rep["notes"] = notes
        mix = W["mix"]; P = W["prices"]
        tickets = food = souv = don = 0.0; adm_all = 0; demand_all = 0; queue = 0; tx = 0
        # теснота: мир без ключа crowding считается ровно как раньше, старые журналы не меняются
        CR = W.get("crowding"); crowd = 0.0
        by_half = []
        for h in range(HALF_N):
            g = rnd(exp[h] * X["noise"][t][h])
            demand_all += g
            cats = dict(zip(["adult", "child", "group", "member", "free"], split_lr(g, [mix["adult"], mix["child"], mix["group"], mix["member"], mix["free"]])))
            free_pm = (h == 1 and D["wd"] == 2 and self.free_wed)
            need_gate = cats["adult"] + cats["child"] + cats["free"]
            cap = rnd(row["cashiers"][h] * W["gate_per_cashier_hour"] * W["halves"]["hours"][h])
            lost = max(0, need_gate - cap)
            # кто не прошёл, уходит: взрослые и дети пропорционально
            if lost:
                la, lc, lf = split_lr(lost, [cats["adult"], cats["child"], cats["free"]]) if need_gate else (0, 0, 0)
                cats["adult"] -= la; cats["child"] -= lc; cats["free"] -= lf
            queue += lost
            adm = sum(cats.values())
            if free_pm:
                tk = 0.0
            else:
                tk = cats["adult"] * self.price + cats["child"] * self.price * P["child_share"] + cats["group"] * P["group"]
            kcap = row["kiosk"][h] * W["kiosk_per_worker_hour"] * W["halves"]["hours"][h]
            buyers = min(adm * 0.7, kcap)
            # когда в половину дня пришло больше, чем зоопарк вмещает без толчеи, посетитель
            # тратит меньше: очередь к киоску, негде сесть, часть вольеров не видно
            over = max(0.0, adm / CR["comfort_per_half"] - 1.0) if CR else 0.0
            drop = min(CR["spend_drop_max"], CR["spend_drop_k"] * over) if CR else 0.0
            crowd = max(crowd, over)
            fd = buyers * W["spend"]["food"] / 0.7 * (1 - drop)
            sv = adm * W["spend"]["souvenir"] * (1 - drop)
            # в бесплатную половину дня жертвуют заметно охотнее: вход по пожертвованию
            dmult = W["free_wed"].get("donation_mult", 1.0) if free_pm else 1.0
            dn = adm * (W["spend"]["donation"] * dmult + W["spend"]["donation_per_show"] * shows)
            tickets += tk; food += fd; souv += sv; don += dn; adm_all += adm; tx += adm
            by_half.append({"half": h, "demand": g, "admitted": adm, "queue_lost": lost, "gate_capacity": cap,
                            "kiosk_short": rnd(adm * 0.7 - buyers), "crowding": round(over, 3)})
        school = 0.0
        for e in self.ev("school"):
            if e["day"] == t and self.choice(e) == "accept":
                kids = E["school"]["kids"]; school = kids * E["school"]["price"]
                food += kids * 3.0; adm_all += kids
                if on["yard"][0] < W["sections"]["yard"]["min"][0] + 1:
                    self.rep = clamp(self.rep - 0.02, W["reputation"]["min"], W["reputation"]["max"]); rep["events"].append("school_unguided")
                else:
                    rep["events"].append("school_" + str(kids))
        don += donation_extra
        revenue = tickets + food + souv + don + school
        cogs = food * W["spend"]["food_cost"] + souv * W["spend"]["souvenir_cost"]
        fee = W["card_share"] * (tickets + food + souv) * W["card_fee_pct"] + W["card_fee_fixed"] * rnd(W["card_share"] * tx * 0.5)
        # зарплата
        kh = sum(on[s][h] * W["halves"]["hours"][h] for s in SECTIONS for h in range(HALF_N))
        paid_h = max(kh, self.headcount(t) * S["keeper"]["salaried_h_week"] / 7.0)   # смотрители на окладе: 40 ч в неделю в любом случае
        wages = paid_h * S["keeper"]["wage"]
        wages += sum(row["cashiers"][h] * W["halves"]["hours"][h] for h in range(HALF_N)) * S["cashier"]["wage"]
        wages += sum(row["kiosk"][h] * W["halves"]["hours"][h] for h in range(HALF_N)) * S["kiosk"]["wage"]
        wages += S["guard"]["count"] * S["guard"]["hours"] * S["guard"]["wage"] + S["vet_tech"]["hours"] * S["vet_tech"]["wage"]
        wages *= 1 + S["burden"]
        self.week_hours += kh
        ot = 0.0
        if D["wd"] == 6 or t == W["days"] - 1:
            over = self.week_hours - S["overtime_after_h"] * max(1, self.headcount(t))
            if over > 0:
                ot = over * S["keeper"]["wage"] * (S["overtime_mult"] - 1) * (1 + S["burden"])
            rep["overtime"] = cents(ot); self.week_hours = 0.0
        wages = cents(wages + ot)
        if self.vet_tomorrow:
            vet_cost += S["vet"]["wage"] * S["vet"]["visit_hours"]; self.vet_visits += 1; rep["events"].append("vet_visit")
        self.vet_tomorrow = False
        elec = W["electricity"]["kwh_day"] * W["electricity"]["price"] * (1 + (W["electricity"]["advisory_extra"] if D["weather"] == "advisory" else 0))
        # списания
        wasted_p = sum(a for a, b in self.produce if b <= t)
        self.produce = [[a, b] for a, b in self.produce if b > t and a > 1e-9]
        self.counts["produce_waste_kg"] = cents(self.counts["produce_waste_kg"] + wasted_p)
        # нарушения дня
        vdays = [s for s in SECTIONS if viol[s]]
        for s in vdays:
            self.violations.append((t, s, viol[s]))
        self.counts["section_violation_days"] += len(vdays)
        # инспекция
        for e in self.ev("inspection"):
            if e["day"] == t:
                lb = E["inspection"]["lookback"]
                found = [v for v in self.violations if t - lb < v[0] <= t]
                self.counts["inspection_findings"] += len(found)
                rep["events"].append("inspection_" + str(len(found)))
        # репутация
        R = W["reputation"]
        qrate = queue / max(1, demand_all)
        closed = sum(1 for n_ in notes if n_ in ("closed_midday", "pool_closed_pm", "tropic_closed"))
        self.rep = clamp(self.rep + R["drift"] - R["queue_k"] * qrate - R["violation"] * len(vdays) - R["closed_k"] * closed
                         + W["shows"]["rep"] * shows - (CR["rep_k"] * crowd if CR else 0.0), R["min"], R["max"])
        # итоги дня
        T = self.totals
        T["tickets"] += tickets; T["food"] += food; T["souvenirs"] += souv; T["donations"] += don; T["school"] += school
        T["cogs"] += cogs; T["card_fees"] += fee; T["wages"] += wages; T["electricity"] += elec; T["vet"] += vet_cost; T["event_costs"] += costs_ev
        for k in T:
            T[k] = cents(T[k])
        C = self.counts
        C["visitors"] += adm_all; C["demand"] += demand_all; C["queue_lost"] += queue; C["shows"] += shows; C["deaths"] = len(self.dead)
        rep.update({"by_half": by_half, "keepers_on": on, "available_keepers": avail, "shows": shows, "fed": {s: round(fed[s], 3) for s in SECTIONS},
                    "violations": {s: viol[s] for s in vdays}, "revenue": cents(revenue), "cogs": cents(cogs), "card_fee": cents(fee), "wages": wages,
                    "vet": cents(vet_cost), "electricity": cents(elec), "event_costs": cents(costs_ev), "visitors": adm_all, "demand": demand_all, "queue_lost": queue,
                    "reputation": round(self.rep, 4), "crowding": round(crowd, 3),
                    "stock_after": {"freezer": {k: cents(v) for k, v in self.freezer.items()}, "hay": cents(self.hay), "produce": cents(sum(a for a, _ in self.produce))},
                    "decisions": self.pending_decisions, "rejections": self.pending_rejections})
        self.pending_decisions = []; self.pending_rejections = []
        self.journal.append(rep)
        self.last_report = {k: rep[k] for k in ("day", "date", "weather", "visitors", "demand", "queue_lost", "revenue", "violations", "fed", "events", "shows", "reputation")}
        self.t += 1

    def score(self):
        W = self.Wd; T = self.totals; C = self.counts; P = W["penalties"]
        price = {k: W["suppliers"]["frozen"]["items"][k]["price_kg"] for k in ("fish", "meat")}
        leftover = sum(self.freezer[k] * price[k] for k in price) + self.hay * W["suppliers"]["hay"]["items"]["hay"]["price_kg"]
        vet_missing = 1 if self.done() and self.vet_visits < W["vet_visits_min"] else 0
        parts = {
            "revenue": cents(T["tickets"] + T["food"] + T["souvenirs"] + T["donations"] + T["school"]),
            "cogs": -T["cogs"], "card_fees": -T["card_fees"], "wages": -T["wages"],
            "feed": -cents(T["feed"] - T["refunds"]), "leftover_feed": cents(leftover),
            "electricity": -T["electricity"], "vet": -T["vet"], "event_costs": -T["event_costs"],
            "section_violations": -C["section_violation_days"] * P["section_day"],
            "inspection": -C["inspection_findings"] * P["inspection"],
            "deaths": -len(self.dead) * P["death"],
            "queue": -C["queue_lost"] * P["queue"],
            "vet_visits": -vet_missing * P["vet_visits_missing"],
        }
        profit = sum(v for k, v in parts.items() if k not in ("section_violations", "inspection", "deaths", "queue", "vet_visits"))
        return {"score": cents(sum(parts.values())), "profit": cents(profit), "parts": parts, "counts": dict(C), "vet_visits": self.vet_visits}


def play(seed, place, team, scenario, policy, world="ny"):
    g = Game(seed, place, team, scenario, world)
    rejs = []
    while not g.done():
        rejs += g.decide(policy(g.observe()))
        g.step()
    return g, rejs


SETTINGS = ("place", "team", "scenario")
MAX_DECISIONS_PER_STEP = 10


def replay(seed, settings, decisions, world="ny"):
    """Пересчёт счёта из журнала решений (LEADERBOARD.md). decisions: [(шаг, решение), ...] в порядке подачи,
    как в g.journal[шаг]["decisions"]. Шаг без решений проходит с прежним планом. Возвращает {"score", "parts", "counts"}.
    Журнал чужой, поэтому всё проверяется: неверный ввод даёт ValueError, а не счёт."""
    W = load_world(world)
    if not isinstance(seed, int) or isinstance(seed, bool) or not (0 <= seed < 2 ** 32):
        raise ValueError("seed: целое от 0 до 2^32-1")
    if not isinstance(settings, dict) or set(settings) != set(SETTINGS):
        raise ValueError("settings: ровно place, team, scenario")
    for k, pool in (("place", W["places"]), ("team", W["teams"]), ("scenario", W["scenarios"])):
        names = sorted(x for x in pool if not x.startswith("_"))   # _tag это пометка источника, а не значение
        if settings[k] not in names:
            raise ValueError("settings.%s: одно из %s" % (k, names))
    g = Game(seed, settings["place"], settings["team"], settings["scenario"], world)
    by_step = {}
    last = -1
    for item in decisions:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("decisions: пары (шаг, решение)")
        t, dec = item
        if not isinstance(t, int) or isinstance(t, bool) or t < last or not (0 <= t < len(g.X["days"])):
            raise ValueError("decisions: шаги по порядку и в пределах месяца")
        if not isinstance(dec, dict):
            raise ValueError("decisions: решение должно быть объектом")
        last = t
        by_step.setdefault(t, []).append(json.loads(json.dumps(dec)))
        if len(by_step[t]) > MAX_DECISIONS_PER_STEP:
            raise ValueError("decisions: не больше %d решений на шаг" % MAX_DECISIONS_PER_STEP)
    while not g.done():
        for dec in by_step.get(g.t, []):
            try:
                g.decide(dec)
            except Exception as e:  # Проверка отказывает с причиной; падение значит журнал не от этой игры
                raise ValueError("шаг %d: решение не разбирается (%s)" % (g.t, type(e).__name__))
        g.step()
    s = g.score()
    return {"score": s["score"], "parts": s["parts"], "counts": s["counts"]}


def decisions_of(journal):
    """Журнал дней (g.journal или runs/*.json["journal"]) -> decisions для replay."""
    return [(d["day"], dec) for d in journal for dec in d["decisions"]]

