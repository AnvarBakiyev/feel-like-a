"""Тесты эпизода машиниста: python3 test_sim.py"""
import json
import sim, drivers, poezdka

DRY = {"seed": 0, "weather": "dry", "adhesion_factor": 1.0, "temp": [], "depart_delay_s": 0, "signal": None}


def same_seed_same_run():
    a = sim.play(7, "de_krm", drivers.full); b = sim.play(7, "de_krm", drivers.full)
    assert json.dumps(a.journal) == json.dumps(b.journal) and a.score() == b.score()


def other_seed_other_world():
    ws = {json.dumps(sim.Game(s, "jp_tokaido").W, sort_keys=True) for s in range(1, 11)}
    assert len(ws) > 5


def world_same_for_both_drivers():
    a = sim.play(3, "ch_gotthard", drivers.full); b = sim.play(3, "ch_gotthard", drivers.careful)
    assert a.W == b.W


def observe_hides_hidden():
    g = sim.Game(4, "de_krm")
    o = json.dumps(g.observe())
    assert "adhesion_factor" not in o
    found = False
    for s in range(1, 30):
        g = sim.Game(s, "de_krm")
        if g.W["signal"]:
            assert g.observe()["signal"] is None
            found = True; break
    assert found


def rules():
    g = sim.Game(1, "de_krm", world=dict(DRY, depart_delay_s=60))
    r = g.decide({"lever": 1.0}); assert r and r[0]["code"] == "early", r
    assert g.decide({"lever": 2})[0]["code"] == "range"
    assert g.decide({"pusher": True})[0]["code"] == "none"
    g2 = sim.Game(1, "ch_gotthard", world=DRY)
    assert g2.decide({"pusher": True}) == []
    for _ in range(200):
        g2.step()
    g2.decide({"lever": 1.0})
    for _ in range(40):
        g2.step()
    assert g2.departed and g2.decide({"pusher": False})[0]["code"] == "late"
    g2.sand_left = 0
    assert g2.decide({"sand": True})[0]["code"] == "empty"


def timetable_reachable():
    for lid in sim.LINES:
        g = sim.Game(0, lid, world=DRY)
        while not g.done():
            d = drivers.full(g.observe(), g)
            if d:
                g.decide(d)
            g.step()
        s = g.score()
        assert s["parts"]["late"] == 0 and s["parts"]["protection"] == 0 and s["parts"]["unfinished"] == 0, (lid, s)
        assert all(abs(x["err_m"]) <= 2 for x in g.stops), (lid, g.stops)


def language():
    g = sim.Game(2, "ch_gotthard")
    ok, e, _, _ = poezdka.check("разгон до 80\nлететь 400", g); assert not ok and e[0]["line"] == 2
    ok, e, _, _ = poezdka.check("разгон до 120", sim.Game(1, "jp_tokaido")); assert not ok and "опоздание" in e[0]["ru"], e
    ok, e, _, _ = poezdka.check("разгон до 285", sim.Game(1, "jp_tokaido")); assert ok, e
    p, e = poezdka.parse("разгон до 280\nтише 200 с км 30 до км 40\nдержать 250 до км 100\nразгон до 160")
    assert poezdka.speed_profile(p, 0, 169) == [(0, 169, 280, 1), (30.0, 40.0, 200, 2)]
    assert [x["line"] for x in e] == [3, 4] and "тише" in e[0]["ru"]
    ok, e, _, _ = poezdka.check("разгон до 320", sim.Game(1, "de_krm")); assert not ok and "300" in e[0]["ru"]
    assert g.W["weather"] == "wet"
    ok, e, _, _ = poezdka.check("разгон до 80", g); assert not ok and "встанет" in e[0]["ru"], e
    ok, e, _, _ = poezdka.check("толкач да\nразгон до 80", g); assert ok, e
    assert poezdka.run("толкач да\nразгон до 80", 2, "ch_gotthard").score()["parts"]["unfinished"] == 0


def all_lines_run():
    for lid in sim.LINES:
        for s in range(1, 6):
            for d in (drivers.full, drivers.careful):
                sim.play(s, lid, d).score()


if __name__ == "__main__":
    for f in [same_seed_same_run, other_seed_other_world, world_same_for_both_drivers, observe_hides_hidden, rules, timetable_reachable, language, all_lines_run]:
        f(); print("ok", f.__name__)
