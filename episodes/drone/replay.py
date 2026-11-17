"""Score of a shift from its decision log, for leaderboards and for verify.py.

replay(seed, {"city": "rotterdam"}, [[step, decision], ...]) -> {"score", "parts", "counts", "steps"}

Strict: anything that is not a decision the game accepts at that step raises ValueError, so a forged log
cannot buy points. A decision is {"drone": 0..2, "route": ["o3", "p6"], "alt": 30|60|100|120, "speed": "eco"|"fast"}
or {"drone": 0..2, "recall": true}.
"""
import sim

KEYS = {"drone", "route", "alt", "speed", "recall"}


def replay(seed, settings, decisions):
    city = (settings or {}).get("city")
    if city not in sim.CITIES:
        raise ValueError("unknown city: %r" % (city,))
    clean = []
    for item in decisions:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("a log entry is [step, decision]: %r" % (item,))
        step, dec = item
        if not isinstance(step, int) or isinstance(step, bool) or step < 0:
            raise ValueError("step must be a non-negative integer: %r" % (step,))
        if not isinstance(dec, dict) or not dec or not set(dec) <= KEYS or "drone" not in dec:
            raise ValueError("not a decision: %r" % (dec,))
        clean.append((step, dec))
    clean.sort(key=lambda x: x[0])
    g = sim.Game(int(seed), city); i = 0; n = 0
    while not g.done():
        while i < len(clean) and clean[i][0] <= n:
            rej = g.decide(clean[i][1])
            if rej:
                raise ValueError("decision at step %d rejected: %s" % (clean[i][0], rej[0]["en"]))
            i += 1
        g.step(); n += 1
    if i < len(clean):
        raise ValueError("decision at step %d comes after the shift ended" % clean[i][0])
    sc = g.score()
    return {"score": sc["score"], "parts": sc["parts"], "counts": sc["counts"], "steps": n}
