"""Тесты симулятора: python3 test_sim.py"""
import hashlib, json, sys
import sim, policies

STREETS = ["quiet", "district", "corridor"]
MONEY = ["low", "mid", "high"]
SCEN = ["calm", "winter", "competitor"]


def digest(g, log):
    return hashlib.sha256(json.dumps({"j": g.journal, "s": g.score(), "l": log}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_same_seed_same_month():
    for pol in (policies.naive, policies.careful):
        a = digest(*sim.play(7, "district", "mid", "winter", pol))
        b = digest(*sim.play(7, "district", "mid", "winter", pol))
        assert a == b, "один и тот же месяц разошёлся: " + pol.__name__


def test_other_seed_other_month():
    a = digest(*sim.play(7, "district", "mid", "calm", policies.careful))
    b = digest(*sim.play(8, "district", "mid", "calm", policies.careful))
    assert a != b


def test_world_same_for_both_players():
    w1 = sim.Game(11, "corridor", "low", "competitor").W
    w2 = sim.Game(11, "corridor", "low", "competitor").W
    assert json.dumps(w1, sort_keys=True) == json.dumps(w2, sort_keys=True)


def test_observe_hides_demand():
    g = sim.Game(5, "district", "mid", "calm")
    text = json.dumps(g.observe(), ensure_ascii=False)
    for e in g.W["events"]:
        assert e["id"] not in text or e.get("show") is not None
    assert "hidden" not in text and "noise" not in text


def test_rules():
    g = sim.Game(5, "district", "mid", "calm")  # завтра чт
    r = g.decide({"orders": {"dairy": {"milk": 50}}})
    assert r and r[0]["code"] == "day", r
    r = g.decide({"discounts": [{"item": "latte", "pct": 50, "dayparts": [0]}]})
    assert not r, r
    r = g.decide({"prices": {"latte": 0.5}})
    assert r and r[0]["code"] == "below_cost"
    sch = {str(w): {"barista": [2, 2, 1], "lead": [0, 0, 0]} for w in range(7)}
    r = g.decide({"schedule": sch})
    assert any(x["code"] == "no_lead" for x in r)
    r = g.decide({"orders": {"bakery": {"croissant": 5}}})
    assert r and r[0]["code"] == "min"
    g.step()  # завтра пт, молочный возит
    r = g.decide({"orders": {"dairy": {"milk": 20}}})
    assert r and r[0]["code"] == "min", r


def test_reorder_replaces():
    g = sim.Game(5, "district", "mid", "calm")
    c0 = g.cash
    g.decide({"orders": {"bakery": {"croissant": 100}}})
    g.decide({"orders": {"bakery": {"croissant": 50}}})
    assert abs(g.cash - (c0 - 75.0)) < 1e-6, g.cash
    assert g.orders["bakery"]["items"]["croissant"] == 50


def test_all_27_run():
    for sc in ["calm", "winter", "competitor"]:
        for st in ["quiet", "district", "corridor"]:
            for mo in ["low", "mid", "high"]:
                g, _ = sim.play(2, st, mo, sc, policies.careful)
                assert g.t == 30 and isinstance(g.score()["score"], float)


def test_replay_matches_play():
    g, log = sim.play(3, "district", "mid", "competitor", policies.careful)
    r = sim.replay(3, {"street": "district", "money": "mid", "scenario": "competitor"}, [(x["day"], x["decision"]) for x in log])
    assert r["score"] == g.score()["score"], (r["score"], g.score()["score"])


def test_replay_extella_runs():
    import glob, json, os
    runs = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "extella", "runs", "*", "*.json"))
    for f in runs:
        d = json.load(open(f))
        if "combo" not in d or "evenings" not in d:
            continue   # в папке лежат и разборы прогонов, не только журналы месяцев
        c = d["combo"]
        r = sim.replay(c["seed"], c, [(e["day"], e["decision"]) for e in d["evenings"]])
        assert abs(r["score"] - d["score"]["score"]) < 0.005, (f, r["score"], d["score"]["score"])


def test_late_clean_is_paid():
    # уборку можно выбрать и в последний вечер, но $250 списываются в любом случае и один раз
    def run(when):
        g = sim.Game(1, "district", "mid", "calm"); e = [x for x in g.W["events"] if x["kind"] == "inspection"][0]
        while g.t < 30:
            d = policies.careful(g.observe()); ch = dict(d.get("choices") or {}); ch.pop(e["id"], None)
            if g.t in when:
                ch[e["id"]] = "clean"
            d["choices"] = ch; g.decide(d); g.step()
        return g.totals["event_costs"]
    assert run([8]) == run([9]) == run([8, 9]) == run([]) + 250


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print("ok  ", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
    sys.exit(1 if fails else 0)


def test_hire_costs_money():
    """Найм не бесплатен: каждый нанятый стоит hire_cost в вечер найма и идёт в зарплату."""
    a = sim.Game(1, "district", "mid", "calm"); b = sim.Game(1, "district", "mid", "calm")
    a.decide({}); b.decide({"hire": 2})
    cost = 2 * b.C["staff"]["hire_cost"]
    assert abs((a.cash - b.cash) - cost) < 1e-6
    assert abs((b.totals["wages"] - a.totals["wages"]) - cost) < 1e-6
