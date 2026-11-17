"""Score from a decision log. Rush hour has one decision, the rules, taken before the first step:
replay(seed, {"level": "district"}, [[0, {"rules": "A: light, ns 12, ew 8"}]]) -> {"score", "parts", "counts", "sha", ...}
Anything that is not a valid decision at step 0 raises ValueError.
"""
import sim


def replay(seed, settings, log):
    g = sim.Game(seed, **settings)
    for item in log:
        if not (isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], dict)):
            raise ValueError("a log entry is [step, decision]")
        step, dec = item
        if step != 0:
            raise ValueError("rules are decided at step 0 only, got step %r" % (step,))
        if set(dec) != {"rules"}:
            raise ValueError("a decision here is {\"rules\": text}, got %s" % sorted(dec))
        rej = g.decide(dec)
        if rej:
            raise ValueError(rej[0]["en"])
    while not g.done():
        g.step()
    out = g.score()
    out["journal"] = g.journal
    return out


if __name__ == "__main__":
    import json, sys
    level = sys.argv[1] if len(sys.argv) > 1 else "district"
    rules = sys.stdin.read()
    r = replay(None, {"level": level}, [[0, {"rules": rules}]])
    print(json.dumps({k: v for k, v in r.items() if k != "journal"}, ensure_ascii=False))
