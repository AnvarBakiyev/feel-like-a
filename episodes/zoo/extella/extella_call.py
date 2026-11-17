"""Calls the zoo expert zoo_game_plan on Extella. Needed only to get new Extella answers; rechecking does not need it.

Environment: EXTELLA_TOKEN_FILE (file with the API key), EXTELLA_AGENT (agent whose scope holds the expert),
EXTELLA_DEVICE (device_id of the device that runs the expert; CAFE_DEVICE is read too). The expert source is
plan_expert.py; save() uploads it, run() executes it on the device. ZOO_LOCAL_EXPERT=1 in player.py runs the same
code locally instead, with the same result (verify.py checks that for every recorded evening).
"""
import ast, hashlib, json, os, time, urllib.request

API = os.environ.get("EXTELLA_API", "https://api.extella.ai/api")
AGENT = os.environ.get("EXTELLA_AGENT", "")
DEVICE = os.environ.get("EXTELLA_DEVICE") or os.environ.get("CAFE_DEVICE", "")
NAME = "zoo_game_plan"
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
    call("/expert/save", {"name": NAME, "description": "Zoo: the model's plan and the evening observation -> thaw, orders, shifts, estimates in dollars.",
                          "code": code(), "kwargs": {"obs": {}, "plan": {}, "world": {}}, "global": False}, timeout=60)
    return {"sha": code_sha()}


def run(obs, plan, world, tries=3, net_wait=600):
    last = None
    k = 0
    net_t0 = None
    while k < tries:
        t0 = time.time()
        try:
            out = call("/expert/run", {"name": NAME, "params": {"obs": obs, "plan": plan, "world": world}, "targets": [DEVICE] if DEVICE else []})
            if isinstance(out, dict) and out.get("task_id") and "deferred" in json.dumps(out):
                out = _wait(out["task_id"])
            res = unwrap(out)
            if isinstance(res, dict) and "decision" in res:
                return res, {"where": "extella", "expert": NAME, "sha": code_sha(), "seconds": round(time.time() - t0, 2), "try": k + 1}
            last = str(res)[:400]
        except Exception as e:
            last = repr(e)[:400]
            if "URLError" in last or "ConnectionError" in last or "timed out" in last or "HTTPError 50" in last:
                net_t0 = net_t0 or time.time()
                if time.time() - net_t0 < net_wait:
                    time.sleep(20)
                    continue
        net_t0 = None
        k += 1
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
