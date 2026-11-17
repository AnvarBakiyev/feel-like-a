"""Обработчик языка полёта на 10 сменах каждого города: замысел по умолчанию в настоящем мире.
Нужен как ориентир: столько даёт обработчик без всякого замысла модели.

python3 run_polet.py ["строки замысла"]
"""
import json, sys, time
import polet, sim

txt = sys.argv[1] if len(sys.argv) > 1 else ""
plan, errs = polet.parse(txt)
if errs:
    print("разбор:", [e["ru"] for e in errs]); sys.exit(1)
res = {}
for city in sim.CITIES:
    rows = []
    for seed in range(1, 11):
        t0 = time.time()
        g, disp, dec = polet.run(txt, seed, city)
        s = g.score(); c = s["counts"]
        rows.append((seed, g.W["day"], s["score"], c["delivered"], c["orders"], c["forced"], c["lost"], c["pads"], disp.launched, round(time.time() - t0, 2)))
    print("%-9s средний %6.0f | доставлено %3d из %3d | рейсов %3d | вынужденных %d | потеряно %d | площадок %d | смены с потерей %d из 10" % (
        city, sum(r[2] for r in rows) / len(rows), sum(r[3] for r in rows), sum(r[4] for r in rows), sum(r[8] for r in rows),
        sum(r[5] for r in rows), sum(r[6] for r in rows), sum(r[7] for r in rows), sum(1 for r in rows if r[6] > 0)))
    print("   ", [(r[0], round(r[2])) for r in rows])
    res[city] = rows
json.dump({"plan": txt, "rows": res}, open("run_polet_10.json", "w"), ensure_ascii=False)
