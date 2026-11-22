"""Recomputes every published number of the zoo episode from the recorded decisions.

python3 verify.py                  no keys, no network: everything below except the two expert checks in 1
python3 verify.py --extella        also the expert checks in 1, on Extella (two calls per evening, about an hour;
                                   answers are cached, a second run is fast)
python3 verify.py --extella-quick  the expert checks on the first evening of every month

The Extella experts are not in this repository: they live in the agent "Extella Zoo Month" in the Extella market
(extella/experts.lock.json). For --extella install that agent as a new agent and set EXTELLA_TOKEN_FILE and
EXTELLA_AGENT (see extella/expert_json.py).

What is checked, for all 27 months (world ny2, seed 1: 3 scenarios x 3 places x 3 team sizes):
1. Qwen 3.5 9B with Extella (extella/runs/ny2-page/): every evening prompt is rebuilt from the game and the expert
   and equals the recorded one (--extella); the model's last answer gives the recorded plan; the expert zoo_game_plan of the
   agent in the market turns that plan into exactly the recorded decision (--extella); the month replays to the recorded score;
   the expert version the runs record is the one in the market.
2. Qwen 3.5 9B without Extella (bench/runs/ny2small_*): prompts rebuilt and equal; the last raw answer gives the
   recorded decision; the month replays to the recorded score.
3. Claude Opus 5.5 without Extella (bench/runs/ny2opus_*, played in Claude Code through bench/closed.py): the system
   text equals the recorded one; the month replays to the recorded score.
4. The Python program (policies.careful) is played again.
5. The table on the page (averages, medians, places) and web/data.json agree with the recomputed scores.
"""
import json, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["ZOO_WORLD"] = "ny2"
os.environ["ZOO_CARDS"] = "expert"; os.environ["ZOO_SHOWS"] = "expert"; os.environ["ZOO_PRICE"] = "expert"
for p in (HERE, os.path.join(HERE, "extella"), os.path.join(HERE, "bench")):
    sys.path.insert(0, p)
import sim, policies  # noqa: E402
import player as P  # noqa: E402
from expert_json import load, sha as expert_sha, available, how  # noqa: E402
zoo_game_plan = load("zoo_game_plan")
EXT = "--extella" in sys.argv or "--extella-quick" in sys.argv
QUICK = "--extella-quick" in sys.argv
if EXT and not available():
    sys.exit("--extella " + how())
from public_world import public_world  # noqa: E402
import common as C  # noqa: E402

WORLD = "ny2"
SEED = 1
COMBOS = [(sc, pl, tm) for sc in ("heat", "spring", "flu") for pl in ("park", "waterfront", "subway") for tm in ("small", "mid", "large")]
NAMES = {"extella": "Qwen 3.5 9B with Extella", "careful": "Python program (no AI)", "opus": "Claude Opus 5.5 without Extella",
         "small": "Qwen 3.5 9B without Extella"}
MODELS = {"extella": "openrouter:qwen/qwen3.5-9b@DeepInfra,Parasail,PrimeIntellect", "small": "openrouter:qwen/qwen3.5-9b@DeepInfra,Parasail,PrimeIntellect",
          "opus": "claude-code:claude-opus-5.5"}
# as published on extella.dev/zoo and in PREDSKAZANIYA.md, whole dollars
PUBLISHED = {"mean": {"extella": 311671, "careful": 263043, "opus": 232054, "small": -45782},
             "median": {"extella": 293612, "careful": 260681, "opus": 228270, "small": 30760},
             "places": {"extella": [27, 0, 0, 0], "careful": [0, 19, 8, 0], "opus": [0, 8, 19, 0], "small": [0, 0, 0, 27]},
             "extella_minus_opus": 79617}
FAIL = []


def need(cond, msg):
    if not cond:
        FAIL.append(msg)
        print("  MISMATCH:", msg)


def same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def load(path):
    return json.load(open(os.path.join(HERE, path), encoding="utf-8"))


def settings(sc, pl, tm):
    return {"scenario": sc, "place": pl, "team": tm}


def check_extella(sc, pl, tm, stats):
    key = "%s_%s_%s" % (sc, pl, tm)
    J = load("extella/runs/ny2-page/%s_s%d_cxs.json" % (key, SEED))
    need(J["world"] == WORLD and J["model"] == MODELS["extella"], key + ": world or model")
    need(J["cards_by"] == J["shows_by"] == J["price_by"] == "expert", key + ": run mode")
    W = public_world(WORLD)
    g = sim.Game(SEED, pl, tm, sc, WORLD)
    plan = {"stock": "normal", "staff": "normal", "shows": "expert", "price": "expert", "free_wed": "expert", "cards": "expert"}
    for i, e in enumerate(J["evenings"]):
        obs = g.observe()
        need(e["day"] == g.t, key + ": evening order")
        ask = EXT and not (QUICK and i > 0)
        if ask:
            pre = json.loads(json.dumps(zoo_game_plan(obs, {k: v for k, v in plan.items() if k != "choices"}, W)))
            need(P.evening_text(g, obs, pre, plan) == e["prompt"], "%s day %d: prompt" % (key, g.t))
            stats["expert_checked"] += 1
        if not e.get("fallback"):
            need(same(P.clean_plan(json.loads(e["calls"][-1]["raw"]), plan), e["plan"]), "%s day %d: answer -> plan" % (key, g.t))
        else:
            stats["fallback"] += 1
        if ask:
            res = json.loads(json.dumps(zoo_game_plan(obs, e["plan"], W)))
            need(same(res["decision"], e["decision"]), "%s day %d: expert decision" % (key, g.t))
        stats["model_calls"] += len(e["calls"]); stats["evenings"] += 1
        g.decide(e["decision"]); g.step()
        plan = e["plan"]
    need(J["expert"]["sha"] == expert_sha("zoo_game_plan"), key + ": expert sha")
    return J, g


def check_noext(tag, sc, pl, tm, stats):
    key = "%s_%s_%s" % (sc, pl, tm)
    J = load("bench/runs/%s_%s_s%d.json" % (tag, key, SEED))
    who = "opus" if tag == "ny2opus" else "small"
    need(J["world"] == WORLD and J["model"] == MODELS[who], key + ": world or model")
    need(J["system"] == C.SYSTEM, key + ": system text")
    g = sim.Game(SEED, pl, tm, sc, WORLD)
    ev = {e["day"]: e for e in J["evenings"]}
    while not g.done():
        obs = g.observe(); e = ev.get(g.t)
        stats["evenings"] += 1
        if e is not None and "prompt" in e:
            need(e["prompt"] == C.evening_text(g, obs), "%s %s day %d: prompt" % (tag, key, g.t))
            stats["model_calls"] += len(e["calls"])
        if e is not None and e.get("decision") is not None:
            if "calls" in e:
                need(same(C.to_decision(json.loads(e["calls"][-1]["raw"]), obs), e["decision"]), "%s %s day %d: raw -> decision" % (tag, key, g.t))
            g.decide(e["decision"])
        else:
            stats["no_decision"] += 1
        g.step()
    return J, g


def main():
    need(sum([0.4, 0.25, 0.05, 0.2, 0.1]) == 1.0, "Python 3.12 or newer is needed (compensated sum)")
    data = load("web/data.json")
    S = {k: {} for k in NAMES}
    ST = {k: {"evenings": 0, "model_calls": 0, "fallback": 0, "no_decision": 0, "expert_checked": 0} for k in ("extella", "small", "opus")}
    PARTS = {k: [] for k in NAMES}
    for sc, pl, tm in COMBOS:
        key = "%s_%s_%s" % (sc, pl, tm)
        J, g = check_extella(sc, pl, tm, ST["extella"])
        rows = [("extella", J, g)]
        for tag, who in (("ny2small", "small"), ("ny2opus", "opus")):
            Jn, gn = check_noext(tag, sc, pl, tm, ST[who])
            rows.append((who, Jn, gn))
        for who, Jr, gr in rows:
            r = sim.replay(SEED, settings(sc, pl, tm), sim.decisions_of(Jr["journal"]), WORLD)
            need(abs(r["score"] - gr.score()["score"]) < 1e-6, key + " " + who + ": journal and evenings disagree")
            need(abs(r["score"] - Jr["score"]["score"]) < 0.005, "%s %s: recorded %.2f, recomputed %.2f" % (key, who, Jr["score"]["score"], r["score"]))
            S[who][key] = r["score"]; PARTS[who].append(r["parts"])
        gc = sim.Game(SEED, pl, tm, sc, WORLD)
        while not gc.done():
            gc.decide(policies.careful(gc.observe())); gc.step()
        S["careful"][key] = gc.score()["score"]; PARTS["careful"].append(gc.score()["parts"])
        # the page shows these numbers
        need(abs(data["ghosts"][key]["score"] - S["extella"][key]) < 0.005, key + ": data.json Extella")
        need(abs(data["careful"][key]["score"] - S["careful"][key]) < 0.005, key + ": data.json Python program")
        for who in ("small", "opus"):
            need(abs(data["rivals"][who][key]["score"] - S[who][key]) < 0.005, key + ": data.json " + who)
    print("27 months x 4 players recomputed, world %s, seed %d" % (WORLD, SEED))
    print()
    print("%-34s %12s %12s %8s  %s" % ("player", "mean", "median", "first", "places 1/2/3/4"))
    keys = [k for k in S["extella"]]
    places = {w: [0, 0, 0, 0] for w in NAMES}
    for k in keys:
        order = sorted(NAMES, key=lambda w: -S[w][k])
        for i, w in enumerate(order):
            places[w][i] += 1
    for w in ("extella", "careful", "opus", "small"):
        v = list(S[w].values()); mean = sum(v) / len(v); med = statistics.median(v)
        print("%-34s %12s %12s %8d  %s" % (NAMES[w], "{:,.0f}".format(mean), "{:,.0f}".format(med), places[w][0], " / ".join(map(str, places[w]))))
        need(round(mean) == PUBLISHED["mean"][w], "%s mean %.2f, published %d" % (w, mean, PUBLISHED["mean"][w]))
        need(round(med) == PUBLISHED["median"][w], "%s median %.2f, published %d" % (w, med, PUBLISHED["median"][w]))
        need(places[w] == PUBLISHED["places"][w], "%s places %s, published %s" % (w, places[w], PUBLISHED["places"][w]))
    gap = [S["extella"][k] - S["opus"][k] for k in keys]
    print()
    print("Extella above Claude Opus 5.5 in %d of 27 months, by $%s a month on average" % (sum(x > 0 for x in gap), "{:,.0f}".format(sum(gap) / 27)))
    need(sum(x > 0 for x in gap) == 27 and round(sum(gap) / 27) == PUBLISHED["extella_minus_opus"], "Extella minus Opus")
    print()
    print("mean per month        %12s %12s %12s %12s" % ("Extella", "Python", "Opus 5.5", "Qwen alone"))
    for part, label in (("revenue", "revenue"), ("section_violations", "care penalties"), ("inspection", "inspection"), ("deaths", "animal deaths")):
        print("%-21s %s" % (label, " ".join("%12s" % "{:,.0f}".format(sum(p[part] for p in PARTS[w]) / 27) for w in ("extella", "careful", "opus", "small"))))
    print()
    for w in ("extella", "small", "opus"):
        s = ST[w]
        if w == "opus":
            print("%s: %d evenings, every evening decided" % (NAMES[w], s["evenings"]))
        elif w == "small":
            print("%s: %d evenings, %d model calls, %d evenings without an accepted decision" % (NAMES[w], s["evenings"], s["model_calls"], s["no_decision"]))
        else:
            print("%s: %d evenings, %d model calls, %d evenings fell back to the previous plan" % (NAMES[w], s["evenings"], s["model_calls"], s["fallback"]))
            print("  expert on Extella checked on %d evenings%s" % (s["expert_checked"], "" if EXT else " (run with --extella)"))
    print()
    if FAIL:
        print("FAILED: %d mismatches" % len(FAIL))
        sys.exit(1)
    print("all published numbers reproduced")


if __name__ == "__main__":
    main()
