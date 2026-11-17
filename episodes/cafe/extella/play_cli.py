"""Пошаговый игрок: месяц играет тот, кто вызывает этот файл, а не модель по сети.

Нужен, чтобы в соперники можно было поставить модель, у которой нет ключа для прогона
скриптом: Opus 5 играет прямо в чате. Правила и текст вечера те же, что у player_bare,
то есть сравнение честное: видно ровно то же и отвечать надо тем же JSON.

    python3 play_cli.py start <scenario> <street> <money> [seed=1]
    python3 play_cli.py show  <scenario> <street> <money> [seed=1]
    python3 play_cli.py step  <scenario> <street> <money> '<json решения>' [seed=1]

start печатает первый вечер. step применяет решение, печатает итог дня и следующий
вечер; после тридцатого дня пишет журнал в runs/<CAFE_OUT>/ в том же виде, что и
player_bare, и печатает счёт месяца.

Состояние месяца между вызовами лежит в runs/<CAFE_OUT>/state/.
"""
import json, os, pickle, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
import sim  # noqa: E402
import player_bare as PB  # noqa: E402

OUT = os.path.join(HERE, "runs", os.environ.get("CAFE_OUT", "m_opus"))
MODEL = os.environ.get("CAFE_PLAYER_TAG", "claude-opus-5 (в чате)")


def paths(sc, st, mo, seed):
    return (os.path.join(OUT, "state", "%s_%s_%s_s%d.pkl" % (sc, st, mo, seed)),
            os.path.join(OUT, "%s_%s_%s_s%d.json" % (sc, st, mo, seed)))


def load(sc, st, mo, seed):
    p, _ = paths(sc, st, mo, seed)
    with open(p, "rb") as f:
        return pickle.load(f)


def save(S, sc, st, mo, seed):
    p, _ = paths(sc, st, mo, seed)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        pickle.dump(S, f)


def show_evening(g):
    print(PB.evening_text(g, g.observe()))


def start(sc, st, mo, seed):
    g = sim.Game(seed, st, mo, sc)
    S = {"g": g, "J": {"combo": {"street": st, "money": mo, "scenario": sc, "seed": seed}, "model": MODEL,
                       "expert": None, "player": "bare-cli", "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "evenings": [], "daily": []}, "t0": time.time()}
    save(S, sc, st, mo, seed)
    print("=== мир %s / %s / %s, зерно %d ===" % (sc, st, mo, seed))
    show_evening(g)


def step(sc, st, mo, raw, seed):
    S = load(sc, st, mo, seed)
    g = S["g"]; J = S["J"]
    if g.t >= g.C["days"]:
        print("месяц уже сыгран"); return
    obs = g.observe()
    try:
        p = json.loads(raw)
        assert isinstance(p, dict)
    except Exception as e:
        print("ОТКАЗ формы: ответ не разобрался как JSON (%s). Пришли только JSON." % type(e).__name__); return
    dec = PB.to_decision(p, obs)
    rej, _ = g.check(dec)
    if rej:
        print("ОТКАЗ проверки игры:")
        for r in rej:
            print(" -", r["ru"])
        print("Исправь решение и пришли снова: день не пошёл.")
        return
    ev = {"day": g.t, "decision": dec, "why_ru": str(p.get("why_ru", ""))[:240], "why_en": str(p.get("why_en", ""))[:240]}
    ev["rejections"] = g.decide(dec)
    rep = g.step()
    s = g.score()
    J["daily"].append({"day": g.t - 1, "score": s["score"], "profit": s["profit"], "cash": g.cash, "loan": g.loan})
    J["evenings"].append(ev)
    print("--- день %d: пришло %d, обслужено %d, очередь %d, без позиции %d, выручка %s, счёт месяца %s ---" % (
        g.t - 1, rep["demand"], rep["served"], rep["queue_guests"], rep["stockout_guests"],
        PB.money(rep["revenue"]), PB.money(s["score"])))
    if g.t >= g.C["days"]:
        J["score"] = s; J["journal"] = g.journal
        J["minutes"] = round((time.time() - S["t0"]) / 60, 1); J["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        J["fallbacks"] = 0
        os.makedirs(OUT, exist_ok=True)
        _, out = paths(sc, st, mo, seed)
        json.dump(J, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("=== месяц сыгран. счёт %s -> %s ===" % (PB.money(s["score"]), out))
        save(S, sc, st, mo, seed)
        return
    save(S, sc, st, mo, seed)
    print()
    show_evening(g)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    cmd = a[0]
    if cmd == "start":
        start(a[1], a[2], a[3], int(a[4]) if len(a) > 4 else 1)
    elif cmd == "show":
        S = load(a[1], a[2], a[3], int(a[4]) if len(a) > 4 else 1)
        if S["g"].t >= S["g"].C["days"]:
            print("месяц сыгран, счёт", PB.money(S["g"].score()["score"]))
        else:
            show_evening(S["g"])
    elif cmd == "step":
        step(a[1], a[2], a[3], a[4], int(a[5]) if len(a) > 5 else 1)
    else:
        print("команды: start, show, step"); sys.exit(1)
