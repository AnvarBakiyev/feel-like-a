"""Соперники без Extella: модель получает тот же брифинг и сама пишет правила смены по точкам.
Никакого языка полёта, обработчика и Проверки замысла: правила исполняются как есть. Заряд по прогнозу
никто не считает, Проверка игры (ветер, масса, запретные зоны, мощность батареи) работает, как и у человека.

python3 noext.py briefings                     -> noext/briefings.json (30 брифингов для большой модели)
python3 noext.py small                         -> noext/small_<city>_s<seed>.json (qwen3.5:9b, Ollama)
python3 noext.py score <file.json> <who> <model>   -> смены по правилам из файла {"<city>_s<seed>": {...}}
"""
import json, math, os, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import sim
from player import briefing, MODEL

OUT = os.path.join(HERE, "noext"); os.makedirs(OUT, exist_ok=True)
SYSTEM = """Ты диспетчер доставки дронами. До смены ты пишешь правила, по которым пойдёт вся смена. Правила исполняются буквально: как только дрон свободен, ему дают первый подходящий заказ по твоему порядку, и он летит с той высотой, скоростью и через ту площадку, которые ты назначил для этой точки. Заряд за тебя никто не считает: если на обратном плече не хватит заряда, дрон сядет вне площадки (минус 250) или будет потерян (минус 600).
Ответ: только JSON. Пример для другого города (не твоего, числа не переписывай):
{"order": "urgent", "default": {"alt": 60, "speed": "fast", "max_kg": 40, "per_flight": 1, "pad": null},
 "points": {"2": {"alt": 30, "speed": "eco", "max_kg": 10, "pad": 1}, "4": {"skip": true}},
 "why_ru": "почему так", "why_en": "why"}
order: порядок заказов, "urgent" (по сроку), "near" (по близости) или "heavy" (сначала тяжёлые).
default: что делать на точке, для которой нет своей строки. points: правила по номеру точки из брифинга;
alt 30, 60, 100 или 120; speed "eco" (12 м/с) или "fast" (18 м/с); max_kg: не брать заказ тяжелее;
per_flight: 1, 2 или 3 заказа подряд за рейс; pad: номер площадки зарядки на обратном пути или null;
skip: true, если на эту точку не летать совсем.
Считай сам: дальность, встречный ветер на обратном плече, заряд, мощность висения с грузом."""


def rule(P, pid):
    d = dict({"alt": 60, "speed": "fast", "max_kg": 40.0, "per_flight": 1, "pad": None, "skip": False})
    for k, v in (P.get("default") or {}).items():
        d[k] = v
    for k, v in ((P.get("points") or {}).get(str(pid)) or {}).items():
        d[k] = v
    d["alt"] = d["alt"] if d["alt"] in sim.ALTS else 60
    d["speed"] = d["speed"] if d["speed"] in sim.SPEEDS else "fast"
    try:
        d["max_kg"] = float(d["max_kg"])
    except Exception:
        d["max_kg"] = 40.0
    try:
        d["per_flight"] = max(1, min(3, int(d["per_flight"])))
    except Exception:
        d["per_flight"] = 1
    return d


def execute(city, seed, P):
    """Исполнить правила как есть."""
    g = sim.Game(seed, city); n = 0; decisions = []; rejected = []; seen_rej = set()
    order = P.get("order") if P.get("order") in ("urgent", "near", "heavy") else "urgent"
    while not g.done():
        if int(g.t) % 5 == 0:
            for dr in g.drones:
                if dr["mode"] != "dock" or dr["busy"] > 0 or dr["route"]:
                    continue
                taken = set(int(t[1:]) for _, d in decisions[-6:] for t in d["route"] if t[0] == "o")
                cands = []
                for o in g.orders:
                    if o["status"] != "wait" or o["t"] > g.t or o["id"] in taken:
                        continue
                    r = rule(P, o["point"])
                    if r["skip"] or o["kg"] > r["max_kg"]:
                        continue
                    p = g.pts[o["point"]]
                    cands.append((o, p, math.sqrt(p["x"] * p["x"] + p["y"] * p["y"]), r))
                if not cands:
                    continue
                if order == "near":
                    cands.sort(key=lambda c: (c[2], c[0]["id"]))
                elif order == "heavy":
                    cands.sort(key=lambda c: (-c[0]["kg"], c[0]["id"]))
                else:
                    cands.sort(key=lambda c: (c[0]["due"], c[0]["id"]))
                for head in cands:
                    o, p, _, r = head
                    group = [head]
                    for c in cands:
                        if len(group) >= r["per_flight"]:
                            break
                        if c is head or sum(x[0]["kg"] for x in group) + c[0]["kg"] > r["max_kg"]:
                            continue
                        group.append(c)
                    route = ["o%d" % x[0]["id"] for x in group]
                    if r["pad"] is not None and r["pad"] in g.pts and g.pts[r["pad"]]["pad"]:
                        route.append("p%d" % int(r["pad"]))
                    dec = {"drone": dr["id"], "route": route, "alt": r["alt"], "speed": r["speed"]}
                    rej = g.decide(dec)
                    if rej:
                        key = (dec["drone"], tuple(route), rej[0]["code"])
                        if key not in seen_rej:
                            seen_rej.add(key); rejected.append([n, dec, rej[0]["code"], rej[0]["ru"]])
                        continue
                    decisions.append([n, dec])
                    break
        g.step(); n += 1
    return g, decisions, rejected


def ask_json(messages):
    body = {"model": MODEL, "messages": messages, "stream": False, "think": False, "format": "json",
            "options": {"temperature": 0, "seed": 7, "num_ctx": 4096, "num_predict": 900}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        out = json.loads(r.read())
    return out["message"]["content"], round(time.time() - t0, 2)


def ask(city, seed):
    g0 = sim.Game(seed, city)
    b = briefing(g0).replace("Напиши замысел.", "Напиши правила (JSON).")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": b}]
    calls = []; P = None
    for attempt in range(2):
        raw, secs = ask_json(msgs)
        calls.append({"raw": raw, "seconds": secs})
        try:
            P = json.loads(raw)
            assert isinstance(P, dict) and (P.get("default") or P.get("points"))
            break
        except Exception:
            P = None
            msgs += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "Это не JSON нужного вида. Пришли только JSON с полями order, default, points."}]
    return b, calls, (P if P is not None else {})


def save(who, model, city, seed, b, calls, P):
    g, dec, rej = execute(city, seed, P)
    sc = g.score(); c = sc["counts"]
    J = {"who": who, "model": model, "city": city, "seed": seed, "day": g.W["day"], "briefing": b, "calls": calls, "plan": P,
         "score": sc, "journal": g.journal, "events": g.events, "decisions": dec, "rejected": rej,
         "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
    json.dump(J, open(os.path.join(OUT, "%s_%s_s%d.json" % (who, city, seed)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%-10s %-9s s%-2d %s счёт %7s доставлено %2d из %2d рейсов %2d вынужденных %d потеряно %d отвергнуто %d | %s" % (
        who, city, seed, g.W["day"], sc["score"], c["delivered"], c["orders"], len(dec), c["forced"], c["lost"], len(rej),
        json.dumps({k: v for k, v in P.items() if k in ("order", "default", "points")}, ensure_ascii=False)[:90]), flush=True)
    return J


def run_small():
    for city in sim.CITIES:
        for seed in range(1, 11):
            if os.path.exists(os.path.join(OUT, "small_%s_s%d.json" % (city, seed))):
                print("skip", city, seed, flush=True); continue
            b, calls, P = ask(city, seed)
            save("small", MODEL, city, seed, b, calls, P)


def dump_briefings():
    B = {"system": SYSTEM, "shifts": {}}
    for city in sim.CITIES:
        for seed in range(1, 11):
            B["shifts"]["%s_s%d" % (city, seed)] = briefing(sim.Game(seed, city)).replace("Напиши замысел.", "Напиши правила (JSON).")
    json.dump(B, open(os.path.join(OUT, "briefings.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(B["shifts"]), "брифингов")


def score_file(path, who, model):
    P = json.load(open(path, encoding="utf-8"))
    for key in sorted(P):
        city, s = key.rsplit("_s", 1)
        save(who, model, city, int(s), "см. noext/briefings.json", [], P[key])


if __name__ == "__main__":
    if sys.argv[1] == "briefings":
        dump_briefings()
    elif sys.argv[1] == "small":
        run_small()
    elif sys.argv[1] == "score":
        score_file(sys.argv[2], sys.argv[3], sys.argv[4])
