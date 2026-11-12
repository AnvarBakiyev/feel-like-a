"""Прогон Extella: 3 участка × зёрна 1–10, по очереди. Готовые журналы не пересчитываются."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import player
for lid in ("de_krm", "ch_gotthard", "jp_tokaido"):
    for seed in range(1, 11):
        p = os.path.join(HERE, os.environ.get("TRAIN_RUNS", "runs"), "%s_s%d.json" % (lid, seed))
        if os.path.exists(p):
            print("skip", p, flush=True); continue
        try:
            player.play(lid, seed)
        except Exception as e:
            print("ERROR", lid, seed, repr(e)[:300], flush=True)
