"""Тестовые диспетчеры на 10 сменах каждого города: сводка и проверка правдоподобия дрона в штиль."""
import json, sys, time
import sim, drivers

def plausibility():
    g = sim.Game(1, "rotterdam")
    out = {}
    for kg, name in ((0.0, "пустой"), (30.0, "30 кг")):
        m = sim.D["empty_kg"] + kg; ph = sim.D["hover_c"] * m ** 1.25 * 1.0
        out[name] = {"висение, мин": round(sim.D["battery_wh"] / ph * 60, 1),
                     "дальность на 15 м/с, км": round(sim.D["battery_wh"] / ph * 15 * 3.6, 1)}
    return out

print("правдоподобие в штиль на уровне моря (DJI: висение 29 / 18 мин, дальность 28 / 16 км):", json.dumps(plausibility(), ensure_ascii=False))
res = {}
for city in sim.CITIES:
    for name, drv in drivers.DRIVERS.items():
        rows = []
        for seed in range(1, 11):
            g = sim.Game(seed, city); t0 = time.time()
            while not g.done():
                d = drv(g.observe(), g)
                if d:
                    g.decide(d)
                g.step()
            s = g.score(); c = s["counts"]
            rows.append((seed, g.W["day"], s["score"], c["delivered"], c["orders"], c["forced"], c["lost"], c["pads"], round(time.time() - t0, 2)))
        avg = sum(r[2] for r in rows) / len(rows)
        print("%-9s %-7s средний %6.0f | доставлено %3d из %3d | вынужденных %d | потеряно %d | площадок %d | смены с потерей %d из 10" % (
            city, name, avg, sum(r[3] for r in rows), sum(r[4] for r in rows), sum(r[5] for r in rows), sum(r[6] for r in rows), sum(r[7] for r in rows), sum(1 for r in rows if r[6] > 0)))
        res[city + ":" + name] = rows
json.dump(res, open("run_seeds_10.json", "w"), ensure_ascii=False)
