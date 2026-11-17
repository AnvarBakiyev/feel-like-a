"""replay(seed, settings, log) -> {"score", "parts", "counts"} from a decision log [[step, decision], ...].

settings: {"place", "team", "scenario"} and optionally "world" ("ny2" by default: the world of the published runs
and of web/play.html; "ny" is the earlier balance). Anything that is not a decision of this game raises ValueError.
"""
import sim

ALLOWED = {"schedule", "thaw", "orders", "price", "free_wed", "vet_visit", "hire", "fire", "choices"}
WORLDS = ("ny2", "ny")


def replay(seed, settings, log):
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")
    s = dict(settings)
    world = s.pop("world", "ny2")
    if world not in WORLDS:
        raise ValueError("world: one of %s" % (WORLDS,))
    clean = []
    for item in log:
        if not isinstance(item, (list, tuple)) or len(item) != 2 or not isinstance(item[1], dict):
            raise ValueError("bad log item: %r" % (item,))
        extra = set(item[1]) - ALLOWED
        if extra:
            raise ValueError("not a decision field: %s" % ", ".join(sorted(extra)))
        clean.append((item[0], item[1]))
    return sim.replay(seed, s, clean, world)
