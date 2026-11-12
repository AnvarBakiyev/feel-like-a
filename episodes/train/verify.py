"""Перепроверка эпизода «машинист»: все опубликованные счёты пересчитываются из записанных решений.

python3 verify.py

Что делает:
1. тесты симулятора (test_sim.py);
2. Extella, язык v2: план каждого рейса из журнала исполняется заново тем же обработчиком (poezdka.run) в мире зерна;
3. малая и большая модель без Extella: записанные планы контроллера исполняются заново (noext.execute);
4. большая модель с обратной связью: записанные действия проигрываются заново (closed.replay);
5. тестовые машинисты full и careful считаются заново.
Каждый пересчитанный счёт сравнивается с записанным; в конце таблица средних. Ключи и сеть не нужны:
всё считается на этой машине стандартной библиотекой Python. Ответы моделей взяты из журналов как есть.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "extella"))
import sim, drivers, poezdka
import noext, closed
import test_sim

LINES = ("de_krm", "ch_gotthard", "jp_tokaido")
bad = []


def same(a, b):
    return abs(a - b) < 0.05


def main():
    print("1. тесты симулятора")
    for f in [test_sim.same_seed_same_run, test_sim.other_seed_other_world, test_sim.world_same_for_both_drivers, test_sim.observe_hides_hidden,
              test_sim.rules, test_sim.timetable_reachable, test_sim.language, test_sim.all_lines_run]:
        f(); print("   ok", f.__name__)
    avg = {}
    print("2. Extella (язык v2): план из журнала исполняется заново")
    for lid in LINES:
        xs = []
        for s in range(1, 11):
            J = json.load(open(os.path.join(HERE, "extella", "runs_v2", "%s_s%d.json" % (lid, s)), encoding="utf-8"))
            got = poezdka.run(J["plan"], s, lid).score()["score"]
            if not same(got, J["score"]["score"]):
                bad.append(("extella", lid, s, J["score"]["score"], got))
            xs.append(got)
        avg[("Extella", lid)] = sum(xs) / len(xs)
    print("3. без Extella: планы контроллера исполняются заново")
    for who, name in (("small", "малая без Extella"), ("big", "большая без Extella")):
        for lid in LINES:
            xs = []
            for s in range(1, 11):
                J = json.load(open(os.path.join(HERE, "extella", "noext", "%s_%s_s%d.json" % (who, lid, s)), encoding="utf-8"))
                got = noext.execute(lid, s, J["plan"]).score()["score"]
                if not same(got, J["score"]["score"]):
                    bad.append((who, lid, s, J["score"]["score"], got))
                xs.append(got)
            avg[(name, lid)] = sum(xs) / len(xs)
    print("4. большая модель с обратной связью: действия проигрываются заново")
    for lid in LINES:
        xs = []
        for s in (1, 2, 3):
            J = json.load(open(os.path.join(HERE, "extella", "noext", "closed", "%s_s%d.json" % (lid, s)), encoding="utf-8"))
            g, _ = closed.replay(lid, s, J["acts"])
            got = g.score()["score"]
            if not same(got, J["score"]["score"]):
                bad.append(("bigfb", lid, s, J["score"]["score"], got))
            xs.append(got)
        avg[("большая с обратной связью (зёрна 1–3)", lid)] = sum(xs) / len(xs)
    print("5. тестовые машинисты")
    for name, drv in (("тест full", drivers.full), ("тест careful", drivers.careful)):
        for lid in LINES:
            avg[(name, lid)] = sum(sim.play(s, lid, drv).score()["score"] for s in range(1, 11)) / 10
    print()
    names = []
    for k in avg:
        if k[0] not in names:
            names.append(k[0])
    print("%-42s %10s %10s %10s" % ("средний счёт", "Германия", "Готард", "Япония"))
    for n in names:
        print("%-42s %10.0f %10.0f %10.0f" % (n, avg[(n, "de_krm")], avg[(n, "ch_gotthard")], avg[(n, "jp_tokaido")]))
    print()
    if bad:
        print("НЕ СОВПАЛО (кто, участок, зерно, записано, пересчитано):")
        for b in bad:
            print("  ", b)
        sys.exit(1)
    print("Все пересчитанные счёты совпали с записанными.")


if __name__ == "__main__":
    main()
