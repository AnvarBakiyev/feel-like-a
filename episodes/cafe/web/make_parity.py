"""Трассы для теста совпадения Python и JS: решения по дням, наблюдения, полный журнал симулятора, счёт.

Игроки: осторожный, наивный, случайный (годные и негодные решения, чтобы проверить и отказы)
и решения Extella из extella/runs/g14/. Запуск: python3 web/make_parity.py && node web/parity.mjs
"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sim, policies


def chaos(seed):
    r = sim.Rng(sim.fnv("chaos:" + str(seed)))

    def pol(obs):
        d = {}
        u = r.u()
        if u < 0.7:
            d["orders"] = {"dairy": {"milk": r.int(0, 30)}, "roaster": {"beans": r.int(0, 25), "cups": r.int(0, 3)}, "bakery": {"croissant": r.int(0, 90)}}
        if r.u() < 0.15:
            d["prices"] = {"latte": [4.0, 5.25, 5.9, 0.5, 9.0][r.int(0, 4)], "croissant": [3.5, 4.25][r.int(0, 1)]}
        if r.u() < 0.1:
            d["discounts"] = [{"item": ["latte", "drip", "croissant"][r.int(0, 2)], "pct": [10, 20, 35][r.int(0, 2)], "dayparts": [[2], [1, 2], [0, 0]][r.int(0, 2)]}]
        if r.u() < 0.1:
            d["hire"] = r.int(0, 2)
        if r.u() < 0.05:
            d["fire"] = r.int(0, 1)
        if r.u() < 0.1:
            b = [r.int(1, 3), r.int(1, 3), r.int(0, 2)]
            d["schedule"] = {str(w): {"barista": list(b), "lead": [1, r.int(0, 1), 0]} for w in range(7)}
        if r.u() < 0.08:
            d["buy"] = [["machine2", "marketing", "neon"][r.int(0, 2)]]
        ch = {}
        for c in obs["cards"]:
            if r.u() < 0.8:
                ch[c["id"]] = c["options"][r.int(0, len(c["options"]) - 1)] if r.u() < 0.9 else "maybe"
        if r.u() < 0.03:
            ch["ghost_9"] = "accept"
        if ch:
            d["choices"] = ch
        return d
    return pol


def trace(seed, street, money, scenario, policy=None, decisions=None):
    g = sim.Game(seed, street, money, scenario)
    by_day = {}
    for day, dec in decisions or []:
        by_day.setdefault(day, []).append(dec)
    steps = []; obs_all = []
    while g.t < g.C["days"]:
        obs = g.observe(); obs_all.append(obs)
        decs = [policy(obs)] if policy else by_day.get(g.t, [])
        for dec in decs:
            g.decide(dec)
        steps.append(decs)
        g.step()
    return {"settings": {"seed": seed, "street": street, "money": money, "scenario": scenario}, "steps": steps,
            "observe": obs_all, "journal": g.journal, "score": g.score()}


out = []
SC = ["calm", "winter", "competitor"]; ST = ["quiet", "district", "corridor"]; MO = ["low", "mid", "high"]
for seed in (1, 2, 5):
    for sc in SC:
        for st in ST:
            mo = MO[(seed + SC.index(sc) + ST.index(st)) % 3]
            out.append(trace(seed, st, mo, sc, policy=policies.careful))
            out.append(trace(seed, st, mo, sc, policy=chaos(seed * 100 + SC.index(sc) * 10 + ST.index(st))))
    out.append(trace(seed, "district", "low", "calm", policy=policies.naive))
for f in sorted(glob.glob(os.path.join(HERE, "..", "extella", "runs", "g14", "*.json"))):
    d = json.load(open(f)); c = d["combo"]
    out.append(trace(c["seed"], c["street"], c["money"], c["scenario"], decisions=[(e["day"], e["decision"]) for e in d["evenings"]]))
city = sim.load_city("ny")
json.dump({"city": city, "traces": out}, open(os.path.join(HERE, "parity_trace.json"), "w"), ensure_ascii=False)
print(len(out), "трасс")
