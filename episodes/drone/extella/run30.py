"""Прогоны соперников: Extella (модель + эксперт) и малая модель без Extella, по 30 смен.
Готовые журналы не пересчитываются. python3 run30.py [extella|small|all]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import sim

what = sys.argv[1] if len(sys.argv) > 1 else "all"
if what in ("extella", "all"):
    import player
    for city in sim.CITIES:
        for seed in range(1, 11):
            p = os.path.join(HERE, os.environ.get("DRONE_RUNS", "runs"), "%s_s%d.json" % (city, seed))
            if os.path.exists(p):
                print("skip", city, seed, flush=True); continue
            try:
                player.play(city, seed)
            except Exception as e:
                print("ERROR", city, seed, repr(e)[:300], flush=True)
if what in ("small", "all"):
    import noext
    noext.run_small()
