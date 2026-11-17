"""Данные страницы курьера дронов: миры 30 смен (готовые из Python), рельеф трёх городов и решения соперников.
Соперники берутся из записанных прогонов (extella/runs, extella/noext) и из простых программ (drivers.py), которые
прогоняются здесь же. Перед записью каждый журнал решений пересчитывается sim.replay: счёт должен совпасть с записанным.

    python3 build_data.py      # -> data.json
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
DR = os.path.dirname(HERE)
sys.path.insert(0, DR)
import drivers, sim

EX = os.path.join(DR, "extella")
STAGE_DIR = "runs4b"   # журналы Extella, которые показывает страница: ступень 4 языка (цепочка советов, пример без чисел)


def run_driver(seed, city, fn):
    g = sim.Game(seed, city); decs = []; n = 0
    while not g.done():
        d = fn(g.observe(), g)
        if d is not None and not g.decide(d):
            decs.append([n, d])
        g.step(); n += 1
    return decs, g.score()


def strip_plan(p):
    if isinstance(p, str):
        return "\n".join(l for l in p.split("\n") if not l.startswith("#"))
    return None


out = {"worlds": {}, "terrain": {}, "rivals": {}, "meta": {}, "stage1": {}, "stage2": {}, "stage3": {}}
bad = []
for city in sim.CITIES:
    for seed in range(1, 11):
        key = "%s_%d" % (city, seed)
        g = sim.Game(seed, city)
        if city not in out["terrain"]:
            out["terrain"][city] = g.W["map"]["terrain"]
        W = json.loads(json.dumps(g.W)); W["map"]["terrain"] = None
        out["worlds"][key] = W
        R = {}
        ex = json.load(open(os.path.join(EX, STAGE_DIR, "%s_s%d.json" % (city, seed))))
        ex1 = json.load(open(os.path.join(EX, "runs", "%s_s%d.json" % (city, seed))))
        ex2 = json.load(open(os.path.join(EX, "runs2", "%s_s%d.json" % (city, seed))))
        ex3 = json.load(open(os.path.join(EX, "runs3", "%s_s%d.json" % (city, seed))))
        adv = ex.get("advice") or None
        R["extella"] = {"decisions": ex["decisions"], "score": ex["score"]["score"], "plan": strip_plan(ex["plan"]),
                        "first_plan": strip_plan(ex["calls"][0]["plan"]) if len(ex["calls"]) > 1 else None,
                        "advice_ru": adv["ru"] if adv else None, "advice_en": adv["en"] if adv else None,
                        "took_advice": bool(ex.get("took_advice")),
                        "why_ru": ex.get("why_ru"), "why_en": ex.get("why_en"),
                        "refusals": [[r["t"], r["order"], r["why"]] for r in ex.get("refusals", [])][:40],
                        "calls": len(ex["calls"]), "model": ex["model"], "stage": ex.get("lang_version", 1)}
        out["stage1"][key] = ex1["score"]["score"]
        out["stage2"][key] = ex2["score"]["score"]
        out["stage3"][key] = ex3["score"]["score"]
        for who, pre in (("big", "big"), ("small", "small")):
            d = json.load(open(os.path.join(EX, "noext", "%s_%s_s%d.json" % (pre, city, seed))))
            plan = d["plan"]
            why = (plan.get("why_ru"), plan.get("why_en")) if isinstance(plan, dict) else (None, None)
            R[who] = {"decisions": d["decisions"], "score": d["score"]["score"], "why_ru": why[0], "why_en": why[1], "model": d["model"]}
        for who, fn in (("careful", drivers.careful), ("simple", drivers.simple)):
            decs, sc = run_driver(seed, city, fn)
            R[who] = {"decisions": decs, "score": sc["score"]}
        for who, r in R.items():
            chk = sim.replay(seed, {"city": city}, r["decisions"])
            if chk["score"] != r["score"]:
                bad.append((key, who, r["score"], chk["score"]))
            r["counts"] = chk["counts"]
        out["rivals"][key] = R
        out["meta"][key] = {"day": W["day"]}
if bad:
    print("пересчёт не совпал:", bad); sys.exit(1)
s = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
open(os.path.join(HERE, "data.json"), "w", encoding="utf-8").write(s)
avg = {}
for key, R in out["rivals"].items():
    c = key.split("_")[0]
    for who, r in R.items():
        avg.setdefault(who, {}).setdefault(c, []).append(r["score"])
for who, cs in avg.items():
    print("%-8s" % who, " ".join("%s %.0f" % (c, sum(v) / len(v)) for c, v in cs.items()))
print(len(s) // 1024, "КБ; все 150 журналов пересчитаны, счёт совпал")
