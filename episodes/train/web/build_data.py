"""Данные для страницы: участки, поезда, миры открытых зёрен 1–10, призраки Extella (ступень 2) и пример для урока 5."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import sim, drivers

def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list):
        return [strip(x) for x in o]
    return o

D = {"lines": {}, "trains": {}, "worlds": {}, "ghosts": {}, "bench": {}, "ladder": {}}
S1 = json.load(open(os.path.join(ROOT, "extella", "runs", "summary.json"), encoding="utf-8"))
for lid in sim.LINES:
    L = sim.load("lines", sim.LINES[lid]); T = sim.load("trains", sim.TRAIN_OF[lid])
    D["lines"][lid] = strip(L); D["trains"][lid] = strip(T)
    D["worlds"][lid] = {}; D["ghosts"][lid] = {}; D["bench"][lid] = {}
    v2 = []
    for s in range(1, 11):
        g = sim.Game(s, lid); D["worlds"][lid][s] = g.W
        J = json.load(open(os.path.join(ROOT, "extella", "runs_v2", "%s_s%d.json" % (lid, s)), encoding="utf-8"))
        jr = [[round(e["t"], 1), round(e["km"], 3), round(e["v"], 1), round(e["e"], 1)] for e in J["journal"]]
        D["ghosts"][lid][s] = {"plan": J["plan"], "why_ru": J.get("why_ru", ""), "why_en": J.get("why_en", ""), "score": J["score"]["score"],
                               "parts": J["score"]["parts"], "stops": J["score"]["stops"], "tries": len(J["calls"]), "fallback": bool(J.get("fallback")), "j": jr}
        f = sim.play(s, lid, drivers.full).score()["score"]; c = sim.play(s, lid, drivers.careful).score()["score"]
        D["bench"][lid][s] = {"full": f, "careful": c, "extella_v1": [r for r in S1[lid] if r["seed"] == s][0]["x"], "extella_v2": J["score"]["score"]}
        v2.append(J["score"]["score"])
    D["ladder"][lid] = {"v1": round(sum(r["x"] for r in S1[lid]) / 10), "v2": round(sum(v2) / 10),
                        "full": round(sum(D["bench"][lid][s]["full"] for s in range(1, 11)) / 10), "careful": round(sum(D["bench"][lid][s]["careful"] for s in range(1, 11)) / 10)}
# соперники без Extella: малая и большая модель пишут контроллер по км сами
D["rivals"] = {}; D["rival_avg"] = {}
for who, pref in (("small", "small"), ("big", "big")):
    for lid in sim.LINES:
        xs = []
        for s_ in range(1, 11):
            p = os.path.join(ROOT, "extella", "noext", "%s_%s_s%d.json" % (pref, lid, s_))
            if not os.path.exists(p):
                continue
            J = json.load(open(p, encoding="utf-8"))
            jj = J["journal"]; last = max([i for i, e in enumerate(jj) if e["v"] > 0.1] or [0])
            jj = jj[:last + 2]; step = max(1, len(jj) // 400)
            jr = [[round(e["t"], 1), round(e["km"], 3), round(e["v"], 1), round(e["e"], 1)] for e in jj[::step]]
            D["rivals"].setdefault(lid, {}).setdefault(str(s_), {})[who] = {"score": J["score"]["score"], "parts": J["score"]["parts"], "stops": J["score"]["stops"], "j": jr,
                "why_ru": (J["plan"] or {}).get("why_ru", ""), "why_en": (J["plan"] or {}).get("why_en", ""), "points": len((J["plan"] or {}).get("plan", [])),
                "stuck_km": None if not J["score"]["parts"]["unfinished"] else round(jj[-1]["km"], 2)}
            xs.append(J["score"]["score"])
        if xs:
            D["rival_avg"].setdefault(lid, {})[who] = {"avg": round(sum(xs) / len(xs)), "n": len(xs)}
# большая модель с обратной связью: зёрна 1–3
for lid in sim.LINES:
    xs = []
    for s_ in range(1, 4):
        p = os.path.join(ROOT, "extella", "noext", "closed", "%s_s%d.json" % (lid, s_))
        if not os.path.exists(p):
            continue
        J = json.load(open(p, encoding="utf-8"))
        if "score" not in J:
            continue
        jj = J["journal"]; step = max(1, len(jj) // 400)
        jr = [[round(e["t"], 1), round(e["km"], 3), round(e["v"], 1), round(e["e"], 1)] for e in jj[::step]]
        D["rivals"].setdefault(lid, {}).setdefault(str(s_), {})["bigfb"] = {"score": J["score"]["score"], "parts": J["score"]["parts"], "stops": J["score"]["stops"], "j": jr, "calls": J["calls"]}
        xs.append(J["score"]["score"])
    if xs:
        D["rival_avg"].setdefault(lid, {})["bigfb"] = {"avg": round(sum(xs) / len(xs)), "n": len(xs)}
# пример для урока 5: Готард, мокро, где был отказ и исправление; иначе первый с отказом
ex = None
for lid in ("ch_gotthard", "de_krm", "jp_tokaido"):
    for s in range(1, 11):
        for d in ("runs", "runs_v2"):
            J = json.load(open(os.path.join(ROOT, "extella", d, "%s_s%d.json" % (lid, s)), encoding="utf-8"))
            if len(J["calls"]) >= 2 and J["calls"][-1]["ok"] and not ex and any("встанет" in e["ru"] or "опоздание" in e["ru"] for e in J["calls"][0]["errors"]):
                ex = {"line": lid, "seed": s, "stage": d, "briefing": J["briefing"], "calls": [{"plan": c["plan"], "ok": c["ok"], "errors": c["errors"],
                      "forecast": c["forecast"] and {"score": c["forecast"]["score"]}} for c in J["calls"]], "score": J["score"]["score"],
                      "full": sim.play(s, lid, drivers.full).score()["score"]}
D["lesson5"] = ex
s = json.dumps(D, ensure_ascii=False, separators=(",", ":"))
open(os.path.join(HERE, "data.json"), "w", encoding="utf-8").write(s)
print(len(s) // 1024, "КБ", "урок 5:", ex and (ex["line"], ex["seed"], ex["stage"], len(ex["calls"])))
