"""Кабина по шагам: большая модель ведёт поезд с обратной связью, без Extella.

Модель видит то же, что машинист в кабине (без скрытого сцепления и без поезда впереди, пока сигнал не виден),
ставит контроллер и говорит, до какого момента его держать. Симулятор едет до этого момента или до первого события
и показывает кабину снова. Никакого языка поездки, обработчика и Проверки плана: только рычаг, песок, толкач.

python3 closed.py start <line> <seed>                 брифинг и кабина; создаёт рейс
python3 closed.py act <line> <seed> '<json>'          {"lever": 0.8, "sand": false, "pusher": false, "km": 25.0} или {"lever": -0.5, "s": 30}
python3 closed.py result <line> <seed>                итог рейса

Поле km: держать до этого километра; s: держать столько секунд. Без них: до следующего события или 5 км.
События, на которых симулятор останавливается раньше: стал виден сигнал, началось или кончилось боксование, вмешалась
защита, экстренное торможение, поезд остановился, прибыл на станцию, пришло время отправления, кончился песок, рейс окончен.
Состояние рейса: список действий в файле; каждый вызов заново проигрывает их с начала (симулятор детерминирован).
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import sim
from player import briefing

DIR = os.path.join(HERE, "noext", "closed"); os.makedirs(DIR, exist_ok=True)


def path(lid, seed):
    return os.path.join(DIR, "%s_s%d.json" % (lid, seed))


def advance(g, act):
    """Применить действие и ехать до цели или события. -> причина остановки."""
    dec = {"lever": max(-1.0, min(1.0, float(act.get("lever", 0.0))))}
    if "sand" in act:
        dec["sand"] = bool(act["sand"])
    if "pusher" in act and not g.departed:
        dec["pusher"] = bool(act["pusher"])
    rej = g.decide(dec)
    x0 = g.x; t0 = g.t
    km_to = act.get("km"); s_to = act.get("s")
    seen0 = g.signal_visible(); slip0 = g.slip; atp0 = g.atp; em0 = g.emerg; stops0 = len(g.stops); sand0 = g.sand_on
    waiting = g.at_station and g.t < g.due()
    steps = 0
    while not g.done():
        g.step(); steps += 1
        if waiting and g.t >= g.due():
            return rej, "время отправления"
        if g.signal_visible() and not seen0:
            return rej, "виден сигнал"
        if g.slip != slip0:
            return rej, "началось боксование" if g.slip else "боксование кончилось"
        if g.atp and not atp0:
            return rej, "защита тормозит"
        if g.emerg and not em0:
            return rej, "экстренное торможение"
        if len(g.stops) > stops0:
            return rej, "остановка на станции" if not g.stops[-1].get("missed") else "станция пропущена"
        if sand0 and not g.sand_on:
            return rej, "песок кончился"
        if g.v < 0.01 and not g.at_station and g.t - t0 > 1.0:
            return rej, "поезд стоит"
        if km_to is not None and g.x >= 1000.0 * float(km_to):
            return rej, "достигнут км"
        if s_to is not None and g.t - t0 >= float(s_to):
            return rej, "прошло время"
        if km_to is None and s_to is None and g.x - x0 >= 5000.0:
            return rej, "проехано 5 км"
        if g.at_station and not waiting and g.t >= g.due() and g.lever <= 0 and steps > 2:
            return rej, "можно отправляться"
        if steps > 4 * 3600 * 2:
            break
    return rej, "рейс окончен"


def replay(lid, seed, acts):
    g = sim.Game(seed, lid)
    last = (None, "начало")
    for a in acts:
        last = advance(g, a)
    return g, last


def cab(g, why, rej):
    o = g.observe()
    st = o["next_stop"]
    lines = ["[кабина] %s · км %.3f · %.1f км/ч · допустимая %.1f · ограничение здесь %.0f · уклон %+.1f ‰ · контроллер %+.2f" % (
        o["clock"], o["km"], o["v_kmh"], o["permitted_kmh"], o["limit_kmh"], o["grade_permille"], o["lever"])]
    if st:
        lines.append("станция %s км %.3f, до неё %.0f м, по графику %s" % (st["name"], st["km"], st["dist_m"], st["arr_clock"] or "-"))
    if o["at_station"]:
        lines.append("стоим на станции, отправление не раньше %s" % o["due_clock"])
    ahead = ["км %.2f–%.2f до %d" % (z["from_km"], z["to_km"], z["limit_kmh"]) for z in o["ahead"] if z["from_km"] > o["km"]][:5]
    lines.append("впереди ограничения: " + ("; ".join(ahead) if ahead else "нет"))
    if o["signal"]:
        lines.append("СИГНАЛ: с км %.2f на %.1f км не больше %d (поезд впереди)" % (o["signal"]["km"], o["signal"]["length_km"], o["signal"]["limit_kmh"]))
    flags = []
    if o["slip"]: flags.append("боксование")
    if o["slide"]: flags.append("юз")
    if o["atp"]: flags.append("защита тормозит")
    if o["emergency"]: flags.append("экстренное")
    if o["sand_on"]: flags.append("песок идёт")
    lines.append("песка осталось %.0f с · энергия %.0f кВт·ч · %s" % (o["sand_left_s"], o["energy_kwh"], ", ".join(flags) or "без сигналов"))
    for r in rej or []:
        lines.append("ОТКАЗ: " + r["ru"])
    lines.append("остановились потому что: " + why)
    if g.done():
        lines.append("РЕЙС ОКОНЧЕН. Вызови result.")
    return "\n".join(lines)


def main():
    cmd, lid, seed = sys.argv[1], sys.argv[2], int(sys.argv[3]); p = path(lid, seed)
    if cmd == "start":
        if not os.path.exists(p):
            json.dump({"line": lid, "seed": seed, "acts": [], "started": time.strftime("%Y-%m-%d %H:%M:%S")}, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        S = json.load(open(p, encoding="utf-8"))
        g, (rej, why) = replay(lid, seed, S["acts"])
        print(briefing(g).replace("Напиши план.", "").strip())
        print("Толкач и песок: поле pusher до отправления; sand true/false. Рычаг: -1 полный тормоз, 0 выбег, 1 полная тяга.")
        print(cab(g, why, rej))
    elif cmd == "act":
        S = json.load(open(p, encoding="utf-8"))
        a = json.loads(sys.argv[4])
        S["acts"].append(a)
        g, (rej, why) = replay(lid, seed, S["acts"])
        S["calls"] = len(S["acts"]); S["t"] = g.t
        json.dump(S, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        print(cab(g, why, rej))
    elif cmd == "result":
        S = json.load(open(p, encoding="utf-8"))
        g, _ = replay(lid, seed, S["acts"])
        sc = g.score()
        S.update({"score": sc, "journal": g.journal, "world": g.W, "finished": time.strftime("%Y-%m-%d %H:%M:%S"), "calls": len(S["acts"])})
        json.dump(S, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        print("счёт %.1f, доехал: %s, действий %d, части %s" % (sc["score"], "да" if not sc["parts"]["unfinished"] else "нет", len(S["acts"]), sc["parts"]))


if __name__ == "__main__":
    main()
