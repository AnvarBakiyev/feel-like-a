"""data.json для страницы: город, тексты карточек, призраки Extella (зерно 1, 27 комбинаций) и осторожный игрок для сравнения.

Призрак берётся только из записанных журналов extella/runs/<папка>/: счёт по дням, объяснения
вечеров, итог по статьям. Папку выбирает CAFE_RUNS, по умолчанию g14: 27 месяцев, сыгранных
в сети на bf16. Все 27 должны быть из одной папки: это одна модель на одной точности, иначе
призраки на странице окажутся из разных замеров.

Запуск: python3 web/build_data.py && python3 web/build_page.py
"""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, ".."))
import sim, policies

RUNS = os.environ.get("CAFE_RUNS", "g14")  # 27 месяцев экспертом 4a9db5d491b0

SC = ["calm", "winter", "competitor"]; ST = ["quiet", "district", "corridor"]; MO = ["low", "mid", "high"]
ghosts = {}; careful = {}; rivals = {}

# прогоны моделей без Extella: папка -> имя соперника на странице.
# Берётся то, что записано: мира без журнала у соперника просто нет.
MODEL_DIRS = {"qwen": "m_qwen", "opus": "m_opus"}
models = {}
for sc in SC:
    for st in ST:
        for mo in MO:
            key = sc + "_" + st + "_" + mo
            d = json.load(open(os.path.join(H, "..", "extella", "runs", RUNS, key + "_s1.json")))
            ev = {e["day"]: e for e in d["evenings"]}
            ghosts[key] = {
                "daily": [x["score"] for x in d["daily"]],
                "why_ru": [ev[t].get("why_ru") or "" for t in range(30)],
                "why_en": [ev[t].get("why_en") or "" for t in range(30)],
                "plan": [{k: v for k, v in (ev[t].get("plan") or {}).items() if k in ("stock", "staff", "buy", "choices")} for t in range(30)],
                "score": d["score"]["score"], "parts": d["score"]["parts"], "counts": d["score"]["counts"],
                "model": d.get("model"), "expert_sha": (d.get("expert") or {}).get("sha"),
            }
            g, _ = sim.play(1, st, mo, sc, policies.careful)
            careful[key] = {"daily": [], "score": g.score()["score"], "parts": g.score()["parts"]}
            g2 = sim.Game(1, st, mo, sc)
            while g2.t < 30:
                g2.decide(policies.careful(g2.observe())); g2.step(); careful[key]["daily"].append(g2.score()["score"])
            assert careful[key]["daily"][-1] == careful[key]["score"]
            # соперники: каждый отличается от осторожного ровно одним
            rivals[key] = {}
            for rname, rfn in (("plenty", policies.plenty), ("thrifty", policies.thrifty), ("bare", policies.bare)):
                g3 = sim.Game(1, st, mo, sc); daily = []
                while g3.t < 30:
                    g3.decide(rfn(g3.observe())); g3.step(); daily.append(g3.score()["score"])
                rivals[key][rname] = {"daily": daily, "score": g3.score()["score"], "parts": g3.score()["parts"]}

# уроки: мир зерна 1, район, $25k, спокойный месяц; до нужного вечера решения осторожного игрока
LS = dict(seed=1, street="district", money="mid", scenario="calm")


def careful_until(t_end, force=None):
    g = sim.Game(LS["seed"], LS["street"], LS["money"], LS["scenario"]); log = []
    while g.t < 30:
        if g.t == t_end and force is None:
            break
        d = policies.careful(g.observe())
        if force:
            ch = dict(d.get("choices") or {}); ch.pop(force[0], None)
            if g.t == t_end:
                ch[force[0]] = force[1]
            d["choices"] = ch
        if g.t < t_end or force is None:
            log.append([g.t, d])
        g.decide(d); g.step()
    return g, log


g0 = sim.Game(LS["seed"], LS["street"], LS["money"], LS["scenario"])
insp = [e for e in g0.W["events"] if e["kind"] == "inspection"][0]
assert g0.W["days"][4]["wd"] == 0 and g0.W["days"][5]["wd"] == 1
_, log5 = careful_until(5)
t_card = insp["day"] - 1
_, log_card = careful_until(t_card)
outc = {}
for opt in ("clean", "none"):
    g, _ = careful_until(t_card, force=(insp["id"], opt))
    gr = [x for r in g.journal for x in r["events"] if x.startswith("inspection")][0][-1]
    outc[opt] = {"grade": gr, "score": g.score()["score"]}
lessons = {"settings": LS, "order_log": log5, "card_log": log_card, "card_t": t_card, "card_id": insp["id"], "card_outcomes": outc}

cards = json.load(open(os.path.join(H, "..", "cards_ny.json"), encoding="utf-8"))
cards.pop("_note", None)
for mname, mdir in MODEL_DIRS.items():
    base = os.path.join(H, "..", "extella", "runs", mdir)
    if not os.path.isdir(base):
        continue
    for fn in sorted(os.listdir(base)):
        if not fn.endswith("_s1.json"):
            continue
        d = json.load(open(os.path.join(base, fn), encoding="utf-8"))
        if len(d.get("daily") or []) != 30:
            print("пропускаю недоигранный", mdir, fn); continue
        key = fn[:-len("_s1.json")]
        models.setdefault(key, {})[mname] = {
            "daily": [x["score"] for x in d["daily"]], "score": d["score"]["score"], "parts": d["score"]["parts"],
            "model": d.get("model"), "fallbacks": d.get("fallbacks", 0),
            # что модель сама написала о главном решении вечера: показывается игроку после дня
            "why_ru": [str((e.get("why_ru") or ""))[:160] for e in d["evenings"]],
            "why_en": [str((e.get("why_en") or ""))[:160] for e in d["evenings"]]}
print("миров с моделями:", len(models), {m: sum(1 for k in models if m in models[k]) for m in MODEL_DIRS})

out = {"city": sim.load_city("ny"), "cards": cards, "ghosts": ghosts, "careful": careful, "rivals": rivals, "models": models, "seed": 1, "lessons": lessons}
json.dump(out, open(os.path.join(H, "data.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print(os.path.getsize(os.path.join(H, "data.json")) // 1024, "КБ")
