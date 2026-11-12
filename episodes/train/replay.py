"""Пересчёт рейса по журналу решений: для общей таблицы рекордов (../LEADERBOARD.md) и для перепроверки.

replay(seed, settings, decisions) -> {"score", "parts", "counts", "stops", "steps"}
  seed       зерно рейса
  settings   {"line": "de_krm" | "ch_gotthard" | "jp_tokaido"}
  decisions  [[шаг, решение], ...]; шаг: номер шага 0,5 с, перед которым решение принято (0 = до отправления);
             решение: {"lever": -1..1, "sand": bool, "pusher": bool, "emergency": true}
Страница пишет такой журнал сама (каждое принятое решение с номером шага). Счёт считает тот же sim.py,
что и страница (sim.js совпадает с ним до последнего знака, см. web/parity.mjs), поэтому подделать счёт нельзя:
в таблицу попадает только пересчитанный.
"""
import sim

ALLOWED = {"lever", "sand", "pusher", "emergency"}
MAX_STEPS = 4 * 3600 * 2


def replay(seed, settings, decisions):
    line = settings.get("line") or settings.get("line_id")  # оба написания: {"line": ...} и как в Game(seed, line_id=...)
    if line not in sim.LINES:
        raise ValueError("неизвестный участок: %r" % line)
    clean = []
    for item in decisions:
        step, dec = int(item[0]), item[1]
        if not isinstance(dec, dict) or set(dec) - ALLOWED or step < 0 or step > MAX_STEPS:
            raise ValueError("неверное решение: %r" % (item,))
        clean.append((step, dec))
    clean.sort(key=lambda d: d[0])
    g = sim.Game(int(seed), line)
    i = 0; n = 0
    while not g.done():
        while i < len(clean) and clean[i][0] <= n:
            g.decide(clean[i][1]); i += 1
        g.step(); n += 1
    sc = g.score()
    return {"score": sc["score"], "parts": sc["parts"], "counts": sc["counts"], "stops": sc["stops"], "steps": n}


def record(seed, line, driver):
    """Журнал решений тестового машиниста в том виде, как его пишет страница (для теста)."""
    g = sim.Game(seed, line); log = []; n = 0; last = {}
    while not g.done():
        d = driver(g.observe(), g)
        if d:
            ch = {k: v for k, v in d.items() if last.get(k) != v}
            if ch and not g.decide(ch):
                log.append([n, ch]); last.update(ch)
        g.step(); n += 1
    return g, log
