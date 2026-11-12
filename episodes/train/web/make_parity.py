"""Трасса для теста совпадения: решения тестовых машинистов по шагам и состояние каждые 50 шагов (repr)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sim, drivers

def trace(seed, lid, drv, pre=None):
    g = sim.Game(seed, lid); steps = []; cps = []
    if pre: g.decide(pre)
    n = 0
    while not g.done():
        d = drv(g.observe(), g)
        steps.append(d)
        if d: g.decide(d)
        g.step(); n += 1
        if n % 50 == 0:
            cps.append([n, repr(g.x), repr(g.v), repr(g.E_in), repr(g.E_back), repr(g.t)])
    sc = g.score()
    return {"seed": seed, "line": lid, "world": g.W, "pre": pre, "steps": steps, "cps": cps,
            "final": [repr(g.x), repr(g.v), repr(g.E_in), repr(g.E_back), repr(g.harsh_s)], "score": repr(sc["raw"]), "counts": g.counts}

out = []
for lid in sim.LINES:
    for seed in (1, 2, 8):
        out.append(trace(seed, lid, drivers.full))
        out.append(trace(seed, lid, drivers.careful))
data = {"lines": {lid: sim.load("lines", sim.LINES[lid]) for lid in sim.LINES}, "trains": {lid: sim.load("trains", sim.TRAIN_OF[lid]) for lid in sim.LINES}, "traces": out}
json.dump(data, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "parity_trace.json"), "w"))
print(len(out), "трасс")
