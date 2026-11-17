"""Rush hour as an episode: a thin wrapper around the "traffic" handler (traffic_handler_v1.py), no logic of its own.

The player's decision is the rules of the city, a short text in the traffic language ("A: light, north-south 12, east-west 8").
The handler checks the rules and runs one rush hour by them, car by car. So the episode has one decision and one step:
    g = Game(seed, level="district"); g.decide({"rules": text}); g.step(); g.score()
seed None (or the level's own seed: district 41, ambulance 53, gridlock 67) is the day played on extella.dev/traffic;
any other seed is another day on the same streets: the same flows, other cars.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
H = {}
exec(open(os.path.join(HERE, "traffic_handler_v1.py"), encoding="utf-8").read(), H)
LEVELS = H["LEVELS"]
MAX_RULES = 2000          # the server keeps at most this many characters of rules
HIDDEN = ("seed", "ducks", "burst")   # the cars' draws, a duck family crossing, the Friday wave: the player meets them on the street


def rej(field, code, ru, en):
    return {"field": field, "code": code, "ru": ru, "en": en}


class Game:
    def __init__(self, seed=None, level="district"):
        if level not in LEVELS:
            raise ValueError("there is no level %s; the levels are %s" % (level, ", ".join(sorted(LEVELS))))
        self.level_key = level
        self.level = dict(LEVELS[level])
        if seed is not None:
            self.level["seed"] = int(seed)
        self.seed = self.level["seed"]
        self.rules = ""
        self.n = 0
        self.result = None
        self.journal = []

    def observe(self):
        lv = self.level
        obs = {"step": self.n, "level": self.level_key, "name": lv.get("name"), "crossings": H["cross_names"](lv),
               "cols": lv["cols"], "rows": lv["rows"], "seconds": lv["seconds"], "lights": lv["lights"],
               "start": dict(lv.get("start") or {}), "flows": dict(lv["flows"]), "turns": dict(lv["turns"]),
               "ambulances": [dict(a) for a in lv.get("ambulances") or []], "goals": dict(lv["goals"]),
               "rules": self.rules, "result": self.result}
        return json.loads(json.dumps(obs))

    def decide(self, dec):
        out = []
        if not isinstance(dec, dict):
            return [rej("decision", "not_a_dict", "Решение: словарь {\"rules\": текст}.", "A decision is {\"rules\": text}.")]
        for k in dec:
            if k != "rules":
                out.append(rej(k, "unknown_field", "Решение здесь одно: правила города (rules).", "The only decision here is the rules of the city (rules)."))
        if "rules" not in dec:
            return out
        text = dec["rules"]
        if self.n > 0:
            return out + [rej("rules", "too_late", "Час пик уже идёт: правила пишут до начала.", "Rush hour is already running: rules are written before it starts.")]
        if not isinstance(text, str):
            return out + [rej("rules", "not_text", "Правила пишутся текстом.", "Rules are text.")]
        if len(text) > MAX_RULES:
            return out + [rej("rules", "too_long", "Правила длиннее %d знаков." % MAX_RULES, "The rules are longer than %d characters." % MAX_RULES)]
        _, _, problems = H["parse"](text, self.level)
        if problems:
            en = "; ".join(problems[:4])
            return out + [rej("rules", "handler_refused", "Обработчик языка traffic не принял правила: " + en, "The traffic handler refused the rules: " + en)]
        self.rules = text
        return out

    def step(self):
        if self.n > 0:
            return
        key = "_episode"
        LEVELS[key] = self.level
        try:
            out = H["simulate"](key, self.rules)
        finally:
            LEVELS.pop(key, None)
        self.result = out.get("result")
        self.journal.append({"step": 0, "level": self.level_key, "seed": self.seed, "rules": self.rules,
                             "problems": out["problems"], "result": self.result})
        self.n = 1

    def done(self):
        return self.n >= 1

    def score(self):
        r = self.result or {}
        parts = {k: r.get(k, 0) for k in ("delivered", "avgWait", "stuck", "ambulance", "ambulanceWorst", "avgTrip")}
        counts = {k: r.get(k, 0) for k in ("spawned", "maxQueue", "gateWait", "ambulances")}
        # the table of mayors orders by stars, then shorter average wait, then more cars home
        return {"score": r.get("stars", 0), "parts": parts, "counts": counts, "sha": r.get("sha", ""),
                "rank_key": [-r.get("stars", 0), r.get("avgWait", 0), -r.get("delivered", 0)]}
