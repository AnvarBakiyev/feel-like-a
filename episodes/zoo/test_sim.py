"""Тесты эпизода «Зоопарк» по договору ../EPISODE.md §2."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, policies

PLACES = ["park", "waterfront", "subway"]; TEAMS = ["small", "mid", "large"]; SCEN = ["heat", "spring", "flu"]


def dump(g):
    return json.dumps({"j": g.journal, "s": g.score()}, sort_keys=True, ensure_ascii=False)


def test_same_seed_same_month():
    a, _ = sim.play(7, "waterfront", "mid", "heat", policies.careful)
    b, _ = sim.play(7, "waterfront", "mid", "heat", policies.careful)
    assert dump(a) == dump(b)


def test_other_seed_other_month():
    a, _ = sim.play(7, "waterfront", "mid", "heat", policies.careful)
    b, _ = sim.play(8, "waterfront", "mid", "heat", policies.careful)
    assert dump(a) != dump(b)


def test_world_same_for_both_players():
    a, _ = sim.play(3, "subway", "small", "flu", policies.naive)
    b, _ = sim.play(3, "subway", "small", "flu", policies.careful)
    assert json.dumps(a.X, sort_keys=True) == json.dumps(b.X, sort_keys=True)


def test_observe_hides_hidden():
    g = sim.Game(5, "waterfront", "mid", "spring")
    while not g.done():
        o = json.dumps(g.observe())
        assert "hidden" not in o and "u_loss" not in o and "boost\"" not in o and "noise" not in o
        g.decide(policies.careful(g.observe())); g.step()


def test_rules():
    g = sim.Game(1, "waterfront", "mid", "heat")
    o = g.observe()
    sch = json.loads(json.dumps(o["schedule"]))
    sch["0"]["keepers"]["cats"] = [1, 1]
    sch["1"]["keepers"]["pool"] = [0, 2]
    sch["2"]["keepers"]["yard"] = [1, 0]
    sch["3"]["shows"] = 1  # в бассейне 3, а для шоу нужно 4
    rj, _ = g.check({"schedule": sch, "orders": {"hay": {"hay": 30}}, "thaw": {"fish": 9999}, "price": 100})
    codes = {r["code"] for r in rj}
    assert {"two_keepers", "water", "contact", "show", "stock", "bounds"} <= codes, codes
    assert all(r["ru"] and r["en"] for r in rj)
    # морозилка и коробки
    rj, _ = g.check({"orders": {"frozen": {"fish": 15}}})
    assert any(r["code"] in ("case", "day") for r in rj)


def test_forbidden_options():
    for seed in range(1, 40):
        g = sim.Game(seed, "waterfront", "mid", "heat")
        while not g.done():
            for c in g.observe()["cards"]:
                if (c["kind"], "none") in sim.FORBIDDEN or (c["kind"], "wait") in sim.FORBIDDEN:
                    bad = "none" if c["kind"] == "heatwave" else "wait"
                    rj, ok = g.check({"choices": {c["id"]: bad}})
                    assert rj and rj[0]["code"] == "law" and c["id"] not in ok["choices"]
                    return
            g.decide(policies.careful(g.observe())); g.step()
    raise AssertionError("не нашли карточку с запрещённым вариантом")


def test_rethaw_replaces():
    g = sim.Game(1, "waterfront", "mid", "heat")
    f0 = g.freezer["fish"] + g.thawed_next["fish"]
    g.decide({"thaw": {"fish": 30}}); g.decide({"thaw": {"fish": 20}})
    assert abs(g.freezer["fish"] + g.thawed_next["fish"] - f0) < 1e-9 and g.thawed_next["fish"] == 20


def test_all_27_run():
    for sc in SCEN:
        for p in PLACES:
            for t in TEAMS:
                for pol in (policies.naive, policies.careful):
                    g, _ = sim.play(1, p, t, sc, pol)
                    assert g.done() and isinstance(g.score()["score"], float)


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); n += 1; print("ok", k)
    print(n, "tests ok")
