"""Тесты договора эпизода: детерминизм, скрытое не в observe, отказы с причиной, пересчёт по журналу."""
import json
import sim, drivers


def run(seed, city, drv, log=None):
    g = sim.Game(seed, city); n = 0
    while not g.done():
        d = drv(g.observe(), g)
        if d and not g.decide(d) and log is not None:
            log.append([n, d])
        g.step(); n += 1
    return g


def test_determinism():
    a = run(3, "rotterdam", drivers.simple).score(); b = run(3, "rotterdam", drivers.simple).score()
    assert a == b, (a, b)


def test_hidden():
    g = sim.Game(1, "almaty"); o = json.dumps(g.observe(), ensure_ascii=False)
    for word in ("truth", "gust", "\"cap\"", "dens"):
        assert word not in o, word
    # прогноз отличается от настоящего ветра
    h = g.W["hours"][1]
    assert h["fc"][60] != h["truth"][60]


def test_rejections():
    g = sim.Game(1, "dubai")
    while not any(o["status"] == "wait" for o in g.observe()["orders"]):
        g.step()
    o = [x for x in g.observe()["orders"] if x["status"] == "wait"][0]
    assert g.check({"drone": 5, "route": ["o0"]})[0]["code"] == "unknown"
    assert g.check({"drone": 0, "route": ["o%d" % o["id"]], "alt": 77})[0]["code"] == "alt"
    assert g.check({"drone": 0, "route": ["p0"]})[0]["code"] == "no_pad"
    assert g.check({"drone": 0, "route": ["o99"]})[0]["code"] == "no_order"
    # запретная зона: прямой отрезок через круг
    assert sim.seg_circle(0, 0, 10000, 0, 5000, 100, 500) and not sim.seg_circle(0, 0, 10000, 0, 5000, 1000, 500)
    r = g.check({"drone": 0, "recall": True}); assert r and r[0]["code"] == "not_air"


def test_heat_and_wind():
    # Дубай, 01.08.2025, 46 °C: 30 кг не поднять
    W = sim.make_world(1, "dubai"); idx = [i for i, d in enumerate(sim.load("dubai")[0]["days"]) if d["day"] == "2025-08-01"][0]
    g = sim.Game(idx + 1, "dubai")
    p = g.p_hover(sim.D["empty_kg"] + 30, 5); assert p > g.hour()["pmax"], (p, g.hour()["pmax"])
    # Роттердам, 01.01.2025: ветер выше предела дрона
    idx = [i for i, d in enumerate(sim.load("rotterdam")[0]["days"]) if d["day"] == "2025-01-01"][0]
    g = sim.Game(idx + 1, "rotterdam")
    u, v = g.wind(30); assert (u * u + v * v) ** 0.5 > 12


def test_replay():
    log = []; g = run(2, "almaty", drivers.careful, log)
    r = sim.replay(2, {"city": "almaty"}, log)
    assert r["score"] == g.score()["score"], (r["score"], g.score()["score"])


def test_plausibility():
    for kg, mins, km in ((0.0, 29, 28), (30.0, 18, 16)):
        ph = sim.D["hover_c"] * (sim.D["empty_kg"] + kg) ** 1.25
        assert abs(sim.D["battery_wh"] / ph * 60 - mins) < 0.5
        assert abs(sim.D["battery_wh"] / ph * 15 * 3.6 - km) / km < 0.1


for name, f in list(globals().items()):
    if name.startswith("test_"):
        f(); print("ok", name)
