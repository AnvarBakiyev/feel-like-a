"""Соперники без Extella: модель получает тот же брифинг и сама пишет рычаг по километрам. Никакого языка поездки,
обработчика и Проверки плана: план исполняется как есть (защита поезда работает, как у человека).

python3 noext.py briefings            -> noext/briefings.json (30 брифингов для большой модели)
python3 noext.py small                -> noext/small_<line>_s<seed>.json (qwen3.5:9b, Ollama)
python3 noext.py score <file.json>    -> рейсы по планам из файла {"<line>_s<seed>": {"plan": [...]}} (большая модель)
"""
import json, os, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import sim
from player import briefing, ask_model

OUT = os.path.join(HERE, "noext"); os.makedirs(OUT, exist_ok=True)
SYSTEM = """Ты машинист. До отправления ты пишешь управление поездом на весь рейс: положение контроллера по километрам.
Контроллер: число от -1 до 1. 1 полная тяга, 0 выбег (без тяги и тормоза), -1 полный служебный тормоз, промежуточные значения тоже можно.
Положение действует от своего километра до следующей точки плана. На станции поезд должен остановиться точно у отметки (её километр в графике) и стоять до времени отправления; потом действует положение плана на этом километре.
Защита поезда тормозит сама, если ты превысишь допустимую скорость (минус 150 очков, экстренное минус 400). Поезд не доехал: минус 1000.
Счёт рейса: 1000 очков; минус 2 за каждую секунду опоздания сверх 30 с; плюс или минус 4 за каждый процент энергии к эталону; минус 5 за метр ошибки остановки сверх 2 м; минус 500 за пропуск станции.
Ответ: только JSON: {"pusher": false, "sand": [[км_от, км_до]], "plan": [{"km": 41.6, "lever": 1.0}, ...], "why_ru": "...", "why_en": "..."}
pusher: взять толкач (только где он есть, минус 100 очков). sand: отрезки, где сыпать песок (всего 600 секунд)."""


def execute(line_id, seed, P):
    """Исполнить план как есть: рычаг по км, песок по отрезкам, толкач до отправления."""
    g = sim.Game(seed, line_id)
    pts = sorted([(float(p["km"]), max(-1.0, min(1.0, float(p["lever"])))) for p in P.get("plan", []) if isinstance(p, dict) and "km" in p and "lever" in p])
    sand = [(float(a), float(b)) for a, b in (P.get("sand") or []) if True]
    if P.get("pusher") and "pusher" in g.T:
        g.decide({"pusher": True})
    def lever_at(km):
        lv = pts[0][1] if pts else 0.0  # до первой точки действует её значение (брифинг округляет км до десятых)
        for k, l in pts:
            if k <= km + 1e-9:
                lv = l
            else:
                break
        return lv
    while not g.done():
        km = g.x / 1000.0
        want = lever_at(km)
        d = {"lever": want}
        ws = any(a <= km <= b for a, b in sand) and g.sand_left > 0
        if ws != g.sand_on:
            d["sand"] = ws
        if g.at_station and g.t < g.due():
            d["lever"] = 0.0 if want > 0 else want
        g.decide(d)
        g.step()
    return g


def run_small():
    for lid in ("de_krm", "ch_gotthard", "jp_tokaido"):
        for seed in range(1, 11):
            p = os.path.join(OUT, "small_%s_s%d.json" % (lid, seed))
            if os.path.exists(p):
                continue
            g0 = sim.Game(seed, lid); b = briefing(g0).replace("Напиши план.", "Напиши управление (JSON).")
            msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": b}]
            calls = []; P = None
            for attempt in range(2):
                raw, secs = ask_model_json(msgs)
                calls.append({"raw": raw, "seconds": secs})
                try:
                    P = json.loads(raw); assert isinstance(P.get("plan"), list) and P["plan"]; break
                except Exception:
                    P = None
                    msgs += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Это не JSON нужного вида. Пришли только JSON с полем plan."}]
            if P is None:
                P = {"plan": []}
            g = execute(lid, seed, P); sc = g.score()
            J = {"who": "small_no_extella", "model": "qwen3.5:9b", "line": lid, "seed": seed, "briefing": b, "calls": calls, "plan": P, "score": sc,
                 "journal": g.journal, "world": g.W, "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
            json.dump(J, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(lid, seed, g.W["weather"], "счёт", sc["score"], "точек", len(P.get("plan", [])), "станции", [(s["name"], round(s["err_m"]), s.get("missed")) for s in sc["stops"]], flush=True)


def ask_model_json(messages):
    body = {"model": "qwen3.5:9b", "messages": messages, "stream": False, "think": False, "format": "json",
            "options": {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 900}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1500) as r:
        out = json.loads(r.read())
    return out["message"]["content"], round(time.time() - t0, 2)


def dump_briefings():
    B = {"system": SYSTEM, "trips": {}}
    for lid in ("de_krm", "ch_gotthard", "jp_tokaido"):
        for seed in range(1, 11):
            B["trips"]["%s_s%d" % (lid, seed)] = briefing(sim.Game(seed, lid)).replace("Напиши план.", "Напиши управление (JSON).")
    json.dump(B, open(os.path.join(OUT, "briefings.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(B["trips"]), "брифингов")


def score_file(path, who, model):
    P = json.load(open(path, encoding="utf-8"))
    for key, plan in P.items():
        lid, s = key.rsplit("_s", 1); seed = int(s)
        g = execute(lid, seed, plan); sc = g.score()
        J = {"who": who, "model": model, "line": lid, "seed": seed, "plan": plan, "score": sc, "journal": g.journal, "world": g.W}
        json.dump(J, open(os.path.join(OUT, "%s_%s_s%d.json" % (who, lid, seed)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(key, sc["score"], [(x["name"], round(x["err_m"]), x.get("missed")) for x in sc["stops"]], sc["counts"]["atp"], sc["counts"]["emergency"])


if __name__ == "__main__":
    if sys.argv[1] == "briefings": dump_briefings()
    elif sys.argv[1] == "small": run_small()
    elif sys.argv[1] == "score": score_file(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "rescore_small":
        for f in sorted(os.listdir(OUT)):
            if f.startswith("small_") and f.endswith(".json"):
                J = json.load(open(os.path.join(OUT, f), encoding="utf-8")); g = execute(J["line"], J["seed"], J["plan"]); sc = g.score()
                J.update({"score": sc, "journal": g.journal, "rescored": "правки H4: до первой точки плана её значение; без бонуса энергии у недоехавшего"})
                json.dump(J, open(os.path.join(OUT, f), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                print(f, sc["score"], [(x["name"], round(x["err_m"]), x.get("missed")) for x in sc["stops"]], "не доехал" if sc["parts"]["unfinished"] else "")
