"""Игрок Extella для эпизода «машинист»: малая модель пишет план рейса, эксперт train_plan на Extella проверяет и ведёт поезд.

python3 player.py <line_id> <seed>  ->  runs/<line_id>_s<seed>.json

1. Модель (Qwen 3.5 9B, Ollama на машине) видит брифинг: то же, что игрок до отправления (паспорт поезда, график, погода по прогнозу,
   лист предупреждений, задержка, профиль). Пишет план на языке поездки.
2. Эксперт на Extella проверяет план (разбор, здравый смысл, симуляция на прогнозе). Отказ с причиной уходит модели, до 2 исправлений.
3. Принятый план исполняет тот же эксперт в мире зерна (со скрытым сцеплением и поездом впереди). Журнал пишется как есть.
"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import sim  # noqa: E402
import extella_call as X  # noqa: E402

MODEL = os.environ.get("TRAIN_MODEL", "qwen3.5:9b")
WX = {"dry": "сухо", "wet": "дождь, мокрый рельс", "leaves": "листопад, скользкий рельс"}

SYSTEM = """Ты машинист. До отправления ты пишешь план рейса на языке поездки. Поезд ведёт обработчик по твоему плану: ограничения скорости и остановки на станциях он соблюдает сам.
Команды (по одной в строке):
толкач да            (второй локомотив сзади на всю поездку, стоит 100 очков; есть только там, где сказано)
разгон до 280        (предел скорости на весь рейс, км/ч; пишется один раз)
тише 200 с км 100 до км 110   (ехать тише допустимой на отрезке; только если есть своя причина)
выбег с км 140 до км 150   (без тяги, поезд катится; экономит энергию, но теряет время)
песок с км 42 до км 70     (подсыпка песка: сцепление выше на 25 %, песка на 600 секунд всего)
по графику           (обработчик сам включает выбег, когда поезд идёт с опережением графика)
Не переписывай профиль в план: ограничения скорости, ремонт пути и остановки обработчик соблюдает сам. Каждая лишняя «тише» стоит времени.
Пример плана для другого участка (не твоего):
разгон до 200
песок с км 12 до км 18
# ru: на подъёме мокро, песок против боксования
# en: wet climb, sand against wheel slip
Счёт рейса: 1000 очков; минус 2 за каждую секунду опоздания сверх 30 с; плюс или минус 4 за каждый процент энергии к эталону; минус 150 за вмешательство защиты; минус 1000, если поезд не доехал.
Ответ: только строки плана. В конце две строки комментария: «# ru: почему так» и «# en: why», не длиннее 12 слов каждая."""


def ask_model(messages):
    body = {"model": MODEL, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 450}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1500) as r:
        out = json.loads(r.read())
    return out["message"]["content"], round(time.time() - t0, 2)


def k(x):
    return ("%.1f" % x).replace(".", ",")


def briefing(g):
    L = g.L; T = g.T; o = g.observe()
    lines = ["Участок: %s, км %s – %s." % (L["name"]["ru"], k(g.stations[0]["km"]), k(g.stations[-1]["km"]))]
    lines.append("Поезд: %s, %d т, %d кВт, предельная скорость %d км/ч, служебный тормоз %s м/с²." % (
        T["name"], g.mass(), T["power_kW"], T["vmax_kmh"], ("%.2f" % T["brake"]["service_ms2"]).replace(".", ",")))
    tt = []
    for st, t in zip(g.stations, g.tt):
        tt.append("%s км %s%s%s" % (st["name"], k(st["km"]), (" приб. " + sim.clock(t["arr_s"])) if t["arr_s"] is not None else "",
                                     (" отпр. " + sim.clock(t["dep_s"])) if t["dep_s"] is not None else ""))
    lines.append("График: " + "; ".join(tt) + ".")
    if o["depart_delay_s"]:
        lines.append("Задержка: отправление на %d мин позже графика (%s)." % (o["depart_delay_s"] // 60, sim.clock(o["due_s"])))
    lines.append("Погода по прогнозу: %s." % WX[o["weather"]])
    if o["warnings"]:
        lines.append("Лист предупреждений: " + "; ".join("км %s–%s не больше %d км/ч (ремонт пути)" % (k(w["from_km"]), k(w["to_km"]), w["limit_kmh"]) for w in o["warnings"]) + ".")
    else:
        lines.append("Лист предупреждений: пусто.")
    prof = []
    for s in g.seg:
        if abs(s["grade_permille"]) >= 15 or s["limit_kmh"] < 0.8 * T["vmax_kmh"]:
            prof.append("км %s–%s: %s ‰, до %d км/ч" % (k(s["from_km"]), k(s["to_km"]), ("+" if s["grade_permille"] > 0 else "") + k(s["grade_permille"]), s["limit_kmh"]))
    lines.append("Профиль (подъём +, спуск −; остальное ровнее и до %d км/ч): %s." % (min(T["vmax_kmh"], max(s["limit_kmh"] for s in g.seg)), "; ".join(prof)))
    lines.append("Толкач: %s." % ("есть" if "pusher" in T else "нет на этом участке"))
    lines.append("Напиши план.")
    return "\n".join(lines)


def clean(raw):
    """Убрать обёртку ``` если модель её поставила; комментарии оставить (язык их пропускает)."""
    s = raw.strip()
    if s.startswith("```"):
        s = "\n".join(x for x in s.splitlines() if not x.startswith("```"))
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


def play(line_id, seed, out_dir=None):
    g = sim.Game(seed, line_id)
    import poezdka
    J = {"line": line_id, "seed": seed, "model": MODEL, "lang_version": poezdka.LANG_VERSION, "expert": {"name": X.NAME, "sha": X.code_sha(), "device": X.DEVICE},
         "started": time.strftime("%Y-%m-%d %H:%M:%S"), "calls": [], "expert_calls": []}
    user = briefing(g); J["briefing"] = user
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    accepted = None
    for attempt in range(3):
        raw, secs = ask_model(msgs)
        plan = clean(raw)
        res, meta = X.run(plan, seed, line_id, "check")
        J["expert_calls"].append(meta)
        J["calls"].append({"raw": raw, "plan": plan, "seconds": secs, "ok": res["ok"], "errors": res["errors"], "forecast": res["forecast"]})
        if res["ok"]:
            accepted = plan; break
        msgs += [{"role": "assistant", "content": raw},
                 {"role": "user", "content": "Проверка отказала:\n- " + "\n- ".join(e["ru"] for e in res["errors"]) + "\nИсправь план и пришли его целиком."}]
    if accepted is None:
        scored = [c for c in J["calls"] if c["forecast"]]
        best = max(scored, key=lambda c: c["forecast"]["score"]) if scored else J["calls"][-1]
        J["fallback"] = "ни один план не принят Проверкой; рейс по плану с лучшим прогнозом, как есть"
        accepted = best["plan"]
    J["plan"] = accepted; J["why_ru"], J["why_en"] = notes(accepted)
    res, meta = X.run(accepted, seed, line_id, "run")
    J["expert_calls"].append(meta)
    J.update({"score": res["score"], "journal": res["journal"], "decisions": res["decisions"], "world": res["world"], "finished": time.strftime("%Y-%m-%d %H:%M:%S")})
    out_dir = out_dir or os.path.join(HERE, os.environ.get("TRAIN_RUNS", "runs"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "%s_s%d.json" % (line_id, seed))
    json.dump(J, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%s s%d  %s  попыток %d%s  счёт %s  %s" % (line_id, seed, g.W["weather"], len(J["calls"]), " ЗАПАС" if J.get("fallback") else "",
          res["score"]["score"], accepted.replace("\n", " / ")[:140]), flush=True)
    return J


if __name__ == "__main__":
    play(sys.argv[1], int(sys.argv[2]))
