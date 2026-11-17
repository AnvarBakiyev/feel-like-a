"""Rush hour: a visitor's rules are saved as an expert in the "traffic" language and replayed by the handler on the device.

Plugged into the blocks proxy under /api/blocks/traffic/*:
  POST /api/blocks/traffic/score    {level, rules, session} -> the server replays rush hour with its own handler; the result
                                    and its fingerprint come back, and a confirmed result enters the table of mayors
  GET  /api/blocks/traffic/mayors?level=<key>   the best mayors of a level

Only the rules themselves are kept: comments are dropped, so the table carries keywords and numbers and nothing else.
"""
import hashlib, json, os, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = "traffic_mayors"
TOP = 25
MAX_RULES = 2000
SESSION_RUNS = 40
LOCK = threading.Lock()
RUNS = {"day": "", "by_session": {}}
_ns = {}
for _where in (HERE, os.path.dirname(HERE)):  # next to this file on the server, one folder up in the repository
    try:
        exec(open(os.path.join(_where, "traffic_handler_v1.py"), encoding="utf-8").read(), _ns)
        break
    except OSError:
        _ns = {}


def canonical(rules):
    """The rules without comments and blank lines, in lower case: what the handler reads, nothing more."""
    out = []
    for raw in str(rules or "").split(chr(10)):
        line = raw.split("#")[0].strip().lower()
        if line:
            out.append(" ".join(line.split()))
    return chr(10).join(out)


def mayor_name(session):
    h = int(hashlib.sha256(session.encode("utf-8")).hexdigest()[:8], 16)
    return {"a": h % 12, "b": (h // 12) % 12, "n": 100 + (h // 144) % 900}


def mayors(kv_get, level):
    table = kv_get(KEY) or {}
    return {"status": "success", "level": level, "mayors": table.get(level, [])}


def score(platform, run_expert, kv_get, kv_set, level, rules, session):
    if not _ns:
        return {"status": "error", "reason": "the handler file is missing on the server"}
    if level not in _ns["LEVELS"]:
        return {"status": "rejected", "problems": ["there is no level %s" % level]}
    text = canonical(rules)[:MAX_RULES]
    cross, ambulance_first, problems = _ns["parse"](text, _ns["LEVELS"][level])
    if problems:
        return {"status": "rejected", "problems": problems[:4]}
    day = time.strftime("%Y-%m-%d")
    with LOCK:
        if RUNS["day"] != day:
            RUNS.update(day=day, by_session={})
        n = RUNS["by_session"].get(session, 0)
        if n >= SESSION_RUNS:
            return {"status": "busy", "reason": "this session checked %d results today; that is the limit" % SESSION_RUNS}
        RUNS["by_session"][session] = n + 1
    name = "traffic_" + hashlib.sha256((level + "|" + text).encode("utf-8")).hexdigest()[:12]
    t0 = time.time()
    # no rules is a valid plan (every crossing keeps its default), but the platform does not save an empty expert
    code = text or "# no rules: every crossing keeps its default"
    try:
        platform("/expert/save", {"name": name, "description": "Rules for the traffic lights of extella.dev/traffic, level %s." % level,
                                  "code": code, "cspl": "traffic", "kwargs": {"level": level}, "global": False}, timeout=60)
    except Exception as err:
        return {"status": "failed", "reason": "the platform did not save the rules: %s" % str(err)[:80]}
    res = run_expert(name, {"level": level})
    out = {"status": res.get("status"), "expert": name, "level": level, "result": res.get("result"),
           "handler_version": res.get("handler_version"), "handler_sha": (res.get("handler_sha") or "")[:12],
           "device": res.get("device") or res.get("host"), "seconds": round(time.time() - t0, 1),
           "problems": res.get("problems") or ([] if res.get("status") == "success" else [res.get("reason") or "the device did not answer"])}
    r = res.get("result")
    if res.get("status") == "success" and r:
        with LOCK:
            table = kv_get(KEY) or {}
            rows = [x for x in table.get(level, []) if x.get("expert") != name]
            rows.append({"expert": name, "rules": text, "mayor": mayor_name(session), "stars": r["stars"], "avgWait": r["avgWait"],
                         "delivered": r["delivered"], "maxQueue": r["maxQueue"], "sha": r["sha"], "at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())})
            rows.sort(key=lambda x: (-x["stars"], x["avgWait"], -x["delivered"], x["at"]))
            rank = next((i + 1 for i, x in enumerate(rows) if x["expert"] == name), None)
            out["rank"], out["of"] = rank, len(rows)
            table[level] = rows[:TOP]
            kv_set(KEY, table, "Rush hour: the best mayors of every level, confirmed by the handler on the server")
    return out
