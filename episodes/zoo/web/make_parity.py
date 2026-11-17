"""Трассы для теста совпадения Python и JS: решения по вечерам, наблюдения, полный журнал симулятора, счёт.

Игроки: наивный, осторожный (zoo/policies.py), буйный (годные и негодные решения, чтобы проверить и отказы)
и решения Extella из zoo/extella/runs/. Запуск: python3 zoo/web/make_parity.py && node zoo/web/parity.mjs
"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
# мир трасс: "ny" (прежний) или "ny2" (баланс 15.11); у каждого свой файл трасс
WORLD = sys.argv[1] if len(sys.argv) > 1 else "ny"
sys.path.insert(0, os.path.join(HERE, ".."))
import sim, policies  # noqa: E402

PLACES = ["park", "waterfront", "subway"]
TEAMS = ["small", "mid", "large"]
SCENARIOS = ["heat", "spring", "flu"]
SECTIONS = sim.SECTIONS


def chaos(seed):
    """Буйный игрок: шлёт и годные, и негодные решения. Числа только целые или с дробной частью:
    Python печатает float 40.0 как «40.0», а JSON отдаёт в JS число 40, и тексты отказов разошлись бы."""
    r = sim.Rng(sim.fnv("chaos:" + str(seed)))

    def pol(obs):
        d = {}
        if r.u() < 0.75:
            d["thaw"] = {"fish": [34.4, 40, 0, 500, 17.2][r.int(0, 4)], "meat": [2.7, 3, 0, 60][r.int(0, 3)]}
        if r.u() < 0.65:
            o = {}
            if r.u() < 0.8:
                o["frozen"] = {"fish": 10 * r.int(0, 20), "meat": 10 * r.int(0, 3)}
            if r.u() < 0.3:
                o["frozen"] = {"fish": r.int(0, 55)}          # не кратно коробке
            if r.u() < 0.2:
                o["frozen"] = {"fish": 10 * r.int(40, 70)}    # не влезет в морозилку
            if r.u() < 0.45:
                o["hay"] = {"hay": 20 * r.int(0, 40)}
            if r.u() < 0.15:
                o["hay"] = {"hay": r.int(500, 900)}           # не кратно тюку
            if r.u() < 0.12:
                o["hay"] = {"hay": 20 * r.int(60, 80)}        # не влезет в сенник
            if r.u() < 0.35:
                o["produce"] = {"produce": r.int(0, 40)}
            if r.u() < 0.08:
                o["produce"] = {"produce": "много"}           # не число
            if r.u() < 0.08:
                o["bakery"] = {"bread": 5}                    # нет такого поставщика
            if r.u() < 0.08:
                o["frozen"] = {"shrimp": 10}                  # нет такой позиции
            d["orders"] = o
        if r.u() < 0.15:
            d["price"] = [6.0, 12.95, 20.0, 3.0, 30.0][r.int(0, 4)]
        if r.u() < 0.12:
            d["free_wed"] = r.u() < 0.5
        if r.u() < 0.06:
            d["free_wed"] = "yes"                             # отказ по форме
        if r.u() < 0.14:
            d["hire"] = r.int(0, 4)                           # 4 вне диапазона
        if r.u() < 0.09:
            d["fire"] = [0, 1, 2, -1, 20][r.int(0, 4)]        # -1 и 20 вне диапазона
        if r.u() < 0.12:
            d["vet_visit"] = r.u() < 0.7
        if r.u() < 0.05:
            d["vet_visit"] = 1                                # отказ по форме
        if r.u() < 0.3:
            row = {"keepers": {s: [r.int(0, 5), r.int(0, 5)] for s in SECTIONS},   # 5 больше предела секции
                   "cashiers": [r.int(0, 9), r.int(1, 3)], "kiosk": [r.int(0, 3), r.int(0, 3)], "shows": r.int(0, 3)}
            d["schedule"] = {str(w): json.loads(json.dumps(row)) for w in range(7)}
            if r.u() < 0.2:
                d["schedule"]["3"] = {"keepers": {"pool": [1, 1]}, "cashiers": [1, 1], "kiosk": [1, 1], "shows": 0}
        ch = {}
        for c in obs["cards"]:
            if r.u() < 0.85:
                ch[c["id"]] = c["options"][r.int(0, len(c["options"]) - 1)] if r.u() < 0.85 else "maybe"
        if r.u() < 0.06:
            ch["ghost_7"] = "ok"                              # нет такой карточки
        if ch:
            d["choices"] = ch
        return d
    return pol


def trace(seed, place, team, scenario, policy=None, decisions=None):
    g = sim.Game(seed, place, team, scenario, WORLD)
    by_step = {}
    for day, dec in decisions or []:
        by_step.setdefault(day, []).append(dec)
    steps = []; obs_all = []
    while not g.done():
        obs = g.observe(); obs_all.append(obs)
        decs = [policy(obs)] if policy else by_step.get(g.t, [])
        for dec in decs:
            g.decide(dec)
        steps.append(decs)
        g.step()
    return {"settings": {"seed": seed, "place": place, "team": team, "scenario": scenario},
            "steps": steps, "observe": obs_all, "journal": g.journal, "score": g.score()}


out = []
# тестовые игроки: все 27 комбинаций на зерне 3
for sc in SCENARIOS:
    for p in PLACES:
        for tm in TEAMS:
            out.append(trace(3, p, tm, sc, policy=policies.naive))
            out.append(trace(3, p, tm, sc, policy=policies.careful))
# зёрна 1 и 2 на части комбинаций
for seed in (1, 2):
    for i, sc in enumerate(SCENARIOS):
        for j in range(3):
            p = PLACES[(i + j) % 3]; tm = TEAMS[(i + 2 * j + seed) % 3]
            out.append(trace(seed, p, tm, sc, policy=policies.naive))
            out.append(trace(seed, p, tm, sc, policy=policies.careful))
# буйный игрок: все сценарии, несколько зёрен
for seed in (1, 2, 3):
    for i, sc in enumerate(SCENARIOS):
        for j in range(2):
            p = PLACES[(seed + j) % 3]; tm = TEAMS[(i + j) % 3]
            out.append(trace(seed, p, tm, sc, policy=chaos(seed * 100 + i * 10 + j)))
# все журналы прогонов Extella
for f in sorted(glob.glob(os.path.join(HERE, "..", "extella", "runs", "*", "*.json"))):
    j = json.load(open(f, encoding="utf-8"))
    c = j["combo"]
    out.append(trace(c["seed"], c["place"], c["team"], c["scenario"], decisions=sim.decisions_of(j["journal"])))

world = sim.load_world(WORLD)
name = "parity_trace.json" if WORLD == "ny" else "parity_trace_%s.json" % WORLD
with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
    json.dump({"world": world, "traces": out}, fh, ensure_ascii=False)
print(len(out), "трасс, мир", WORLD, "->", name)
