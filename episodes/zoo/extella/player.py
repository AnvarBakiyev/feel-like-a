"""Игрок Extella для эпизода «Зоопарк»: малая модель решает замысел, эксперт на Extella считает, Проверка игры отказывает.

python3 player.py <place> <team> <scenario> [seed=1]  ->  runs/<scenario>_<place>_<team>_s<seed>.json

Порядок вечера:
 1. эксперт считает оценки при вчерашнем замысле;
 2. модель видит то же, что игрок, плюс оценки, и пишет замысел на языке плана;
 3. форма языка плана проверяется здесь, ошибка с причиной уходит модели;
 4. эксперт превращает замысел в решение; новые предупреждения модель видит один раз;
 5. Проверка игры отказывает с причиной, модель исправляет (до 2 раз);
 6. решение применяется, день идёт. Всё пишется в журнал.
"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import llm  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
import sim  # noqa: E402
import extella_call as X  # noqa: E402
from public_world import public_world  # noqa: E402

# на чём считали месяц: ollama:qwen3.5:9b или openrouter:<модель>@<провайдер>, пишется в журнал
MODEL = llm.tag()
LOCAL_EXPERT = os.environ.get("ZOO_LOCAL_EXPERT") == "1"
CARDS_BY_EXPERT = os.environ.get("ZOO_CARDS") == "expert"   # G4: ответы на карточки выбирает эксперт по оценке, модель только замысел
SHOWS_BY_EXPERT = os.environ.get("ZOO_SHOWS") == "expert"   # G6: число кормлений при публике выбирает эксперт по оценке
PRICE_BY_EXPERT = os.environ.get("ZOO_PRICE") == "expert"   # G14: цену и бесплатную среду выбирает эксперт по деньгам дня
CARDS = json.load(open(os.path.join(HERE, "..", "cards_ny.json"), encoding="utf-8"))
WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
WX = {"clear": "ясно", "rain": "дождь", "hot": "жара от 90 °F", "advisory": "Heat Advisory"}
NOTE = {"advisory": "Heat Advisory", "closed_midday": "вольеры закрыты днём", "cubs": "котята", "hpai": "птичий грипп", "pool_closed_pm": "бассейн закрыт днём",
        "tropic_closed": "тропический дом закрыт", "cubs_lost": "котят потеряли"}
SEC_RU = {"pool": "бассейн", "cats": "барсы", "birds": "птицы", "yard": "двор", "tropic": "тропики"}
LEVELS = ("lean", "normal", "safe")

SYSTEM = """Ты управляющий небольшого зоопарка в Бруклине на 30 дней. Каждый вечер ты выбираешь замысел на завтра. Точную разморозку, заказы кормов, смены и найм считает эксперт по твоему замыслу, правила проверяет Проверка.
Счёт = выручка минус расходы, минус $5 000 за каждый день секции, где животные недокормлены или без минимума ухода, минус $15 000 за нарушение, найденное инспекцией, минус $100 000 за гибель животного, минус $5 за посетителя, ушедшего из-за очереди. Благополучие животных важнее денег.
Ответ: только JSON такого вида:
{"stock": "normal", "staff": "normal", "shows": 2, "price": 0, "free_wed": false, "choices": {}, "why_ru": "...", "why_en": "..."}
stock: запас мороженой рыбы и мяса, сена и овощей. lean дешевле, но если поставщик не приедет, животные недокормлены; safe с запасом.
staff: кассы, киоски и запас смотрителей. lean дешевле, но очередь и меньше еды продано; safe с запасом.
shows: кормлений морских львов при публике в день, 0, 1 или 2. Каждое берёт смотрителя в бассейн и поднимает пожертвования и репутацию.
price: изменение цены взрослого билета в процентах к базовой $12.95, целое от -50 до 100. Дешевле билет, больше людей; дороже, меньше людей, но каждый платит больше. Эксперт каждый вечер считает деньги завтрашнего дня при каждой цене: смотри его строку.
free_wed: бесплатный вход в среду днём, true или false.
choices: ответ на открытые карточки, {"id карточки": "вариант"}. Без ответа сработает вариант по умолчанию. Вариант, запрещённый законом, Проверка отклонит.
why_ru и why_en: одна короткая фраза до 12 слов о главном решении вечера.
Оценка эксперта: насколько в среднем изменится счёт месяца от этого выбора. Минус значит, что выбор в среднем стоит денег. Исход скрытых событий заранее неизвестен."""


def ask_model(messages):
    """Вызов малой модели через llm.py: Ollama на машине или сеть по CAFE_BACKEND."""
    r = llm.ask(messages, num_predict=300)
    return r["content"], r["seconds"], r["prompt_tokens"], r["out_tokens"], r["tries"]


def expert(obs, plan, world):
    if LOCAL_EXPERT:
        from expert_json import load
        zoo_game_plan = load("zoo_game_plan")
        t0 = time.time()
        r = json.loads(json.dumps(zoo_game_plan(obs, plan, world)))
        return r, {"where": "local", "sha": X.code_sha(), "seconds": round(time.time() - t0, 3)}
    return X.run(obs, plan, world)


def check_plan(p, obs):
    errs = []
    if not isinstance(p, dict):
        return ["Ответ должен быть объектом JSON."]
    for k in ("stock", "staff"):
        if k in p and p[k] not in LEVELS:
            errs.append("%s: «%s», допустимо lean, normal, safe." % (k, p[k]))
    if "shows" in p and p["shows"] not in (0, 1, 2):
        errs.append("shows: %s, допустимо 0, 1 или 2." % p["shows"])
    if "price" in p and (not isinstance(p["price"], int) or isinstance(p["price"], bool) or not -50 <= p["price"] <= 100):
        errs.append("price: %s, нужно целое от -50 до 100." % p["price"])
    if "free_wed" in p and not isinstance(p["free_wed"], bool):
        errs.append("free_wed: нужно true или false.")
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


def system_text():
    s = SYSTEM
    if CARDS_BY_EXPERT:
        s = s.replace(', "choices": {}', '').replace(
            "choices: ответ на открытые карточки, {\"id карточки\": \"вариант\"}. Без ответа сработает вариант по умолчанию. Вариант, запрещённый законом, Проверка отклонит.",
            "Ответы на карточки событий выбирает эксперт: вариант с наибольшей оценкой. Ты учитываешь карточки в замысле (люди, запас, цена), choices не пиши.")
    if SHOWS_BY_EXPERT:
        s = s.replace(' "shows": 2,', '').replace(
            "shows: кормлений морских львов при публике в день, 0, 1 или 2. Каждое берёт смотрителя в бассейн и поднимает пожертвования и репутацию.",
            "Кормления морских львов при публике (0, 1 или 2 в день) выбирает эксперт по оценке; shows не пиши.")
    return s


def clean_plan(p, prev):
    out = {"stock": p.get("stock", prev.get("stock", "normal")), "staff": p.get("staff", prev.get("staff", "normal")),
           "shows": p.get("shows", prev.get("shows", 2)), "price": p.get("price", prev.get("price", 0)), "free_wed": p.get("free_wed", prev.get("free_wed", False))}
    if SHOWS_BY_EXPERT:
        out["shows"] = "expert"
    if PRICE_BY_EXPERT:
        out["price"] = "expert"; out["free_wed"] = "expert"
    if CARDS_BY_EXPERT:
        out["cards"] = "expert"
    elif p.get("choices"):
        out["choices"] = dict(p["choices"])
    return out


def money(x):
    return ("−$" if x < 0 else "$") + "{:,}".format(int(abs(x) + 0.5)).replace(",", " ")


def card_text(c, est, today):
    K = CARDS[c["kind"]]
    t = K["ru"]["text"].replace("{day2}", str(c["day"] + 1)).replace("{day}", str(c["day"]))
    opts = []
    for o in c["options"]:
        e = est.get(o, "нет")
        tail = "" if e == "нет" else (", запрещено законом" if e is None else ", оценка " + money(e))
        opts.append("%s = %s%s" % (o, K["options"][o]["ru"], tail))
    ch = " Уже выбрано: %s." % c["chosen"] if c.get("chosen") else ""
    return "[%s] %s. %s Варианты: %s. По умолчанию %s. %s%s" % (
        c["id"], K["ru"]["title"], t, "; ".join(opts), c["default"], "Решить сегодня." if c["decide_by_evening_of"] == today else "Решить до вечера дня %d." % c["decide_by_evening_of"], ch)


def evening_text(g, obs, pre, prev):
    t = obs["day"]; y = obs["yesterday"]; nd = obs["need_kg_per_day"]; st = obs["stock"]
    L = ["Вечер перед днём %d из 30. Завтра %s, %s." % (t, WD[obs["wd"]], WX[obs["forecast"][0]["weather"]])]
    sc = g.score()
    L.append("Репутация %.2f. Счёт месяца сейчас %s. Нарушений ухода за месяц: %d. Ветеринар был %d раз из %d обязательных." % (
        obs["reputation"], money(sc["score"]), obs["violations"], obs["vet_visits"], obs["vet_visits_min"]))
    if y:
        v = ", ".join("%s: %s" % (SEC_RU[s], ", ".join(r)) for s, r in y["violations"].items())
        L.append("Сегодня: посетителей %d, ушли из-за очереди %d, выручка %s, кормлений при публике %d%s%s." % (
            y["visitors"], y["queue_lost"], money(y["revenue"]), y["shows"], ("; нарушения: " + v) if v else "",
            ("; события: " + ", ".join(y["events"])) if y["events"] else ""))
    fc = []
    for f in obs["forecast"]:
        n = ", ".join(NOTE.get(x, x) for x in f["notes"])
        fc.append("день %d (%s, %s%s): %d–%d" % (f["day"], WD[f["wd"]], WX[f["weather"]], (", " + n if n else ""), sum(f["low"]), sum(f["high"])))
    L.append("Прогноз посетителей: " + "; ".join(fc) + ".")
    fish_days = (st["freezer"]["fish"] + st["thawed_for_tomorrow"]["fish"]) / nd["fish"]
    meat_days = (st["freezer"]["meat"] + st["thawed_for_tomorrow"]["meat"]) / nd["meat"]
    L.append("Корм: рыбы на %.1f дня, мяса на %.1f, сена на %.0f; мороженое возят пн и чт." % (fish_days, meat_days, st["hay"] / nd["hay"]))
    ks = obs["staff"]; new = [s for s in ks if s["start"] > t]
    L.append("Смотрителей %d%s, завтра болеет %d. Эксперт: нужно %d смотрителей при твоём замысле." % (
        len(ks), (" (из них %d выйдут с дня %d)" % (len(new), min(s["start"] for s in new)) if new else ""), obs["sick_tomorrow"], pre["numbers"].get("keepers_needed", 0)))
    if obs["price"] != g.Wd["prices"]["adult"] or obs["free_wed"]:
        L.append("Билет сейчас $%.2f%s." % (obs["price"], ", бесплатная среда днём" if obs["free_wed"] else ""))
    E = pre["estimates"]
    # теснота и цена: эксперт считает деньги завтрашнего дня при каждой цене, модель выбирает
    fill = pre["numbers"].get("fill_tomorrow")
    if fill:
        comfort = pre["numbers"].get("comfort_per_half")
        L.append("Заполненность завтра: утро %.0f %%, день %.0f %% от вместимости (%d человек в половину дня). "
                 "Сверх вместимости люди тратят меньше и хуже отзываются." % (fill[0] * 100, fill[1] * 100, comfort))
    po = E.get("price_options")
    if po:
        order = sorted(po, key=lambda k: int(k))
        L.append("Эксперт, деньги завтрашнего дня при цене (проценты к базе, против твоего замысла): "
                 + "; ".join("%s%%: %s" % (k, money(po[k])) for k in order) + ".")
    if E.get("free_wed") is not None:
        L.append("Эксперт: бесплатная среда завтра даёт %s." % money(E["free_wed"]))
    if obs["cards"]:
        L.append("Карточки:")
        for c in obs["cards"]:
            L.append("- " + card_text(c, E["cards"].get(c["id"], {}), t - 1))
    else:
        L.append("Открытых карточек нет.")
    for w in pre["warnings"]:
        L.append("Предупреждение эксперта: " + w["ru"])
    L.append("Твой вчерашний замысел: stock %s, staff %s, shows %s, price %s, free_wed %s." % (prev.get("stock"), prev.get("staff"), prev.get("shows"), prev.get("price"), str(prev.get("free_wed")).lower()))
    L.append("Ответь JSON.")
    return "\n".join(L)


def _isjson(s):
    try:
        json.loads(s); return True
    except Exception:
        return False


def play(place, team, scenario, seed=1, out_dir=None):
    # мир задаётся снаружи: прежние журналы играны на "ny", новый баланс живёт в "ny2"
    wname = os.environ.get("ZOO_WORLD", "ny")
    g = sim.Game(seed, place, team, scenario, wname)
    W = public_world(wname)
    plan = {"stock": "normal", "staff": "normal", "shows": 2, "price": 0, "free_wed": False}
    if CARDS_BY_EXPERT:
        plan["cards"] = "expert"
    if SHOWS_BY_EXPERT:
        plan["shows"] = "expert"
    if PRICE_BY_EXPERT:
        plan["price"] = "expert"; plan["free_wed"] = "expert"
    J = {"episode": "zoo", "world": wname, "combo": {"place": place, "team": team, "scenario": scenario, "seed": seed}, "model": MODEL, "cards_by": "expert" if CARDS_BY_EXPERT else "model", "shows_by": "expert" if SHOWS_BY_EXPERT else "model", "price_by": "expert" if PRICE_BY_EXPERT else "model",
         "expert": {"name": X.NAME, "sha": X.code_sha(), "device": X.DEVICE}, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "evenings": [], "daily": []}
    t0 = time.time()
    while not g.done():
        obs = g.observe()
        ev = {"day": g.t, "calls": [], "expert_calls": []}
        pre, meta = expert(obs, {k: v for k, v in plan.items() if k != "choices"}, W)
        ev["expert_calls"].append(meta)
        user = evening_text(g, obs, pre, plan)
        msgs = [{"role": "system", "content": system_text()}, {"role": "user", "content": user}]
        ev["prompt"] = user
        final = None; new_plan = None; warned = False
        for attempt in range(6):
            raw, secs, pin, pout, tries = ask_model(msgs)
            call = {"raw": raw, "seconds": secs, "prompt_tokens": pin, "out_tokens": pout, "tries": tries}
            ev["calls"].append(call)
            p = json.loads(raw) if _isjson(raw) else None
            errs = check_plan(p, obs) if p is not None else ["Ответ не JSON. Пришли только JSON."]
            if errs:
                call["plan_errors"] = errs
                if sum(1 for c in ev["calls"] if c.get("plan_errors")) > 2:
                    break
                msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Язык плана отказал:\n- " + "\n- ".join(errs) + "\nИсправь и пришли JSON снова."}]
                continue
            cand = clean_plan(p, plan)
            res, meta = expert(obs, cand, W)
            ev["expert_calls"].append(meta)
            new_w = [w for w in res["warnings"] if w["code"] not in {x["code"] for x in pre["warnings"]}]
            if new_w and not warned:
                warned = True; call["warnings_shown"] = new_w
                msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Эксперт по этому замыслу предупреждает:\n- " + "\n- ".join(w["ru"] for w in new_w) + "\nОставь замысел или измени его. Пришли JSON."}]
                continue
            rj, _ = g.check(res["decision"])
            if rj:
                call["rejections"] = rj
                if sum(1 for c in ev["calls"] if c.get("rejections")) >= 2:
                    new_plan, final = cand, res
                    break
                msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Проверка отказала:\n- " + "\n- ".join(r["ru"] for r in rj) + "\nИзмени замысел и пришли JSON."}]
                continue
            new_plan, final = cand, res
            break
        if final is None:
            ev["fallback"] = "previous_plan"
            new_plan = {k: v for k, v in plan.items() if k != "choices"}
            final, meta = expert(obs, new_plan, W)
            ev["expert_calls"].append(meta)
        last = json.loads(ev["calls"][-1]["raw"]) if ev["calls"] and _isjson(ev["calls"][-1]["raw"]) else {}
        last = last if isinstance(last, dict) else {}
        ev["why_ru"] = str(last.get("why_ru", ""))[:240]; ev["why_en"] = str(last.get("why_en", ""))[:240]
        ev["plan"] = new_plan; ev["decision"] = final["decision"]; ev["estimates"] = final["estimates"]; ev["warnings"] = final["warnings"]
        ev["rejections"] = g.decide(final["decision"])
        g.step()
        s = g.score()
        J["daily"].append({"day": g.t - 1, "score": s["score"], "profit": s["profit"]})
        J["evenings"].append(ev)
        plan = new_plan
        print("day %2d  score %9.0f  model %4.1fs x%d  expert %s  %s" % (g.t - 1, s["score"], sum(c["seconds"] for c in ev["calls"]), len(ev["calls"]),
              "+".join(str(m["seconds"]) for m in ev["expert_calls"]), json.dumps({k: v for k, v in new_plan.items() if v not in ({}, [], None)}, ensure_ascii=False)), flush=True)
    J["score"] = g.score(); J["journal"] = g.journal; J["minutes"] = round((time.time() - t0) / 60, 1); J["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    # ZOO_OUT отделяет прогоны на другой точности: смешивать их в одной папке нельзя
    out_dir = out_dir or os.environ.get("ZOO_OUT") or os.path.join(HERE, "runs")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "%s_%s_%s_s%d%s.json" % (scenario, place, team, seed, ("_cx" if CARDS_BY_EXPERT else "") + ("s" if SHOWS_BY_EXPERT else "")))
    json.dump(J, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("score", J["score"]["score"], "minutes", J["minutes"], "->", path)
    return J


if __name__ == "__main__":
    a = sys.argv[1:]
    play(a[0], a[1], a[2], int(a[3]) if len(a) > 3 else 1)
