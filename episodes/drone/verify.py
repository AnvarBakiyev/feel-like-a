"""Recomputes every published score of the drone courier episode from recorded decisions. No keys, no network.

python3 verify.py          # everything below, about 5-10 minutes
python3 verify.py --quick  # only replays of recorded decision logs (about a minute)
python3 verify.py --full   # also re-runs the plan check of every model call at stages 1-3 (about 10 more minutes)

What is checked:
1. Every recorded shift (Extella stages 1-4, Qwen 3.5 9B without Extella, Claude Opus 5 without Extella) replays
   from its decision log to the recorded score and counts (replay.py, strict: forged logs raise).
2. The prompt each model saw equals the briefing rebuilt now from the world of that seed.
3. Extella: the plan the model wrote, run through the exact expert version recorded in the run (by sha), gives the
   same decisions; at stage 4 (the page) the plan check of every model call gives the same verdict, errors and advice.
4. Without Extella: the rules each model wrote (raw answer), executed literally by noext.execute, give the same decisions.
5. Programs without AI (careful, simple, the handler with an empty plan) are re-run here.
6. web/data.json (what the page shows) holds the same decisions and scores.
7. The averages table in README.md is recomputed and compared number by number.
"""
import glob, hashlib, importlib.util, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "extella")
sys.path.insert(0, HERE); sys.path.insert(0, EX)
import sim, polet, drivers  # noqa: E402
from replay import replay  # noqa: E402
import player, noext  # noqa: E402  (no network at import; only the run commands call models)

QUICK = "--quick" in sys.argv
FULL = "--full" in sys.argv
STAGES = [("extella1", "runs"), ("extella2", "runs2"), ("extella3", "runs3"), ("extella4", "runs4b")]
CITIES = sim.CITIES

# README.md, table "Results": average score per city, delivered of 414, forced landings off a pad, lost drones (30 shifts)
EXPECTED = {
    "big":      ([1138, 779, 952], 242, 4, 0),
    "extella4": ([1084, 803, 975], 242, 0, 0),
    "extella3": ([1014, 674, 983], 235, 0, 0),
    "extella2": ([1014, 599, 983], 235, 3, 0),
    "careful":  ([918, 440, 600], 221, 15, 0),
    "extella1": ([665, 577, 708], 189, 5, 0),
    "handler":  ([559, 447, 567], 154, 7, 0),
    "simple":   ([246, 399, 853], 222, 48, 0),
    "small":    ([53, -38, 640], 199, 66, 0),
}
NAMES = {"big": "Claude Opus 5 without Extella", "extella4": "Qwen 3.5 9B + Extella, stage 4", "extella3": "Qwen 3.5 9B + Extella, stage 3",
         "extella2": "Qwen 3.5 9B + Extella, stage 2", "extella1": "Qwen 3.5 9B + Extella, stage 1", "careful": "careful program (not AI)",
         "handler": "handler, empty plan (not AI)", "simple": "simple program (not AI)", "small": "Qwen 3.5 9B without Extella"}

fails = []
T0 = time.time()


def ok(cond, what):
    if not cond:
        fails.append(what)
        print("   FAIL", what, flush=True)


def norm(x):
    return json.loads(json.dumps(x))


def sha_of(path):
    return hashlib.sha256(open(path, encoding="utf-8").read().rstrip(chr(10)).encode()).hexdigest()[:12]


def load_expert(path):
    spec = importlib.util.spec_from_file_location("expert_" + sha_of(path), path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


experts = {sha_of(os.path.join(EX, "drone_plan.py")): os.path.join(EX, "drone_plan.py")}
for p in glob.glob(os.path.join(EX, "experts", "drone_plan_*.py")):
    s = sha_of(p)
    ok(os.path.basename(p) == "drone_plan_%s.py" % s, "expert file name matches its sha: " + p)
    experts[s] = p
loaded = {}


def expert(sha):
    if sha not in loaded:
        loaded[sha] = load_expert(experts[sha])
    return loaded[sha]


rows = {}   # who -> {(city, seed): (score, delivered, orders, forced, lost)}
decs = {}   # who -> {(city, seed): decisions}


def keep(who, city, seed, sc, d=None):
    c = sc["counts"]
    rows.setdefault(who, {})[(city, seed)] = (sc["score"], c["delivered"], c["orders"], c["forced"], c["lost"])
    if d is not None:
        decs.setdefault(who, {})[(city, seed)] = d


def briefing(city, seed):
    return player.briefing(sim.Game(seed, city))


print("1-3. Extella runs: replay, prompt, plan through the recorded expert", flush=True)
n_calls = 0
for who, folder in STAGES:
    t = time.time()
    for city in CITIES:
        for seed in range(1, 11):
            f = os.path.join(EX, folder, "%s_s%d.json" % (city, seed)); tag = "%s %s s%d" % (folder, city, seed)
            J = json.load(open(f, encoding="utf-8"))
            r = replay(seed, {"city": city}, J["decisions"])
            ok(r["score"] == J["score"]["score"] and r["counts"] == J["score"]["counts"], tag + ": replay gives the recorded score")
            keep(who, city, seed, r, J["decisions"])
            if QUICK:
                continue
            ok(J["briefing"] == briefing(city, seed), tag + ": the briefing the model saw is rebuilt from the world")
            for c in J["calls"]:
                ok(c["plan"] == player.clean(c["raw"]), tag + ": plan is the model's raw answer")
            ok(J["plan"] in [c["plan"] for c in J["calls"]], tag + ": the flown plan is one the model wrote")
            shas = {m["sha"] for m in J["expert_calls"]}
            ok(len(shas) == 1 and shas <= set(experts), tag + ": expert version %s is published" % shas)
            E = expert(sorted(shas)[0])
            res = E.drone_plan(J["plan"], seed, city, "run")
            ok(norm(res["decisions"]) == J["decisions"] and res["score"]["score"] == J["score"]["score"],
               tag + ": the plan through the expert gives the recorded decisions")
            if who == "extella4" or FULL:
                for i, c in enumerate(J["calls"]):
                    chk = E.drone_plan(c["plan"], seed, city, "check"); n_calls += 1
                    ok(chk["ok"] == c["ok"] and norm(chk["errors"]) == c["errors"] and norm(chk["forecast"]) == c["forecast"],
                       tag + ": call %d, the plan check gives the recorded verdict and advice" % (i + 1))
    print("   %-8s 30 shifts, %.0f s" % (folder, time.time() - t), flush=True)
if n_calls:
    print("   plan checks re-run: %d model calls" % n_calls)

print("1, 2, 4. Without Extella: replay, prompt, rules executed literally", flush=True)
t = time.time()
B = json.load(open(os.path.join(EX, "noext", "briefings.json"), encoding="utf-8"))
P_big = json.load(open(os.path.join(EX, "noext", "big_plans.json"), encoding="utf-8"))
if not QUICK and B["system"] != noext.SYSTEM:
    # recorded as given: the large model's system prompt (briefings.json, scored 13.11 21:04) lacks the example line
    # "for another city, do not copy the numbers" that noext.py gained before the Qwen run (finished 21:16 to 21:59)
    print("   note: Claude Opus 5 got the system prompt stored in noext/briefings.json, an earlier wording of noext.SYSTEM")
for who in ("big", "small"):
    for city in CITIES:
        for seed in range(1, 11):
            key = "%s_s%d" % (city, seed); tag = "%s %s" % (who, key)
            J = json.load(open(os.path.join(EX, "noext", "%s_%s.json" % (who, key)), encoding="utf-8"))
            r = replay(seed, {"city": city}, J["decisions"])
            ok(r["score"] == J["score"]["score"] and r["counts"] == J["score"]["counts"], tag + ": replay gives the recorded score")
            keep(who, city, seed, r, J["decisions"])
            if QUICK:
                continue
            b = briefing(city, seed).replace("Напиши замысел.", "Напиши правила (JSON).")
            if who == "big":
                ok(B["shifts"][key] == b, tag + ": briefing rebuilt from the world")
                ok(J["plan"] == P_big[key], tag + ": rules are the model's answer in big_plans.json")
            else:
                ok(J["briefing"] == b, tag + ": briefing rebuilt from the world")
                try:
                    want = json.loads(J["calls"][-1]["raw"])
                except Exception:
                    want = {}
                ok(J["plan"] == want, tag + ": rules are the model's raw answer")
            g, d, _ = noext.execute(city, seed, J["plan"])
            ok(norm(d) == J["decisions"] and g.score()["score"] == J["score"]["score"], tag + ": rules executed literally give the recorded decisions")
print("   60 shifts, %.0f s" % (time.time() - t), flush=True)

print("5. Programs without AI, re-run here", flush=True)
t = time.time()
for who, fn in (("careful", drivers.careful), ("simple", drivers.simple)):
    for city in CITIES:
        for seed in range(1, 11):
            g = sim.Game(seed, city); d = []; n = 0
            while not g.done():
                x = fn(g.observe(), g)
                if x is not None and not g.decide(x):
                    d.append([n, x])
                g.step(); n += 1
            keep(who, city, seed, g.score(), norm(d))
for city in CITIES:
    for seed in range(1, 11):
        g, disp, d = polet.run("", seed, city)
        keep("handler", city, seed, g.score())
S10 = json.load(open(os.path.join(HERE, "run_seeds_10.json"), encoding="utf-8"))
P10 = json.load(open(os.path.join(HERE, "run_polet_10.json"), encoding="utf-8"))
for city in CITIES:
    for who in ("careful", "simple"):
        for row in S10[city + ":" + who]:
            ok(rows[who][(city, row[0])][0] == row[2], "%s %s s%d: same score as run_seeds_10.json" % (who, city, row[0]))
    for row in P10["rows"][city]:
        ok(rows["handler"][(city, row[0])][0] == row[2], "handler %s s%d: same score as run_polet_10.json" % (city, row[0]))
print("   90 shifts, %.0f s" % (time.time() - t), flush=True)

print("6. web/data.json: what the page shows", flush=True)
D = json.load(open(os.path.join(HERE, "web", "data.json"), encoding="utf-8"))
PAGE = {"extella": "extella4", "big": "big", "small": "small", "careful": "careful", "simple": "simple"}
for city in CITIES:
    for seed in range(1, 11):
        key = "%s_%d" % (city, seed); R = D["rivals"][key]
        for pw, who in PAGE.items():
            ok(R[pw]["score"] == rows[who][(city, seed)][0] and R[pw]["decisions"] == decs[who][(city, seed)], "data.json %s %s" % (key, pw))
        for st in (1, 2, 3):
            ok(D["stage%d" % st][key] == rows["extella%d" % st][(city, seed)][0], "data.json %s stage %d" % (key, st))

print("7. Averages (README.md)", flush=True)
print("   %-34s %8s %8s %9s  %-10s %6s %4s" % ("", "Almaty", "Dubai", "Rotterdam", "delivered", "forced", "lost"))
for who, (avg, deliv, forced, lost) in EXPECTED.items():
    got = [sum(rows[who][(c, s)][0] for s in range(1, 11)) / 10.0 for c in CITIES]
    dv = sum(v[1] for v in rows[who].values()); orders = sum(v[2] for v in rows[who].values())
    fo = sum(v[3] for v in rows[who].values()); lo = sum(v[4] for v in rows[who].values())
    print("   %-34s %8.1f %8.1f %9.1f  %3d of %3d %6d %4d" % (NAMES[who], got[0], got[1], got[2], dv, orders, fo, lo))
    ok([int(round(x)) for x in got] == avg and dv == deliv and fo == forced and lo == lost, "README table row: " + NAMES[who])
d1 = [sum(rows["extella1"][(c, s)][0] - rows["small"][(c, s)][0] for s in range(1, 11)) / 10.0 for c in CITIES]
print("   same Qwen 3.5 9B with Extella (stage 1) minus without: %s" % ", ".join("%+.0f" % x for x in d1))
gap = [sum(rows["big"][(c, s)][0] for s in range(1, 11)) / 10.0 - sum(rows[w][(c, s)][0] for s in range(1, 11)) / 10.0
       for w in ("extella1", "extella2", "extella3", "extella4") for c in CITIES]
print("   gap to Claude Opus 5, sum of three city averages, stages 1-4: %s" % " -> ".join("%.0f" % sum(gap[i:i + 3]) for i in (0, 3, 6, 9)))

print()
print("%d problems" % len(fails) if fails else "all published scores recomputed and matched (%.0f s)" % (time.time() - T0))
sys.exit(1 if fails else 0)
