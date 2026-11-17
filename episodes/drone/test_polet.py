"""Тесты языка полёта и обработчика: разбор, здравый смысл, отказ со строкой, обещание обработчика, пересчёт по журналу."""
import sim, polet

NL = chr(10)


def test_parse():
    p, e = polet.parse("высота 100" + NL + "скорость быстро" + NL + "груз до 25 кг" + NL + "заказов за рейс 2" + NL +
                       "запас 20" + NL + "зарядка на площадке 3 если заряд меньше 40" + NL + "сначала близкие" + NL + "не лететь дальше 9 км")
    assert not e, e
    assert (p["alt"], p["speed"], p["load_kg"], p["per_flight"], p["reserve"], p["pad"], p["pad_below"], p["first"], p["max_km"]) == (
        100, "fast", 25.0, 2, 20, 3, 40, "near", 9.0), p
    q, e2 = polet.parse("altitude 100" + NL + "speed fast" + NL + "load up to 25 kg" + NL + "orders per flight 2" + NL +
                        "reserve 20" + NL + "pad 3 if charge below 40" + NL + "first near" + NL + "no farther than 9 km")
    assert not e2, e2
    assert {k: v for k, v in q.items() if k != "lines"} == {k: v for k, v in p.items() if k != "lines"}
    _, e3 = polet.parse("лети быстрее ветра")
    assert e3 and e3[0]["line"] == 1 and "не команда" in e3[0]["ru"], e3
    _, e4 = polet.parse("высота 60" + NL + "высота 100")
    assert e4 and e4[0]["line"] == 2, e4
    p5, e5 = polet.parse("# только комментарий" + NL + "  ВЫСОТА 30  ")
    assert not e5 and p5["alt"] == 30


def test_sense():
    g = sim.Game(1, "almaty")
    for txt, word in (("высота 77", "30, 60, 100 или 120"), ("груз до 50 кг", "не больше 40"), ("заказов за рейс 9", "от 1 до 3"),
                      ("запас 90", "от 5 до 60"), ("зарядка на площадке 0 если заряд меньше 30", "не площадка"),
                      ("не лететь дальше 1 км", "ближняя точка")):
        ok, errs, fc, _ = polet.check(txt, g)
        assert not ok and errs and word in errs[0]["ru"], (txt, errs)
        assert fc is None


def test_check_accepts_and_refuses():
    g = sim.Game(4, "rotterdam")
    ok, errs, fc, _ = polet.check("высота 60" + NL + "скорость эконом", g)
    assert ok and not errs and fc["score"] > 0, (errs, fc)
    ok, errs, fc, _ = polet.check("запас 50", g)
    assert not ok and errs[0]["line"] == 1 and "запас" in errs[0]["ru"] and errs[0]["en"], errs
    assert fc is not None and fc["score"] < 500, fc


def test_handler_keeps_the_rules():
    """Нарушение в языке выразить нельзя: ни одно решение обработчика Проверка игры не отвергает."""
    for city, seed, txt in (("rotterdam", 8, "заказов за рейс 3" + NL + "груз до 40 кг" + NL + "высота 100"),
                            ("dubai", 7, "груз до 40 кг" + NL + "сначала тяжёлые"),
                            ("almaty", 1, "заказов за рейс 2" + NL + "зарядка на площадке 3 если заряд меньше 40")):
        g = sim.Game(seed, city)
        plan, errs = polet.parse(txt)
        assert not errs, errs
        disp = polet.Dispatcher(plan)
        bad = []
        while not g.done():
            for dec in disp.tick(g):
                r = g.decide(dec)
                if r:
                    bad.append((dec, r))
            g.step()
        assert not bad, bad[:2]
        assert g.score()["counts"]["lost"] == 0, (city, seed, g.score()["counts"])


def test_forecast_is_kept():
    """Обещание обработчика: на прогнозе ветра рейс всегда возвращается, вынужденных посадок и потерь нет."""
    for city in sim.CITIES:
        for seed in (1, 5, 9):
            g0 = sim.Game(seed, city)
            g, disp = polet.simulate(dict(polet.DEFAULT, lines={}), g0)
            c = g.score()["counts"]
            assert c["forced"] == 0 and c["lost"] == 0, (city, seed, c)


def test_replay():
    g, disp, dec = polet.run("заказов за рейс 2" + NL + "скорость эконом", 3, "rotterdam")
    r = sim.replay(3, {"city": "rotterdam"}, dec)
    assert r["score"] == g.score()["score"], (r["score"], g.score()["score"])


for name, f in list(globals().items()):
    if name.startswith("test_"):
        f(); print("ok", name)


def test_point_lines():
    """Ступень 4: предел груза на точке и пропуск точки разбираются, проверяются и доходят до отбора заказов."""
    g = sim.Game(1, "almaty")
    p, e = polet.parse("точка 3 груз до 12 кг" + NL + "точку 5 пропускать" + NL + "point 6 load up to 7 kg" + NL + "skip point 2")
    assert not e, e
    assert p["pt_load"] == {3: 12.0, 6: 7.0} and p["skip"] == [2, 5], p
    assert not polet.sense(p, g), polet.sense(p, g)
    _, dup = polet.parse("точка 3 груз до 12 кг" + NL + "точка 3 груз до 8 кг")
    assert dup and dup[0]["line"] == 2, dup
    for txt, word in (("точка 99 груз до 5 кг", "точки 99 в этом городе нет"),
                      ("точка 3 груз до 50 кг", "не больше 40"),
                      ("точка 3 груз до 1 кг", "не полетит ни один"),
                      ("точка 3 груз до 5 кг" + NL + "точку 3 пропускать", "и пропускается, и с пределом груза")):
        bad, pe = polet.parse(txt)
        errs = pe or polet.sense(bad, g)
        assert errs and any(word in x["ru"] for x in errs), (txt, errs)
    # отбор заказов слушается строк про точку
    plan, _ = polet.parse("точку 3 пропускать" + NL + "точка 0 груз до 5 кг")
    disp = polet.Dispatcher(plan)
    gg = sim.Game(1, "almaty", world=polet.expected_world(g))
    while not gg.done():
        for o, pt, d in disp._cands(gg):
            assert pt["id"] != 3, "пропущенная точка попала в отбор"
            assert not (pt["id"] == 0 and o["kg"] > 5.0), "предел груза на точке не соблюдён"
        for dec in disp.tick(gg):
            gg.decide(dec)
        gg.step()


def test_used():
    plan, _ = polet.parse("точку 5 пропускать" + NL + "точка 6 груз до 10 кг" + NL + "скорость быстро")
    assert polet.used(plan, "skip", 5) and not polet.used(plan, "skip", 4)
    assert polet.used(plan, "pt_load", [6, 10.0]) and not polet.used(plan, "pt_load", [6, 12.0])
    assert polet.used(plan, "speed", "fast") and not polet.used(plan, "speed", "eco")
    assert polet.used(plan, "pt_load_off", 3) and not polet.used(plan, "pt_load_off", 6)
    assert polet.used(plan, "skip_off", 2) and not polet.used(plan, "skip_off", 5)
