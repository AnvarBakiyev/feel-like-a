"""Template episode: "Feel like a water tower operator". Copy this folder to start your own episode.

Contract (CONTRACT.md):
    g = Game(seed, **settings); while not g.done(): obs = g.observe(); rej = g.decide(dec); g.step()
    g.score() -> {"score", "parts", "counts"}; g.journal: list of step reports
Everything random comes from the seed (mulberry32 with FNV-1a substreams), built before the first decision.
Only + - * / in the step loop, so a browser port (sim.js) can match byte for byte.
"""
import json

HOURS = 48


def fnv(s):
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h


class Rng:  # mulberry32
    def __init__(self, seed):
        self.a = seed & 0xFFFFFFFF

    def u(self):
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0


def rej(field, code, ru, en):
    return {"field": field, "code": code, "ru": ru, "en": en}


class Game:
    def __init__(self, seed, town="small"):
        r = Rng(fnv(str(seed) + ":demand"))
        base = {"small": 40.0, "big": 90.0}[town]
        self.demand = [base * (0.6 + 0.8 * r.u()) * (1.4 if 6 <= h % 24 <= 9 else 1.0) for h in range(HOURS)]  # hidden
        self.forecast = [d * 0.9 + base * 0.1 for d in self.demand]  # what the operator sees
        self.t = 0; self.level = 200.0; self.cap = 400.0; self.pump = 0.0
        self.cost = 0.0; self.dry = 0.0; self.spill = 0.0; self.journal = []

    def observe(self):
        return {"hour": self.t, "level": round(self.level, 1), "capacity": self.cap, "pump": self.pump,
                "forecast_next_3h": [round(x, 1) for x in self.forecast[self.t:self.t + 3]]}

    def check(self, dec):
        out = []; ok = {}
        if "pump" in dec:
            p = dec["pump"]
            if not isinstance(p, (int, float)) or isinstance(p, bool) or p < 0 or p > 100:
                out.append(rej("pump", "range", "Насос от 0 до 100 м³ в час.", "Pump is 0 to 100 m3 per hour."))
            else:
                ok["pump"] = float(p)
        return out, ok

    def decide(self, dec):
        out, ok = self.check(dec)
        if "pump" in ok:
            self.pump = ok["pump"]
        return out

    def step(self):
        night = self.t % 24 < 6
        self.cost += self.pump * (0.5 if night else 1.0)
        self.level += self.pump - self.demand[self.t]
        if self.level < 0:
            self.dry += -self.level; self.level = 0.0
        if self.level > self.cap:
            self.spill += self.level - self.cap; self.level = self.cap
        self.journal.append({"hour": self.t, "level": round(self.level, 3), "pump": self.pump})
        self.t += 1

    def done(self):
        return self.t >= HOURS

    def score(self):
        parts = {"energy": -self.cost, "dry": -20.0 * self.dry, "spill": -2.0 * self.spill}
        return {"score": round(5000.0 + sum(parts.values()), 1), "parts": {k: round(v, 1) for k, v in parts.items()},
                "counts": {"dry_m3": round(self.dry, 1), "spill_m3": round(self.spill, 1)}}
