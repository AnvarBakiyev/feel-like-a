"""Прогон Extella на 27 комбинациях по очереди (одно зерно). Готовые журналы не пересчитываются."""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
pid = int(os.environ.get("WAIT_PID", "0") or 0)   # дождаться чужого прогона: Ollama на машине одна на всех
while pid:
    try:
        os.kill(pid, 0)
    except OSError:
        break
    time.sleep(30)
import player  # noqa: E402

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1
ORDER = [(sc, st, m) for sc in ("calm", "winter", "competitor") for st in ("quiet", "district", "corridor") for m in ("low", "mid", "high")]
for sc, st, m in ORDER:
    out_dir = os.path.join(HERE, "runs", os.environ.get("CAFE_OUT", ""))
    path = os.path.join(out_dir, "%s_%s_%s_s%d.json" % (sc, st, m, SEED))
    if os.path.exists(path):
        print("skip", path, flush=True); continue
    print("==", sc, st, m, time.strftime("%H:%M:%S"), flush=True)
    try:
        player.play(st, m, sc, SEED, out_dir=out_dir)
    except Exception as e:
        print("ОШИБКА на", sc, st, m, ":", type(e).__name__, e, flush=True)
