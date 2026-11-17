"""Игрок без Extella: модель сама решает всё, что решает человек.

Зачем он нужен. В player.py модель пишет только замысел («запас обычный, людей с
запасом»), а точные заказы, смены и цены считает эксперт на Extella. Чтобы сравнение
«с Extella против без Extella» было честным, нужен второй игрок, где та же модель
выдаёт полное решение сама: сколько галлонов молока, сколько людей в каждую смену,
какие цены, что ответить на карточку.

Что видит модель: ровно то же, что видит человек на странице игры — остатки с
сроками, дни привоза и минимальные суммы, прогноз по частям дня с разбросом, смены,
ставки, цены, вложения, карточки. Ничего сверх этого и ничего из расчётов эксперта.

Проверка игры (sim.Game.check) отказывает с причиной, модель исправляет (до 3 раз).
Если годного решения нет, в журнал пишется fallback: заказа нет, смены как были.

python3 player_bare.py <street> <money> <scenario> [seed=1]
  -> runs/<CAFE_OUT>/<scenario>_<street>_<money>_s<seed>.json
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
import sim  # noqa: E402
import llm as LLM  # noqa: E402

MODEL = LLM.tag()
CARDS = json.load(open(os.path.join(HERE, "..", "cards_ny.json"), encoding="utf-8"))
WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
WX = {"clear": "ясно", "rain": "дождь", "snow": "снег", "blizzard": "метель"}
NOTE = {"fair": "ярмарка", "repair": "ремонт тротуара", "blogger": "после блогера", "blizzard": "метель", "competitor": "конкурент",
        "marketing": "реклама", "grade_b": "оценка B"}
SUP = {"dairy": "молочный поставщик", "roaster": "обжарщик", "bakery": "пекарня"}
DP = ["утро", "день", "вечер"]

SYSTEM = """Ты владелец кофейни в Бруклине на 30 дней. Каждый вечер ты решаешь всё сам: что заказать поставщикам, кого поставить в смену, какие держать цены, что ответить на событие. Никто не считает за тебя.
Счёт = прибыль минус $3 за каждого гостя, которому не хватило позиции, минус $5 за каждого, кто ушёл из-за очереди, минус 10 % от займа. Аренда за весь месяц вносится в первый день, поэтому в начале месяца счёт отрицательный: это нормально.
День делится на три части: утро 7–11, день 11–15, вечер 15–19.
Ответ: только JSON такого вида, без пояснений вокруг.
{"orders": {"dairy": {"milk": 0}, "roaster": {"beans": 0, "cups": 0}, "bakery": {"croissant": 0}},
 "schedule": {"barista": [2, 2, 1], "lead": [1, 0, 0]},
 "hire": 0, "fire": 0,
 "prices": {},
 "discounts": [],
 "buy": [],
 "choices": {},
 "why_ru": "...", "why_en": "..."}
orders: сколько заказать у каждого поставщика в его единицах. Заказ придёт завтра утром. Поставщика, который завтра не возит, не указывай. Пустой объект значит «ничего не заказываю».
schedule: сколько бариста и старших в утро, день и вечер завтрашнего дня недели. Старший утром обязателен. Больше, чем есть в штате, поставить нельзя.
hire: нанять бариста (выходят через 3 дня, $500 за человека). fire: уволить.
prices: новая цена в долларах, например {"latte": 6.5}. Пусто значит без изменений.
discounts: список скидок, например [{"item": "latte", "pct": 10, "dayparts": [2]}]. dayparts: 0 утро, 1 день, 2 вечер. Пустой список снимает скидки.
buy: "machine2" (вторая эспрессо-машина) или "marketing" (реклама). Каждое можно купить один раз.
choices: ответ на открытые карточки, {"id карточки": "вариант"}. Без ответа сработает вариант по умолчанию.
why_ru и why_en: одна короткая фраза до 12 слов о главном решении вечера."""


def money(x):
    return ("−$" if x < 0 else "$") + "{:,}".format(int(abs(x) + 0.5)).replace(",", " ")


def card_text(c):
    K = CARDS[c["kind"]]
    tx = K["ru"]["text"].replace("{day2}", str(c["day"] + 1)).replace("{day}", str(c["day"]))
    opts = ["%s = %s" % (o, K["options"][o]["ru"]) for o in c["options"]]
    ch = " Уже выбрано: %s." % c["chosen"] if c.get("chosen") else ""
    return "[%s] %s. %s Варианты: %s. По умолчанию %s. Решить до вечера дня %d.%s" % (
        c["id"], K["ru"]["title"], tx, "; ".join(opts), c["default"], c["decide_by_evening_of"], ch)


def evening_text(g, obs):
    t = obs["day"]; y = obs["yesterday"]; C = g.C
    L = []
    L.append("Вечер перед днём %d из 30. Завтра %s, %s." % (t, WD[obs["wd"]], WX[obs["forecast"][0]["weather"]]))
    L.append("Деньги %s, заём %s, репутация %.2f, оценка санинспекции %s. Счёт месяца сейчас %s." % (
        money(obs["cash"]), money(obs["loan"]), obs["reputation"], obs["grade"], money(g.score()["score"])))
    if y:
        L.append("Сегодня: пришло %d, обслужено %d, ушли из-за очереди %d, не хватило позиции %d, выручка %s, зарплата %s, списано молока %.0f л и круассанов %d%s." % (
            y["demand"], y["served"], y["queue_guests"], y["stockout_guests"], money(y["revenue"]), money(y["wages"]),
            y["milk_written_off_l"], y["croissant_written_off"], (", закрыто" if y["closed"] else "")))
        by = "; ".join("%s: пришло %d, вместимость смены %d, обслужено %d" % (DP[r["dp"]], r["demand"], r["capacity"], r["served"]) for r in y["by_dp"])
        L.append("По частям дня — " + by + ".")
    nd = [e[len("no_delivery_"):] for e in ((y or {}).get("events") or []) if str(e).startswith("no_delivery_")]
    if nd:
        L.append("Сегодня не привезли заказ: %s. Деньги вернулись на счёт, на складе этого нет." % ", ".join(SUP.get(x, x) for x in nd))
    fc = []
    for f in obs["forecast"]:
        n = ", ".join(NOTE.get(x, x) for x in f["notes"])
        fc.append("день %d (%s, %s%s): всего %d–%d, по частям дня %s" % (
            f["day"], WD[f["wd"]], WX[f["weather"]], (", " + n if n else ""), sum(f["low"]), sum(f["high"]),
            "/".join(str(x) for x in f["guests"])))
    L.append("Прогноз гостей: " + "; ".join(fc) + ".")
    st = obs["stock"]
    milk = "; ".join("%.1f л годно по день %d" % (a, b) for a, b in st["milk_l"]) or "нет"
    L.append("Остатки: молоко %s. Зерно %.1f фунтов, стаканы %d, круассаны %d (круассаны не хранятся до утра)." % (
        milk, st["beans_lb"], st["cups"], st["croissant"]))
    M = C["menu"]
    L.append("Расход на гостя в среднем: молоко %.2f л на латте (доля латте %.0f %%), зерно около %.0f г на напиток, один стакан, круассан берёт каждый %.0f-й." % (
        M["latte"]["milk_l"], M["latte"]["share"] * 100,
        sum(M[k]["share"] * M[k]["beans_g"] for k in ("latte", "cold_brew", "drip", "tea")),
        1.0 / max(M["croissant"]["attach"], 1e-9)))
    for s, S in obs["suppliers"].items():
        items = C["suppliers"][s]["items"]
        pr = ", ".join("%s $%.2f за %s" % (k, (S["prices"]["milk"] if k == "milk" else v["price"]),
                                           ("%g л" % v["liters"] if "liters" in v else ("%d шт" % v["count"] if "count" in v else ("1 фунт" if k == "beans" else "1 шт"))))
                       for k, v in items.items())
        when = "возит завтра" if S["delivers_tomorrow"] else "завтра не возит, возит " + ", ".join(WD[x] for x in S["days"])
        lim = (", минимум $%d" % S["min_order"] if S.get("min_order") else "") + (", минимум %d шт" % S["min_qty"] if S.get("min_qty") else "")
        L.append("%s: %s. Цены: %s%s." % (SUP[s].capitalize(), when, pr, lim))
    nb = [s for s in obs["staff"] if s["role"] == "barista"]
    new = [s for s in nb if s["start"] > t]
    row = obs["schedule"][str(obs["wd"])]
    S = C["staff"]
    L.append("В штате бариста %d%s, старших 1. Ставка бариста $%.2f/ч, старшего $%.2f/ч, сверх 40 ч в неделю в полтора раза." % (
        len(nb), (" (из них %d выйдут с дня %d)" % (len(new), min(s["start"] for s in new)) if new else ""),
        S["barista"]["wage"], S["lead"]["wage"]))
    L.append("Смены на завтрашний день недели сейчас: бариста %s, старший %s. Один человек за 4 часа успевает около %d напитков." % (
        row["barista"], row["lead"], C["drinks_per_barista_hour"] * 4))
    L.append("Цены сейчас: " + ", ".join("%s $%.2f" % (k, v) for k, v in obs["prices"].items()) +
             (". Скидки: " + json.dumps(obs["discounts"], ensure_ascii=False) + "." if obs["discounts"] else ". Скидок нет."))
    inv = []
    for k, nm in (("machine2", "вторая машина"), ("marketing", "реклама")):
        b = obs["investments"][k]["bought_from_day"]
        inv.append("%s куплена (с дня %d)" % (nm, b) if b is not None else "%s $%d" % (nm, obs["investments"][k]["cost"]))
    L.append("Вложения: " + "; ".join(inv) + ".")
    if obs["cards"]:
        L.append("Карточки:")
        for c in obs["cards"]:
            L.append("- " + card_text(c))
    else:
        L.append("Открытых карточек нет.")
    L.append("Ответь JSON.")
    return "\n".join(L)


def to_decision(p, obs):
    """Ответ модели -> решение в формате игры. Форму проверяет сама игра."""
    dec = {}
    o = p.get("orders")
    if isinstance(o, dict) and o:
        dec["orders"] = {s: v for s, v in o.items() if isinstance(v, dict) and any(v.values())}
        if not dec["orders"]:
            dec.pop("orders")
    sch = p.get("schedule")
    if isinstance(sch, dict) and ("barista" in sch or "lead" in sch):
        row = obs["schedule"][str(obs["wd"])]
        new = json.loads(json.dumps(obs["schedule"]))
        new[str(obs["wd"])] = {"barista": sch.get("barista", row["barista"]), "lead": sch.get("lead", row["lead"])}
        dec["schedule"] = new
    for k in ("hire", "fire"):
        if p.get(k):
            dec[k] = p[k]
    if isinstance(p.get("prices"), dict) and p["prices"]:
        dec["prices"] = p["prices"]
    if isinstance(p.get("discounts"), list):
        cur = obs["discounts"] or []
        if json.dumps(p["discounts"], sort_keys=True) != json.dumps(cur, sort_keys=True):
            dec["discounts"] = p["discounts"]
    if p.get("buy"):
        dec["buy"] = p["buy"]
    if isinstance(p.get("choices"), dict) and p["choices"]:
        dec["choices"] = p["choices"]
    return dec


def play(street, money_, scenario, seed=1, out_dir=None):
    g = sim.Game(seed, street, money_, scenario)
    J = {"combo": {"street": street, "money": money_, "scenario": scenario, "seed": seed}, "model": MODEL, "expert": None,
         "player": "bare", "started": time.strftime("%Y-%m-%d %H:%M:%S"), "evenings": [], "daily": []}
    t_start = time.time()
    while g.t < g.C["days"]:
        obs = g.observe()
        ev = {"day": g.t, "calls": []}
        user = evening_text(g, obs)
        ev["prompt"] = user
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        dec = None
        for attempt in range(4):
            r = LLM.ask(msgs, num_predict=600)
            raw = r["content"]
            call = {"raw": raw, "seconds": r["seconds"], "prompt_tokens": r["prompt_tokens"], "out_tokens": r["out_tokens"]}
            ev["calls"].append(call)
            try:
                p = json.loads(raw)
                assert isinstance(p, dict)
            except Exception:
                call["plan_errors"] = ["Ответ не JSON."]
                if attempt >= 2:
                    break
                msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Ответ не разобрался как JSON. Пришли только JSON нужного вида."}]
                continue
            cand = to_decision(p, obs)
            rej, _ = g.check(cand)
            if rej:
                call["rejections"] = rej
                if attempt >= 2:
                    break
                msgs += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": "Проверка игры отказала:\n- " + "\n- ".join(x["ru"] for x in rej) + "\nИсправь и пришли JSON снова."}]
                continue
            dec = cand
            ev["why_ru"] = str(p.get("why_ru", ""))[:240]
            ev["why_en"] = str(p.get("why_en", ""))[:240]
            break
        if dec is None:
            ev["fallback"] = "empty_decision"   # заказа нет, смены как были
            dec = {}
        ev["decision"] = dec
        ev["rejections"] = g.decide(dec)
        g.step()
        s = g.score()
        J["daily"].append({"day": g.t - 1, "score": s["score"], "profit": s["profit"], "cash": g.cash, "loan": g.loan})
        J["evenings"].append(ev)
        print("day %2d  score %8.0f  model %5.1fs x%d%s" % (
            g.t - 1, s["score"], sum(c["seconds"] for c in ev["calls"]), len(ev["calls"]),
            "  FALLBACK" if ev.get("fallback") else ""), flush=True)
    J["score"] = g.score(); J["journal"] = g.journal
    J["minutes"] = round((time.time() - t_start) / 60, 1); J["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    J["tokens"] = {"in": sum(c["prompt_tokens"] or 0 for e in J["evenings"] for c in e["calls"]),
                   "out": sum(c["out_tokens"] or 0 for e in J["evenings"] for c in e["calls"])}
    J["fallbacks"] = sum(1 for e in J["evenings"] if e.get("fallback"))
    out_dir = out_dir or os.path.join(HERE, "runs", os.environ.get("CAFE_OUT", "bare"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "%s_%s_%s_s%d.json" % (scenario, street, money_, seed))
    json.dump(J, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("score", J["score"]["score"], "fallbacks", J["fallbacks"], "minutes", J["minutes"], "tokens", J["tokens"], "->", path)
    return J


if __name__ == "__main__":
    a = sys.argv[1:]
    play(a[0], a[1], a[2], int(a[3]) if len(a) > 3 else 1)
