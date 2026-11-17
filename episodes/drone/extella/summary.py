"""Сводка прогонов эпизода: соперники по городам и цифры для итогов предсказаний Д1-Д5.

python3 summary.py  ->  summary.json и таблица на экран
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import sim

RUNS = os.path.join(HERE, "runs"); RUNS2 = os.path.join(HERE, "runs2"); RUNS3 = os.path.join(HERE, "runs3"); RUNS4B = os.path.join(HERE, "runs4b")
NOEXT = os.path.join(HERE, "noext")
WHO = ["extella4b", "extella3", "extella2", "extella", "small", "big", "simple", "careful", "obrabotchik"]
RU = {"extella4b": "Extella, ступень 4, пример без чисел", "extella4": "Extella, ступень 4 языка", "extella3": "Extella, ступень 3 языка", "extella2": "Extella, ступень 2 языка",
      "extella": "Extella, ступень 1 (9B + обработчик)", "small": "9B без Extella",
      "big": "большая модель без Extella", "simple": "простая программа", "careful": "расчётливая программа",
      "obrabotchik": "обработчик, замысел по умолчанию"}


def rows_extella(RUNS=RUNS):
    out = {}
    for city in sim.CITIES:
        for seed in range(1, 11):
            p = os.path.join(RUNS, "%s_s%d.json" % (city, seed))
            if not os.path.exists(p):
                continue
            J = json.load(open(p, encoding="utf-8")); c = J["score"]["counts"]
            out[(city, seed)] = {"score": J["score"]["score"], "delivered": c["delivered"], "orders": c["orders"],
                                 "forced": c["forced"], "lost": c["lost"], "pads": c["pads"], "flights": J["flights"],
                                 "tries": len(J["calls"]), "fallback": bool(J.get("fallback")), "plan": J["plan"],
                                 "first_ok": J["calls"][0]["ok"], "errors": [e["ru"] for c2 in J["calls"] for e in c2["errors"]],
                                 "day": J["day"], "seconds_model": sum(c2["seconds"] for c2 in J["calls"]),
                                 "seconds_expert": sum(m["seconds"] for m in J["expert_calls"]),
                                 "advice": (J.get("advice") or {}).get("line_ru"), "took_advice": J.get("took_advice"),
                                 "advice_line_used": J.get("advice_line_used"), "advice_lines": J.get("advice_lines"),
                                 "advice_lines_used": J.get("advice_lines_used"),
                                 "advice_all": (J.get("advice") or {}).get("lines_ru"), "kwh": c["kwh"], "late_s": c["late_s"]}
    return out


def rows_noext(prefix):
    out = {}
    for city in sim.CITIES:
        for seed in range(1, 11):
            p = os.path.join(NOEXT, "%s_%s_s%d.json" % (prefix, city, seed))
            if not os.path.exists(p):
                continue
            J = json.load(open(p, encoding="utf-8")); c = J["score"]["counts"]
            codes = {}
            for r in J.get("rejected", []):
                codes[r[2]] = codes.get(r[2], 0) + 1
            aborted = 0
            ev = J.get("events", [])
            for i, e in enumerate(ev):
                if e[1] == "takeoff":
                    for f in ev[i + 1:]:
                        if f[2] != e[2]:
                            continue
                        if f[1] == "dock" and f[0] - e[0] < 120:
                            aborted += 1
                        break
            out[(city, seed)] = {"score": J["score"]["score"], "delivered": c["delivered"], "orders": c["orders"],
                                 "forced": c["forced"], "lost": c["lost"], "pads": c["pads"], "flights": len(J["decisions"]),
                                 "rejected": codes, "aborted": aborted, "plan": J["plan"], "day": J["day"]}
    return out


def rows_drivers(path, key):
    """run_seeds_10.json шага 2 и run_polet_10.json: (seed, day, score, delivered, orders, forced, lost, pads, ...)"""
    out = {}
    if not os.path.exists(path):
        return out
    D = json.load(open(path, encoding="utf-8"))
    src = D["rows"] if "rows" in D else D
    for city in sim.CITIES:
        rows = src[city + ":" + key] if key else src[city]
        for r in rows:
            out[(city, r[0])] = {"score": r[2], "delivered": r[3], "orders": r[4], "forced": r[5], "lost": r[6], "pads": r[7], "day": r[1]}
    return out


ROOT = os.path.dirname(HERE)
data = {"extella": rows_extella(), "extella2": rows_extella(RUNS2), "extella3": rows_extella(RUNS3), "extella4b": rows_extella(RUNS4B), "small": rows_noext("small"), "big": rows_noext("big"),
        "simple": rows_drivers(os.path.join(ROOT, "run_seeds_10.json"), "simple"),
        "careful": rows_drivers(os.path.join(ROOT, "run_seeds_10.json"), "careful"),
        "obrabotchik": rows_drivers(os.path.join(ROOT, "run_polet_10.json"), None)}

print("%-34s %s" % ("", "  ".join("%-28s" % c for c in sim.CITIES)))
tab = {}
for who in WHO:
    d = data[who]
    line = []
    for city in sim.CITIES:
        rs = [v for (c, s), v in d.items() if c == city]
        if not rs:
            line.append("%-28s" % "нет"); continue
        n = len(rs)
        line.append("%-28s" % ("средний %6.0f из %2d смен" % (sum(r["score"] for r in rs) / n, n)))
        tab[(who, city)] = {"n": n, "score": round(sum(r["score"] for r in rs) / n, 1),
                            "delivered": sum(r["delivered"] for r in rs), "orders": sum(r["orders"] for r in rs),
                            "forced": sum(r["forced"] for r in rs), "lost": sum(r["lost"] for r in rs),
                            "pads": sum(r["pads"] for r in rs), "shifts_with_loss": sum(1 for r in rs if r["lost"] > 0),
                            "shifts_with_forced": sum(1 for r in rs if r["forced"] > 0)}
    print("%-34s %s" % (RU[who], "  ".join(line)))
print()
for who in WHO:
    for city in sim.CITIES:
        t = tab.get((who, city))
        if t:
            print("%-30s %-10s доставлено %3d из %3d | вынужденных %2d (в %d сменах) | потеряно %d (в %d сменах) | площадок %d" % (
                RU[who], city, t["delivered"], t["orders"], t["forced"], t["shifts_with_forced"], t["lost"], t["shifts_with_loss"], t["pads"]))
json.dump({"table": {who + ":" + city: tab[(who, city)] for (who, city) in tab},
           "rows": {who: {c + "_s" + str(s): v for (c, s), v in data[who].items()} for who in WHO}},
          open(os.path.join(HERE, "summary.json"), "w"), ensure_ascii=False, indent=1)
print()
print("сохранено в summary.json")
