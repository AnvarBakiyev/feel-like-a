"""replay(seed, settings, decisions) -> score from a decision log [[step, decision], ...]. Rejects anything that is not a decision."""
import sim

ALLOWED = {"pump"}


def replay(seed, settings, decisions):
    clean = []
    for item in decisions:
        step, dec = int(item[0]), item[1]
        if not isinstance(dec, dict) or set(dec) - ALLOWED or step < 0:
            raise ValueError("bad decision: %r" % (item,))
        clean.append((step, dec))
    clean.sort(key=lambda d: d[0])
    g = sim.Game(int(seed), **settings); i = 0; n = 0
    while not g.done():
        while i < len(clean) and clean[i][0] <= n:
            g.decide(clean[i][1]); i += 1
        g.step(); n += 1
    return g.score()
