"""Малая модель без Extella: qwen3.5:9b сама пишет решение вечера в формате игры. Эксперта и оценок нет,
Проверка игры та же: отказ с причиной уходит модели, не больше 2 исправлений; что осталось отклонённым, не применяется
(как на странице у человека). Ответ не JSON трижды подряд: вечер без решений, это пишется в журнал.

python3 bench/noext.py <scenario> <place> <team> <seed>   -> bench/runs/small_<scenario>_<place>_<team>_s<seed>.json
python3 bench/noext.py set                                -> весь набор бенчмарка (episode.json), готовые пропускаются
"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "extella"))
import llm  # noqa: E402
from common import sim, SYSTEM, evening_text, to_decision, bench_set, WORLD  # noqa: E402

# на чём считали месяц: ollama:qwen3.5:9b или openrouter:<модель>@<провайдер>, пишется в журнал
MODEL = llm.tag()
# ZOO_TAG отделяет прогоны с разным системным текстом: small_* это первый заход, small2_* второй
TAG = os.environ.get("ZOO_TAG", "small")
OUT = os.path.join(HERE, "runs")


def ask(messages):
    """Вызов малой модели через extella/llm.py: Ollama на машине или сеть по CAFE_BACKEND."""
    # ZOO_MAX_TOKENS: у модели с обязательным размышлением ответ длиннее, 700 на него не хватит
    r = llm.ask(messages, num_predict=int(os.environ.get("ZOO_MAX_TOKENS", "700")))
    return r["content"], r["seconds"], r["prompt_tokens"], r["out_tokens"], r["tries"]


def play(sc, pl, tm, seed):
    g = sim.Game(seed, pl, tm, sc, WORLD)
    J = {"player": TAG + "_noext", "world": WORLD, "model": MODEL, "combo": {"scenario": sc, "place": pl, "team": tm, "seed": seed},
         "started": time.strftime("%Y-%m-%d %H:%M:%S"), "system": SYSTEM, "evenings": [], "daily": []}
    t_start = time.time()
    while not g.done():
        obs = g.observe()
        text = evening_text(g, obs)
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]
        ev = {"day": g.t, "prompt": text, "calls": []}
        dec = None
        bad_json = 0
        fixes = 0
        while True:
            raw, secs, pin, pout, tries = ask(msgs)
            ev["calls"].append({"raw": raw, "seconds": secs, "prompt_tokens": pin, "out_tokens": pout, "tries": tries})
            try:
                p = json.loads(raw)
            except Exception:
                p = None
            if not isinstance(p, dict):
                bad_json += 1
                if bad_json >= 3:
                    ev["skipped"] = "не JSON трижды"
                    break
                msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Ответ должен быть объектом JSON. Повтори."}]
                continue
            d = to_decision(p, g.observe())
            rej = g.check(d)[0]
            if rej and fixes < 2:
                fixes += 1
                msgs += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": "Проверка отклонила:\n" + "\n".join("- " + r["ru"] for r in rej) + "\nИсправь и пришли решение целиком."}]
                continue
            dec = d
            ev["why_ru"] = p.get("why_ru")
            ev["why_en"] = p.get("why_en")
            break
        if dec is not None:
            ev["decision"] = dec
            ev["rejections"] = [r["ru"] for r in g.decide(dec)]
        ev["fixes"] = fixes
        J["evenings"].append(ev)
        g.step()
        J["daily"].append({"day": g.t - 1, "score": g.score()["score"]})
        print("day %2d score %9.0f %s" % (g.t - 1, g.score()["score"], "" if dec is not None else "вечер пропущен"), flush=True)
    s = g.score()
    J["score"] = s
    J["journal"] = g.journal
    J["minutes"] = round((time.time() - t_start) / 60, 1)
    path = os.path.join(OUT, TAG + "_%s_%s_%s_s%d.json" % (sc, pl, tm, seed))
    json.dump(J, open(path, "w"), ensure_ascii=False)
    print("score %.2f minutes %s -> %s" % (s["score"], J["minutes"], path), flush=True)
    return path


if __name__ == "__main__":
    pid = int(os.environ.get("WAIT_PID", "0") or 0)
    while pid:
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(60)
    a = sys.argv[1:]
    if a[:1] == ["set"]:
        for sc, pl, tm, seed in bench_set():
            p = os.path.join(OUT, TAG + "_%s_%s_%s_s%d.json" % (sc, pl, tm, seed))
            if os.path.exists(p):
                print("skip", os.path.basename(p), flush=True)
                continue
            print("==", sc, pl, tm, seed, time.strftime("%H:%M:%S"), flush=True)
            play(sc, pl, tm, seed)
    elif len(a) == 4:
        play(a[0], a[1], a[2], int(a[3]))
    else:
        print(__doc__)
