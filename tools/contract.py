"""Generic checks every episode must pass. Used by tools/check_episodes.py and by each episode's own tests.

An episode is a folder with sim.py (class Game) and replay.py (function replay). The checks:
1. same seed, same decisions -> same journal and score, byte for byte;
2. the decision log the page would record replays to the same score;
3. hidden state never appears in observe();
4. a forged decision is rejected by replay.
"""
import importlib.util, json, os, sys


def load(folder, name):
    # episodes share module names (sim, replay, drivers): forget the previous episode's modules first
    for f in os.listdir(folder):
        if f.endswith(".py"):
            sys.modules.pop(f[:-3], None)
    if sys.path[0] != folder:
        sys.path.insert(0, folder)
    spec = importlib.util.spec_from_file_location(name + "_" + os.path.basename(folder), os.path.join(folder, name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def play(sim, seed, settings, driver):
    g = sim.Game(seed, **settings); log = []; n = 0; last = {}
    while not g.done():
        d = driver(g.observe(), g)
        if d:
            ch = {k: v for k, v in d.items() if last.get(k) != v}
            if ch and not g.decide(ch):
                log.append([n, ch]); last.update(ch)
        g.step(); n += 1
    return g, log


def check(folder, contract):
    sim = load(folder, "sim"); rp = load(folder, "replay")
    mod, fn = contract["driver"].split(":")
    driver = getattr(load(folder, mod), fn)
    report = []
    for seed in contract.get("seeds", [1, 2]):
        settings = contract["settings"]
        a, log = play(sim, seed, settings, driver); b, _ = play(sim, seed, settings, driver)
        assert json.dumps(a.journal, sort_keys=True) == json.dumps(b.journal, sort_keys=True), "same seed gave a different journal"
        assert a.score() == b.score(), "same seed gave a different score"
        r = rp.replay(seed, settings, log)
        assert abs(r["score"] - a.score()["score"]) < 1e-9, "replay of the decision log gave a different score"
        obs = json.dumps(sim.Game(seed, **settings).observe(), default=str)
        for key in contract.get("hidden_keys", []):
            assert '"%s"' % key not in obs, "hidden key '%s' is visible in observe()" % key
        report.append("seed %s: score %.1f, %d decisions, replay ok" % (seed, a.score()["score"], len(log)))
    try:
        rp.replay(contract.get("seeds", [1])[0], contract["settings"], [[0, {"score": 1e9}]])
        raise AssertionError("a forged decision was accepted by replay")
    except ValueError:
        report.append("forged decision rejected")
    return report
