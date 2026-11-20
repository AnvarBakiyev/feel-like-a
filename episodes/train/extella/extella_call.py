"""Вызов эксперта train_plan на Extella. Нужен только чтобы заново получить ответы Extella; для перепроверки не нужен.

Код эксперта лежит рядом JSON-записью: extella/experts/train_plan.json (то же, что держит агент игры
«Extella Train Driver» в маркете Extella). Этот файл берёт код и его sha оттуда и ничего не собирает сам.

Переменные окружения: EXTELLA_TOKEN_FILE (файл с ключом API), EXTELLA_AGENT (агент, в скоупе которого живёт эксперт),
EXTELLA_DEVICE (device_id устройства, где исполнять эксперта; пусто — эксперт идёт в облаке).
"""
import ast, json, os, time, urllib.request

import expert_json

API = os.environ.get("EXTELLA_API", "https://api.extella.ai/api")
AGENT = os.environ.get("EXTELLA_AGENT", "")
DEVICE = os.environ.get("EXTELLA_DEVICE", "")
NAME = "train_plan"


def _token():
    return open(os.path.expanduser(os.environ["EXTELLA_TOKEN_FILE"])).read().strip()


def call(path, body, timeout=180):
    req = urllib.request.Request(API + path, data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"X-Auth-Token": _token(), "X-Profile-Id": "default", "X-Agent-Id": AGENT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def unwrap(out):
    res = out.get("result", out) if isinstance(out, dict) else out
    for _ in range(8):
        if isinstance(res, str):
            for loader in (json.loads, ast.literal_eval):
                try:
                    res = loader(res); break
                except Exception:
                    pass
            else:
                break
        elif isinstance(res, dict) and "result" in res and "ok" not in res and "score" not in res:
            res = res["result"]
        else:
            break
    return res


def code():
    return expert_json.record(NAME)["code"]


def code_sha():
    return expert_json.sha(NAME)


def local():
    """Тот же эксперт прямо здесь, без сети и ключа: для перепроверки этого достаточно."""
    return expert_json.load(NAME)


def save():
    r = expert_json.record(NAME)
    call("/expert/save", {"name": NAME, "description": r["description"], "code": r["code"],
                          "kwargs": r.get("params", {}), "global": False}, timeout=60)


def run(text, seed, line_id, mode="check", tries=3):
    last = None
    for k in range(tries):
        t0 = time.time()
        try:
            body = {"name": NAME, "params": {"text": text, "seed": seed, "line_id": line_id, "mode": mode}}
            if DEVICE:
                body["targets"] = [DEVICE]
            out = call("/expert/run", body)
            if isinstance(out, dict) and out.get("task_id") and "deferred" in json.dumps(out):
                out = _wait(out["task_id"])
            res = unwrap(out)
            if isinstance(res, dict) and ("ok" in res or "score" in res):
                return res, {"where": "extella", "expert": NAME, "sha": code_sha(), "seconds": round(time.time() - t0, 2), "try": k + 1}
            last = str(res)[:400]
        except Exception as e:
            last = repr(e)[:400]
        time.sleep(3)
    raise RuntimeError("expert failed: " + str(last))


def _wait(task_id, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        time.sleep(3)
        r = call("/tasks/check", {"task_id": task_id}, timeout=60)
        s = json.dumps(r)
        if "deferred" not in s and ('"ok"' in s or '"score"' in s):
            return r
    raise RuntimeError("task timeout " + task_id)
