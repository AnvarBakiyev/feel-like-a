"""Calls the drone_plan expert on Extella: save the code, run it, unwrap the answer.
Only needed to get new answers from Extella; rechecking the published results (verify.py) does not need it.

The expert code comes from its record here, extella/experts/drone_plan.json: the same record the episode's agent
"Extella Drone Courier" holds in the Extella market, where you can also install the agent and play in chat.

Environment: EXTELLA_TOKEN_FILE (file with your API key), EXTELLA_AGENT (the agent whose scope holds the expert),
EXTELLA_DEVICE (device_id of the machine that runs the expert; leave it empty to run in the cloud), EXTELLA_API
(optional, default below).

python3 extella_call.py save
python3 extella_call.py run "speed fast|orders per flight 2" 4 rotterdam check
"""
import ast, hashlib, json, os, time, urllib.request

from expert_json import record

API = os.environ.get("EXTELLA_API", "https://api.extella.ai/api")
AGENT = os.environ.get("EXTELLA_AGENT", "")
DEVICE = os.environ.get("EXTELLA_DEVICE", "")
NAME = "drone_plan"
HERE = os.path.dirname(os.path.abspath(__file__))


def _token():
    return open(os.path.expanduser(os.environ["EXTELLA_TOKEN_FILE"])).read().strip()


def call(path, body, timeout=300):
    req = urllib.request.Request(API + path, data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"X-Auth-Token": _token(), "X-Profile-Id": "default", "X-Agent-Id": AGENT,
                                          "Content-Type": "application/json"})
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
    return record(NAME)["code"]


def code_sha():
    return hashlib.sha256(code().rstrip(chr(10)).encode()).hexdigest()[:12]


def save():
    c = code()
    call("/expert/save", {"name": NAME, "description": "Feel like a drone courier: check a shift plan in the flight language and fly the shift.",
                          "code": c, "kwargs": record(NAME).get("params") or {"text": "", "seed": 1, "city": "rotterdam", "mode": "check"},
                          "global": False}, timeout=120)
    return {"sha": code_sha(), "bytes": len(c.encode())}


def run(text, seed, city, mode="check", tries=3):
    last = None
    for k in range(tries):
        t0 = time.time()
        try:
            body = {"name": NAME, "params": {"text": text, "seed": seed, "city": city, "mode": mode}}
            if DEVICE:
                body["targets"] = [DEVICE]   # without targets the expert runs in the cloud
            out = call("/expert/run", body, timeout=120)
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


def _wait(task_id, limit=240):
    t0 = time.time()
    while time.time() - t0 < limit:
        time.sleep(3)
        r = call("/tasks/check", {"task_id": task_id}, timeout=60)
        s = json.dumps(r)
        if "deferred" not in s and ("result" in r or chr(34) + "ok" + chr(34) in s or chr(34) + "score" + chr(34) in s):
            return r
    raise RuntimeError("task timeout " + task_id)


if __name__ == "__main__":
    import sys
    if sys.argv[1] == "save":
        print(json.dumps(save(), ensure_ascii=False))
    elif sys.argv[1] == "run":
        res, meta = run(sys.argv[2].replace("|", chr(10)), int(sys.argv[3]), sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "check")
        print(json.dumps(meta, ensure_ascii=False))
        print(json.dumps(res, ensure_ascii=False)[:1200])
