"""Мир ny2 целиком для страницы: 27 месяцев зерна 1, три соперника.

python3 run_ny2_all.py extella <device_id> <часть 0|1> [потоков]   Qwen 3.5 9B с Extella, цену и среду выбирает эксперт
python3 run_ny2_all.py small [потоков]                            Qwen 3.5 9B без Extella
python3 run_ny2_all.py opus [потоков]                             Claude Opus 5.5 через OpenRouter (размышление low). Опубликованные
                                                                  месяцы Claude Opus 5.5 сыграны иначе: в Claude Code через bench/opus.sh

Готовые журналы пропускаются, так что перезапуск безопасен. Программа на Python (careful) не гоняется:
она детерминирована и считается при сборке страницы.
"""
import concurrent.futures as cf
import json, os, sys, threading, time

MODE = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["CAFE_BACKEND"] = "openrouter"
os.environ["ZOO_WORLD"] = "ny2"
os.environ["ZOO_CARDS"] = "expert"; os.environ["ZOO_SHOWS"] = "expert"
COMBOS = [(sc, p, tm, 1) for sc in ("heat", "spring", "flu") for p in ("park", "waterfront", "subway") for tm in ("small", "mid", "large")]
if MODE == "extella":
    os.environ["CAFE_DEVICE"] = sys.argv[2]
    part = int(sys.argv[3]); TH = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    COMBOS = COMBOS[part::2]
    os.environ["CAFE_OR_PROVIDER"] = "DeepInfra,Parasail,PrimeIntellect"
    os.environ["ZOO_PRICE"] = "expert"; os.environ["ZOO_TAG"] = "ny2page"
    OUT = os.path.join(HERE, "extella", "runs", "ny2-page"); os.environ["ZOO_OUT"] = OUT
elif MODE == "small":
    TH = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    os.environ["CAFE_OR_PROVIDER"] = "DeepInfra,Parasail,PrimeIntellect"; os.environ["ZOO_TAG"] = "ny2small"
elif MODE == "opus":
    TH = int(sys.argv[2]) if len(sys.argv) > 2 else 9
    os.environ["CAFE_OR_MODEL"] = "anthropic/claude-opus-5.5"; os.environ["CAFE_OR_PROVIDER"] = "Anthropic"
    os.environ["CAFE_OR_REASONING"] = "low"; os.environ["ZOO_MAX_TOKENS"] = "6000"; os.environ["ZOO_TAG"] = "ny2opus"
else:
    raise SystemExit("режим: extella | small | opus")
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "extella")); sys.path.insert(0, os.path.join(HERE, "bench"))
if MODE == "extella":
    import player  # noqa: E402
else:
    import noext  # noqa: E402
# ZOO_REVERSE=1: тот же набор с конца, чтобы второй процесс шёл навстречу первому
if os.environ.get("ZOO_REVERSE") == "1":
    COMBOS = COMBOS[::-1]
LOCK = threading.Lock(); DONE = [0]


def path_of(sc, p, tm, seed):
    if MODE == "extella":
        return os.path.join(OUT, "%s_%s_%s_s%d_cxs.json" % (sc, p, tm, seed))
    return os.path.join(HERE, "bench", "runs", "%s_%s_%s_%s_s%d.json" % (os.environ["ZOO_TAG"], sc, p, tm, seed))


def one(job):
    sc, p, tm, seed = job
    name = "%s_%s_%s_s%d" % (sc, p, tm, seed)
    if os.path.exists(path_of(*job)):
        return name + ": уже сыгран"
    t0 = time.time()
    try:
        player.play(p, tm, sc, seed) if MODE == "extella" else noext.play(sc, p, tm, seed)
    except Exception as e:
        return name + ": ОШИБКА %s: %s" % (type(e).__name__, str(e)[:200])
    s = json.load(open(path_of(*job), encoding="utf-8"))["score"]["score"]
    with LOCK:
        DONE[0] += 1; n = DONE[0]
    return "%s: счёт %.0f, %.1f мин (%d из %d)" % (name, s, (time.time() - t0) / 60, n, len(COMBOS))


if __name__ == "__main__":
    if MODE == "extella":
        os.makedirs(OUT, exist_ok=True)
    print("%s: месяцев %d, потоков %d, %s" % (MODE, len(COMBOS), TH, time.strftime("%H:%M:%S")), flush=True)
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=TH) as ex:
        for line in ex.map(one, COMBOS):
            print(line, flush=True)
    print("всё, %.1f минут" % ((time.time() - t0) / 60), flush=True)
