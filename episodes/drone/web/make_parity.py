"""Трасса для теста совпадения: миры по зерну, решения диспетчеров по шагам и состояние каждые 50 шагов (repr)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import drivers, polet, sim

NL = chr(10)


def st(g):
    out = []
    for d in g.drones:
        out += [repr(d["x"]), repr(d["y"]), repr(d["agl"]), repr(d["soc"]), repr(d["wh"]), d["mode"], d["phase"], repr(d["gs"])]
    out += [repr(g.counts["wh"]), repr(g.counts["late_s"]), g.counts["delivered"], g.counts["forced"], g.counts["lost"], g.counts["pads"]]
    return out


def trace(seed, city, who, drv=None, text=None, recall_at=None):
    g = sim.Game(seed, city)
    disp = polet.Dispatcher(polet.parse(text)[0]) if text is not None else None
    steps = []; cps = []; n = 0
    while not g.done():
        decs = []
        if recall_at is not None and n == recall_at:
            decs = [{"drone": 0, "recall": True}]
        elif disp is not None:
            decs = disp.tick(g)
        else:
            d = drv(g.observe(), g)
            if d is not None:
                decs = [d]
        taken = []
        for d in decs:
            if not g.decide(d):
                taken.append(d)
        if taken:
            steps.append([n, taken])
        g.step(); n += 1
        if n % 50 == 0:
            cps.append([n] + st(g))
    sc = g.score()
    return {"seed": seed, "city": city, "who": who, "steps": steps, "n": n, "cps": cps,
            "final": st(g), "score": repr(sc["raw"]), "counts": sc["counts"], "journal_tail": g.journal[-3:], "events": g.events}


PADS = {"almaty": 4, "dubai": 3, "rotterdam": 1}
out = []; worlds = {}; terrain = {}
for city in sim.CITIES:
    for seed in (1, 4, 8):
        kinds = [("simple", {"drv": drivers.simple}),
                 ("careful", {"drv": drivers.careful}),
                 ("polet", {"text": "скорость быстро" + NL + "заказов за рейс 2"}),
                 ("polet_pad", {"text": "заказов за рейс 2" + NL + "зарядка на площадке %d если заряд меньше 45" % PADS[city]}),
                 ("recall", {"text": "скорость быстро", "recall_at": 900})]
        for who, kw in kinds:
            t = trace(seed, city, who, **kw)
            t["world"] = "%s_%d" % (city, seed)
            out.append(t)
        g = sim.Game(seed, city)
        terrain[city] = g.W["map"]["terrain"]
        W = json.loads(json.dumps(g.W)); W["map"]["terrain"] = None
        worlds["%s_%d" % (city, seed)] = W
json.dump({"traces": out, "worlds": worlds, "terrain": terrain}, open(os.path.join(HERE, "parity_trace.json"), "w"))
print(len(out), "трасс,", sum(t["n"] for t in out), "шагов,", sum(len(t["steps"]) for t in out), "решений")
