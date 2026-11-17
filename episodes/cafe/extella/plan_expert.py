def cafe_game_plan(obs, plan, city):
    """Эксперт Extella для «Месяца кофейни»: из замысла модели и наблюдения вечера делает точное решение.

    obs: то же, что видит игрок (sim.Game.observe()).
    plan: замысел модели: stock, staff (lean / normal / safe), buy, prices (проценты к базе), evening_discount, choices.
    city: открытые цифры города (то же, что на странице правил).
    Возвращает decision для Проверки, оценки в долларах для карточек, вложений и цен, и предупреждения о деньгах.
    """
    S = _Ctx(obs, plan or {}, city)
    dec = {"orders": S.orders(), "schedule": S.schedule()}
    hire = S.hire_needed(dec["schedule"])
    if hire:
        dec["hire"] = hire
    if plan.get("buy"):
        dec["buy"] = [b for b in plan["buy"] if b in city["investments"]]
    pr = S.prices()
    if pr:
        dec["prices"] = pr
    if "evening_discount" in plan:
        dec["discounts"] = S.discounts()
    ch = {}
    for c in obs["cards"]:
        pick = (plan.get("choices") or {}).get(c["id"])
        if pick is not None:
            ch[c["id"]] = pick
    if ch:
        dec["choices"] = ch
    return {"decision": dec, "estimates": S.estimates(dec), "warnings": S.warnings(dec), "numbers": S.numbers}


LEVEL = {"lean": 0, "normal": 1, "safe": 2}
ORDER_SHIFT = [-0.10, 0.0, 0.05]   # сдвиг уровня заказа по замыслу: lean, normal, safe

MARKETING_SHORT_K = 5.0  # то же для рекламы; до 14.11 у рекламы наказания не было вовсе
MACHINE_SHORT_K = 5.0  # цена доллара нехватки на закупки. Замер 14.11 на 180 месяцах (extella/ghost.py):
# от 5 и выше счёт не меняется, ниже 5 обрывом падает. Весь выигрыш правки дал не этот вес,
# а исправленный прогноз денег на завтра: до него нехватка считалась от завышенного счёта.


def cash_short(p3, tomorrow, cost):
    """Насколько покупка за cost урежет закупки на три дня. Общая для машины и рекламы.

    Прогноз режется по нулю намеренно: ниже нуля счёт не опускается, симулятор сам берёт
    срочный заём за 10 %. Проверено 14.11 на 540 месяцах призраком: если считать по
    непорезанному прогнозу, наказание вырастает до пятикратной цены покупки и запрещает
    вторую машину там, где она всё равно окупается. На малых деньгах это стоило −$2 228
    на месяц. Подробный разбор — bench/PREDSKAZANIYA.md, раздел G7.
    """
    return max(0.0, p3 - max(0.0, tomorrow - cost)) - max(0.0, p3 - max(0.0, tomorrow))


def _ceil(x):
    i = int(x)
    return i if i >= x - 1e-9 else i + 1


class _Ctx:
    def __init__(self, obs, plan, city):
        self.o = obs; self.p = plan; self.C = city
        self.t = obs["day"]; self.n = obs["days_total"]
        self.stock_lv = LEVEL.get(plan.get("stock", "normal"), 1)
        self.staff_lv = LEVEL.get(plan.get("staff", "normal"), 1)
        M = city["menu"]
        self.D = ["latte", "cold_brew", "drip", "tea"]
        self.milk_g = sum(M[k]["share"] * M[k]["milk_l"] for k in self.D)
        self.beans_g = sum(M[k]["share"] * M[k]["beans_g"] for k in self.D)
        S = city["staff"]
        self.w_b = S["barista"]["wage"] * (1 + S["burden"])
        self.dp_h = [b - a for a, b in city["hours"]["dayparts"]]
        self.numbers = {}
        self.margin = self.guest_margin()

    # --- деньги с одного гостя ---
    def guest_margin(self, prices=None):
        C = self.C; M = C["menu"]; pr = prices or self.o["prices"]; cost = self.o["costs"]
        check = sum(M[k]["share"] * pr[k] for k in self.D) + M["croissant"]["attach"] * pr["croissant"]
        var = sum(M[k]["share"] * cost[k] for k in self.D) + M["croissant"]["attach"] * cost["croissant"]
        fee = C["card_share"] * (check * (1 + C["sales_tax"]) * C["card_fee_pct"] + C["card_fee_fixed"])
        m = check - var - fee - C["supplies_pct"] * check
        self.numbers["margin_per_guest"] = round(m, 2)
        return m

    def dph(self, day, with_machine=None):
        inv = self.o["investments"]["machine2"]
        has = inv["bought_from_day"] is not None and inv["bought_from_day"] <= day
        if with_machine is not None:
            has = with_machine
        if "machine2" in (self.p.get("buy") or []):
            has = True if with_machine is None else with_machine
        return self.C["drinks_per_barista_hour"] + (self.C["investments"]["machine2"]["extra_drinks_per_hour"] if has else 0)

    # --- спрос по дням: прогноз на 3 дня, дальше по дням недели ---
    def price_mult(self, dp):
        base = self.o["prices"]; new = self.new_prices()
        M = self.C["menu"]
        num = sum(M[k]["share"] * self._eff(new, k, dp) for k in self.D)
        den = sum(M[k]["share"] * self._eff(base, k, dp, current=True) for k in self.D)
        r = num / den
        if abs(r - 1) < 1e-9:
            return 1.0
        # прогноз уже учитывает текущие цены; пересчёт через индекс к базе
        b0 = sum(M[k]["share"] * M[k]["price"] for k in self.D)
        e = self.C["elasticity_drinks"]
        def f(pi):
            return pi ** (e["up"] if pi > 1 else e["down"][dp])
        return f(num / b0) / f(den / b0)

    def _eff(self, prices, k, dp, current=False):
        p = prices[k]
        ds = self.o["discounts"] if current else self.new_discounts()
        for d in ds:
            if d["item"] == k and dp in d.get("dayparts", [0, 1, 2]):
                p = p * (1 - d["pct"] / 100.0)
        return p

    def days(self, k):
        """Гости по частям дня на дни t..t+k-1: середина, низ, верх."""
        fc = self.o["forecast"]; out = []
        wm = self.C["weekday_mult"]
        for i in range(k):
            d = self.t + i
            if d >= self.n:
                break
            if i < len(fc):
                f = fc[i]
                pm = [self.price_mult(dp) for dp in range(3)]
                mid = [f["guests"][dp] * pm[dp] for dp in range(3)]
                lo = [f["low"][dp] * pm[dp] for dp in range(3)]
                hi = [f["high"][dp] * pm[dp] for dp in range(3)]
                closed = f.get("closed_if_chosen", False) or self._closing(d)
            else:
                last = out[-1] if out else None
                ref = fc[-1]; wd_ref = ref["wd"]; wd = (wd_ref + (d - ref["day"])) % 7
                k_ = wm[wd] / wm[wd_ref]
                mid = [x * k_ for x in out[len(fc) - 1]["mid"]] if last else [0, 0, 0]
                lo = [x * 0.85 for x in mid]; hi = [x * 1.15 for x in mid]
                closed = False
            if closed:
                mid = [0, 0, 0]; lo = [0, 0, 0]; hi = [0, 0, 0]
            out.append({"day": d, "mid": mid, "lo": lo, "hi": hi, "closed": closed})
        return out

    def _closing(self, d):
        for c in self.o["cards"]:
            if c["kind"] == "blizzard" and c["day"] == d and (self.p.get("choices") or {}).get(c["id"], c["default"]) == "close":
                return True
        return False

    def _chosen(self, kind, day=None):
        for c in self.o["cards"]:
            if c["kind"] == kind and (day is None or c["day"] == day):
                return (self.p.get("choices") or {}).get(c["id"], c.get("chosen") or c["default"])
        return None

    def q(self, lo, hi, p):
        return lo + (hi - lo) * p

    def order_level(self, over_per_guest):
        """Уровень заказа из цены ошибки, как уже сделано для выпечки.

        Нехватка стоит маржу с гостя плюс penalty_stockout, излишек — закупочную цену
        того, что останется. Для молока это $0,12 на гостя, для зерна около нуля, поэтому
        уровень выходит 0,97…0,99. До 14.11 здесь стоял жёсткий список
        [0.5, 0.85, 1.0] по замыслу: при замысле «экономный» заказ считался по медиане
        прогноза и по построению кончался примерно в половине дней. Полки пустели во всех
        36 месяцах прогона G7. Разбор — bench/PREDSKAZANIYA.md, раздел G10.

        Замысел остался сдвигом вокруг расчётного уровня (ORDER_SHIFT), а не отдельным
        числом: «экономный» по-прежнему заказывает меньше «надёжного», но оба внутри
        арифметики цены ошибки.
        """
        # гость, которому не хватило позиции, бьёт по репутации так же, как ушедший
        # из-за очереди, и эта потеря копится до конца месяца: см. rep_terms
        _, rep_extra = self.rep_terms()
        under = self.margin + self.C["penalty_stockout"] + rep_extra * [0.5, 1.0, 1.5][self.stock_lv]
        cr = under / (under + max(0.0, over_per_guest))
        return min(0.99, max(0.5, cr + ORDER_SHIFT[self.stock_lv]))

    # --- закупки ---
    def orders(self):
        o = {}; sup = self.o["suppliers"]; st = self.o["stock"]; C = self.C
        wd = self.o["wd"]
        if wd is None:
            return o
        buf_days = [0.0, 0.5, 1.0][self.stock_lv]
        _dI = C["suppliers"]["dairy"]["items"]["milk"]
        p_milk = self.order_level(self.milk_g * sup["dairy"]["prices"]["milk"] / _dI["liters"])
        p_beans = self.order_level(0.0)
        self.numbers["order_level_milk"] = round(p_milk, 3)
        self.numbers["order_level_beans"] = round(p_beans, 3)
        if sup["dairy"]["delivers_tomorrow"]:
            gap = next(k for k in range(1, 8) if (wd + k) % 7 in sup["dairy"]["days"])
            rows = self.days(gap + 2)
            need = 0.0
            for i, r in enumerate(rows[:gap]):
                need += sum(self.q(r["lo"][dp], r["hi"][dp], p_milk) for dp in range(3)) * self.milk_g
            if len(rows) > gap:
                need += buf_days * sum(rows[gap]["mid"]) * self.milk_g
            need += self._catering_milk(self.t, self.t + gap)
            have = sum(a for a, b in st["milk_l"] if b >= self.t + gap - 1) + sum(min(a, self._milk_until(b)) for a, b in st["milk_l"] if self.t <= b < self.t + gap - 1)
            lit = need - have
            if lit > 0:
                I = C["suppliers"]["dairy"]["items"]["milk"]; price = sup["dairy"]["prices"]["milk"]
                gal = max(_ceil(lit / I["liters"]), _ceil(sup["dairy"]["min_order"] / price - 1e-9))
                o["dairy"] = {"milk": gal}
            self.numbers["milk_need_l"] = round(need, 1); self.numbers["milk_have_l"] = round(have, 1)
        if sup["roaster"]["delivers_tomorrow"]:
            gap = next(k for k in range(1, 8) if (wd + k) % 7 in sup["roaster"]["days"])
            extra = [0, 2, 4][self.stock_lv]
            rows = self.days(gap + extra)
            g = sum(sum(self.q(r["lo"][dp], r["hi"][dp], p_beans) for dp in range(3)) for r in rows)
            g += 60 * self._catering_count(self.t, self.t + gap + extra)
            I = C["suppliers"]["roaster"]["items"]
            lb = (g * self.beans_g) / I["beans"]["grams"] - st["beans_lb"]
            cups = g - st["cups"]
            it = {}
            if lb > 0:
                it["beans"] = _ceil(lb)
            if cups > 0:
                it["cups"] = _ceil(cups / I["cups"]["count"])
            if it:
                tot = it.get("beans", 0) * sup["roaster"]["prices"]["beans"] + it.get("cups", 0) * sup["roaster"]["prices"]["cups"]
                if tot < sup["roaster"]["min_order"]:
                    it["beans"] = it.get("beans", 0) + _ceil((sup["roaster"]["min_order"] - tot) / sup["roaster"]["prices"]["beans"])
                o["roaster"] = it
            self.numbers["beans_guests_covered"] = round(g)
        # пекарня: распродажа против списания, квантиль по цене ошибки
        r = self.days(1)
        if r and not r[0]["closed"]:
            r = r[0]
            M = C["menu"]["croissant"]
            under = self.o["prices"]["croissant"] - self.o["costs"]["croissant"] + C["penalty_stockout"]
            over = self.o["costs"]["croissant"]
            cr = under / (under + over)
            cr = [0.55, cr, min(0.97, cr + 0.1)][self.stock_lv]
            cap = self.capacity_plan(r)
            served = [min(self.q(r["lo"][dp], r["hi"][dp], cr), cap[dp]) for dp in range(3)]
            pc = max(sup["bakery"]["min_qty"], _ceil(sum(served) * M["attach"]))
            o["bakery"] = {"croissant": pc}
            self.numbers["croissant_quantile"] = round(cr, 2)
        return o

    def _milk_until(self, b):
        rows = self.days(b - self.t + 1)
        return sum(sum(r["mid"]) for r in rows) * self.milk_g

    def _catering_count(self, d0, d1):
        n = 0
        for c in self.o["cards"]:
            if c["kind"] == "catering" and d0 <= c["day"] < d1 and (self.p.get("choices") or {}).get(c["id"], c.get("chosen") or c["default"]) == "accept":
                n += 1
        return n

    def _catering_milk(self, d0, d1):
        return 60 * self.C["menu"]["latte"]["milk_l"] * self._catering_count(d0, d1)

    # --- люди ---
    def value_served(self):
        # прямая цена гостя, который не дождался: упущенная маржа и штраф
        return self.margin + self.C["penalty_queue"]

    def rep_terms(self):
        """Что стоит недовольный гость сверх штрафа.

        Репутация ходит по правилу rep += drift - unhappy_k * доля_недовольных, а спрос
        идёт следом за репутацией. Значит доля недовольных drift / unhappy_k отыгрывается
        дрейфом и ничего не стоит, а всё, что сверх неё, роняет репутацию, и потеря спроса
        копится до конца месяца: за D дней она складывается примерно в unhappy_k * D / 2
        потерянных гостей на каждого лишнего недовольного.

        Раньше здесь стояла константа 0, 3 или 6 долларов по уровню замысла. На «впритык»
        она равна нулю, и эксперт не видел цены репутации вовсе: в мире district/low
        репутация просела до 0,94, спрос упал с 316 до 250 гостей, и месяц потерял около
        тысячи гостей при очереди всего в 116 человек за все 30 дней.
        """
        R = self.C["reputation"]
        sustain = R["drift"] / R["unhappy_k"]
        days_left = max(0, self.n - self.t - 1)
        extra = R["unhappy_k"] * days_left * self.margin / 2.0
        return sustain, extra

    def best_n(self, lo, hi, dp, dph, lead, day_kind=None, cap_mult=1.0):
        h = self.dp_h[dp]
        best = None
        mx = self.C["max_per_daypart"] - lead
        v = self.value_served()
        sustain, rep_extra = self.rep_terms()
        rep_extra *= [0.5, 1.0, 1.5][self.staff_lv]
        ed = (lo + hi) / 2.0
        for n in range(1, mx + 1):
            cap = (n + self.C["lead_capacity_share"] * lead) * dph * h * cap_mult
            es = _exp_min_uniform(lo, hi, cap)
            excess = max(0.0, (ed - es) - sustain * ed)   # недовольные сверх того, что отыграет дрейф
            score = v * es - n * h * self.w_b - excess * rep_extra
            if self.staff_lv == 2 and cap < hi:
                score -= 1e6 * (hi - cap) / max(1.0, hi)
            if best is None or score > best[0] + 1e-9:
                best = (score, n, cap)
        return best[1]

    def capacity_plan(self, r):
        dph = self.dph(r["day"])
        cap = []
        for dp in range(3):
            lead = 1 if dp == 0 else 0
            n = self._plan_n(r, dp)
            cm = 0.5 if (dp == 0 and self._chosen("blogger", r["day"]) == "accept") else 1.0
            cap.append((n + self.C["lead_capacity_share"] * lead) * dph * self.dp_h[dp] * cm)
        return cap

    def _plan_n(self, r, dp):
        dph = self.dph(r["day"]); lead = 1 if dp == 0 else 0
        lo, hi = r["lo"][dp], r["hi"][dp]
        if dp == 0 and self._catering_count(r["day"], r["day"] + 1):
            lo += 60; hi += 60
        cm = 0.5 if (dp == 0 and self._chosen("blogger", r["day"]) == "accept") else 1.0
        if r["closed"] or hi <= 0:
            return 1
        return self.best_n(lo, hi, dp, dph, lead, cap_mult=cm)

    def schedule(self):
        sch = {k: {"barista": list(v["barista"]), "lead": list(v["lead"])} for k, v in self.o["schedule"].items()}
        rows = self.days(3)
        for r in rows[:1]:
            wd = str((self.o["wd"]) % 7)
            sch[wd] = {"barista": [self._plan_n(r, dp) for dp in range(3)], "lead": [1, 0, 0]}
        # дни после завтра: предварительно, тоже по прогнозу (перепишутся в свой вечер)
        for i, r in enumerate(rows[1:], start=1):
            wd = str((self.o["wd"] + i) % 7)
            sch[wd] = {"barista": [self._plan_n(r, dp) for dp in range(3)], "lead": [1, 0, 0]}
        self._sched = sch
        return sch

    def hire_needed(self, sch):
        S = self.C["staff"]
        nb = sum(1 for s in self.o["staff"] if s["role"] == "barista")
        week_h = sum(sum(sch[str(w)]["barista"][dp] * self.dp_h[dp] for dp in range(3)) for w in range(7))
        need_ot = _ceil(week_h / S["overtime_after_h"])
        need_dp = max(max(sch[str(w)]["barista"]) for w in range(7))
        # больничный: на день меньше одного человека
        if self._chosen("sick") == "short":
            need_dp += 1
        self.numbers["week_barista_hours"] = week_h; self.numbers["baristas"] = nb
        days_left = self.n - self.t
        if days_left <= S["hire_delay_days"] + 1:
            return 0
        hire = max(0, need_dp - nb)            # без этих людей смену не закрыть
        # ради переработок нанимать, только если экономия до конца месяца больше цены найма
        ot_h = S[ "barista"]["wage"] * (S["overtime_mult"] - 1) * (1 + S["burden"])
        weeks = max(0, days_left - S["hire_delay_days"]) / 7.0
        while nb + hire < need_ot and hire < 3:
            over = week_h - S["overtime_after_h"] * (nb + hire)
            save = min(over, S["overtime_after_h"]) * ot_h * weeks
            if save <= S.get("hire_cost", 0):
                break
            hire += 1
        return min(3, hire)

    # --- цены и скидки ---
    def new_prices(self):
        pr = dict(self.o["prices"])
        for k, pct in (self.p.get("prices") or {}).items():
            if k in pr and isinstance(pct, (int, float)):
                pr[k] = int(self.C["menu"][k]["price"] * (1 + pct / 100.0) * 100 + 0.5) / 100.0
        return pr

    def prices(self):
        if not self.p.get("prices"):
            return {}
        new = self.new_prices()
        return {k: v for k, v in new.items() if abs(v - self.o["prices"][k]) > 1e-9}

    def new_discounts(self):
        if "evening_discount" not in self.p:
            return self.o["discounts"]
        pct = self.p.get("evening_discount") or 0
        if not pct:
            return []
        return [{"item": k, "pct": pct, "dayparts": [2]} for k in self.D]

    def discounts(self):
        return self.new_discounts()

    # --- оценки ---
    def avg_day(self):
        rows = self.days(3)
        rows = [r for r in rows if not r["closed"]] or rows
        return [sum(r["mid"][dp] for r in rows) / max(1, len(rows)) for dp in range(3)]

    def staff_cost_day(self, g, dph):
        tot = 0.0; served = 0.0
        for dp in range(3):
            lead = 1 if dp == 0 else 0
            lo, hi = g[dp] * 0.92, g[dp] * 1.08
            n = self.best_n(lo, hi, dp, dph, lead)
            cap = (n + self.C["lead_capacity_share"] * lead) * dph * self.dp_h[dp]
            served += _exp_min_uniform(lo, hi, cap)
            tot += n * self.dp_h[dp] * self.w_b
        return tot, served

    def estimates(self, dec):
        E = {}; C = self.C; left = self.n - self.t
        g = self.avg_day(); G = sum(g)
        v_net = self.margin
        inv = self.o["investments"]
        if inv["machine2"]["bought_from_day"] is None:
            base = self.C["drinks_per_barista_hour"]
            I = C["investments"]["machine2"]
            # день за днём до конца месяца: машина даёт выигрыш там, где упирается потолок
            # выдачи, то есть на выходных и в дни событий. Один средний день их съедает.
            gain = 0.0
            for r in self.days(left):
                if r["closed"]:
                    continue
                c0, s0 = self.staff_cost_day(r["mid"], base)
                c1, s1 = self.staff_cost_day(r["mid"], base + I["extra_drinks_per_hour"])
                gain += (c0 - c1) + (s1 - s0) * v_net
            val = gain - I["cost"] * (1 - I["residual"])
            # купить сегодня, когда после аренды и покупки не хватит на закупки: пустые полки стоят дороже выгоды машины
            P0 = self.cash_proj({k: v for k, v in dec.items() if k != "buy"})
            T0 = P0["tomorrow"]
            short = cash_short(P0["p3"], T0, I["cost"])
            more_loan = max(0.0, -(T0 - I["cost"])) - max(0.0, -T0)
            self.numbers["machine2_cash_short"] = round(short)
            E["machine2"] = round(val - MACHINE_SHORT_K * short - C.get("loan_penalty", 0.1) * more_loan)
        if inv["marketing"]["bought_from_day"] is None:
            I = C["investments"]["marketing"]
            lift = sum(I["lift"]) / len(I["lift"])
            d = max(0, min(I["days"], left - I["delay"]))
            dph = self.dph(self.t)
            c0, s0 = self.staff_cost_day(g, dph)
            c1, s1 = self.staff_cost_day([x * (1 + lift) for x in g], dph)
            val = ((s1 - s0) * v_net - (c1 - c0)) * d - I["cost"]
            # реклама стоит тех же денег, что и закупки: раньше у неё наказания не было вовсе,
            # и в месяце с отказами заказов эксперт советовал её наравне со второй машиной
            P0 = self.cash_proj({k: v for k, v in dec.items() if k != "buy"})
            T0 = P0["tomorrow"]
            short = cash_short(P0["p3"], T0, I["cost"])
            more_loan = max(0.0, -(T0 - I["cost"])) - max(0.0, -T0)
            self.numbers["marketing_cash_short"] = round(short)
            E["marketing"] = round(val - MARKETING_SHORT_K * short - C.get("loan_penalty", 0.1) * more_loan)
        if self.p.get("prices") or "evening_discount" in self.p:
            old_m = self.margin
            new_m = self.guest_margin(self.new_prices())
            self.margin = old_m
            rows = self.days(1)
            if rows:
                pm = [self.price_mult(dp) for dp in range(3)]
                base_g = [rows[0]["mid"][dp] / pm[dp] if pm[dp] else 0 for dp in range(3)]
                E["prices_per_day"] = round(sum(rows[0]["mid"]) * new_m - sum(base_g) * old_m)
        Ecards = {}
        for c in self.o["cards"]:
            Ecards[c["id"]] = self.card_ev(c, g, G, left, v_net)
        E["cards"] = Ecards
        return E

    def card_ev(self, c, g, G, left, v):
        k = c["kind"]; C = self.C; EV = C.get("events_public", {})
        staff_per_guest = self.w_b * 4 / (C["drinks_per_barista_hour"] * 4)
        vnet = v - staff_per_guest
        rem = max(0, self.n - c["day"])
        if k == "blogger":
            boost = sum(a * b for a, b in zip([-0.1, 0.0, 0.15, 0.35], [0.2, 0.3, 0.3, 0.2]))
            gain = G * boost * min(5, max(0, self.n - c["day"] - 1)) * vnet
            cap0 = (self._sched_n(c["day"], 0) + 0.5) * self.dph(c["day"]) * 4
            lost = max(0.0, g[0] - cap0 * 0.5) - max(0.0, g[0] - cap0)
            return {"accept": round(gain - 60 - lost * self.value_served()), "decline": 0}
        if k == "repair":
            rec = (0.0 + 0.5 + 0.8) / 3
            return {"sign": round(G * 0.2 * rec * min(7, rem) * vnet - 120), "none": 0}
        if k == "inspection":
            loss = 0.35 * 0.1 * G * max(0, rem - 1) * vnet
            return {"clean": round(loss - 250), "none": 0}
        if k == "breakdown":
            if self.dph(c["day"]) > C["drinks_per_barista_hour"]:
                return {"fast": -450, "slow": -200}
            lat = C["menu"]["latte"]["share"] * (g[0] + g[1])
            drip_gap = self.o["prices"]["latte"] - self.o["prices"]["drip"]
            loss = lat * (0.5 * drip_gap + 0.5 * (v + C["penalty_stockout"]))
            return {"fast": -450, "slow": round(-200 - loss)}
        if k == "sick":
            nb = sum(1 for s in self.o["staff"] if s["role"] == "barista" and s["start"] <= c["day"])
            cost = 0.0; lost = 0.0
            for dd in (c["day"], c["day"] + 1):
                for dp in range(3):
                    want = self._sched_n(dd, dp)
                    miss = max(0, want - (nb - 1))
                    cost += miss * 4 * C["staff"]["agency_hourly"]
                    lost += miss * self.dph(dd) * 4
            lost = min(lost, G * 2)
            return {"agency": round(-cost + 0), "short": round(-lost * self.value_served() * 0.5)}
        if k == "catering":
            rev = 60 * (4.5 - self.o["costs"]["latte"])
            extra_staff = (60 / (self.dph(c["day"]) * 4)) * 4 * self.w_b
            return {"accept": round(rev - extra_staff), "decline": 0}
        if k == "blizzard":
            keep = (0.6 + 0.4 + 0.2) / 3
            gb = G / max(0.4, C["weather_mult"].get("blizzard", 0.4)) * keep
            wages = 3 * 4 * self.w_b + 4 * C["staff"]["lead"]["wage"] * (1 + C["staff"]["burden"])
            return {"open": round(gb * v - wages), "close": 0}
        if k == "competitor":
            s = (0.12 + 0.2 + 0.28) / 3
            loyal = (0.05 + s * 2 * 0.05) * G * rem * vnet - 300
            promo = s * 0.5 * G * min(7, rem) * vnet - 500
            return {"loyalty": round(loyal), "promo": round(promo), "none": 0}
        if k == "complaint":
            return {"coupons": round(0.04 * G * rem * vnet - 40), "reply": round(0.02 * G * rem * vnet), "ignore": 0}
        return {o: 0 for o in c["options"]}

    def _sched_n(self, day, dp):
        sch = getattr(self, "_sched", None) or self.o["schedule"]
        wd = (self.o["wd"] + (day - self.t)) % 7 if self.o["wd"] is not None else 0
        return sch[str(wd)]["barista"][dp]

    # --- деньги ---
    def cash_proj(self, dec, extra_buy=0.0):
        """Деньги после сегодняшних трат и завтра вечером (с арендой в первый день) и закупки на 3 дня."""
        C = self.C; cash = self.o["cash"]
        buy = sum(C["investments"][b]["cost"] for b in dec.get("buy", [])) + extra_buy
        buy += (dec.get("hire") or 0) * C["staff"].get("hire_cost", 0)
        sup = self.o["suppliers"]
        orders = 0.0
        for s, it in dec["orders"].items():
            orders += sum(sup[s]["prices"][k] * q for k, q in it.items())
        rent = C.get("rent_month", 0.0) if self.t == 0 else 0.0
        g = self.avg_day(); G = sum(g)
        daily_in = G * self.margin
        c_day, _ = self.staff_cost_day(g, self.dph(self.t))
        daily_out = c_day + C["fixed_month"] / self.n + 4 * C["staff"]["lead"]["wage"] * (1 + C["staff"]["burden"])
        purchases_day = G * (sum(C["menu"][k]["share"] * self.o["costs"][k] for k in self.D) + 0.35 * self.o["costs"]["croissant"])
        after = cash - buy - orders
        # маржа гостя уже без себестоимости, но товар ещё и оплачивается поставщику, то есть
        # день съедает закупки ещё раз. Прибавлять их к деньгам было ошибкой: прогноз завышал
        # счёт на дневную закупку, и предупреждение о пустых полках приходило слишком поздно.
        tomorrow = after - rent + daily_in - daily_out
        return {"cash": cash, "buy": buy, "orders": orders, "rent": rent, "after": after, "tomorrow": tomorrow, "p3": purchases_day * 3}

    def warnings(self, dec):
        W = []
        C = self.C; cash = self.o["cash"]
        P = self.cash_proj(dec)
        buy = P["buy"]
        orders = P["orders"]; rent = P["rent"]; after = P["after"]; tomorrow = P["tomorrow"]; purchases_day = P["p3"] / 3
        self.numbers.update({"cash_now": round(cash), "orders_tonight": round(orders), "buy_tonight": buy, "rent_tomorrow": round(rent),
                             "cash_tomorrow_evening_est": round(tomorrow), "purchases_3_days_est": round(purchases_day * 3)})
        if after < 0:
            W.append({"code": "cash_now", "ru": "Денег на счёте $%d, а покупки и заказы на $%d: часть отклонят." % (cash, buy + orders),
                      "en": "Cash $%d, but purchases and orders total $%d: some will be rejected." % (cash, buy + orders)})
        elif tomorrow < purchases_day * 3:
            W.append({"code": "cash_low", "ru": "Завтра вечером на счёте будет около $%d, а закупки на 3 дня около $%d: заказы начнут отклонять, полки опустеют." % (tomorrow, purchases_day * 3),
                      "en": "Tomorrow evening cash will be about $%d, while 3 days of supplies cost about $%d: orders will start being rejected and shelves will empty." % (tomorrow, purchases_day * 3)})
        # последний вечер для карточки, а выбран не лучший по оценке вариант
        g = self.avg_day(); G = sum(g); left = self.n - self.t
        for c in self.o["cards"]:
            if c.get("decide_by_evening_of") != self.t:
                continue
            ev = self.card_ev(c, g, G, left, self.margin)
            pick = (dec.get("choices") or {}).get(c["id"]) or c.get("chosen") or c["default"]
            best = max(ev, key=lambda o: ev[o])
            if best != pick and ev[best] - ev.get(pick, 0) >= 100:
                W.append({"code": "card_last_" + c["id"],
                          "ru": "Сегодня последний вечер для карточки %s: сейчас выйдет «%s» (оценка %+d), лучший по оценке «%s» (оценка %+d)." % (c["id"], pick, ev.get(pick, 0), best, ev[best]),
                          "en": "Tonight is the last evening for card %s: it will resolve to \"%s\" (estimate %+d); the best by estimate is \"%s\" (estimate %+d)." % (c["id"], pick, ev.get(pick, 0), best, ev[best])})
        return W


def _exp_min_uniform(lo, hi, cap):
    """E[min(D, cap)] для D, равномерного на [lo, hi]."""
    if hi <= lo + 1e-9:
        return min(lo, cap)
    if cap >= hi:
        return (lo + hi) / 2.0
    if cap <= lo:
        return cap
    # часть ниже cap: среднее (lo+cap)/2 с весом (cap-lo)/(hi-lo); выше cap: cap
    w = (cap - lo) / (hi - lo)
    return w * (lo + cap) / 2.0 + (1 - w) * cap
