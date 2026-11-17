"""Игрок Extella для эпизода «курьер дронов»: малая модель пишет замысел смены на языке полёта,
эксперт drone_plan на Extella проверяет его по прогнозу и ведёт смену.

python3 player.py <city> <seed>  ->  runs/<city>_s<seed>.json

1. Модель (qwen3.5:9b, Ollama на Mac) видит брифинг: карта, прогноз ветра по часам, цифры дрона, счёт, лента заказов.
2. Эксперт на Extella проверяет замысел (разбор, здравый смысл, прогон на прогнозе и на худшем крае прогноза).
   Отказ с причиной уходит модели, до 2 исправлений.
3. Принятый замысел ведёт тот же эксперт в мире зерна (со скрытым ветром и порывами). Журнал пишется как есть.
"""
import json, math, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import sim  # noqa: E402
import extella_call as X  # noqa: E402

MODEL = os.environ.get("DRONE_MODEL", "qwen3.5:9b")
STAGE = int(os.environ.get("DRONE_STAGE", "2"))      # 2: разница в счёте от одной строки; 4: цепочка строк и пределы по точке
CITY_RU = {"almaty": "Алматы", "dubai": "Дубай", "rotterdam": "Роттердам"}
ROSE = ("севера", "северо-востока", "востока", "юго-востока", "юга", "юго-запада", "запада", "северо-запада")
ROSE_TO = ("северу", "северо-востоку", "востоку", "юго-востоку", "югу", "юго-западу", "западу", "северо-западу")

SYSTEM = """Ты диспетчер доставки дронами. До смены ты пишешь замысел на языке полёта. Смену ведёт обработчик: он сам решает, какой дрон и когда летит, и перед каждым взлётом считает круг по прогнозу ветра по худшему краю. Рейс, который по прогнозу не возвращается с запасом, он не начинает, и правила (ветер выше 12 м/с, масса, запретные зоны, мощность батареи в жару) соблюдает сам.
Команды (по одной в строке, любую можно не писать, тогда берётся значение по умолчанию):
высота 60             (30, 60, 100 или 120 м; по умолчанию 60)
скорость эконом       (эконом 12 м/с или быстро 18 м/с; по умолчанию эконом)
груз до 20 кг         (не брать заказы тяжелее; по умолчанию 40 кг)
заказов за рейс 2     (1, 2 или 3 заказа подряд за один рейс; по умолчанию 1)
запас 20              (сколько процентов заряда должно остаться по возвращении на склад; по умолчанию 15)
зарядка на площадке 6 если заряд меньше 35   (возвращаться через площадку зарядки; номер площадки из брифинга)
сначала срочные       (срочные, близкие или тяжёлые; по умолчанию срочные)
не лететь дальше 8 км (совсем не брать дальние точки)
Ответ: только строки замысла. В конце две строки комментария: «# ru: почему так» и «# en: why», не длиннее 12 слов каждая."""

POINT_LINES = """точка N груз до K кг (предел груза на одной точке; вместо N поставь номер точки из брифинга, вместо K килограммы)
точку N пропускать    (эту точку совсем не обслуживать; номер точки из брифинга)
"""


def system_text(stage):
    """Ступень 4 добавляет в язык строки про точку, и модель должна их видеть."""
    if stage < 4:
        return SYSTEM
    mark = "не лететь дальше 8 км (совсем не брать дальние точки)" + chr(10)
    return SYSTEM.replace(mark, mark + POINT_LINES)

RULES = """Счёт смены: 1000 очков; +40 за доставленный заказ; −1 за каждые 10 с опоздания; −60 за недоставленный; −250 за вынужденную посадку вне площадки; −600 за потерянный дрон; −10 за посадку на зарядку; ±2 очка за каждый процент энергии к эталону (эталон: туда и обратно по прямой в штиль на эконом-скорости).
Заказы: 12-16 за смену, приходят в течение смены, груз от 2 до 30 кг, срок 25-50 минут с появления. Куда придёт заказ, заранее неизвестно."""


def _n(x, d=1):
    s = ("%." + str(d) + "f") % (x + 0.0)
    if s == "-0" or s == "-0.0":
        s = s[1:]
    return s.replace(".", ",")


def rose(dx, dy):
    """Откуда дует, словом: вектор «куда» -> сторона, откуда."""
    a = math.degrees(math.atan2(-dx, -dy)) % 360.0
    return ROSE[int((a + 22.5) % 360 // 45)]


def rose_to(dx, dy):
    """Куда смотрит вектор, словом (к северу, к юго-западу)."""
    a = math.degrees(math.atan2(dx, dy)) % 360.0
    return ROSE_TO[int((a + 22.5) % 360 // 45)]


def drone_facts(g):
    zc = g.M["depot"]["z"]
    ph = g.p_hover(sim.D["empty_kg"], zc)
    ph30 = g.p_hover(sim.D["empty_kg"] + 30, zc)
    hr = g.hour()
    L = ["Дрон (3 штуки): пустой 65 кг, груз до 40 кг, взлётная масса до 95 кг, батарея 3969 Вт·ч, предел ветра 12 м/с.",
         "Висение у склада: пустой %s кВт (хватает на %s мин), с грузом 30 кг %s кВт (%s мин). Мощность висения растёт как масса в степени 1,25." % (
             _n(ph / 1000, 1), _n(sim.D["battery_wh"] / ph * 60, 0), _n(ph30 / 1000, 1), _n(sim.D["battery_wh"] / ph30 * 60, 0)),
         "Полёт вперёд стоит почти столько же, сколько висение: на 12 м/с 0,95 от висения, на 18 м/с 1,01.",
         "Ветер складывается с воздушной скоростью: против ветра 9 м/с на эконом-скорости 12 м/с дрон идёт над землёй 3 м/с, и километр стоит в 4 раза дороже, чем в штиль.",
         "Подъём стоит на 15 % больше висения, спуск на 10 % меньше; подъём и спуск идут по 3 м/с. Выгрузка заказа: 40 с висения на 20 м.",
         "Замена батареи на складе 90 с, на площадке зарядки 120 с. Ниже 8 % заряда автопилот садится там, где он есть.",
         "Сейчас у склада %s °C: ёмкость батареи %s %% от полной, батарея даёт не больше %s кВт." % (_n(hr["t"], 0), _n(100 * hr["cap"], 0), _n(hr["pmax"] / 1000, 1))]
    return L


def briefing(g):
    M = g.M; o = g.observe()
    L = ["Город: %s, %s, смена 13:00-15:00." % (CITY_RU[g.city], g.W["day"])]
    L.append("Склад: %s, %s м над морем." % (M["depot"]["ru"], _n(M["depot"]["z"], 0)))
    L.append("Точки (расстояние от склада, высота над морем):")
    for p in M["points"]:
        d = math.sqrt(p["x"] * p["x"] + p["y"] * p["y"]) / 1000.0
        L.append("  %d %s: %s км, %s м%s" % (p["id"], p["ru"], _n(d, 1), _n(p["z"], 0), ", площадка зарядки" if p["pad"] else ""))
    for nf in M["nofly"]:
        L.append("Запретная зона: %s, радиус %s км, центр в %s км от склада к %s (летать через неё нельзя)." % (
            nf["ru"], _n(nf["r"] / 1000.0, 1), _n(math.sqrt(nf["x"] * nf["x"] + nf["y"] * nf["y"]) / 1000.0, 1), rose_to(nf["x"], nf["y"])))
    L.append("Прогноз ветра (сила и откуда дует):")
    for h in o["forecast"]:
        parts = []
        for a in (30, 60, 120):
            u, v = h["wind"][a]
            parts.append("%d м: %s м/с с %s" % (a, _n(math.sqrt(u * u + v * v), 1), rose(u, v)))
        L.append("  %02d:00, %s °C; %s" % (h["hour"], _n(h["t"], 0), "; ".join(parts)))
    L += drone_facts(g)
    L.append(RULES)
    L.append("Напиши замысел.")
    return chr(10).join(L)


def ask_model(messages):
    body = {"model": MODEL, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 400}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        out = json.loads(r.read())
    return out["message"]["content"], round(time.time() - t0, 2)


def clean(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = chr(10).join(x for x in s.splitlines() if not x.startswith("```"))
    return s


def notes(text):
    ru = en = ""
    for line in text.splitlines():
        t = line.strip()
        if t.lower().startswith("# ru:"):
            ru = t[5:].strip()
        elif t.lower().startswith("# en:"):
            en = t[5:].strip()
    return ru[:200], en[:200]


def play(city, seed, out_dir=None):
    g = sim.Game(seed, city)
    import polet
    J = {"who": "extella", "stage": STAGE, "city": city, "seed": seed, "day": g.W["day"], "model": MODEL, "lang_version": polet.LANG_VERSION,
         "expert": {"name": X.NAME, "sha": X.code_sha(), "device": X.DEVICE}, "started": time.strftime("%Y-%m-%d %H:%M:%S"),
         "calls": [], "expert_calls": []}
    user = briefing(g); J["briefing"] = user
    msgs = [{"role": "system", "content": system_text(STAGE)}, {"role": "user", "content": user}]
    accepted = None
    for attempt in range(3):
        raw, secs = ask_model(msgs)
        plan = clean(raw)
        res, meta = X.run(plan, seed, city, "check")
        J["expert_calls"].append(meta)
        J["calls"].append({"raw": raw, "plan": plan, "seconds": secs, "ok": res["ok"], "errors": res["errors"], "forecast": res["forecast"]})
        if res["ok"]:
            accepted = plan; break
        msgs += [{"role": "assistant", "content": raw},
                 {"role": "user", "content": "Проверка отказала:" + chr(10) + "- " + (chr(10) + "- ").join(e["ru"] for e in res["errors"]) +
                  chr(10) + "Исправь замысел и пришли его целиком."}]
    if accepted is None:
        scored = [c for c in J["calls"] if c["forecast"]]
        best = max(scored, key=lambda c: c["forecast"]["score"]) if scored else J["calls"][-1]
        J["fallback"] = "ни один замысел не принят Проверкой; смена по замыслу с лучшим прогнозом, как есть"
        accepted = best["plan"]
    # ступень 2: Проверка приняла замысел, но говорит, что дала бы одна строка; модель получает один круг
    adv = (J["calls"][-1].get("forecast") or {}).get("advice") if J["calls"] else None
    J["advice"] = adv; J["took_advice"] = None
    if STAGE >= 2 and accepted is not None and adv:
        msgs += [{"role": "assistant", "content": J["calls"][-1]["raw"]},
                 {"role": "user", "content": "Проверка приняла замысел. " + adv["ru"] +
                  " Пришли замысел целиком: с этой строкой или свой, если считаешь иначе."}]
        raw, secs = ask_model(msgs)
        plan2 = clean(raw)
        res2, meta2 = X.run(plan2, seed, city, "check")
        J["expert_calls"].append(meta2)
        J["calls"].append({"raw": raw, "plan": plan2, "seconds": secs, "ok": res2["ok"], "errors": res2["errors"],
                           "forecast": res2["forecast"], "after_advice": True})
        plan_got, _ = polet.parse(plan2)
        steps = adv.get("steps") or [{"field": adv["field"], "value": adv["value"]}]
        got_n = sum(1 for st in steps if polet.used(plan_got, st["field"], st["value"]))
        J["advice_lines"] = len(steps); J["advice_lines_used"] = got_n
        J["advice_line_used"] = bool(res2["ok"]) and got_n == len(steps)
        better = res2["ok"] and res2["forecast"] and res2["forecast"]["score"] > (J["calls"][0]["forecast"] or {}).get("score", -1e9)
        J["took_advice"] = bool(better)
        if better:
            accepted = plan2
    J["plan"] = accepted; J["why_ru"], J["why_en"] = notes(accepted)
    res, meta = X.run(accepted, seed, city, "run")
    J["expert_calls"].append(meta)
    J.update({"score": res["score"], "journal": res["journal"], "events": res["events"], "decisions": res["decisions"],
              "refusals": res["refusals"], "flights": res["flights"], "finished": time.strftime("%Y-%m-%d %H:%M:%S")})
    out_dir = out_dir or os.path.join(HERE, os.environ.get("DRONE_RUNS", "runs"))
    os.makedirs(out_dir, exist_ok=True)
    json.dump(J, open(os.path.join(out_dir, "%s_s%d.json" % (city, seed)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    c = res["score"]["counts"]
    print("%-9s s%-2d %s попыток %d%s%s счёт %7s доставлено %2d из %2d рейсов %2d вынужденных %d потеряно %d | %s" % (
        city, seed, g.W["day"], len(J["calls"]), " ЗАПАС" if J.get("fallback") else "",
        ("" if J["took_advice"] is None else (" совет взят" if J["took_advice"] else " совет мимо")), res["score"]["score"],
        c["delivered"], c["orders"], res["flights"], c["forced"], c["lost"], accepted.replace(chr(10), " / ")[:110]), flush=True)
    return J


if __name__ == "__main__":
    play(sys.argv[1], int(sys.argv[2]))
