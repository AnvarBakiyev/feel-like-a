"""Do the browser (web/traffic_core.js, run with node) and the device's handler (traffic_core.py) run the same rush hour?
Random rules on every level, written well and badly: the refusals, and every number of the result, must match.
python3 conformance.py [N]"""
import json, os, random, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
rng = random.Random(2026)
NL = chr(10)
ns = {}
exec(open(os.path.join(HERE, "traffic_handler_v1.py"), encoding="utf-8").read(), ns)
LEVELS = ns["LEVELS"]


def random_rules(level):
    names = ns["cross_names"](level)
    lines = []
    for n in rng.sample(names, rng.randint(1, len(names))) + (["all"] if rng.random() < 0.1 else []):
        kind = rng.random()
        parts = []
        if kind < 0.35:
            parts = ["light"]
            if rng.random() < 0.6:
                parts += ["%s %d" % (rng.choice(["north-south", "ns", "север-юг"]), rng.randint(2, 42)), "%s %d" % (rng.choice(["east-west", "ew", "запад-восток"]), rng.randint(2, 42))]
            elif rng.random() < 0.7:
                parts += [rng.choice(["longest queue", "самая длинная очередь"]), "min %d" % rng.randint(2, 12), "max %d" % rng.randint(8, 41)]
            if rng.random() < 0.3:
                parts.append("offset %d" % rng.choice([0, 3, 6, 70]))
        elif kind < 0.6:
            parts = [rng.choice(["main north-south", "main ns", "главная север-юг", "main east-west", "главная запад-восток", "main up"])]
        elif kind < 0.8:
            parts = [rng.choice(["stop", "стоп"])]
        else:
            parts = [rng.choice(["north-south 12, east-west 8", "ns 1_0, ew 8", "blue 5", "box", "no box", "light, ns 9"])]
        if rng.random() < 0.4:
            parts.append(rng.choice(["box", "вафельная разметка", "no box"]))
        line = "%s: %s" % (n, ", ".join(parts))
        if rng.random() < 0.04:
            line = rng.choice(["Z: stop", "A light", "# just a note", "", "ambulance  first", "пропускать скорую", "please go"])
        lines.append(line)
    if rng.random() < 0.5:
        lines.append(rng.choice(["ambulance first", "пропускать скорую"]))
    return NL.join(lines)


def valid_plan(level):
    """A city plan that the handler accepts: lights within the budget, signs, boxes, sometimes ambulance first."""
    names = ns["cross_names"](level)
    lit = set(rng.sample(names, rng.randint(0, level["lights"])))
    lines = []
    for n in names:
        if n in lit:
            p = ["light"]
            r = rng.random()
            if r < 0.6:
                a = rng.randint(5, 30)
                p += ["north-south %d" % a, "east-west %d" % rng.randint(5, 66 - a - 4 if 66 - a - 4 >= 5 else 5)]
            else:
                p += ["longest queue", "min %d" % rng.randint(3, 8), "max %d" % rng.randint(10, 40)]
            if rng.random() < 0.4:
                p.append("offset %d" % rng.choice([3, 6, 9]))
        else:
            p = [rng.choice(["stop", "main north-south", "main east-west"])]
        if rng.random() < 0.45:
            p.append("box")
        lines.append("%s: %s" % (n, ", ".join(p)))
    if rng.random() < 0.5:
        lines.append("ambulance first")
    return NL.join(lines)


cases = []
for k in range(N):
    lvl = list(LEVELS)[k % len(LEVELS)]
    cases.append((lvl, valid_plan(LEVELS[lvl]) if k % 3 else random_rules(LEVELS[lvl])))
t0 = time.time()
py = []
for lvl, rules in cases:
    out = ns["simulate"](lvl, rules)
    py.append({"problems": out["problems"], "result": out.get("result")})
t_py = time.time() - t0
open(os.path.join(HERE, "_cases.json"), "w").write(json.dumps(cases))
js_src = "import { simulate } from './web/traffic_core.js'; import { readFileSync } from 'fs';" + NL + \
         "const cases = JSON.parse(readFileSync('_cases.json', 'utf8'));" + NL + \
         "process.stdout.write(JSON.stringify(cases.map(([l, r]) => { const o = simulate(l, r, { record: false }); return { problems: o.problems, result: o.result || null }; })));"
open(os.path.join(HERE, "_conf.mjs"), "w").write(js_src)
t0 = time.time()
js = json.loads(subprocess.run(["node", "_conf.mjs"], cwd=HERE, capture_output=True, text=True, check=True).stdout)
t_js = time.time() - t0
os.remove(os.path.join(HERE, "_cases.json")); os.remove(os.path.join(HERE, "_conf.mjs"))
mism = [i for i in range(N) if json.dumps(py[i], sort_keys=True) != json.dumps(js[i], sort_keys=True)]
res = {"cases": N, "levels": list(LEVELS), "mismatches": len(mism), "refused": sum(1 for p in py if p["problems"]),
       "ran": sum(1 for p in py if p["result"]), "stars": {s: sum(1 for p in py if p["result"] and p["result"]["stars"] == s) for s in range(4)},
       "python_seconds": round(t_py, 1), "node_seconds": round(t_js, 1), "date": time.strftime("%Y-%m-%d %H:%M"),
       "examples": [{"level": cases[i][0], "rules": cases[i][1], "py": py[i], "js": js[i]} for i in mism[:3]]}
json.dump(res, open(os.path.join(HERE, "conformance_result.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in res.items() if k != "examples"}, ensure_ascii=False))
for e in res["examples"]:
    print(json.dumps(e, ensure_ascii=False)[:600])
