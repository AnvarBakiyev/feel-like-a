"""Тест пересчёта: журнал решений тестовых машинистов даёт тот же счёт, что и сам рейс. python3 test_replay.py"""
import sim, drivers
from replay import replay, record

for lid in sim.LINES:
    for seed in (1, 2, 3):
        for drv in (drivers.full, drivers.careful):
            g, log = record(seed, lid, drv)
            r = replay(seed, {"line": lid}, log)
            assert abs(r["score"] - g.score()["score"]) < 1e-9, (lid, seed, drv.__name__, r["score"], g.score()["score"])
            print("ok", lid, seed, drv.__name__, r["score"], "решений", len(log))
try:
    replay(1, {"line": "de_krm"}, [[0, {"score": 1000}]]); raise SystemExit("подделка прошла")
except ValueError:
    print("ok подделка отклонена")
