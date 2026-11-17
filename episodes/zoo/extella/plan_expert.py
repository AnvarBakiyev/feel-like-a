def zoo_game_plan(obs, plan, world):
    """Эксперт Extella для эпизода «Зоопарк»: замысел модели и наблюдение вечера -> точное решение и оценки.

    obs: то же, что видит игрок (sim.Game.observe()).
    plan: замысел модели: stock, staff (lean / normal / safe), shows (0-2), price (проценты к базе), free_wed, choices.
          plan["cards"] == "expert": ответы на карточки выбирает эксперт по наибольшей оценке, choices модели не учитываются.
          plan["shows"] == "expert": число кормлений при публике выбирает эксперт по оценке estimates["shows"].
          plan["price"] == "expert" и plan["free_wed"] == "expert": цену и бесплатную среду выбирает эксперт
          по деньгам завтрашнего дня, считая тесноту.
    world: открытые цифры зоопарка (то же, что на странице правил).
    Возвращает decision для Проверки, оценки в долларах для карточек и цены, предупреждения о людях.
    """
    plan = dict(plan or {})
    if plan.get("cards") == "expert":
        # Ответы на карточки выбирает эксперт: вариант с наибольшей оценкой; None (запрещено или не оценить) не берётся.
        Z0 = _Zoo(obs, {k: v for k, v in plan.items() if k != "choices"}, world)
        est = Z0.estimates()["cards"]
        ch = {}
        for c in obs["cards"]:
            opts = [(o, v) for o, v in (est.get(c["id"]) or {}).items() if v is not None and o in c["options"]]
            if opts:
                ch[c["id"]] = max(opts, key=lambda ov: ov[1])[0]
        plan["choices"] = ch
    if plan.get("shows") == "expert":
        # Число кормлений при публике выбирает эксперт: наибольшая оценка за остаток месяца.
        Z1 = _Zoo(obs, dict(plan, shows=2), world)
        sv = Z1.shows_ev()
        plan["shows"] = int(max(sv, key=lambda k: (sv[k], k)))
    if plan.get("price") == "expert" or plan.get("free_wed") == "expert":
        # Цену и бесплатную среду выбирает эксперт: вариант с наибольшими деньгами завтрашнего дня.
        Z2 = _Zoo(obs, dict(plan, price=0, free_wed=False), world)
        if plan.get("free_wed") == "expert":
            fw = Z2.free_wed_value()
            plan["free_wed"] = bool(fw is not None and fw > 0)
            Z2 = _Zoo(obs, dict(plan, price=0), world)
        if plan.get("price") == "expert":
            po = Z2.price_options()
            plan["price"] = int(max(po, key=lambda k: (po[k], -abs(int(k)))))
    Z = _Zoo(obs, plan, world)
    dec = {"thaw": Z.thaw(), "orders": Z.orders(), "schedule": Z.schedule()}
    hire = Z.hire()
    if hire:
        dec["hire"] = hire
    if "price" in plan:
        dec["price"] = Z.price()
    if "free_wed" in plan:
        dec["free_wed"] = bool(plan["free_wed"])
    if Z.vet_needed():
        dec["vet_visit"] = True
    ch = {}
    for c in obs["cards"]:
        pick = (plan.get("choices") or {}).get(c["id"])
        if pick is not None:
            ch[c["id"]] = pick
    if ch:
        dec["choices"] = ch
    return {"decision": dec, "estimates": Z.estimates(), "warnings": Z.warnings(dec), "numbers": Z.numbers}


SECT = ["pool", "cats", "birds", "yard", "tropic"]
LV = {"lean": 0, "normal": 1, "safe": 2}


def _ceil(x):
    i = int(x)
    return i if i >= x - 1e-9 else i + 1


class _Zoo:
    def __init__(self, obs, plan, W):
        self.o = obs; self.p = plan; self.W = W
        self.t = obs["day"]; self.n = obs["days_total"]
        self.stock_lv = LV.get(plan.get("stock", "normal"), 1)
        self.staff_lv = LV.get(plan.get("staff", "normal"), 1)
        self.shows = plan.get("shows", 2) if plan.get("shows", 2) in (0, 1, 2) else 2
        self.numbers = {}
        self.margin = self.visitor_margin()

    def _choice(self, c):
        return (self.p.get("choices") or {}).get(c["id"], c.get("chosen") or c["default"])

    def card(self, kind, day=None):
        for c in self.o["cards"]:
            if c["kind"] == kind and (day is None or c["day"] == day):
                return c
        return None

    # --- деньги с посетителя ---
    def visitor_margin(self, price=None):
        W = self.W; m = W["mix"]; P = W["prices"]; sp = W["spend"]
        p = price or self.o["price"]
        ticket = m["adult"] * p + m["child"] * p * P["child_share"] + m["group"] * P["group"]
        food = sp["food"] * (1 - sp["food_cost"]); souv = sp["souvenir"] * (1 - sp["souvenir_cost"])
        don = sp["donation"] + sp["donation_per_show"] * self.shows
        fee = W["card_share"] * (ticket + sp["food"] + sp["souvenir"]) * W["card_fee_pct"]
        v = ticket + food + souv + don - fee
        self.numbers["margin_per_visitor"] = round(v, 2)
        return v

    # --- теснота и деньги за день ---
    def crowd_drop(self, g_half):
        """Насколько падают траты с человека, когда в половину дня приходит больше вместимости."""
        CR = self.W.get("crowding")
        if not CR:
            return 0.0
        over = max(0.0, g_half / CR["comfort_per_half"] - 1.0)
        return min(CR["spend_drop_max"], CR["spend_drop_k"] * over)

    def half_value(self, g_half, price, free):
        """Деньги с половины дня: билеты, еда и сувениры с поправкой на тесноту, пожертвования."""
        W = self.W; m = W["mix"]; P = W["prices"]; sp = W["spend"]
        drop = self.crowd_drop(g_half)
        ticket = 0.0 if free else (m["adult"] * price + m["child"] * price * P["child_share"] + m["group"] * P["group"])
        food = sp["food"] * (1 - sp["food_cost"]) * (1 - drop)
        souv = sp["souvenir"] * (1 - sp["souvenir_cost"]) * (1 - drop)
        dmult = W["free_wed"].get("donation_mult", 1.0) if free else 1.0
        don = sp["donation"] * dmult + sp["donation_per_show"] * self.shows
        fee = W["card_share"] * (ticket + (sp["food"] + sp["souvenir"]) * (1 - drop)) * W["card_fee_pct"]
        return g_half * (ticket + food + souv + don - fee)

    def day_value(self, pct, free):
        """Деньги завтрашнего дня при цене pct процентов к базе и бесплатной среде free."""
        W = self.W; base = W["prices"]["adult"]; el = W["elasticity"]
        p_new = base * (1 + pct / 100.0)
        f = lambda pi: pi ** (el["up"] if pi > 1 else el["down"])
        k = f(p_new / base) / f(self.o["price"] / base)
        fc = self.o["forecast"][0]
        S = W["staff"]; hh = W["halves"]["hours"]
        tot = 0.0
        for h, g in enumerate(fc["visitors"]):
            gh = g * k
            fr = bool(free) and fc.get("wd") == 2 and h == 1
            if fr:
                gh *= W["free_wed"]["afternoon_mult"]
            tot += self.half_value(gh, p_new, fr)
            # кассы и киоски под этот поток: их зарплата идёт в тот же счёт, иначе дешёвый
            # билет «выигрывает» на бумаге, а в игре упирается в очередь
            cash = max(1, min(8, _ceil(gh * (1 - W["mix"]["member"] - W["mix"]["group"]) / (W["gate_per_cashier_hour"] * hh[h]))))
            kio = max(0, min(8, _ceil(gh * 0.7 / (W["kiosk_per_worker_hour"] * hh[h]))))
            tot -= (cash * S["cashier"]["wage"] + kio * S["kiosk"]["wage"]) * hh[h] * (1 + S["burden"])
        return tot

    def fill(self):
        """Ожидаемая заполненность половин завтрашнего дня в долях вместимости."""
        CR = self.W.get("crowding")
        if not CR:
            return None
        return [round(g / CR["comfort_per_half"], 2) for g in self.o["forecast"][0]["visitors"]]

    # весь законный диапазон цены (мир: от 0,5 до 2 базовой). Первая версия меню была ±20 %, и эксперт не видел,
    # что у метро в выходные выгоднее всего потолок: Claude Opus 5.5 без Extella это нашёл, а эксперт не мог.
    PRICE_OPTIONS = (-50, -30, -20, -10, -5, 0, 5, 10, 20, 30, 50, 75, 100)

    def price_options(self):
        """Деньги завтрашнего дня при каждой цене из набора, считая от нынешнего замысла."""
        cur = self.p.get("price", 0)
        cur = cur if isinstance(cur, (int, float)) else 0
        free = bool(self.p.get("free_wed")) and self.p.get("free_wed") != "expert"
        b = self.day_value(cur, free)
        return {str(x): round(self.day_value(x, free) - b) for x in self.PRICE_OPTIONS}

    def free_wed_value(self):
        """Деньги за бесплатную среду; None, если завтра не среда."""
        if self.o["forecast"][0].get("wd") != 2:
            return None
        cur = self.p.get("price", 0)
        cur = cur if isinstance(cur, (int, float)) else 0
        return round(self.day_value(cur, True) - self.day_value(cur, False))

    # --- корм ---
    def thaw(self):
        nd = self.o["need_kg_per_day"]; st = self.o["stock"]
        out = {}
        for k in ("fish", "meat"):
            have = st["freezer"][k] + st["thawed_for_tomorrow"][k]
            out[k] = round(min(nd[k], have), 1)
        return out

    def orders(self):
        o = {}; nd = self.o["need_kg_per_day"]; st = self.o["stock"]; sup = self.o["suppliers"]; wd = self.o["wd"]
        if wd is None:
            return o
        # запас сверх дней до следующей поставки: при «экономном» и «обычном» замысле он должен
        # покрывать одну сорванную поставку, иначе день недокорма за $5 000 дороже сэкономленного
        # корма. При «надёжном» оставлено прежнее число: замер показал, что 4, 5, 6 и 8 дней дают
        # там один и тот же счёт и те же дни недокорма (лишний корм возвращается по цене закупки),
        # а модели лишние килограммы мешают — она видит другие числа и играет ценой хуже.
        buf = [4, 5, 4][self.stock_lv]
        if sup["frozen"]["delivers_tomorrow"]:
            gap = next(k for k in range(1, 8) if (wd + k) % 7 in sup["frozen"]["days"])
            it = {}
            for k in ("fish", "meat"):
                have = st["freezer"][k] + st["thawed_for_tomorrow"][k] - nd[k]   # завтрашняя норма уже разморожена
                want = nd[k] * (gap + buf) - have
                if want > 0:
                    it[k] = 10 * _ceil(want / 10)
            if it:
                pr = sup["frozen"]["prices_kg"]
                tot = sum(pr[k] * q for k, q in it.items())
                while tot < sup["frozen"]["min_order"]:
                    it["fish"] = it.get("fish", 0) + 10; tot += 10 * pr["fish"]
                room = st["freezer_kg"] - (sum(st["freezer"].values()) + sum(st["thawed_for_tomorrow"].values()) - sum(self.thaw().values()))
                while sum(it.values()) > room and it.get("fish", 0) > 10:
                    it["fish"] -= 10
                o["frozen"] = it
            self.numbers["frozen_cover_days"] = gap + buf
        if sup["hay"]["delivers_tomorrow"] and st["hay"] < nd["hay"] * (8 + 3 * self.stock_lv):
            bale = sup["hay"]["bale_kg"]
            q = max(sup["hay"]["min_kg"], bale * _ceil((nd["hay"] * 14 - st["hay"]) / bale))
            q = min(q, bale * int((st["hay_store_kg"] - st["hay"]) / bale))
            if q >= sup["hay"]["min_kg"]:
                o["hay"] = {"hay": q}
        usable = sum(a for a, b in st["produce"] if b >= self.t)
        cover = [1.2, 1.6, 2.0][self.stock_lv]
        if usable < nd["produce"] * cover:
            o["produce"] = {"produce": max(sup["produce"]["min_kg"], _ceil(nd["produce"] * (cover + 0.5) - usable))}
        return o

    # --- люди ---
    def keepers_for(self, i):
        """Смотрители на день t+i по секциям: минимум, кормления при публике, события."""
        kp = {s: list(self.W["sections"][s]["min"]) for s in SECT}
        day = self.t + i
        for h in range(self.shows):
            kp["pool"][h] = max(kp["pool"][h], self.W["shows"]["pool_keepers_needed"])
        c = self.card("school", day)
        if c and self._choice(c) == "accept":
            kp["yard"][0] += 1
        c = self.card("donor", day)
        if c and self._choice(c) == "tour":
            kp["cats"][0] += self.W["events"]["donor"]["cats_halves"]
        c = self.card("power", day)
        if c and self._choice(c) == "move":
            kp["tropic"] = [kp["tropic"][0] + 1, kp["tropic"][1] + 1]
        if self.staff_lv == 2:
            kp["birds"][1] = max(kp["birds"][1], 2)
        for s in SECT:
            kp[s] = [min(self.W["staff"]["max_per_half"], x) for x in kp[s]]
        return kp

    def demand_k(self):
        """Во сколько раз изменится спрос от выбранной цены: расписание считается уже по ней."""
        W = self.W; base = W["prices"]["adult"]; el = W["elasticity"]
        pct = self.p.get("price", 0)
        pct = pct if isinstance(pct, (int, float)) else 0
        f = lambda pi: pi ** (el["up"] if pi > 1 else el["down"])
        return f(base * (1 + pct / 100.0) / base) / f(self.o["price"] / base)

    def gate_kiosk(self, f):
        q = [0.7, 1.0, 1.0][self.staff_lv]
        extra = [1.0, 1.0, 1.1][self.staff_lv]
        kprice = self.demand_k()
        g = []; k = []
        for h in range(2):
            v = (f["low"][h] + (f["high"][h] - f["low"][h]) * q) * extra * kprice
            if h == 1 and f.get("wd") == 2 and bool(self.p.get("free_wed")) and self.p.get("free_wed") != "expert":
                v *= self.W["free_wed"]["afternoon_mult"]
            g.append(max(1, min(8, _ceil(v * (1 - self.W["mix"]["member"] - self.W["mix"]["group"]) / (self.W["gate_per_cashier_hour"] * self.W["halves"]["hours"][h])))))
            k.append(max(0, min(8, _ceil(v * 0.7 / (self.W["kiosk_per_worker_hour"] * self.W["halves"]["hours"][h])))))
        return g, k

    def schedule(self):
        sch = {k: {"keepers": {s: list(v["keepers"][s]) for s in SECT}, "cashiers": list(v["cashiers"]), "kiosk": list(v["kiosk"]), "shows": v.get("shows", 0)}
               for k, v in self.o["schedule"].items()}
        for i, f in enumerate(self.o["forecast"]):
            wd = str((self.o["wd"] + i) % 7)
            g, k = self.gate_kiosk(f)
            sch[wd] = {"keepers": self.keepers_for(i), "cashiers": g, "kiosk": k, "shows": self.shows}
        # дни недели вне прогноза: та же логика смотрителей, кассы как были
        seen = {str((self.o["wd"] + i) % 7) for i in range(len(self.o["forecast"]))}
        for w in range(7):
            if str(w) not in seen:
                sch[str(w)]["keepers"] = self.keepers_for(3)
                sch[str(w)]["shows"] = self.shows
        self._sch = sch
        return sch

    def hire(self):
        S = self.W["staff"]
        nb = len(self.o["staff"])
        week_halves = sum(sum(sum(self._sch[str(w)]["keepers"][s]) for s in SECT) for w in range(7))
        week_h = week_halves * self.W["halves"]["hours"][0]
        per_half = max(sum(self._sch[str(w)]["keepers"][s][h] for s in SECT) for w in range(7) for h in range(2))
        spare = [0, 1, 2][self.staff_lv]
        need = max(_ceil(week_h / S["overtime_after_h"]), per_half + spare)
        self.numbers.update({"week_keeper_hours": week_h, "keepers_needed": need, "keepers": nb, "max_per_half": per_half})
        if self.n - self.t <= S["hire_delay_days"] + 2:
            return 0
        return max(0, min(3, need - nb))

    def vet_needed(self):
        left = self.n - self.t
        need = self.W["vet_visits_min"] - self.o["vet_visits"]
        if need <= 0:
            return False
        plan_days = [8, 20]
        return self.t in plan_days[-need:] or left <= need + 1

    # --- цена ---
    def price(self):
        pct = self.p.get("price", 0)
        if not isinstance(pct, (int, float)):
            pct = 0
        base = self.W["prices"]["adult"]
        return int(base * (1 + pct / 100.0) * 100 + 0.5) / 100.0

    # --- репутация: множитель посетителей до конца месяца, растёт на drift в день, упирается в max ---
    def rep_value(self, delta, start, rate=None):
        """Деньги от сдвига репутации на delta, начиная со дня start, до конца месяца."""
        R = self.W["reputation"]; r0 = self.o.get("reputation", 1.0)
        rate = R["drift"] + self.W["shows"]["rep"] * self.shows if rate is None else rate
        base = self.avg_visitors() / max(r0, 1e-6)        # посетителей при репутации 1
        tot = 0.0
        for d in range(max(0, start), self.n):
            k = d - self.t
            p0 = min(R["max"], max(R["min"], r0 + rate * k))
            p1 = min(R["max"], max(R["min"], r0 + rate * k + delta))
            tot += (p1 - p0) * base * self.margin
        return tot

    def shows_ev(self):
        """Оценка 0, 1 и 2 кормлений в день до конца месяца: пожертвования, репутация, лишние часы смотрителей."""
        W = self.W; R = W["reputation"]; r0 = self.o.get("reputation", 1.0)
        S = W["staff"]; hh = W["halves"]["hours"][0]
        G = self.avg_visitors(); rem = max(0, self.n - self.t - 1)
        nb = sum(1 for s in self.o["staff"] if s["start"] <= self.t + 1)
        kp = {s: list(W["sections"][s]["min"]) for s in SECT}
        kh = sum(sum(v) for v in kp.values()) * hh
        slack = nb * S["keeper"]["salaried_h_week"] / 7.0 - kh
        out = {}
        for n_ in (0, 1, 2):
            extra_h = n_ * (W["shows"]["pool_keepers_needed"] - W["sections"]["pool"]["min"][0]) * hh
            wage = max(0.0, extra_h - max(0.0, slack)) * S["keeper"]["wage"] * (1 + S["burden"])
            don = W["spend"]["donation_per_show"] * n_ * G
            rate = R["drift"] + W["shows"]["rep"] * n_
            rep = 0.0; base = G / max(r0, 1e-6)
            for k in range(1, rem + 1):
                p0 = min(R["max"], max(R["min"], r0 + R["drift"] * k)); p1 = min(R["max"], max(R["min"], r0 + rate * k))
                rep += (p1 - p0) * base * self.margin
            out[str(n_)] = round((don - wage) * (rem + 1) + rep)
        base0 = out["0"]
        return {k: v - base0 for k, v in out.items()}

    # --- оценки ---
    def avg_visitors(self):
        fc = self.o["forecast"]
        return sum(sum(f["visitors"]) for f in fc) / max(1, len(fc))

    def estimates(self):
        E = {}; W = self.W
        G = self.avg_visitors(); v = self.margin
        if "price" in self.p or "free_wed" in self.p:
            p_new = self.price(); base = W["prices"]["adult"]
            pi_new = p_new / base; pi_old = self.o["price"] / base
            el = W["elasticity"]
            f = lambda pi: pi ** (el["up"] if pi > 1 else el["down"])
            G_new = G * f(pi_new) / f(pi_old)
            E["price_per_day"] = round(G_new * self.visitor_margin(p_new) - G * v)
            self.visitor_margin()
        E["price_options"] = self.price_options()
        fw = self.free_wed_value()
        if fw is not None:
            E["free_wed"] = fw
        fl = self.fill()
        if fl is not None:
            self.numbers["fill_tomorrow"] = fl
            self.numbers["comfort_per_half"] = self.W["crowding"]["comfort_per_half"]
        E["cards"] = {c["id"]: self.card_ev(c, G, v) for c in self.o["cards"]}
        E["shows"] = self.shows_ev()
        return E

    def card_ev(self, c, G, v):
        k = c["kind"]; W = self.W; Ev = W["events"]; P = W["penalties"]
        rem = max(0, self.n - c["day"])
        if k == "heatwave":
            days = Ev["heatwave"]["days"]
            lost = G * W["weather_mult"]["advisory"] * (1 - Ev["heatwave"]["close_mult"]) * days * v
            closed = -self.rep_value(-W["reputation"]["closed_k"] * days, c["day"] + days)
            return {"shade": -Ev["heatwave"]["shade_cost"], "close_midday": round(-lost - closed), "none": None}
        if k == "cubs_press":
            b = Ev["cubs"]["boost"]
            press = (b[0] + b[-1]) / 2 * G * max(0, rem - 1) * v - Ev["cubs"]["press_cost"]
            quiet = Ev["cubs"]["quiet_boost"] * G * max(0, rem - 1) * v
            return {"press": round(press), "quiet": round(quiet)}
        if k == "cubs_watch":
            nights = Ev["cubs"]["watch_days"]; loss = P["death"]
            return {"keeper": round(-Ev["cubs"]["watch_cost_night"] * nights), "camera": round(-Ev["cubs"]["cam_cost"] - 0.05 * loss),
                    "none": round(-Ev["cubs"]["loss_risk"] * loss)}
        if k == "hpai":
            out = {}
            for opt in ("all_indoor", "vulnerable", "none"):
                lost = (1 - Ev["hpai"]["mult"][opt]) * G * rem * v
                hit = Ev["hpai"]["risk"][opt] * (P["death"] + (1 - Ev["hpai"]["hit_mult"]) * G * max(0, rem - 4) * v)
                out[opt] = round(-lost - hit)
            return out
        if k == "pump":
            closed = -self.rep_value(-W["reputation"]["closed_k"], c["day"] + 1)
            lost_shows = W["spend"]["donation_per_show"] * G * self.shows + self.rep_value(W["shows"]["rep"] * self.shows, c["day"] + 1)
            return {"fast": -Ev["pump"]["fast_cost"], "slow": round(-Ev["pump"]["slow_cost"] - (1 - Ev["pump"]["slow_mult"]) * G * v - lost_shows - closed)}
        if k == "power":
            move_staff = 2 * W["halves"]["hours"][0] * W["staff"]["keeper"]["wage"] * (1 + W["staff"]["burden"])
            closed = -self.rep_value(-W["reputation"]["closed_k"], c["day"] + 1)
            return {"generator": -Ev["power"]["generator_cost"], "move": round(-move_staff - (1 - Ev["power"]["move_mult"]) * G * v - closed),
                    "none": round(-P["section_day"] - Ev["power"]["death_risk"] * P["death"])}
        if k == "sealion":
            r = Ev["sealion"]["relapse_risk"]
            return {"vet_now": round(-W["staff"]["vet"]["emergency"] - r * (P["section_day"] + W["staff"]["vet"]["emergency"])), "vet_full": -Ev["sealion"]["vet_full_cost"], "wait": None}
        if k == "school":
            return {"accept": round(Ev["school"]["kids"] * (Ev["school"]["price"] + 3.0 * (1 - W["spend"]["food_cost"]))), "decline": 0}
        if k == "donor":
            a = Ev["donor"]["amounts"]; avg = (a[0] + a[-1]) / 2   # на карточке только разброс
            return {"tour": round(avg), "decline": 0}
        return {o: 0 for o in c["options"]}

    # --- предупреждения ---
    def warnings(self, dec):
        out = []
        avail = sum(1 for s in self.o["staff"] if s["start"] <= self.t) - self.o.get("sick_tomorrow", 0)
        sch = dec["schedule"][str(self.o["wd"])]
        for h in range(2):
            want = sum(sch["keepers"][s][h] for s in SECT)
            if want > avail:
                out.append({"code": "short_" + str(h), "ru": "Завтра %s нужно %d смотрителей, а выйдут %d: секции останутся без минимума ухода (штраф $5 000 за день секции)." % (["утром", "днём"][h], want, avail),
                            "en": "Tomorrow %s needs %d keepers but only %d will show up: sections will miss their care minimum ($5,000 per section-day)." % (["morning", "afternoon"][h], want, avail)})
        need = self.W["vet_visits_min"] - self.o["vet_visits"]
        if need > 0 and self.n - self.t <= need + 2:
            out.append({"code": "vet", "ru": "Ветеринар был %d раз из %d обязательных." % (self.o["vet_visits"], self.W["vet_visits_min"]),
                        "en": "The vet came %d of the %d required times." % (self.o["vet_visits"], self.W["vet_visits_min"])})
        return out
