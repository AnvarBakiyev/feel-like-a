"""Recomputes every published number of this episode from recorded decisions.

python3 verify.py                  no keys, no network: checks 1, 2, 4, 5 and the expert version against the runs
python3 verify.py --extella        also check 3 and the agent's whole-month expert, on Extella (about 30 minutes;
                                   answers are cached, a second run is fast)
python3 verify.py --extella-quick  check 3 on the first evening of every month, plus the whole-month expert

The Extella experts are not in this repository: they live in the agent "Extella Cafe Month" in the Extella market
(extella/experts.lock.json). For --extella install that agent as a new agent and set EXTELLA_TOKEN_FILE and
EXTELLA_AGENT (see extella/expert_json.py).

What it checks:
1. every recorded month (extella/runs/g14, m_qwen, m_opus) replays to its recorded score and day-by-day scores;
2. web/data.json (what the page shows) holds exactly those numbers, and every rival on the page has a recorded month;
3. Qwen 3.5 9B with Extella (--extella): each evening, the expert cafe_game_plan of the agent in the Extella market turns
   the recorded intent into exactly the recorded decision (so the decision came from that expert, not from an edit);
4. Qwen 3.5 9B alone: each evening's recorded prompt is the text the player builds from the game, and the decision
   is the recorded raw answer passed through player_bare.to_decision (or nothing, when no answer passed);
5. the simple programs on the page (careful, plenty, thrifty, bare) are recomputed from policies.py.
Then it prints the table the README quotes.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(1, os.path.join(HERE, "extella"))
import sim, policies  # noqa: E402
from replay import daily  # noqa: E402
from expert_json import load, sha as expert_sha, available, how  # noqa: E402
cafe_game_plan = load("cafe_game_plan")
EXT = "--extella" in sys.argv or "--extella-quick" in sys.argv
QUICK = "--extella-quick" in sys.argv
if EXT and not available():
    sys.exit("--extella " + how())
from public_city import public_city  # noqa: E402
import player_bare  # noqa: E402

RUNS = {"g14": ("ghosts", None), "m_qwen": ("models", "qwen"), "m_opus": ("models", "opus")}
NAMES = {"g14": "Qwen 3.5 9B with Extella", "m_qwen": "Qwen 3.5 9B alone", "m_opus": "Claude Opus 5 alone"}
EPS = 0.005
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg); print("FAIL", msg)


def canon(x):
    return json.loads(json.dumps(x))


DATA = json.load(open(os.path.join(HERE, "web", "data.json"), encoding="utf-8"))
scores = {}  # run -> {world: score}
for run, (sect, sub) in RUNS.items():
    folder = os.path.join(HERE, "extella", "runs", run)
    scores[run] = {}
    expert_same = expert_all = prompt_same = dec_same = evenings = 0
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith("_s1.json"):
            continue
        world = fn[:-len("_s1.json")]
        d = json.load(open(os.path.join(folder, fn), encoding="utf-8"))
        c = d["combo"]; s = {k: c[k] for k in ("street", "money", "scenario")}
        log = [[e["day"], e["decision"]] for e in d["evenings"]]
        days, g = daily(c["seed"], s, log)
        sc = g.score()
        check(abs(sc["score"] - d["score"]["score"]) < EPS, "%s/%s: replay %.2f, recorded %.2f" % (run, world, sc["score"], d["score"]["score"]))
        check(all(abs(a - b["score"]) < EPS for a, b in zip(days, d["daily"])) and len(days) == len(d["daily"]) == 30, "%s/%s: daily scores differ" % (run, world))
        page = DATA[sect].get(world) if sub is None else (DATA[sect].get(world) or {}).get(sub)
        check(page is not None, "%s/%s: not on the page" % (run, world))
        if page:
            check(abs(page["score"] - sc["score"]) < EPS, "%s/%s: page shows %.2f, replay %.2f" % (run, world, page["score"], sc["score"]))
            check(all(abs(a - b) < EPS for a, b in zip(page["daily"], days)), "%s/%s: page daily differs" % (run, world))
            check(all(abs(page["parts"][k] - v) < EPS for k, v in sc["parts"].items()), "%s/%s: page parts differ" % (run, world))
        scores[run][world] = sc["score"]
        # where each evening's decision came from
        g = sim.Game(c["seed"], s["street"], s["money"], s["scenario"])
        city = public_city(s["street"]) if run == "g14" else None
        for e in d["evenings"]:
            obs = g.observe(); evenings += 1
            if run == "g14" and EXT and not (QUICK and expert_all >= len(scores[run])):
                out = canon(cafe_game_plan(canon(obs), e["plan"], city))
                expert_all += 1; expert_same += out["decision"] == e["decision"]
            if run == "m_qwen":
                prompt_same += e["prompt"] == player_bare.evening_text(g, obs)
                ok = [cl for cl in e["calls"] if "plan_errors" not in cl and "rejections" not in cl]
                want = player_bare.to_decision(json.loads(ok[-1]["raw"]), obs) if ok and not e.get("fallback") else {}
                dec_same += canon(want) == e["decision"]
            g.decide(e["decision"]); g.step()
    n = len(scores[run])
    print("%-26s %2d months replayed" % (NAMES[run], n), end="")
    if run == "g14" and EXT:
        print(", expert on Extella gave the recorded decision on %d of %d evenings" % (expert_same, expert_all), end="")
        check(expert_same == expert_all, "g14: expert decisions differ")
    elif run == "g14":
        print(", expert check skipped (run with --extella)", end="")
    if run == "m_qwen":
        print(", prompt rebuilt %d/%d, decision from raw answer %d/%d" % (prompt_same, evenings, dec_same, evenings), end="")
        check(prompt_same == evenings and dec_same == evenings, "m_qwen: prompts or decisions differ")
    print()

# every rival on the page has a recorded month
for world, m in DATA["models"].items():
    for who in m:
        run = {"qwen": "m_qwen", "opus": "m_opus"}.get(who)
        check(run is not None and world in scores[run], "page shows %s in %s without a recorded month" % (who, world))
check(set(DATA["ghosts"]) == set(scores["g14"]), "page Extella worlds differ from recorded ones")

# simple programs
prog = {}
for world in sorted(DATA["careful"]):
    sc_, st, mo = world.split("_")
    for name, fn in (("careful", policies.careful), ("plenty", policies.plenty), ("thrifty", policies.thrifty), ("bare", policies.bare)):
        g = sim.Game(DATA["seed"], st, mo, sc_); ds = []
        while not g.done():
            g.decide(fn(g.observe())); g.step(); ds.append(g.score()["score"])
        page = DATA["careful"][world] if name == "careful" else DATA["rivals"][world][name]
        check(abs(page["score"] - ds[-1]) < EPS, "%s/%s: page %.2f, recomputed %.2f" % (name, world, page["score"], ds[-1]))
        if page.get("daily"):
            check(all(abs(a - b) < EPS for a, b in zip(page["daily"], ds)), "%s/%s: daily differs" % (name, world))
        prog.setdefault(name, {})[world] = ds[-1]
print("simple programs: %d worlds x 4 recomputed" % len(prog["careful"]))

# the expert version in the market is the one the runs record
check(expert_sha("cafe_game_plan") == "4a9db5d491b0", "cafe_game_plan: sha %s, runs record 4a9db5d491b0" % expert_sha("cafe_game_plan"))
# the agent's whole-month expert cafe_month (on Extella) gives the recorded score from the recorded decisions
cafe_month = load("cafe_month")
nm = 0
for fn in sorted(os.listdir(os.path.join(HERE, "extella", "runs", "g14"))) if EXT else []:
    if fn.endswith("_s1.json"):
        d = json.load(open(os.path.join(HERE, "extella", "runs", "g14", fn), encoding="utf-8"))
        c = d["combo"]
        got = cafe_month("check", c["street"], c["money"], c["scenario"], c["seed"], [[e["day"], e["decision"]] for e in d["evenings"]])["score"]["score"]
        check(abs(got - d["score"]["score"]) < EPS, "cafe_month/%s: %.2f, recorded %.2f" % (fn, got, d["score"]["score"])); nm += 1
print("agent expert cafe_month on Extella: %d months checked to the recorded score" % nm if EXT else "agent expert cafe_month: skipped (run with --extella)")


def money(x):
    return ("-$" if x < 0 else "$") + format(abs(round(x)), ",")


ext, qw, op, ca = scores["g14"], scores["m_qwen"], scores["m_opus"], prog["careful"]
W = sorted(ext)
avg = lambda xs: sum(xs) / len(xs)
print()
print("All 27 worlds (seed 1): average score")
print("  Qwen 3.5 9B with Extella  %s" % money(avg([ext[w] for w in W])))
print("  Qwen 3.5 9B alone         %s" % money(avg([qw[w] for w in W])))
for name in ("careful", "plenty", "thrifty", "bare"):
    print("  program %-17s %s" % (name, money(avg([prog[name][w] for w in W]))))
print("  Extella ahead of Qwen alone in %d of 27, of careful in %d of 27" % (sum(ext[w] > qw[w] for w in W), sum(ext[w] > ca[w] for w in W)))
O = sorted(op)
print()
print("The %d worlds Claude Opus 5 played:" % len(O))
print("  %-26s %10s %10s %10s %10s" % ("world", "Extella", "Opus 5", "Qwen alone", "careful"))
for w in O:
    print("  %-26s %10s %10s %10s %10s" % (w, money(ext[w]), money(op[w]), money(qw[w]), money(ca[w])))
print("  %-26s %10s %10s %10s %10s" % ("average", money(avg([ext[w] for w in O])), money(avg([op[w] for w in O])), money(avg([qw[w] for w in O])), money(avg([ca[w] for w in O]))))
print("  Extella ahead of Claude Opus 5 in %d of %d" % (sum(ext[w] > op[w] for w in O), len(O)))
print()
if fails:
    print("FAILED: %d checks" % len(fails)); sys.exit(1)
print("all published numbers recomputed")
