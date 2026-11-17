"""Месяц кофейни: симулятор без интерфейса.

Детерминирован по зерну. Свой генератор (mulberry32) и своё округление,
чтобы перенести на JS один к одному. Скрытое (спрос, исходы событий)
наружу через observe() не выходит.

Ход: g = Game(seed, street, money, scenario); вечер перед днём t:
    obs = g.observe(); rej = g.decide({...}); g.step()
после 30 шагов g.score().
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
DRINKS = ["latte", "cold_brew", "drip", "tea"]
DP_N = 3
WD_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SUP_RU = {"dairy": "Молочный поставщик", "roaster": "Обжарщик", "bakery": "Пекарня"}
SUP_EN = {"dairy": "The dairy", "roaster": "The roaster", "bakery": "The bakery"}
ITEM_RU = {"latte": "латте", "cold_brew": "колд-брю", "drip": "фильтр-кофе", "tea": "чай", "croissant": "круассан"}
DP_RU = ["утро", "день", "вечер"]
DP_EN = ["morning", "midday", "evening"]


# ---------- переносимые основы ----------
def rnd(x):
    return int(math.floor(x + 0.5))


def cents(x):
    return math.floor(x * 100 + 0.5) / 100


def fnv(s):
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def imul(a, b):
    return (a * b) & 0xFFFFFFFF


class Rng:
    def __init__(self, seed_int):
        self.a = seed_int & 0xFFFFFFFF

    def u(self):
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = imul(t ^ (t >> 15), t | 1)
        t = t ^ ((t + imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF)
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    def int(self, lo, hi):  # включительно
        return lo + int(math.floor(self.u() * (hi - lo + 1)))

    def pick_w(self, weights):
        x = self.u() * sum(weights); acc = 0.0
        for i, w in enumerate(weights):
            acc += w
            if x < acc:
                return i
        return len(weights) - 1


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def split_lr(n, shares):
    """Делит n на целые части по долям, наибольшие остатки, порядок стабилен."""
    tot = sum(shares)
    raw = [n * s / tot for s in shares]
    base = [int(math.floor(r)) for r in raw]
    rest = n - sum(base)
    order = sorted(range(len(shares)), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:rest]:
        base[i] += 1
    return base


def days_in_month(y, m):
    return [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]


def weekday(y, m, d):  # пн=0, Сакамото
    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    yy = y - 1 if m < 3 else y
    w = (yy + yy // 4 - yy // 100 + yy // 400 + t[m - 1] + d) % 7  # вс=0
    return (w + 6) % 7


def load_city(name="ny"):
    with open(os.path.join(HERE, "city_" + name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def rej(field, code, ru, en):
    return {"field": field, "code": code, "ru": ru, "en": en}


def _int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _form(field, what_ru, what_en):
    return rej(field, "form", "Неверная форма поля «" + field + "»: " + what_ru + ".", "Wrong form of '" + field + "': " + what_en + ".")


EMPTY_OK = {"orders": {}, "prices": {}, "hire": 0, "fire": 0, "buy": [], "choices": {}}


# ---------- мир ----------
def make_world(seed, street, money, scenario, C):
    sc = C["scenarios"][scenario]
    y, m, d0 = sc["start"]
    n = C["days"]
    R = lambda label: Rng(fnv(str(seed) + ":" + label))
    days = []
    wd0 = weekday(y, m, d0)
    wx = C["weather"][sc["weather"]]
    dim = days_in_month(y, m)
    rw = R("weather")
    for i in range(n):
        dd = d0 + i
        date = "%04d-%02d-%02d" % (y, m, dd)
        u = rw.u()
        p_snow = wx["snow_days"] / dim
        p_rain = wx["rain_days"] / dim
        w = "snow" if u < p_snow else "rain" if u < p_snow + p_rain else "clear"
        days.append({"date": date, "wd": (wd0 + i) % 7, "weather": w, "holiday": C["holidays"].get(date, 1.0)})
    rn = R("noise")
    noise = [[1 + C["noise"] * (2 * rn.u() - 1) for _ in range(DP_N)] for _ in range(n)]

    re = R("events")
    used = set()
    events = []

    def free_day(lo, hi, pred=lambda d: True):
        cand = [d for d in range(lo, hi + 1) if d not in used and pred(d)]
        if not cand:
            cand = [d for d in range(lo, hi + 1) if pred(d)] or list(range(lo, hi + 1))
        d = cand[re.int(0, len(cand) - 1)]
        used.add(d)
        return d

    E = C["events"]
    dairy_days = C["suppliers"]["dairy"]["days"]
    for k, kind in enumerate(sc["events"]):
        ev = {"id": kind + "_" + str(k), "kind": kind}
        if kind == "blogger":
            ev["day"] = free_day(3, 20); ev["show"] = ev["day"] - 2
            ev["hidden"] = {"boost": E["blogger"]["outcomes"][re.pick_w(E["blogger"]["weights"])]}
        elif kind == "repair":
            ev["day"] = free_day(5, 20); ev["show"] = ev["day"] - E["repair"]["notice"]
            ev["hidden"] = {"recover": E["repair"]["sign_recover"][re.int(0, 2)]}
        elif kind == "inspection":
            ev["day"] = free_day(4, 27); ev["show"] = ev["day"] - E["inspection"]["notice"]
            ev["hidden"] = {"u": re.u()}
        elif kind == "breakdown":
            ev["day"] = free_day(2, 27); ev["show"] = ev["day"] + 1  # карточка вечером дня поломки
        elif kind == "sick":
            ev["day"] = free_day(1, 27); ev["show"] = ev["day"]
        elif kind == "dairy_up":
            ev["day"] = free_day(5, 20); ev["show"] = ev["day"] - E["dairy_up"]["notice"]
        elif kind == "catering":
            ev["day"] = free_day(2, 27, lambda d: days[d]["wd"] < 5); ev["show"] = ev["day"]
        elif kind == "fair":
            ev["day"] = free_day(7, 27, lambda d: days[d]["wd"] == 5); ev["show"] = ev["day"] - E["fair"]["notice"]
        elif kind == "no_show":
            ev["day"] = free_day(2, 27, lambda d: days[d]["wd"] in dairy_days); ev["show"] = None
        elif kind == "blizzard":
            ev["day"] = free_day(8, 24); ev["show"] = ev["day"] - E["blizzard"]["notice"]
            ev["hidden"] = {"keep": E["blizzard"]["severity"][re.int(0, 2)]}
            days[ev["day"]]["weather"] = "blizzard"
        elif kind == "competitor":
            ev["day"] = E["competitor"]["open_day"]; used.add(ev["day"]); ev["show"] = ev["day"] - 2
            ev["hidden"] = {"s": E["competitor"]["strength"][re.int(0, 2)]}
        events.append(ev)
    events.sort(key=lambda e: (e["day"], e["id"]))
    ri = R("invest")
    hidden_inv = {"marketing_lift": C["investments"]["marketing"]["lift"][ri.int(0, 2)]}
    return {"hidden_inv": hidden_inv, "seed": seed, "street": street, "money": money, "scenario": scenario, "days": days, "noise": noise, "events": events}


# Карточки: варианты и вечер, до которого нужно решить. «Вечер e» = перед днём e+1.
def card_options(kind):
    return {
        "blogger": ["accept", "decline"], "repair": ["sign", "none"], "inspection": ["clean", "none"],
        "breakdown": ["fast", "slow"], "sick": ["agency", "short"], "dairy_up": ["ok"], "catering": ["accept", "decline"],
        "fair": ["ok"], "blizzard": ["open", "close"], "competitor": ["loyalty", "promo", "none"], "complaint": ["coupons", "reply", "ignore"],
    }[kind]


DEFAULT = {"blogger": "decline", "repair": "none", "inspection": "none", "breakdown": "slow", "sick": "short", "dairy_up": "ok",
           "catering": "decline", "fair": "ok", "blizzard": "open", "competitor": "none", "complaint": "ignore", "no_show": "none"}


# ---------- игра ----------
class Game:
    def __init__(self, seed, street, money, scenario, city="ny"):
        self.C = C = load_city(city)
        self.W = make_world(seed, street, money, scenario, C)
        self.t = 0
        st = C["streets"][street]
        self.base = st["guests"]
        self.rent_day = st["rent_month"] / C["days"]
        self.cash = float(C["money"][money])
        self.loan = 0.0
        self.rep = C["reputation"]["start"]
        self.prices = {k: C["menu"][k]["price"] for k in DRINKS + ["croissant"]}
        self.discounts = []
        S = C["staff"]
        self.staff = [{"id": "b" + str(i + 1), "role": "barista", "start": 0} for i in range(S["start_baristas"])]
        self.staff += [{"id": "l" + str(i + 1), "role": "lead", "start": 0} for i in range(S["start_leads"])]
        self.next_id = S["start_baristas"] + 1
        self.schedule = {str(w): {"barista": [2, 2, 1], "lead": [1, 0, 0]} for w in range(7)}
        # склад
        g = self.base
        lat = C["menu"]["latte"]
        milk_day = g * lat["share"] * lat["milk_l"]
        beans_day = g * sum(C["menu"][k]["share"] * C["menu"][k]["beans_g"] for k in DRINKS)
        sd = C["start_stock_days"]
        self.milk = [[cents(milk_day * sd["milk"]), 2]]  # [литры, последний день годности]
        self.beans_g = float(rnd(beans_day * sd["beans"]))
        self.cups = rnd(g * sd["cups"])
        self.croissant = 0
        self.orders = {}  # заказ на день t
        self.choices = {}
        self.cards_extra = []  # карточки, которые рождает ход игры (жалоба)
        self.grade_b_from = None
        self.week_hours = {"barista": 0.0, "lead": 0.0}
        self.totals = {k: 0.0 for k in ["revenue", "purchases", "refunds", "wages", "rent", "fixed", "card_fees", "event_costs", "agency", "investments"]}
        self.counts = {"stockout_guests": 0, "queue_guests": 0, "guests": 0, "demand": 0, "written_off_milk_l": 0.0, "written_off_croissant": 0}
        self.journal = []
        self.last_report = None
        self.pending_rejections = []
        self.pending_decisions = []
        self.bought = {}  # вложение -> день, с которого действует
        self.clean_paid = set()

    def done(self):
        return self.t >= self.C["days"]

    # --- справочные ---
    def ev(self, kind):
        return [e for e in self.W["events"] if e["kind"] == kind]

    def choice(self, e):
        return self.choices.get(e["id"], DEFAULT[e["kind"]])

    def milk_price(self, day):
        p = self.C["suppliers"]["dairy"]["items"]["milk"]["price"]
        for e in self.ev("dairy_up"):
            if day >= e["day"]:
                p = cents(p * (1 + self.C["events"]["dairy_up"]["pct"]))
        return p

    def has(self, inv, day):
        return inv in self.bought and day >= self.bought[inv]

    def headcount(self, role, day, include_pending=False):
        return sum(1 for s in self.staff if s["role"] == role and (include_pending or s["start"] <= day))

    def sick_out(self, day):
        return sum(1 for e in self.ev("sick") if e["day"] <= day <= e["day"] + self.C["events"]["sick"]["days"] - 1)

    def eff_price(self, item, dp):
        p = self.prices[item]
        for d in self.discounts:
            if d["item"] == item and dp in d["dayparts"]:
                p = cents(p * (1 - d["pct"] / 100.0))
        return p

    def cost_of(self, item, day):
        C = self.C
        if item == "croissant":
            return C["suppliers"]["bakery"]["items"]["croissant"]["price"]
        m = C["menu"][item]
        beans = C["suppliers"]["roaster"]["items"]["beans"]
        cups = C["suppliers"]["roaster"]["items"]["cups"]
        milk = C["suppliers"]["dairy"]["items"]["milk"]
        return cents(m["beans_g"] * beans["price"] / beans["grams"] + m["milk_l"] * self.milk_price(day) / milk["liters"]
                     + m["cup"] * cups["price"] / cups["count"] + m["other"])

    # --- спрос: ожидание без шума; hidden=True подставляет скрытые исходы ---
    def demand_mult(self, day, hidden):
        C = self.C; W = self.W; D = W["days"][day]
        m = C["weekday_mult"][D["wd"]] * D["holiday"]
        notes = []
        extra = 0.0
        w = D["weather"]
        if w != "blizzard":
            m *= C["weather_mult"][w]
        for e in W["events"]:
            k = e["kind"]; E = C["events"].get(k, {})
            if k == "fair" and day == e["day"]:
                m *= E["mult"]; notes.append("fair")
            elif k == "repair" and e["day"] <= day < e["day"] + E["days"]:
                loss = 1 - E["mult"]
                if self.choice(e) == "sign":
                    if hidden:
                        loss *= 1 - e["hidden"]["recover"]
                    else:
                        r = E["sign_recover"]; loss *= 1 - sum(r) / len(r); extra += 0.08
                m *= 1 - loss; notes.append("repair")
            elif k == "blogger" and self.choice(e) == "accept" and e["day"] < day <= e["day"] + E["days"]:
                if hidden:
                    m *= 1 + e["hidden"]["boost"]
                else:
                    extra += 0.2
                notes.append("blogger")
            elif k == "blizzard" and day == e["day"]:
                if hidden:
                    m *= e["hidden"]["keep"]
                else:
                    sv = E["severity"]; m *= sum(sv) / len(sv); extra += 0.2
                notes.append("blizzard")
            elif k == "competitor" and day >= e["day"]:
                s = e["hidden"]["s"] if hidden else sum(E["strength"]) / len(E["strength"])
                if not hidden:
                    extra += 0.08
                if self.choice(e) == "promo" and day < e["day"] + E["promo_days"]:
                    s *= 0.5
                pidx = self.price_index(1)
                f = clamp(1 + 1.5 * (pidx - 1) - 2 * (self.rep - 1), 0.5, 1.5)
                m *= 1 - s * f; notes.append("competitor")
        if "marketing" in self.bought:
            I = C["investments"]["marketing"]; d0 = self.bought["marketing"]
            if d0 <= day < d0 + I["days"]:
                if hidden:
                    m *= 1 + W["hidden_inv"]["marketing_lift"]
                else:
                    m *= 1 + sum(I["lift"]) / len(I["lift"]); extra += 0.06
                notes.append("marketing")
        if self.grade_b_from is not None and day >= self.grade_b_from:
            m *= C["events"]["inspection"]["b_mult"]; notes.append("grade_b")
        return m * self.rep, notes, extra

    def price_index(self, dp):
        M = self.C["menu"]
        num = sum(M[k]["share"] * self.eff_price(k, dp) for k in DRINKS)
        den = sum(M[k]["share"] * M[k]["price"] for k in DRINKS)
        return num / den

    def expected_guests(self, day, hidden):
        C = self.C
        m, notes, extra = self.demand_mult(day, hidden)
        out = []
        for dp in range(DP_N):
            pi = self.price_index(dp)
            pm = pi ** (C["elasticity_drinks"]["up"] if pi > 1 else C["elasticity_drinks"]["down"][dp])
            out.append(self.base * C["hours"]["share"][dp] * m * pm)
        return out, notes, extra

    def closed(self, day):
        return any(e["kind"] == "blizzard" and e["day"] == day and self.choice(e) == "close" for e in self.W["events"])

    # --- наблюдение: только то, что знает владелец вечером перед днём t ---
    def open_cards(self):
        t = self.t; ev_ = t - 1  # сегодняшний вечер
        cards = []
        for e in self.W["events"] + self.cards_extra:
            if e.get("show") is None:
                continue
            deadline = e["deadline"] if "deadline" in e else (e["day"] if e["kind"] == "breakdown" else e["day"] - 1)
            # карточка видна с вечера show-1 до вечера deadline
            if e["show"] - 1 <= ev_ <= deadline:
                c = {"id": e["id"], "kind": e["kind"], "day": e["day"], "options": card_options(e["kind"]),
                     "chosen": self.choices.get(e["id"]), "default": DEFAULT[e["kind"]], "decide_by_evening_of": deadline}
                if e["kind"] in ("breakdown",):
                    c["day"] = e["day"] + 1
                cards.append(c)
        return cards

    def observe(self):
        C = self.C; t = self.t
        fc = []
        for d in range(t, min(t + 3, C["days"])):
            g, notes, extra = self.expected_guests(d, hidden=False)
            band = C["noise"] + extra
            D = self.W["days"][d]
            fc.append({"day": d, "date": D["date"], "wd": D["wd"], "weather": D["weather"], "notes": notes,
                       "guests": [rnd(x) for x in g], "low": [rnd(x * (1 - band)) for x in g], "high": [rnd(x * (1 + band)) for x in g],
                       "closed_if_chosen": self.closed(d)})
        nxt = self.W["days"][t] if t < C["days"] else None
        sup = {}
        for s, S in C["suppliers"].items():
            items = {}
            for it, I in S["items"].items():
                items[it] = I["price"] if it != "milk" else self.milk_price(t)
            sup[s] = {"days": S["days"], "delivers_tomorrow": (nxt is not None and nxt["wd"] in S["days"]),
                      "min_order": S.get("min_order"), "min_qty": S.get("min_qty"), "prices": items}
        return {
            "day": t, "date": nxt["date"] if nxt else None, "wd": nxt["wd"] if nxt else None, "days_total": C["days"],
            "cash": cents(self.cash), "loan": cents(self.loan), "reputation": round(self.rep, 3),
            "stock": {"milk_l": [[cents(a), b] for a, b in self.milk], "beans_lb": cents(self.beans_g / C["suppliers"]["roaster"]["items"]["beans"]["grams"]),
                      "cups": self.cups, "croissant": self.croissant},
            "staff": [dict(s) for s in self.staff], "schedule": json.loads(json.dumps(self.schedule)),
            "prices": dict(self.prices), "discounts": json.loads(json.dumps(self.discounts)),
            "costs": {k: self.cost_of(k, t) for k in DRINKS + ["croissant"]},
            "suppliers": sup, "forecast": fc, "cards": self.open_cards(), "grade": "B" if self.grade_b_from is not None and self.grade_b_from <= t else "A",
            "investments": {k: {"cost": v["cost"], "bought_from_day": self.bought.get(k)} for k, v in C["investments"].items()},
            "yesterday": self.last_report, "totals": {k: cents(v) for k, v in self.totals.items()}, "counts": dict(self.counts),
        }

    # --- Проверка решений ---
    def check(self, dec):
        C = self.C; t = self.t
        out = []
        if t >= C["days"]:
            return [rej("day", "over", "Месяц закончился.", "The month is over.")]
        if not isinstance(dec, dict):
            return [_form("decision", "нужен объект JSON", "a JSON object is required")], dict(EMPTY_OK)
        D = self.W["days"][t]
        wd = D["wd"]
        cash = self.cash
        ok = {}
        # заказы
        orders = dec.get("orders") or {}
        if not isinstance(orders, dict):
            out.append(_form("orders", "нужен объект {поставщик: {позиция: количество}}", "an object {supplier: {item: qty}} is required")); orders = {}
        ok_orders = {}
        for s, items in orders.items():
            if items and not isinstance(items, dict):
                out.append(_form("orders." + s, "нужен объект {позиция: количество}", "an object {item: qty} is required")); continue
            if s not in C["suppliers"]:
                out.append(rej("orders." + s, "no_supplier", "Нет поставщика «" + s + "».", "No supplier '" + s + "'.")); continue
            S = C["suppliers"][s]
            items = {k: v for k, v in (items or {}).items() if v}
            if not items:
                continue
            bad = False
            for it, q in items.items():
                if it not in S["items"]:
                    out.append(rej("orders." + s, "no_item", SUP_RU[s] + " не возит «" + it + "».", SUP_EN[s] + " does not carry '" + it + "'.")); bad = True
                elif not _int(q) or q < 0:
                    out.append(rej("orders." + s, "qty", "Количество должно быть целым: " + str(q) + ".", "Quantity must be a whole number: " + str(q) + ".")); bad = True
            if bad:
                continue
            if wd not in S["days"]:
                ds_ru = ", ".join(WD_RU[x] for x in S["days"]); ds_en = ", ".join(WD_EN[x] for x in S["days"])
                out.append(rej("orders." + s, "day", SUP_RU[s] + " возит только " + ds_ru + ", а завтра " + WD_RU[wd] + ".",
                               SUP_EN[s] + " delivers only " + ds_en + "; tomorrow is " + WD_EN[wd] + ".")); continue
            price = {it: (self.milk_price(t) if it == "milk" else S["items"][it]["price"]) for it in items}
            total = cents(sum(price[it] * q for it, q in items.items()))
            if "min_order" in S and total < S["min_order"]:
                out.append(rej("orders." + s, "min", SUP_RU[s] + ": заказ $" + ("%.2f" % total) + " меньше минимума $" + str(S["min_order"]) + ".",
                               SUP_EN[s] + ": order $" + ("%.2f" % total) + " is below the $" + str(S["min_order"]) + " minimum.")); continue
            if "min_qty" in S and sum(items.values()) < S["min_qty"]:
                out.append(rej("orders." + s, "min", SUP_RU[s] + ": меньше " + str(S["min_qty"]) + " штук не возит.",
                               SUP_EN[s] + ": minimum " + str(S["min_qty"]) + " pieces.")); continue
            prev = self.orders.get(s, {}).get("total", 0.0)  # повторный заказ тем же вечером заменяет прежний
            if total > cash + prev + 1e-9:
                out.append(rej("orders." + s, "cash", "Не хватает денег: заказ $" + ("%.2f" % total) + ", на счёте $" + ("%.2f" % cash) + ".",
                               "Not enough cash: order $" + ("%.2f" % total) + ", balance $" + ("%.2f" % cash) + ".")); continue
            cash -= total - prev
            ok_orders[s] = {"items": items, "total": total}
        ok["orders"] = ok_orders
        # цены
        prices = dec.get("prices") or {}
        if not isinstance(prices, dict):
            out.append(_form("prices", "нужен объект {позиция: цена}", "an object {item: price} is required")); prices = {}
        ok_prices = {}
        lo, hi = C["price_bounds"]
        for it, p in prices.items():
            if it not in self.prices:
                out.append(rej("prices." + it, "no_item", "Нет позиции «" + it + "».", "No item '" + it + "'.")); continue
            base = C["menu"][it]["price"]; cost = self.cost_of(it, t)
            if not _num(p) or p <= cost:
                out.append(rej("prices." + it, "below_cost", ITEM_RU[it] + ": цена $" + str(p) + " не выше себестоимости $" + ("%.2f" % cost) + ".",
                               it + ": price $" + str(p) + " is not above cost $" + ("%.2f" % cost) + ".")); continue
            if p < base * lo or p > base * hi:
                out.append(rej("prices." + it, "bounds", ITEM_RU[it] + ": цена должна быть от $" + ("%.2f" % (base * lo)) + " до $" + ("%.2f" % (base * hi)) + ".",
                               it + ": price must be between $" + ("%.2f" % (base * lo)) + " and $" + ("%.2f" % (base * hi)) + ".")); continue
            ok_prices[it] = cents(p)
        ok["prices"] = ok_prices
        # скидки
        if "discounts" in dec and dec["discounts"] and not isinstance(dec["discounts"], list):
            out.append(_form("discounts", "нужен список скидок", "a list of discounts is required"))
        elif "discounts" in dec:
            ok_d = []
            for i, d in enumerate(dec["discounts"] or []):
                if not isinstance(d, dict):
                    out.append(rej("discounts." + str(i), "form", "Скидка " + str(i + 1) + ": нужна позиция, процент и части дня 0–2.", "Discount " + str(i + 1) + ": needs item, percent and dayparts 0-2.")); continue
                it = d.get("item"); pct = d.get("pct"); dps = d.get("dayparts", [0, 1, 2])
                if not isinstance(it, str) or it not in self.prices or not _num(pct) or not isinstance(dps, list) or not dps or any(not _int(x) or x not in (0, 1, 2) for x in dps):
                    out.append(rej("discounts." + str(i), "form", "Скидка " + str(i + 1) + ": нужна позиция, процент и части дня 0–2.", "Discount " + str(i + 1) + ": needs item, percent and dayparts 0-2.")); continue
                if pct <= 0 or pct > C["max_discount_pct"]:
                    out.append(rej("discounts." + str(i), "pct", "Скидка " + str(i + 1) + ": от 1 до " + str(C["max_discount_pct"]) + " %.", "Discount " + str(i + 1) + ": 1 to " + str(C["max_discount_pct"]) + "%.")); continue
                p = cents(ok_prices.get(it, self.prices[it]) * (1 - pct / 100.0)); cost = self.cost_of(it, t)
                if p <= cost:
                    out.append(rej("discounts." + str(i), "below_cost", "Скидка " + str(pct) + " % на " + ITEM_RU[it] + " даёт $" + ("%.2f" % p) + ", это не выше себестоимости $" + ("%.2f" % cost) + ": запрещено.",
                                   str(pct) + "% off " + it + " makes $" + ("%.2f" % p) + ", not above cost $" + ("%.2f" % cost) + ": not allowed.")); continue
                if any(x["item"] == it and set(x["dayparts"]) & set(dps) for x in ok_d):
                    out.append(rej("discounts." + str(i), "double", "Две скидки на " + ITEM_RU[it] + " в одну часть дня.", "Two discounts on " + it + " in the same daypart.")); continue
                ok_d.append({"item": it, "pct": pct, "dayparts": sorted(dps)})
            ok["discounts"] = ok_d
        # люди
        hire = dec.get("hire", 0) or 0
        fire = dec.get("fire", 0) or 0
        hb = self.headcount("barista", 0, include_pending=True)
        if not _int(hire) or hire < 0 or hire > 3:
            out.append(rej("hire", "range", "Нанять можно от 0 до 3 человек за вечер.", "You can hire 0 to 3 people per evening.")); hire = 0
        if not _int(fire) or fire < 0 or fire > hb:
            out.append(rej("fire", "range", "Уволить можно не больше, чем есть бариста (" + str(hb) + ").", "You cannot let go more baristas than you have (" + str(hb) + ").")); fire = 0
        ok["hire"] = hire; ok["fire"] = fire
        # смены
        if "schedule" in dec:
            sch = dec["schedule"]; good = True
            hb_after = hb + hire - fire
            for w in range(7):
                row = sch.get(str(w)) if isinstance(sch, dict) else None
                if not isinstance(row, dict) or not isinstance(row.get("barista"), list) or not isinstance(row.get("lead"), list) or len(row["barista"]) != 3 or len(row["lead"]) != 3:
                    out.append(rej("schedule." + str(w), "form", WD_RU[w] + ": нужны три числа бариста и три старшего.", WD_EN[w] + ": need three barista numbers and three lead numbers.")); good = False; continue
                b, l = row["barista"], row["lead"]
                if any(not _int(x) for x in b + l) or any(x < 0 for x in b):
                    out.append(rej("schedule." + str(w), "form", WD_RU[w] + ": старший 0 или 1, бариста целым числом от 0.", WD_EN[w] + ": lead is 0 or 1, baristas a whole number from 0.")); good = False; continue
                if l[0] < 1:
                    out.append(rej("schedule." + str(w), "no_lead", WD_RU[w] + ": утром нет старшего, кофейня не откроется.", WD_EN[w] + ": no lead in the morning, the shop cannot open.")); good = False
                if any(x < 0 or x > 1 for x in l):
                    out.append(rej("schedule." + str(w), "form", WD_RU[w] + ": старший 0 или 1, бариста целым числом.", WD_EN[w] + ": lead is 0 or 1, baristas a whole number.")); good = False; continue
                for dp in range(3):
                    if b[dp] + l[dp] > C["max_per_daypart"]:
                        out.append(rej("schedule." + str(w), "space", WD_RU[w] + " " + DP_RU[dp] + ": за стойкой помещается " + str(C["max_per_daypart"]) + " человек.", WD_EN[w] + " " + DP_EN[dp] + ": only " + str(C["max_per_daypart"]) + " fit behind the bar.")); good = False
                    if b[dp] > hb_after:
                        out.append(rej("schedule." + str(w), "headcount", WD_RU[w] + " " + DP_RU[dp] + ": " + str(b[dp]) + " бариста, а в штате " + str(hb_after) + ".", WD_EN[w] + " " + DP_EN[dp] + ": " + str(b[dp]) + " baristas, but you employ " + str(hb_after) + ".")); good = False
            if good:
                ok["schedule"] = {str(w): {"barista": list(sch[str(w)]["barista"]), "lead": list(sch[str(w)]["lead"])} for w in range(7)}
        # вложения
        ok_b = []
        buy = dec.get("buy") or []
        if not isinstance(buy, list):
            out.append(_form("buy", "нужен список, например [\"machine2\"]", "a list is required, e.g. [\"machine2\"]")); buy = []
        for k in buy:
            if not isinstance(k, str):
                out.append(_form("buy", "в списке нужны названия вложений", "the list needs investment names")); continue
            if k not in C["investments"]:
                out.append(rej("buy." + str(k), "no_item", "Нет такого вложения: «" + str(k) + "».", "No such investment: '" + str(k) + "'.")); continue
            if k in self.bought or k in ok_b:
                out.append(rej("buy." + k, "twice", "Это уже куплено.", "Already bought.")); continue
            cost = C["investments"][k]["cost"]
            if cost > cash + 1e-9:
                out.append(rej("buy." + k, "cash", "Не хватает денег: стоит $" + str(cost) + ", на счёте $" + ("%.2f" % cash) + ".",
                               "Not enough cash: costs $" + str(cost) + ", balance $" + ("%.2f" % cash) + ".")); continue
            cash -= cost; ok_b.append(k)
        ok["buy"] = ok_b
        # карточки
        cards = {c["id"]: c for c in self.open_cards()}
        ok_c = {}
        choices = dec.get("choices") or {}
        if not isinstance(choices, dict):
            out.append(_form("choices", "нужен объект {id карточки: вариант}", "an object {card id: option} is required")); choices = {}
        for cid, opt in choices.items():
            if cid not in cards:
                out.append(rej("choices." + cid, "closed", "Карточки «" + cid + "» сейчас нет.", "Card '" + cid + "' is not open now.")); continue
            if opt not in cards[cid]["options"]:
                out.append(rej("choices." + cid, "option", "У карточки нет варианта «" + str(opt) + "».", "The card has no option '" + str(opt) + "'.")); continue
            ok_c[cid] = opt
        ok["choices"] = ok_c
        return out, ok

    def decide(self, dec):
        out, ok = self.check(dec)
        t = self.t
        for s, o in ok["orders"].items():
            if s in self.orders:
                self.cash += self.orders[s]["total"]; self.totals["purchases"] -= self.orders[s]["total"]
            self.orders[s] = o
            self.cash -= o["total"]; self.totals["purchases"] += o["total"]
        self.prices.update(ok["prices"])
        if "discounts" in ok:
            self.discounts = ok["discounts"]
        for _ in range(ok["hire"]):
            self.staff.append({"id": "b" + str(self.next_id), "role": "barista", "start": t + self.C["staff"]["hire_delay_days"]}); self.next_id += 1
        if ok["hire"]:
            hc = ok["hire"] * self.C["staff"]["hire_cost"]  # оформление и оплачиваемая учебная смена, платится в вечер найма
            self.cash -= hc; self.totals["wages"] += hc
        for _ in range(ok["fire"]):
            bs = [s for s in self.staff if s["role"] == "barista"]
            bs.sort(key=lambda s: (-s["start"], -int(s["id"][1:])))
            self.staff.remove(bs[0])
        if "schedule" in ok:
            self.schedule = ok["schedule"]
        self.choices.update(ok["choices"])
        for k in ok["buy"]:
            I = self.C["investments"][k]
            self.cash -= I["cost"]; self.totals["investments"] += I["cost"]
            self.bought[k] = t + (I.get("delay", 0))
        self.pending_rejections += out
        self.pending_decisions.append(dec)
        return out

    # --- день ---
    def step(self):
        C = self.C; t = self.t; W = self.W
        D = W["days"][t]
        rep = {"day": t, "date": D["date"], "wd": D["wd"], "weather": D["weather"], "events": [], "closed": False}
        costs_ev = 0.0
        # карточки с ценой
        for e in W["events"] + self.cards_extra:
            k = e["kind"]; ch = self.choice(e); E = C["events"].get(k, {})
            if k == "blogger" and e["day"] == t and ch == "accept":
                costs_ev += E["cost"]; rep["events"].append("blogger_shoot")
            if k == "repair" and e["day"] == t and ch == "sign":
                costs_ev += E["sign_cost"]
            if k == "inspection" and ch == "clean" and e["id"] not in self.clean_paid and t in (e["day"] - 1, e["day"]):
                costs_ev += E["clean_cost"]; self.clean_paid.add(e["id"])  # выбор в последний вечер: уборка утром в день проверки, цена та же
            if k == "breakdown" and e["day"] + 1 == t:
                costs_ev += E["fast_cost"] if ch == "fast" else E["slow_cost"]
            if k == "competitor" and e["day"] == t:
                if ch == "loyalty":
                    costs_ev += E["loyalty_cost"]; self.rep = clamp(self.rep + E["loyalty_rep"], C["reputation"]["min"], C["reputation"]["max"])
                elif ch == "promo":
                    costs_ev += E["promo_cost"]
            if k == "complaint" and e["day"] == t:
                if ch == "coupons":
                    costs_ev += 40; self.rep = clamp(self.rep + 0.03, C["reputation"]["min"], C["reputation"]["max"])
                elif ch == "reply":
                    self.rep = clamp(self.rep + 0.01, C["reputation"]["min"], C["reputation"]["max"])
                else:
                    self.rep = clamp(self.rep - 0.01, C["reputation"]["min"], C["reputation"]["max"])
        closed = self.closed(t)
        rep["closed"] = closed
        # поставки утром
        delivered = {}
        no_show = any(e["kind"] == "no_show" and e["day"] == t for e in W["events"])
        for s, o in self.orders.items():
            if closed or D["weather"] == "blizzard" or (s == "dairy" and no_show):
                self.cash += o["total"]; self.totals["refunds"] += o["total"]
                rep["events"].append("no_delivery_" + s); continue
            for it, q in o["items"].items():
                if it == "milk":
                    I = C["suppliers"]["dairy"]["items"]["milk"]
                    self.milk.append([q * I["liters"], t + I["shelf_days"] - 1])
                elif it == "beans":
                    self.beans_g += q * C["suppliers"]["roaster"]["items"]["beans"]["grams"]
                elif it == "cups":
                    self.cups += q * C["suppliers"]["roaster"]["items"]["cups"]["count"]
                elif it == "croissant":
                    self.croissant += q
            delivered[s] = o["items"]
        self.orders = {}
        rep["delivered"] = delivered
        # люди
        row = self.schedule[str(D["wd"])]
        avail_b = max(0, self.headcount("barista", t) - self.sick_out(t))
        agency = any(e["kind"] == "sick" and e["day"] <= t <= e["day"] + C["events"]["sick"]["days"] - 1 and self.choice(e) == "agency" for e in W["events"])
        hours_dp = C["hours"]["dayparts"]
        on_b = []; on_l = []; ag = []
        for dp in range(DP_N):
            want = row["barista"][dp]
            have = min(want, avail_b)
            extra = want - have if agency else 0
            on_b.append(0 if closed else have); ag.append(0 if closed else extra)
            on_l.append(0 if closed else min(row["lead"][dp], self.headcount("lead", t)))
        # поломка: часы без латте
        no_latte = [False] * DP_N
        for e in W["events"]:
            if e["kind"] == "breakdown":
                if t == e["day"]:
                    no_latte[1] = no_latte[2] = True
                if t == e["day"] + 1 and self.choice(e) == "slow":
                    no_latte[0] = no_latte[1] = True
        if self.has("machine2", t):
            no_latte = [False] * DP_N
        if any(no_latte):
            rep["events"].append("no_espresso")
        # спрос
        exp, notes, _ = self.expected_guests(t, hidden=True)
        rep["notes"] = notes
        M = C["menu"]
        I_beans = C["suppliers"]["roaster"]["items"]["beans"]
        revenue = 0.0; tx = 0; served_all = 0; queue = 0; stockout = 0; demand_all = 0; pastry_missing = 0
        by_dp = []
        catering = None
        for e in W["events"]:
            if e["kind"] == "catering" and e["day"] == t and self.choice(e) == "accept":
                catering = e
        for dp in range(DP_N):
            g = 0 if closed else rnd(exp[dp] * W["noise"][t][dp])
            h = hours_dp[dp][1] - hours_dp[dp][0]
            dph = C["drinks_per_barista_hour"] + (C["investments"]["machine2"]["extra_drinks_per_hour"] if self.has("machine2", t) else 0)
            cap = rnd((on_b[dp] + ag[dp] + C["lead_capacity_share"] * on_l[dp]) * dph * h)
            if dp == 0:
                for e in W["events"]:
                    if e["kind"] == "blogger" and e["day"] == t and self.choice(e) == "accept":
                        cap = rnd(cap * C["events"]["blogger"]["morning_capacity"])
            rec = {"dp": dp, "demand": g, "capacity": cap}
            if dp == 0 and catering is not None and not closed:
                want = C["events"]["catering"]["drinks"]
                can = min(want, cap, self.units_available("latte") if not no_latte[0] else 0)
                self.consume("latte", can, t)
                revenue += can * C["events"]["catering"]["price"]
                cap -= can
                queue += want - can
                rec["catering"] = can
                rep["events"].append("catering_" + str(can))
            served = min(g, cap)
            queue += g - served; demand_all += g
            counts = dict(zip(DRINKS, split_lr(served, [M[k]["share"] for k in DRINKS])))
            sold = {}
            for k in DRINKS:
                want = counts[k]
                if k == "latte" and no_latte[dp]:
                    av = 0
                else:
                    av = self.units_available(k)
                s_ = min(want, av)
                self.consume(k, s_, t)
                sold[k] = s_
                short = want - s_
                if short > 0:
                    if k == "latte":
                        sw = rnd(short * C["latte_to_drip"])
                        counts["drip"] += sw
                        stockout += short - sw
                    else:
                        stockout += short
            guests_ok = sum(sold.values())
            for k in DRINKS:
                revenue += sold[k] * self.eff_price(k, dp)
            pr = self.eff_price("croissant", dp) / M["croissant"]["price"]
            pm = pr ** (C["elasticity_pastry"]["up"] if pr > 1 else C["elasticity_pastry"]["down"])
            pw = rnd(guests_ok * M["croissant"]["attach"] * pm)
            ps = min(pw, self.croissant)
            self.croissant -= ps
            revenue += ps * self.eff_price("croissant", dp)
            pastry_missing += pw - ps
            tx += guests_ok; served_all += guests_ok
            rec.update({"served": served, "sold": sold, "croissant": ps, "croissant_missing": pw - ps})
            by_dp.append(rec)
        stockout += pastry_missing
        revenue = cents(revenue)
        fee = 0.0 if tx == 0 else cents(C["card_share"] * (revenue * (1 + C["sales_tax"])) * C["card_fee_pct"] + C["card_fee_fixed"] * rnd(C["card_share"] * tx))
        # зарплата
        S = C["staff"]
        hb = sum(on_b[dp] * (hours_dp[dp][1] - hours_dp[dp][0]) for dp in range(DP_N))
        hl = sum(on_l[dp] * (hours_dp[dp][1] - hours_dp[dp][0]) for dp in range(DP_N))
        ha = sum(ag[dp] * (hours_dp[dp][1] - hours_dp[dp][0]) for dp in range(DP_N))
        wages = (hb * S["barista"]["wage"] + hl * S["lead"]["wage"]) * (1 + S["burden"])
        self.week_hours["barista"] += hb; self.week_hours["lead"] += hl
        ot = 0.0
        if D["wd"] == 6 or t == C["days"] - 1:
            for role in ("barista", "lead"):
                over = self.week_hours[role] - S["overtime_after_h"] * max(1, self.headcount(role, t))
                if over > 0:
                    ot += over * S[role]["wage"] * (S["overtime_mult"] - 1) * (1 + S["burden"])
            rep["overtime"] = cents(ot)
            self.week_hours = {"barista": 0.0, "lead": 0.0}
        wages = cents(wages + ot)
        agency_cost = cents(ha * S["agency_hourly"])
        # списания
        expired = sum(a for a, b in self.milk if b <= t)
        self.milk = [[a, b] for a, b in self.milk if b > t and a > 1e-9]
        wo_c = self.croissant; self.croissant = 0
        # деньги
        rent = cents(self.rent_day * C["days"]) if t == 0 else 0.0  # аренда вносится за месяц вперёд
        fixed = cents(C["fixed_month"] / C["days"] + C["supplies_pct"] * revenue)
        costs_ev = cents(costs_ev)
        self.cash += revenue - fee - wages - agency_cost - rent - fixed - costs_ev
        self.cash = cents(self.cash)
        loan_new = 0.0
        if self.cash < 0:
            loan_new = -self.cash; self.loan += loan_new; self.cash = 0.0
        T = self.totals
        T["revenue"] += revenue; T["card_fees"] += fee; T["wages"] += wages; T["agency"] += agency_cost
        T["rent"] += rent; T["fixed"] += fixed; T["event_costs"] += costs_ev
        for k in T:
            T[k] = cents(T[k])
        Cn = self.counts
        Cn["stockout_guests"] += stockout; Cn["queue_guests"] += queue; Cn["guests"] += served_all; Cn["demand"] += demand_all
        Cn["written_off_milk_l"] = cents(Cn["written_off_milk_l"] + expired); Cn["written_off_croissant"] += wo_c
        # инспекция
        for e in W["events"]:
            if e["kind"] == "inspection" and e["day"] == t:
                qrate = queue / max(1, demand_all)
                b = self.choice(e) != "clean" and (qrate > 0.10 or e["hidden"]["u"] < C["events"]["inspection"]["b_risk"])
                if b:
                    self.grade_b_from = t + 1
                rep["events"].append("inspection_" + ("B" if b else "A"))
        # репутация
        R = C["reputation"]
        unhappy = (queue + (stockout - pastry_missing) + 0.3 * pastry_missing) / max(1, demand_all)
        if not closed:
            self.rep = clamp(self.rep + R["drift"] - R["unhappy_k"] * unhappy, R["min"], R["max"])
        # жалоба на очередь: одна за месяц
        if not closed and demand_all > 0 and queue / demand_all >= 0.05 and not self.cards_extra and t + 1 < C["days"]:
            self.cards_extra.append({"id": "complaint_" + str(t), "kind": "complaint", "day": t + 1, "show": t + 1, "deadline": t})
        rep.update({"by_dp": by_dp, "revenue": revenue, "card_fee": fee, "wages": wages, "agency": agency_cost, "rent": rent, "fixed": fixed,
                    "event_costs": costs_ev, "queue_guests": queue, "stockout_guests": stockout, "demand": demand_all, "served": served_all,
                    "milk_written_off_l": cents(expired), "croissant_written_off": wo_c, "cash": self.cash, "loan_new": cents(loan_new),
                    "reputation": round(self.rep, 4), "staff_on": {"barista": on_b, "lead": on_l, "agency": ag},
                    "stock": {"milk_l": cents(sum(a for a, b in self.milk)), "beans_lb": cents(self.beans_g / I_beans["grams"]), "cups": self.cups, "croissant": wo_c},
                    "decisions": self.pending_decisions, "rejections": self.pending_rejections})
        self.pending_rejections = []
        self.pending_decisions = []
        self.journal.append(rep)
        self.last_report = {k: v for k, v in rep.items() if k != "rejections"}
        self.t += 1
        return rep

    def units_available(self, k):
        m = self.C["menu"][k]
        lim = self.cups // m["cup"] if m["cup"] else 10 ** 9
        if m["beans_g"]:
            lim = min(lim, int(math.floor(self.beans_g / m["beans_g"] + 1e-9)))
        if m["milk_l"]:
            lim = min(lim, int(math.floor(sum(a for a, b in self.milk) / m["milk_l"] + 1e-9)))
        return lim

    def consume(self, k, n, t):
        if n <= 0:
            return
        m = self.C["menu"][k]
        self.cups -= n * m["cup"]
        self.beans_g = cents(self.beans_g - n * m["beans_g"])
        need = n * m["milk_l"]
        self.milk.sort(key=lambda x: x[1])
        for lot in self.milk:
            if need <= 1e-9:
                break
            take = min(lot[0], need); lot[0] = cents(lot[0] - take); need -= take

    # --- счёт ---
    def score(self):
        C = self.C; T = self.totals; Cn = self.counts
        beans = C["suppliers"]["roaster"]["items"]["beans"]; cups = C["suppliers"]["roaster"]["items"]["cups"]
        left = cents(self.beans_g / beans["grams"] * beans["price"] + self.cups * cups["price"] / cups["count"])
        parts = {
            "revenue": T["revenue"], "purchases": -cents(T["purchases"] - T["refunds"]), "leftover_stock": left,
            "wages": -cents(T["wages"] + T["agency"]), "rent_fixed": -cents(T["rent"] + T["fixed"]), "card_fees": -T["card_fees"],
            "event_costs": -T["event_costs"], "investments": -T["investments"],
            "leftover_equipment": cents(C["investments"]["machine2"]["cost"] * C["investments"]["machine2"]["residual"]) if "machine2" in self.bought else 0.0,
            "stockout_penalty": -cents(Cn["stockout_guests"] * C["penalty_stockout"]),
            "queue_penalty": -cents(Cn["queue_guests"] * C["penalty_queue"]), "loan_penalty": -cents(self.loan * C["loan_penalty"]),
        }
        profit = cents(sum(v for k, v in parts.items() if not k.endswith("_penalty")))
        return {"score": cents(sum(parts.values())), "profit": profit, "parts": parts, "counts": dict(Cn), "loan": cents(self.loan), "cash": cents(self.cash)}


def play(seed, street, money, scenario, policy, city="ny"):
    g = Game(seed, street, money, scenario, city)
    log = []
    while g.t < g.C["days"]:
        obs = g.observe()
        dec = policy(obs)
        r = g.decide(dec)
        log.append({"day": g.t, "decision": dec, "rejections": r})
        g.step()
    return g, log


def replay(seed, settings, decisions, city="ny"):
    """Пересчёт счёта по журналу решений: decisions = [(день, решение), ...] в порядке вызовов decide.
    Мир задан зерном и настройками, поэтому тот же журнал всегда даёт тот же счёт."""
    g = Game(seed, settings["street"], settings["money"], settings["scenario"], city)
    by_day = {}
    for day, dec in decisions:
        by_day.setdefault(int(day), []).append(dec)
    while g.t < g.C["days"]:
        g.observe()
        for dec in by_day.get(g.t, []):
            g.decide(dec)
        g.step()
    return g.score()
