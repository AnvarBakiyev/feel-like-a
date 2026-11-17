"""A decision log replays to the same score; recorded model runs replay to their recorded scores; forgeries are rejected.

python3 test_replay.py
"""
import glob, json, os, sys
import sim, drivers
from replay import replay

HERE = os.path.dirname(os.path.abspath(__file__))


def test_play_log_replays():
    for seed, st, mo, sc in ((1, "district", "mid", "winter"), (4, "corridor", "low", "competitor"), (2, "quiet", "high", "calm")):
        g = sim.Game(seed, st, mo, sc); log = []
        while not g.done():
            d = drivers.careful(g.observe(), g)
            log.append([g.t, d]); g.decide(d); g.step()
        r = replay(seed, {"street": st, "money": mo, "scenario": sc}, log)
        assert r["score"] == g.score()["score"], (r["score"], g.score()["score"])


def test_recorded_runs_replay():
    n = 0
    for f in sorted(glob.glob(os.path.join(HERE, "extella", "runs", "*", "*.json"))):
        d = json.load(open(f, encoding="utf-8")); c = d["combo"]
        s = {k: c[k] for k in ("street", "money", "scenario")}
        r = replay(c["seed"], s, [[e["day"], e["decision"]] for e in d["evenings"]])
        assert abs(r["score"] - d["score"]["score"]) < 0.005, (f, r["score"], d["score"]["score"])
        n += 1
    assert n >= 65, n


def test_forgeries_rejected():
    s = {"street": "district", "money": "mid", "scenario": "calm"}
    for bad in ([[0, {"score": 1e9}]], [[0, "orders"]], [[30, {}]], [[-1, {}]], [["x", {}]], [[0, {"orders": {}, "cash": 1}]], [{"day": 0}]):
        try:
            replay(1, s, bad)
        except ValueError:
            continue
        raise AssertionError("accepted: %r" % (bad,))
    try:
        replay(1, {"street": "district", "money": "mid"}, [])
        raise AssertionError("accepted incomplete settings")
    except ValueError:
        pass


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print("ok  ", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
    sys.exit(1 if fails else 0)
