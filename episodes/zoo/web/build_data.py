"""data.json для страницы зоопарка: мир, карточки, призраки Extella (зерно 1, 27 комбинаций), осторожный игрок и уроки.

Призрак берётся только из записанных журналов extella/runs/new-expert/<сценарий>_<место>_<команда>_s1_cxs.json
(папка нынешнего эксперта: журналы прежнего лежат рядом и в страницу не идут, иначе призрак и эксперт разойдутся)
(прогон G6: карточки и кормления выбирает эксперт). Ничего не досчитывается.
Запуск: python3 zoo/web/build_data.py && python3 zoo/web/build_page.py
"""
import json, os, sys

H = os.path.dirname(os.path.abspath(__file__))
Z = os.path.join(H, "..")
sys.path.insert(0, Z)
import sim, policies  # noqa: E402

SEED = 1
# мир страницы: с 15.11 новый баланс ny2; журналы Extella и соперников берутся из прогонов этого мира
WORLD = os.environ.get("ZOO_WORLD", "ny2")
EXT_DIR = {"ny": "new-expert", "ny2": "ny2-page"}[WORLD]
RIVAL_TAGS = {"ny": [("small", "small")], "ny2": [("small", "ny2small"), ("opus", "ny2opus")]}[WORLD]
SC = ["heat", "spring", "flu"]
PL = ["park", "waterfront", "subway"]
TM = ["small", "mid", "large"]
N = 30


def daily_scores(seed, place, team, scenario, policy):
    g = sim.Game(seed, place, team, scenario, WORLD)
    out = []
    while not g.done():
        g.decide(policy(g.observe()))
        g.step()
        out.append(g.score()["score"])
    return g, out


GROUPS = {"revenue": ["revenue"], "goods": ["cogs", "card_fees"], "wages": ["wages"], "feed": ["feed", "leftover_feed"],
          "other": ["electricity", "vet", "event_costs"], "penalties": ["section_violations", "inspection", "deaths", "queue", "vet_visits"]}


def pnl_by_day(seed, place, team, scenario, decisions=None, policy=None):
    """Прибыль и убытки нарастающим итогом на конец каждого дня: шесть строк, в сумме дают счёт.
    Считается проигрыванием записанных решений тем же симулятором, ничего не досчитывается."""
    g = sim.Game(seed, place, team, scenario, WORLD)
    by = {}
    for d, dec in decisions or []:
        by.setdefault(d, []).append(dec)
    out = []
    while not g.done():
        if policy:
            g.decide(policy(g.observe()))
        else:
            for dec in by.get(g.t, []):
                g.decide(dec)
        g.step()
        P = g.score()["parts"]
        out.append([round(sum(P[k] for k in ks)) for ks in GROUPS.values()])
    return g, out


ghosts = {}
careful = {}
rivals = {}
missing = []
for sc in SC:
    for p in PL:
        for tm in TM:
            key = sc + "_" + p + "_" + tm
            path = os.path.join(Z, "extella", "runs", EXT_DIR, "%s_%s_%s_s%d_cxs.json" % (sc, p, tm, SEED))
            if not os.path.exists(path):
                missing.append(key)
                continue
            d = json.load(open(path, encoding="utf-8"))
            ev = {e["day"]: e for e in d["evenings"]}
            shows = [r["shows"] for r in d["journal"]]
            ch = {}
            for r in d["journal"]:
                for dec in r["decisions"]:
                    ch.update(dec.get("choices") or {})
            ghosts[key] = {
                "daily": [x["score"] for x in d["daily"]],
                "why_ru": [(ev.get(t) or {}).get("why_ru") or "" for t in range(N)],
                "why_en": [(ev.get(t) or {}).get("why_en") or "" for t in range(N)],
                "plan": [{k: v for k, v in ((ev.get(t) or {}).get("plan") or {}).items() if k in ("stock", "staff", "price", "free_wed")} for t in range(N)],
                "shows": shows,
                "choices": ch,
                "score": d["score"]["score"], "parts": d["score"]["parts"], "counts": d["score"]["counts"],
                "model": d.get("model"), "expert_sha": (d.get("expert") or {}).get("sha"),
                "cards_by": d.get("cards_by"), "shows_by": d.get("shows_by"),
            }
            gg, pnl = pnl_by_day(SEED, p, tm, sc, decisions=sim.decisions_of(d["journal"]))
            assert abs(gg.score()["score"] - d["score"]["score"]) < 0.005, "журнал Extella пересчитался иначе: " + key
            ghosts[key]["pnl"] = pnl
            g, dl = daily_scores(SEED, p, tm, sc, policies.careful)
            s = g.score()
            careful[key] = {"daily": dl, "score": s["score"], "parts": s["parts"], "pnl": pnl_by_day(SEED, p, tm, sc, policy=policies.careful)[1]}
            assert abs(dl[-1] - s["score"]) < 1e-6
            # соперники без Extella: малая модель и сильная, если месяц у них записан в этом мире (сеть, зерно 1)
            for who, tag in RIVAL_TAGS:
                rp = os.path.join(Z, "bench", "runs", "%s_%s_%s_%s_s%d.json" % (tag, sc, p, tm, SEED))
                if not os.path.exists(rp):
                    continue
                rj = json.load(open(rp, encoding="utf-8"))
                if rj.get("world", "ny") != WORLD:
                    continue
                rg, rpnl = pnl_by_day(SEED, p, tm, sc, decisions=sim.decisions_of(rj["journal"]))
                assert abs(rg.score()["score"] - rj["score"]["score"]) < 0.005, "журнал соперника пересчитался иначе: " + who + " " + key
                rivals.setdefault(who, {})[key] = {"daily": [sum(x) for x in rpnl], "score": rj["score"]["score"], "pnl": rpnl, "model": rj.get("model")}

# --- уроки: один и тот же месяц, решения осторожного игрока как основа ---
LS = {"seed": SEED, "place": "waterfront", "team": "mid", "scenario": "flu"}


def careful_log(t_end, force_choice=None):
    """Решения careful до вечера t_end включительно. force_choice=(id, вариант) подменяет ответ на карточку в этот вечер."""
    g = sim.Game(LS["seed"], LS["place"], LS["team"], LS["scenario"], WORLD)
    log = []
    while not g.done():
        dec = policies.careful(g.observe())
        if force_choice and g.t == t_end:
            dec["choices"] = dict(dec.get("choices") or {})
            dec["choices"][force_choice[0]] = force_choice[1]
        if g.t <= t_end:
            log.append([g.t, json.loads(json.dumps(dec))])
        g.decide(dec)
        g.step()
        if g.t > t_end and force_choice is None:
            break
    return g, log


g0 = sim.Game(LS["seed"], LS["place"], LS["team"], LS["scenario"], WORLD)
hp = [e for e in g0.X["events"] if e["kind"] == "hpai"][0]
# вечер, в который карточка открыта: ищем прогоном, а не по дню события
t_card = None
gs = sim.Game(LS["seed"], LS["place"], LS["team"], LS["scenario"], WORLD)
while not gs.done():
    o = gs.observe()
    if t_card is None and any(c["id"] == hp["id"] for c in o["cards"]):
        t_card = gs.t
    gs.decide(policies.careful(o))
    gs.step()
assert t_card is not None, "карточка гриппа ни в один вечер не открыта"
_, base_log = careful_log(t_card)          # решения вечеров 0..t_card, последний с ответом careful
outcomes = {}
for opt in ("all_indoor", "vulnerable", "none"):
    g, _ = careful_log(t_card, force_choice=(hp["id"], opt))
    hit = any("hpai_hit" in r["events"] for r in g.journal)
    outcomes[opt] = {"score": g.score()["score"], "hit": hit, "deaths": g.score()["counts"]["deaths"]}

# оценки эксперта в этот вечер: тот же код, что считает их для Extella
sys.path.insert(0, os.path.join(Z, "extella"))
from expert_json import load  # noqa: E402
zoo_game_plan = load("zoo_game_plan")
from public_world import public_world  # noqa: E402
gE = sim.Game(LS["seed"], LS["place"], LS["team"], LS["scenario"], WORLD)
for t, dec in base_log[:-1]:
    gE.observe(); gE.decide(dec); gE.step()
est = zoo_game_plan(gE.observe(), {"stock": "normal", "staff": "normal", "shows": 2}, public_world(WORLD))["estimates"]["cards"].get(hp["id"], {})

lessons = {"settings": LS, "base_log": base_log, "card_t": t_card, "card_id": hp["id"], "card_outcomes": outcomes, "card_est": est,
           "shift_t": 0, "thaw_t": 0}

cards = json.load(open(os.path.join(Z, "cards_ny.json"), encoding="utf-8"))
cards.pop("_note", None)
out = {"world": sim.load_world(WORLD), "cards": cards, "seed": SEED, "ghosts": ghosts, "careful": careful, "rivals": rivals, "pnl_groups": list(GROUPS), "lessons": lessons,
       "combos": {"sc": SC, "pl": PL, "tm": TM}}
p_out = os.path.join(H, "data.json")
json.dump(out, open(p_out, "w"), ensure_ascii=False, separators=(",", ":"))
print(len(ghosts), "призраков,", os.path.getsize(p_out) // 1024, "КБ")
if missing:
    print("нет журналов:", ", ".join(missing))
