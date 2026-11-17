"""Игрок Extella для «Месяца кофейни»: малая модель решает замысел, эксперт на Extella считает, Проверка игры отказывает.

python3 player.py <street> <money> <scenario> [seed=1]  ->  runs/<scenario>_<street>_<money>_s<seed>.json

Каждый вечер:
 1. эксперт (на Extella) считает оценки при вчерашнем замысле;
 2. модель (Qwen 3.5 9B: Ollama на машине или OpenRouter, см. llm.py) видит то же, что игрок, плюс оценки эксперта, и пишет замысел на языке плана;
 3. язык плана проверяется здесь (форма), ошибка с причиной уходит модели;
 4. эксперт превращает замысел в решение; если появились новые предупреждения о деньгах, модель видит их один раз;
 5. Проверка игры (sim.Game.check) отказывает с причиной, модель исправляет (до 2 раз);
 6. решение применяется, день идёт. Всё пишется в журнал. Ничего не досчитывается после.
"""
import hashlib, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
import sim  # noqa: E402
import extella_call as X  # noqa: E402
import llm as LLM  # noqa: E402
from public_city import public_city  # noqa: E402

MODEL = LLM.tag()
LOCAL_EXPERT = os.environ.get("CAFE_LOCAL_EXPERT") == "1"   # только для отладки; журнал помечает where=local
CARDS = json.load(open(os.path.join(HERE, "..", "cards_ny.json"), encoding="utf-8"))
WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
WX = {"clear": "ясно", "rain": "дождь", "snow": "снег", "blizzard": "метель"}
NOTE = {"fair": "ярмарка", "repair": "ремонт тротуара", "blogger": "после блогера", "blizzard": "метель", "competitor": "конкурент",
        "marketing": "реклама", "grade_b": "оценка B"}
LEVELS = ("lean", "normal", "safe")
SUP = {"dairy": "молочный поставщик", "roaster": "обжарщик", "bakery": "пекарня"}

SYSTEM = """Ты владелец кофейни в Бруклине на 30 дней. Каждый вечер ты выбираешь замысел на завтра. Точные заказы поставщикам и смены считает эксперт по твоему замыслу, правила проверяет Проверка.
Счёт = прибыль минус $3 за гостя, которому не хватило позиции, минус $5 за гостя, ушедшего из-за очереди, минус 10 % от займа.
Ответ: только JSON такого вида:
{"stock": "normal", "staff": "normal", "buy": [], "prices": {}, "evening_discount": 0, "choices": {}, "why_ru": "...", "why_en": "..."}
stock: запас молока, зерна и выпечки. lean дешевле, но чаще пустые полки; safe реже пустые полки, но больше списаний.
staff: сколько людей за стойкой. lean дешевле, но очереди и падение репутации; safe без очередей, но дороже.
buy: "machine2" (вторая эспрессо-машина $3500) или "marketing" (реклама $1500). Каждое можно купить один раз. Эксперт присылает оценку каждого в долларах к счёту месяца.
prices: изменение цены в процентах к базовой, целое от -10 до 10, например {"latte": 5}. Ключи: latte, cold_brew, drip, tea, croissant. Пусто значит без изменений.
evening_discount: 0, 10 или 20 (процент скидки на напитки вечером).
choices: ответ на открытые карточки, {"id карточки": "вариант"}. Без ответа сработает вариант по умолчанию.
why_ru и why_en: одна короткая фраза до 12 слов о главном решении вечера (по-русски и по-английски).
Оценка эксперта: насколько в среднем изменится счёт месяца от этого выбора. Минус значит, что в среднем выбор убыточен. Исход скрытых событий заранее неизвестен.
Аренда за весь месяц вносится в первый день, поэтому в начале месяца счёт отрицательный: это нормально."""


def ask_model(messages):
    """Вызов малой модели через общий слой tools/llm.py.

    Путь и провайдер задаются окружением: по умолчанию Ollama на машине, как во всех
    прежних замерах; CAFE_BACKEND=openrouter зовёт ту же модель в сети. Какой путь
    сработал, видно в журнале в поле model.
    """
    r = LLM.ask(messages, num_predict=350)
    return r["content"], r["seconds"], r["prompt_tokens"], r["out_tokens"]


def expert(obs, plan, city):
    if LOCAL_EXPERT:
        from plan_expert import cafe_game_plan
        t0 = time.time()
        r = json.loads(json.dumps(cafe_game_plan(obs, plan, city)))
        return r, {"where": "local", "sha": X.code_sha(), "seconds": round(time.time() - t0, 3)}
    return X.run(obs, plan, city)


# --- язык плана: форма ---
def check_plan(p, obs):
    errs = []
    if not isinstance(p, dict):
        return ["Ответ должен быть объектом JSON."]
    for k in ("stock", "staff"):
        if k in p and p[k] not in LEVELS:
            errs.append("%s: «%s», допустимо lean, normal, safe." % (k, p[k]))
    buy = p.get("buy", [])
    if not isinstance(buy, list):
        errs.append("buy: нужен список, например [] или [\"machine2\"].")
    else:
        for b in buy:
            if b not in obs["investments"]:
                errs.append("buy: нет вложения «%s», есть machine2 и marketing." % b)
            elif obs["investments"][b]["bought_from_day"] is not None:
                errs.append("buy: %s уже куплено, второй раз нельзя." % b)
    pr = p.get("prices", {}) or {}
    if not isinstance(pr, dict):
        errs.append("prices: нужен объект, например {\"latte\": 5}.")
    else:
        for k, v in pr.items():
            if k not in obs["prices"]:
                errs.append("prices: нет позиции «%s»." % k)
            elif not isinstance(v, int) or isinstance(v, bool) or v < -10 or v > 10:
                errs.append("prices.%s: %s, нужно целое от -10 до 10." % (k, v))
    if "evening_discount" in p and p["evening_discount"] not in (0, 10, 20):
        errs.append("evening_discount: %s, допустимо 0, 10 или 20." % p["evening_discount"])
    ch = p.get("choices", {}) or {}
    open_ = {c["id"]: c for c in obs["cards"]}
    if not isinstance(ch, dict):
        errs.append("choices: нужен объект {\"id\": \"вариант\"}.")
    else:
        for cid, v in ch.items():
            if cid not in open_:
                errs.append("choices: карточки «%s» сейчас нет; открытые: %s." % (cid, ", ".join(open_) or "нет"))
            elif v not in open_[cid]["options"]:
                errs.append("choices.%s: «%s», варианты: %s." % (cid, v, ", ".join(open_[cid]["options"])))
    return errs


def clean_plan(p, prev):
    """Замысел на завтра: что модель не назвала, берётся из вчерашнего (кроме buy и choices)."""
    out = {"stock": p.get("stock", prev.get("stock", "normal")), "staff": p.get("staff", prev.get("staff", "normal"))}
    if p.get("buy"):
        out["buy"] = list(p["buy"])
    pr = p.get("prices")
    out["prices"] = dict(pr) if isinstance(pr, dict) else dict(prev.get("prices", {}))
    out["evening_discount"] = p.get("evening_discount", prev.get("evening_discount", 0))
    if p.get("choices"):
        out["choices"] = dict(p["choices"])
    return out


def money(x):
    return ("−$" if x < 0 else "$") + "{:,}".format(int(abs(x) + 0.5)).replace(",", " ")


def card_text(c, est):
    K = CARDS[c["kind"]]
    t = K["ru"]["text"].replace("{day2}", str(c["day"] + 1)).replace("{day}", str(c["day"]))
    opts = []
    for o in c["options"]:
        e = est.get(o)
        opts.append("%s = %s%s" % (o, K["options"][o]["ru"], ("" if e is None else ", оценка " + money(e))))
    ch = " Уже выбрано: %s." % c["chosen"] if c.get("chosen") else ""
    return "[%s] %s. %s Варианты: %s. По умолчанию %s. Решить до вечера дня %d.%s" % (
        c["id"], K["ru"]["title"], t, "; ".join(opts), c["default"], c["decide_by_evening_of"], ch)


def evening_text(g, obs, pre, prev_plan):
    t = obs["day"]; y = obs["yesterday"]
    L = []
    L.append("Вечер перед днём %d из 30. Завтра %s, %s." % (t, WD[obs["wd"]], WX[obs["forecast"][0]["weather"]]))
    sc = g.score()
    L.append("Деньги %s, заём %s, репутация %.2f, оценка санинспекции %s. Счёт месяца сейчас %s." % (
        money(obs["cash"]), money(obs["loan"]), obs["reputation"], obs["grade"], money(sc["score"])))
    if y:
        L.append("Сегодня: пришло %d, обслужено %d, ушли из-за очереди %d, не хватило позиции %d, выручка %s, списано молока %.0f л и круассанов %d%s." % (
            y["demand"], y["served"], y["queue_guests"], y["stockout_guests"], money(y["revenue"]), y["milk_written_off_l"], y["croissant_written_off"],
            (", закрыто" if y["closed"] else "")))
    nd = [e[len("no_delivery_"):] for e in ((y or {}).get("events") or []) if str(e).startswith("no_delivery_")]
    if nd:
        L.append("Сегодня не привезли заказ: %s. Деньги за него вернулись на счёт; на складе этого нет." % ", ".join(SUP.get(x, x) for x in nd))
    fc = []
    for f in obs["forecast"]:
        n = ", ".join(NOTE.get(x, x) for x in f["notes"])
        fc.append("день %d (%s, %s%s): %d–%d" % (f["day"], WD[f["wd"]], WX[f["weather"]], (", " + n if n else ""), sum(f["low"]), sum(f["high"])))
    L.append("Прогноз гостей: " + "; ".join(fc) + ".")
    nb = [s for s in obs["staff"] if s["role"] == "barista"]
    new = [s for s in nb if s["start"] > t]
    L.append("Бариста %d%s, старший 1." % (len(nb), (" (из них %d выйдут с дня %d)" % (len(new), min(s["start"] for s in new)) if new else "")))
    E = pre["estimates"]
    inv = []
    for k, nm in (("machine2", "вторая машина"), ("marketing", "реклама")):
        b = obs["investments"][k]["bought_from_day"]
        if b is not None:
            inv.append("%s куплена (с дня %d)" % (nm, b))
        elif k in E:
            inv.append("%s $%d, оценка эксперта %s к счёту" % (nm, obs["investments"][k]["cost"], money(E[k])))
    L.append("Вложения: " + "; ".join(inv) + ".")
    if obs["prices"] != {k: v["price"] for k, v in g.C["menu"].items()} or obs["discounts"]:
        L.append("Цены сейчас: " + ", ".join("%s $%.2f" % (k, v) for k, v in obs["prices"].items()) +
                 (". Вечерняя скидка %d %%." % obs["discounts"][0]["pct"] if obs["discounts"] else "."))
    if obs["cards"]:
        L.append("Карточки:")
        for c in obs["cards"]:
            L.append("- " + card_text(c, E["cards"].get(c["id"], {})))
    else:
        L.append("Открытых карточек нет.")
    for w in pre["warnings"]:
        L.append("Предупреждение эксперта: " + w["ru"])
    L.append("Твой вчерашний замысел: stock %s, staff %s%s." % (prev_plan.get("stock", "normal"), prev_plan.get("staff", "normal"),
                                                             (", цены " + json.dumps(prev_plan["prices"]) if prev_plan.get("prices") else "")))
    L.append("Ответь JSON.")
    return "\n".join(L)


def play(street, money_, scenario, seed=1, out_dir=None):
    g = sim.Game(seed, street, money_, scenario)
    city = public_city(street)
    plan = {"stock": "normal", "staff": "normal"}
    J = {"combo": {"street": street, "money": money_, "scenario": scenario, "seed": seed}, "model": MODEL, "expert": {"name": X.NAME, "sha": X.code_sha(), "device": X.DEVICE},
         "started": time.strftime("%Y-%m-%d %H:%M:%S"), "evenings": [], "daily": []}
    t_start = time.time()
    while g.t < g.C["days"]:
        obs = g.observe()
        ev = {"day": g.t, "calls": [], "expert_calls": []}
        pre, meta = expert(obs, {k: v for k, v in plan.items() if k not in ("buy", "choices")}, city)
        ev["expert_calls"].append(meta)
        user = evening_text(g, obs, pre, plan)
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        ev["prompt"] = user
        new_plan = None; final = None; extra_warn_shown = False
        for attempt in range(6):
            raw, secs, pin, pout = ask_model(msgs)
            call = {"raw": raw, "seconds": secs, "prompt_tokens": pin, "out_tokens": pout}
            ev["calls"].append(call)
            try:
                p = json.loads(raw)
            except Exception:
                p = None
            errs = check_plan(p, obs) if p is not None else ["Ответ не JSON. Пришли только JSON."]
            if errs:
                call["plan_errors"] = errs
                if sum(1 for c in ev["calls"] if c.get("plan_errors")) > 2:
                    break
                msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Язык плана отказал:\n- " + "\n- ".join(errs) + "\nИсправь и пришли JSON снова."}]
                continue
            cand = clean_plan(p, plan)
            res, meta = expert(obs, cand, city)
            ev["expert_calls"].append(meta)
            new_w = [w for w in res["warnings"] if w["code"] not in {x["code"] for x in pre["warnings"]}]
            if new_w and not extra_warn_shown:
                extra_warn_shown = True
                call["warnings_shown"] = new_w
                msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Эксперт по этому замыслу предупреждает:\n- " + "\n- ".join(w["ru"] for w in new_w) + "\nОставь замысел или измени его. Пришли JSON."}]
                continue
            rej, _ = g.check(res["decision"])
            if rej:
                call["rejections"] = rej
                if sum(1 for c in ev["calls"] if c.get("rejections")) >= 2:
                    new_plan, final = cand, res
                    break
                msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Проверка отказала:\n- " + "\n- ".join(r["ru"] for r in rej) + "\nИзмени замысел и пришли JSON."}]
                continue
            new_plan, final = cand, res
            break
        if final is None:
            # модель не дала годного замысла: вчерашний замысел без покупок и выборов, это пишется в журнал
            ev["fallback"] = "previous_plan"
            new_plan = {k: v for k, v in plan.items() if k not in ("buy", "choices")}
            final, meta = expert(obs, new_plan, city)
            ev["expert_calls"].append(meta)
        last = json.loads(ev["calls"][-1]["raw"]) if ev["calls"] and _isjson(ev["calls"][-1]["raw"]) else {}
        ev["why_ru"] = str(last.get("why_ru", ""))[:240]; ev["why_en"] = str(last.get("why_en", ""))[:240]
        ev["plan"] = new_plan; ev["decision"] = final["decision"]; ev["estimates"] = final["estimates"]; ev["warnings"] = final["warnings"]
        ev["rejections"] = g.decide(final["decision"])
        g.step()
        s = g.score()
        J["daily"].append({"day": g.t - 1, "score": s["score"], "profit": s["profit"], "cash": g.cash, "loan": g.loan})
        J["evenings"].append(ev)
        plan = new_plan
        print("day %2d  score %8.0f  model %4.1fs x%d  expert %s  %s" % (g.t - 1, s["score"], sum(c["seconds"] for c in ev["calls"]), len(ev["calls"]),
              "+".join(str(m["seconds"]) for m in ev["expert_calls"]), json.dumps({k: v for k, v in new_plan.items() if v not in ({}, [], 0)}, ensure_ascii=False)), flush=True)
    J["score"] = g.score(); J["journal"] = g.journal; J["minutes"] = round((time.time() - t_start) / 60, 1); J["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out_dir = out_dir or os.path.join(HERE, "runs", os.environ.get("CAFE_OUT", ""))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "%s_%s_%s_s%d.json" % (scenario, street, money_, seed))
    json.dump(J, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("score", J["score"]["score"], "minutes", J["minutes"], "->", path)
    return J


def _isjson(s):
    try:
        json.loads(s); return True
    except Exception:
        return False


if __name__ == "__main__":
    a = sys.argv[1:]
    play(a[0], a[1], a[2], int(a[3]) if len(a) > 3 else 1)
