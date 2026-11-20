"""Load an Extella expert from its JSON record and call it locally.

Each expert of this episode is stored the way Extella stores it: extella/experts/<name>.json with the
fields name, description, cspl, params and code. The same record lives in the episode's agent on Extella
(install the agent from the Extella market to run it there). Locally the code is executed as a module,
so rechecking the published results needs no key and no network.

    from expert_json import load
    cafe_game_plan = load("cafe_game_plan")
"""
import hashlib, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(HERE, "experts")


def record(name):
    with open(os.path.join(FOLDER, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def sha(name):
    """First 12 hex of sha256 of the code without the trailing newline, as recorded in the runs."""
    return hashlib.sha256(record(name)["code"].rstrip("\n").encode()).hexdigest()[:12]


def load(name):
    r = record(name)
    assert r["name"] == name and r.get("cspl", "fython") == "fython", name
    ns = {"__name__": "expert_" + name}
    exec(compile(r["code"], name + ".json", "exec"), ns)
    return ns[name]
