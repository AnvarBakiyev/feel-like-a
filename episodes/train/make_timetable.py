"""Расписание участка: техническое время машиниста full (сухо, без ограничений, без задержки) × запас 1,06, вверх до 30 с.
Пишет timetable в lines/<участок>.json. Отправление 10:00:00 = 0 с."""
import json, math, os, sys
import sim, drivers

def build(line_id):
    world = {"seed": 0, "weather": "dry", "adhesion_factor": 1.0, "temp": [], "depart_delay_s": 0, "signal": None}
    g = sim.Game(0, line_id, timetable=False, world=world)
    while not g.done():
        d = drivers.full(g.observe(), g)
        if d: g.decide(d)
        g.step()
    tt = [{"name": g.stations[0]["name"], "arr_s": None, "dep_s": 0}]
    prev_tech = 0.0; prev_dep = 0.0
    for i, s in enumerate(g.stops, start=1):
        st = g.stations[i]
        run = s["t"] - prev_tech  # техническое время перегона
        arr = prev_dep + math.ceil(run * sim.P["sched_margin"] / 30.0) * 30
        dep = arr + st.get("dwell_s", 0) if i < len(g.stations) - 1 else None
        tt.append({"name": st["name"], "arr_s": arr, "dep_s": dep, "tech_run_s": round(run, 1)})
        prev_tech = s["t"] + st.get("dwell_s", 0); prev_dep = dep if dep is not None else arr
    path = os.path.join(sim.HERE, "lines", sim.LINES[line_id] + ".json")
    L = json.load(open(path, encoding="utf-8")); L["timetable"] = tt
    L["ref_kwh"] = round((g.E_in - g.E_back) / 3.6e6, 1)
    L["_ref_kwh"] = "эталон энергии: тот же прогон машиниста full; в счёте ±4 очка за каждый процент к нему (О)"
    L["_timetable"] = "техническое время машиниста full на сухом рельсе × %.2f, вверх до 30 с (О)" % sim.P["sched_margin"]
    json.dump(L, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return tt, g

if __name__ == "__main__":
    for lid in sim.LINES:
        tt, g = build(lid)
        print(lid, [(t["name"], sim.clock(t["arr_s"]) if t["arr_s"] is not None else "-", t.get("tech_run_s")) for t in tt], "stops", [(s["name"], s["err_m"]) for s in g.stops])
