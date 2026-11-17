"""Tests of the Rush hour episode. python3 test_sim.py  (Node is needed for the browser parity and the handler rebuild.)

1. one seed, one day: the same rules give the same journal; another seed gives another day;
2. the decision log replays to the same score; forged or late decisions are refused;
3. hidden parts of the day (seed, ducks, the Friday wave) are not in observe();
4. the handler refuses bad rules and says why, in both languages;
5. the browser (web/traffic_core.js) and the handler (traffic_handler_v1.py) give the same result, number by number,
   on the live days and on other seeds;
6. the handler file is exactly what build_traffic.py makes from traffic_core.py and the browser's levels.
"""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim, replay, drivers

GOOD = "A: light, north-south 12, east-west 8, box\nB: main east-west\nall: box\n"


def run(seed, level, rules):
    g = sim.Game(seed, level=level)
    assert g.decide({"rules": rules}) == []
    g.step()
    return g


def test_seed():
    a, b = run(None, "district", GOOD), run(None, "district", GOOD)
    assert json.dumps(a.journal, sort_keys=True) == json.dumps(b.journal, sort_keys=True)
    assert a.score() == b.score()
    assert sim.Game(None, level="district").seed == 41 and run(41, "district", GOOD).score() == a.score()
    c = run(7, "district", GOOD)
    assert c.score()["sha"] != a.score()["sha"], "another seed should be another day"
    assert a.done() and a.score()["score"] in (0, 1, 2, 3)


def test_replay():
    for lv in sim.LEVELS:
        g = sim.Game(None, level=lv)
        dec = drivers.plan(g.observe(), g)
        assert g.decide(dec) == []
        g.step()
        r = replay.replay(None, {"level": lv}, [[0, dec]])
        assert r["score"] == g.score()["score"] and r["sha"] == g.score()["sha"]
    for bad in ([[0, {"score": 1e9}]], [[1, {"rules": GOOD}]], [[0, {"rules": "Z: light"}]], [[0, {"rules": GOOD, "stars": 3}]], [["x"]]):
        try:
            replay.replay(None, {"level": "district"}, bad)
            raise AssertionError("accepted %r" % (bad,))
        except ValueError:
            pass
    assert replay.replay(None, {"level": "district"}, [])["score"] == replay.replay(None, {"level": "district"}, [[0, {"rules": ""}]])["score"]


def test_hidden():
    for lv in sim.LEVELS:
        obs = json.dumps(sim.Game(None, level=lv).observe())
        for k in sim.HIDDEN:
            assert '"%s"' % k not in obs, (lv, k)


def test_refusals():
    g = sim.Game(None, level="district")
    cases = {
        "A: light, ns 1, ew 8": "too short",
        "A: light, ns 12": "missing",
        "A: light\nB: light\nC: light": "only 2 traffic lights",
        "Q: stop": "no crossing",
        "B: main north-south, ns 10, ew 10": "no traffic light",
        "please go": "a rule is",
    }
    for rules, words in cases.items():
        rej = g.decide({"rules": rules})
        assert rej and rej[0]["code"] == "handler_refused" and words in rej[0]["en"] and rej[0]["ru"], (rules, rej)
    assert g.decide({"rules": "x" * 2001})[0]["code"] == "too_long"
    assert g.decide({"rules": GOOD, "mayor": 1})[0]["code"] == "unknown_field"
    g.step()
    assert g.decide({"rules": GOOD})[0]["code"] == "too_late"


def node():
    return shutil.which("node")


def test_parity():
    if not node():
        print("   (no node: parity skipped)")
        return
    cases = []
    for lv in sim.LEVELS:
        g = sim.Game(None, level=lv)
        plan = drivers.plan(g.observe(), g)["rules"]
        for seed in (None, 1, 2026):
            cases += [[lv, seed, plan], [lv, seed, ""]]
        cases += [[lv, None, GOOD + "ambulance first\nC: light, longest queue, min 4, max 18, offset 6"], [lv, None, "A: light, ns 50, ew 8"]]
    py = []
    for lv, seed, rules in cases:
        level = dict(sim.LEVELS[lv])
        if seed is not None:
            level["seed"] = seed
        sim.LEVELS["_p"] = level
        try:
            out = sim.H["simulate"]("_p", rules)
        finally:
            sim.LEVELS.pop("_p")
        py.append({"problems": out["problems"], "result": out.get("result")})
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "cases.json")
        json.dump(cases, open(path, "w", encoding="utf-8"))
        js = json.loads(subprocess.run([node(), os.path.join(HERE, "web", "parity.mjs"), path], capture_output=True, text=True, check=True).stdout)
    bad = [i for i in range(len(cases)) if json.dumps(py[i], sort_keys=True) != json.dumps(js[i], sort_keys=True)]
    assert not bad, "browser and handler differ: %s" % [(cases[i][:2], py[i], js[i]) for i in bad[:2]]
    print("   parity: %d cases, browser = handler" % len(cases))


def test_handler_rebuild():
    if not node():
        print("   (no node: rebuild check skipped)")
        return
    sys.path.insert(0, HERE)
    import build_traffic
    text, sha = build_traffic.handler_text()
    assert text == open(os.path.join(HERE, "traffic_handler_v1.py"), encoding="utf-8").read(), "traffic_handler_v1.py is not what build_traffic.py makes"
    name, code, _ = build_traffic.registrar()
    assert code == open(os.path.join(HERE, "extella", name + ".fython"), encoding="utf-8").read(), "the registrar is stale"
    print("   handler rebuilt byte for byte, sha", sha[:12])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
