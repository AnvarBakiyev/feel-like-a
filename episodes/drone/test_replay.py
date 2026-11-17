"""A decision log replays to the same score; recorded model runs replay to their recorded score; forgeries are rejected."""
import glob, json, os
import sim, drivers
from replay import replay

HERE = os.path.dirname(os.path.abspath(__file__))


def play(seed, city, drv):
    g = sim.Game(seed, city); log = []; n = 0
    while not g.done():
        d = drv(g.observe(), g)
        if d and not g.decide(d):
            log.append([n, d])
        g.step(); n += 1
    return g, log


def test_driver_log():
    g, log = play(4, "dubai", drivers.careful)
    assert replay(4, {"city": "dubai"}, log)["score"] == g.score()["score"]


def test_recorded_runs():
    # one shift per city from each kind of recorded run; verify.py replays all 150
    for pat in ("extella/runs4b/*_s5.json", "extella/noext/big_*_s5.json", "extella/noext/small_*_s5.json"):
        files = sorted(glob.glob(os.path.join(HERE, pat)))
        assert len(files) == 3, pat
        for f in files:
            J = json.load(open(f, encoding="utf-8"))
            r = replay(J["seed"], {"city": J["city"]}, J["decisions"])
            assert r["score"] == J["score"]["score"], (f, r["score"], J["score"]["score"])


def test_forgeries():
    _, log = play(2, "rotterdam", drivers.simple)
    bad = [
        [[0, {"score": 1e9}]],                                   # not a decision
        [[0, {"drone": 0, "route": ["o0"], "delivered": 99}]],     # unknown field
        [[-1, {"drone": 0, "recall": True}]],                   # negative step
        [[0, {"drone": 0, "route": ["o15"]}]],                  # order that does not exist yet
        log[:1] + [[log[0][0], log[0][1]]],                     # the same order twice
    ]
    for b in bad:
        try:
            replay(2, {"city": "rotterdam"}, b)
        except ValueError:
            continue
        raise AssertionError("accepted a forged log: %r" % (b,))
    try:
        replay(2, {"city": "atlantis"}, log)
        raise AssertionError("accepted an unknown city")
    except ValueError:
        pass


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f(); print("ok", name)
