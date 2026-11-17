"""Прогон игрока без Extella по 27 комбинациям (одно зерно). Готовые журналы не пересчитываются.

Куда писать и кого звать задаётся окружением:
    CAFE_OUT=m_qwen CAFE_BACKEND=openrouter CAFE_OR_MODEL=qwen/qwen3.5-9b CAFE_OR_PROVIDER=DeepInfra,Parasail
    CAFE_OUT=m_deepseek CAFE_BACKEND=azure CAFE_AZ_MODEL=DeepSeek-V4-Flash
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import player_bare  # noqa: E402

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1
OUT = os.path.join(HERE, "runs", os.environ.get("CAFE_OUT", "bare"))
ORDER = [(sc, st, m) for sc in ("calm", "winter", "competitor") for st in ("quiet", "district", "corridor") for m in ("low", "mid", "high")]
done = 0
for sc, st, m in ORDER:
    path = os.path.join(OUT, "%s_%s_%s_s%d.json" % (sc, st, m, SEED))
    if os.path.exists(path):
        print("skip", path, flush=True); done += 1; continue
    print("==", sc, st, m, time.strftime("%H:%M:%S"), flush=True)
    try:
        player_bare.play(st, m, sc, SEED, out_dir=OUT)
        done += 1
    except Exception as e:
        print("ОШИБКА на", sc, st, m, ":", type(e).__name__, e, flush=True)
print("готово миров:", done, "из", len(ORDER), flush=True)
