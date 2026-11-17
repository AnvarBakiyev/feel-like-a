"""Saves the traffic handler's registrar in an Extella account and registers the handler on the given devices.
Only needed to run the language on your own Extella devices; the game and every check work without it.

Environment: EXTELLA_TOKEN_FILE (file with the API key), EXTELLA_AGENT (agent whose scope keeps the registrar),
EXTELLA_DEVICE (one or more device ids, separated by commas), EXTELLA_API (optional, default https://api.extella.ai/api).
python3 extella/setup_traffic.py
"""
import json, os, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_traffic as b

API = os.environ.get("EXTELLA_API", "https://api.extella.ai/api")
T = open(os.path.expanduser(os.environ["EXTELLA_TOKEN_FILE"])).read().strip()
agent = os.environ["EXTELLA_AGENT"]
devices = [d.strip() for d in os.environ.get("EXTELLA_DEVICE", "").split(",") if d.strip()]


def call(path, body, timeout=150):
    r = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                               headers={"X-Auth-Token": T, "X-Profile-Id": "default", "X-Agent-Id": agent, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())


name, code, sha = b.registrar()
print(name, call("/expert/save", {"name": name, "description": "Registers the traffic language handler on the device it runs on.",
                                  "code": code, "cspl": "fython", "kwargs": {}, "global": False}).get("status"))
for d in devices:
    t0 = time.time()
    out = call("/expert/run", {"name": name, "params": {}, "targets": [d]})
    print("register on", d[:8], round(time.time() - t0, 1), json.dumps(out)[:200])
