"""Зоопарк по вечерам для большой модели без Extella: тот же текст вечера, решение в формате игры, та же Проверка.

python3 bench/closed.py start <scenario> <place> <team> <seed>          правила и первый вечер; создаёт месяц
python3 bench/closed.py act <scenario> <place> <team> <seed> '<json>'   решение вечера; если Проверка отказала,
        вечер не закрывается и показываются отказы (не больше 2 раз за вечер, на третий раз принятое применяется,
        отклонённое нет); иначе наступает день и показывается следующий вечер
python3 bench/closed.py result <scenario> <place> <team> <seed>         итог месяца

Состояние: список решений в файле bench/runs/big_<...>.json; каждый вызов заново проигрывает их с начала (симулятор
детерминирован), поэтому подменить мир или счёт нельзя: счёт всегда пересчитывается открытым счётчиком.
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import sim, SYSTEM, evening_text, to_decision, WORLD  # noqa: E402

# ZOO_TAG отделяет прогоны: big_* это первый заход 13.11 (мир ny, игрок знал исходники), ny2opus_* чистый заход в мире ny2
TAG = os.environ.get("ZOO_TAG", "big")
MODEL_TAG = os.environ.get("ZOO_MODEL_TAG")

OUT = os.path.join(HERE, "runs")


def path(sc, pl, tm, seed):
    return os.path.join(OUT, TAG + "_%s_%s_%s_s%d.json" % (sc, pl, tm, seed))


def load(sc, pl, tm, seed):
    p = path(sc, pl, tm, seed)
    if not os.path.exists(p):
        return {"player": TAG + "_noext", "world": WORLD, "model": MODEL_TAG, "combo": {"scenario": sc, "place": pl, "team": tm, "seed": seed},
                "started": time.strftime("%Y-%m-%d %H:%M:%S"), "system": SYSTEM, "evenings": [], "daily": [], "tries": {}}
    return json.load(open(p, encoding="utf-8"))


def save(J, sc, pl, tm, seed):
    json.dump(J, open(path(sc, pl, tm, seed), "w"), ensure_ascii=False)


def replay(J, sc, pl, tm, seed):
    """Проигрывает записанные вечера и возвращает игру на текущем вечере."""
    g = sim.Game(seed, pl, tm, sc, J.get("world", "ny"))
    for ev in J["evenings"]:
        if ev.get("decision"):
            g.decide(ev["decision"])
        g.step()
    return g


def show(g, J):
    if g.done():
        s = g.score()
        return "Месяц закончен. Счёт %.2f. Нарушений %d, гибель животных %d." % (
            s["score"], s["counts"]["section_violation_days"], s["counts"]["deaths"])
    return evening_text(g, g.observe())


def main(a):
    cmd = a[0]
    sc, pl, tm, seed = a[1], a[2], a[3], int(a[4])
    J = load(sc, pl, tm, seed)
    g = replay(J, sc, pl, tm, seed)
    if cmd == "start":
        print(SYSTEM)
        print("")
        print(show(g, J))
        save(J, sc, pl, tm, seed)
        return 0
    if cmd == "result":
        s = g.score()
        J["score"] = s
        J["journal"] = g.journal
        save(J, sc, pl, tm, seed)
        print(json.dumps({"score": s["score"], "parts": s["parts"], "counts": s["counts"], "evenings": len(J["evenings"])}, ensure_ascii=False))
        return 0
    if cmd != "act":
        print(__doc__)
        return 2
    if g.done():
        print("Месяц уже закончен.")
        return 0
    p = json.loads(a[5])
    if not isinstance(p, dict):
        print("Ответ должен быть объектом JSON.")
        return 1
    d = to_decision(p, g.observe())
    key = str(g.t)
    tries = J["tries"].get(key, 0)
    rej = g.check(d)[0]
    if rej and tries < 2:
        J["tries"][key] = tries + 1
        save(J, sc, pl, tm, seed)
        print("Проверка отклонила решение (попытка %d из 3). Вечер не закрыт." % (tries + 1))
        for r in rej:
            print("- [%s] %s" % (r["field"], r["ru"]))
        return 1
    ev = {"day": g.t, "decision": d, "why_ru": p.get("why_ru"), "why_en": p.get("why_en"),
          "rejections": [r["ru"] for r in rej], "tries": tries + 1}
    J["evenings"].append(ev)
    g.decide(d)
    g.step()
    J["daily"].append({"day": g.t - 1, "score": g.score()["score"]})
    J["journal"] = g.journal
    save(J, sc, pl, tm, seed)
    if rej:
        print("Проверка отклонила часть решения, она не применена:")
        for r in rej:
            print("- [%s] %s" % (r["field"], r["ru"]))
    print("День %d прошёл. Счёт месяца %.2f." % (g.t - 1, g.score()["score"]))
    print("")
    print(show(g, J))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(a) if len(a) >= 5 else (print(__doc__) or 2))
