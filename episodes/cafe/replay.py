"""replay(seed, settings, decisions) -> score from a decision log [[evening, decision], ...].

settings = {"street": ..., "money": ..., "scenario": ...}. An evening is 0..29: the decision is made the evening
before day t. Anything that is not a decision (unknown field, not an object, evening outside the month) raises
ValueError. Parts of a decision that the game rejects are not applied, exactly as in play.
"""
import sim

ALLOWED = {"orders", "prices", "discounts", "hire", "fire", "schedule", "choices", "buy"}
SETTINGS = {"street", "money", "scenario"}


def clean_log(decisions, days=30):
    out = []
    for item in decisions:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("a log entry is [evening, decision]: %r" % (item,))
        step, dec = item
        if isinstance(step, bool) or not isinstance(step, int) and not (isinstance(step, str) and step.isdigit()):
            raise ValueError("evening must be an integer: %r" % (step,))
        step = int(step)
        if not 0 <= step < days:
            raise ValueError("evening %d is outside the month" % step)
        if not isinstance(dec, dict):
            raise ValueError("a decision is an object: %r" % (dec,))
        extra = set(dec) - ALLOWED
        if extra:
            raise ValueError("not a decision field: %s" % ", ".join(sorted(map(str, extra))))
        out.append((step, dec))
    return out


def replay(seed, settings, decisions):
    if set(settings) != SETTINGS:
        raise ValueError("settings are street, money, scenario")
    return sim.replay(int(seed), settings, clean_log(decisions))


def daily(seed, settings, decisions):
    """Score after each day, for comparing with recorded runs."""
    log = clean_log(decisions)
    g = sim.Game(int(seed), settings["street"], settings["money"], settings["scenario"])
    by_day = {}
    for t, d in log:
        by_day.setdefault(t, []).append(d)
    out = []
    while not g.done():
        g.observe()
        for d in by_day.get(g.t, []):
            g.decide(d)
        g.step()
        out.append(g.score()["score"])
    return out, g
