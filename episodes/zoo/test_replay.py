"""replay: журнал решений даёт тот же счёт, что и живая игра (LEADERBOARD.md)."""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sim import play, replay, decisions_of  # noqa: E402
import policies  # noqa: E402

COMBOS = [(p, t, sc) for sc in ("heat", "spring", "flu") for p in ("park", "waterfront", "subway") for t in ("small", "mid", "large")]


def test_policies_all_combos():
    for name in ("naive", "careful"):
        for p, t, sc in COMBOS:
            g, _ = play(3, p, t, sc, getattr(policies, name))
            dec = json.loads(json.dumps(decisions_of(g.journal)))  # как после отправки страницей
            r = replay(3, {"place": p, "team": t, "scenario": sc}, dec)
            assert r["score"] == g.score()["score"], (name, p, t, sc)


def test_extella_runs():
    n = 0
    for f in sorted(glob.glob(os.path.join(HERE, "extella", "runs", "*", "*_s*.json"))):
        j = json.load(open(f))
        if not j.get("finished"):
            continue
        c = j["combo"]
        r = replay(c["seed"], {k: c[k] for k in ("place", "team", "scenario")}, decisions_of(j["journal"]), j.get("world", "ny"))
        assert r["score"] == j["score"]["score"], f
        n += 1
    return n


def test_bad_input():
    S = {"place": "park", "team": "small", "scenario": "heat"}
    for args in [(1.5, S, []), (1, {"place": "moon", "team": "small", "scenario": "heat"}, []), (1, S, [(5, {}), (2, {})]),
                 (1, S, [(99, {})]), (1, S, [(0, "x")]), (1, S, [(0, {})] * 11),
                 (1, {"place": "_tag", "team": "small", "scenario": "heat"}, []),      # пометка источника не значение настройки
                 (1, {"place": "park", "team": "_tag", "scenario": "heat"}, []),
                 (1, {"place": "park", "team": "small", "scenario": "_tag"}, [])]:
        try:
            replay(*args)
        except ValueError:
            continue
        raise AssertionError(args)
    assert replay(1, S, [])["score"] == play(1, "park", "small", "heat", lambda o: {})[0].score()["score"]


def test_check_survives_wrong_shape():
    """Модель без Extella присылает что угодно: Проверка обязана отказать с причиной, а не упасть."""
    import sim
    g = sim.Game(1, "park", "mid", "heat")
    for dec, field in [({"orders": {"frozen": 300}}, "orders.frozen"), ({"orders": 300}, "orders"),
                       ({"thaw": 12}, "thaw"), ({"choices": ["a"]}, "choices"), ({"schedule": "утро"}, "schedule")]:
        out, ok = g.check(dec)
        codes = [(r["field"], r["code"]) for r in out]
        assert (field, "form") in codes, (dec, codes)
    assert g.check(7)[0][0]["code"] == "form"
    assert g.check({})[0] == []


def test_python_sum():
    """core/det.py опирается на компенсированное sum() из Python 3.12: на старом интерпретаторе доли посетителей
    разложатся иначе и все записанные счета (прогоны Extella, таблица рекордов, перенос на JS) перестанут сходиться."""
    assert sum([0.4, 0.25, 0.05, 0.2, 0.1]) == 1.0, "нужен Python 3.12 или новее: sum() считает иначе"


if __name__ == "__main__":
    test_python_sum(); print("python sum ok")
    test_policies_all_combos(); print("policies ok")
    print("extella runs ok:", test_extella_runs())
    test_bad_input(); print("bad input ok")
    test_check_survives_wrong_shape(); print("wrong shape ok")


def test_ny2_crowding_and_old_world_untouched():
    """Мир ny2: теснота срабатывает и снижает траты; мир ny считается ровно как раньше."""
    import json as _json
    # счёт прежнего мира не зависит от нового кода: сверяем с записанным журналом Extella
    j = _json.load(open(os.path.join(HERE, "extella", "runs", "ny2-page", "heat_subway_mid_s1_cxs.json"), encoding="utf-8"))
    st = {k: j["combo"][k] for k in ("place", "team", "scenario")}
    got = replay(j["combo"]["seed"], st, decisions_of(j["journal"]), j.get("world", "ny"))
    assert abs(got["score"] - j["score"]["score"]) < 0.005, "прежний мир посчитался иначе"

    # у метро в жару людей много: теснота обязана появиться хотя бы в одном дне
    g2, _ = play(1, "subway", "mid", "heat", policies.careful, "ny2")
    crowd = [r["crowding"] for r in g2.journal]
    assert max(crowd) > 0, "теснота ни разу не сработала"
    # тот же месяц в прежнем мире тесноты не знает
    g1, _ = play(1, "subway", "mid", "heat", policies.careful, "ny")
    assert max(r["crowding"] for r in g1.journal) == 0, "в мире ny тесноты быть не должно"
    assert g2.score()["score"] != g1.score()["score"], "миры должны считаться по-разному"


if __name__ == "__main__":
    test_ny2_crowding_and_old_world_untouched(); print("ny2 crowding ok")
