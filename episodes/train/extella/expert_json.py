"""The Extella experts of this episode: fingerprints here, code in the episode's agent on Extella.

The experts are not in this repository. Each one lives in the episode's agent in the Extella market
(name and listing in extella/experts.lock.json). The lock file keeps, for every expert version the runs used,
its name, description, argument names and sha (first 12 hex of sha256 of the code), so every recorded run
says which version produced it.

To call an expert, install the episode's agent from the Extella market as a new agent, then set
    EXTELLA_TOKEN_FILE  file with your Extella API key
    EXTELLA_AGENT       id of the installed agent in your account
    EXTELLA_API         optional, default https://api.extella.ai/api
    EXTELLA_DEVICE      optional device_id; without it the expert runs in the Extella cloud

    from expert_json import load, available
    cafe_game_plan = load("cafe_game_plan")   # calls the expert on Extella with the same arguments
    available()                               # False without the variables above: verify.py then skips those checks

Answers are cached in extella/.extella_cache/ by arguments, so a second run of verify.py does not call Extella again.
Delete that folder to call Extella afresh.
"""
import ast, hashlib, json, os, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(HERE, "experts.lock.json")
CACHE = os.path.join(HERE, ".extella_cache")
API = os.environ.get("EXTELLA_API", "https://api.extella.ai/api")


class NeedExtella(RuntimeError):
    pass


def lock():
    with open(LOCK, encoding="utf-8") as f:
        return json.load(f)


def record(name):
    """Lock entry of the current version: name, description, cspl, args, sha. No code."""
    for e in lock()["experts"]:
        if e["name"] == name:
            return e
    raise KeyError(name)


def sha(name):
    return record(name)["sha"]


def available():
    return bool(os.environ.get("EXTELLA_AGENT")) and bool(os.environ.get("EXTELLA_TOKEN_FILE"))


def how():
    a = lock()["agent"]
    return ("needs the agent %r (version %s) from the Extella market: find it by name, install it as a new agent, "
            "then set EXTELLA_TOKEN_FILE and EXTELLA_AGENT, see extella/expert_json.py" % (a["name"], a["version"]))


def _call(path, body, timeout=180):
    tok = open(os.path.expanduser(os.environ["EXTELLA_TOKEN_FILE"])).read().strip()
    req = urllib.request.Request(API + path, data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"X-Auth-Token": tok, "X-Profile-Id": "default", "X-Agent-Id": os.environ["EXTELLA_AGENT"],
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _unwrap(out):
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
        elif isinstance(res, dict) and "result" in res and set(res) <= {"result", "status", "ok", "success", "task_id", "stdout", "logs", "time"}:
            res = res["result"]
        else:
            break
    return res


def _wait(task_id, limit=600):
    t0 = time.time()
    while time.time() - t0 < limit:
        time.sleep(3)
        r = _call("/tasks/check", {"task_id": task_id}, timeout=60)
        if "deferred" not in json.dumps(r)[:2000]:
            return r
    raise RuntimeError("task timeout " + task_id)


def run(name, params, tries=3):
    """One call of the expert on Extella with named params; the answer as the expert returned it."""
    if not available():
        raise NeedExtella(name + ": " + how())
    key = hashlib.sha256(json.dumps([name, sha(name), params], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    cp = os.path.join(CACHE, name, key + ".json")
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            return json.load(f)
    body = {"name": name, "params": params}
    if os.environ.get("EXTELLA_DEVICE"):
        body["targets"] = [os.environ["EXTELLA_DEVICE"]]
    last = None
    for _ in range(tries):
        try:
            out = _call("/expert/run", body)
            if isinstance(out, dict) and out.get("task_id") and "deferred" in json.dumps(out)[:2000]:
                out = _wait(out["task_id"])
            res = _unwrap(out)
            if isinstance(res, (dict, list)):
                os.makedirs(os.path.dirname(cp), exist_ok=True)
                with open(cp, "w", encoding="utf-8") as f:
                    json.dump(res, f, ensure_ascii=False)
                return res
            last = str(res)[:400]
        except Exception as e:
            last = repr(e)[:400]
        time.sleep(3)
    raise RuntimeError("expert %s failed on Extella: %s" % (name, last))


def load(name):
    """A function with the expert's signature that runs the expert on Extella."""
    args = record(name)["args"]

    def call(*a, **kw):
        if len(a) > len(args):
            raise TypeError("%s takes %d arguments" % (name, len(args)))
        params = dict(zip(args, a)); params.update(kw)
        return run(name, json.loads(json.dumps(params)))
    call.__name__ = name
    return call
