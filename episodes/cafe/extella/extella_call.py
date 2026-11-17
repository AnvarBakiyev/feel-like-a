"""Call the cafe_game_plan expert on Extella: save the code, run it on a device, unwrap the answer.

Only needed to get new answers from Extella; rechecking published results does not need it (see verify.py).

Environment: EXTELLA_TOKEN_FILE (file with your API key), EXTELLA_AGENT (the agent whose scope holds the expert),
EXTELLA_DEVICE (device_id where the expert runs), EXTELLA_API (optional). The expert code is plan_expert.py.
"""
import ast, hashlib, json, os, time, urllib.request

API = os.environ.get("EXTELLA_API", "https://api.extella.ai/api")
AGENT = os.environ.get("EXTELLA_AGENT", "")
DEVICE = os.environ.get("EXTELLA_DEVICE", "")
NAME = "cafe_game_plan"
HERE = os.path.dirname(os.path.abspath(__file__))


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
        elif isinstance(res, dict) and "result" in res and "decision" not in res:
            res = res["result"]
        else:
            break
    return res


def code():
    return open(os.path.join(HERE, "plan_expert.py"), encoding="utf-8").read()


def code_sha():
    return hashlib.sha256(code().rstrip("\n").encode()).hexdigest()[:12]


def save():
    c = code()
    call("/expert/save", {"name": NAME, "description": "A month at the cafe: the model's intent and the evening's view -> orders, shifts, dollar estimates.",
                          "code": c, "kwargs": {"obs": {}, "plan": {}, "city": {}}, "global": False}, timeout=60)
    back = call("/expert/get", {"name": NAME}, timeout=60)
    got = back.get("code") or back.get("expert_code") or (back.get("result") or {}).get("code") if isinstance(back, dict) else None
    return {"sha": code_sha(), "same": (got or "").rstrip("\n") == c.rstrip("\n")}


def run(obs, plan, city, tries=3):
    last = None
    for k in range(tries):
        t0 = time.time()
        try:
            out = call("/expert/run", {"name": NAME, "params": {"obs": obs, "plan": plan, "city": city}, "targets": [DEVICE] if DEVICE else []})
            if isinstance(out, dict) and out.get("task_id") and "deferred" in json.dumps(out):
                out = _wait(out["task_id"])
            res = unwrap(out)
            if isinstance(res, dict) and "decision" in res:
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
        if "deferred" not in s and ("result" in r or "decision" in s):
            return r
    raise RuntimeError("task timeout " + task_id)
