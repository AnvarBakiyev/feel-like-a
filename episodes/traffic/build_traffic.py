"""Builds the traffic handler: traffic_core.py + the levels taken from web/traffic_core.js + handler_tail_traffic.py,
and its registrar. python3 build_traffic.py"""
import hashlib, json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
NL = chr(10)
SIM_FIELDS = ("cols", "rows", "seconds", "seed", "lights", "start", "flows", "turns", "goals", "ducks", "burst", "ambulances")


def levels_from_browser():
    js = "import('./web/traffic_core.js').then(m => process.stdout.write(JSON.stringify(m.LEVELS)))"
    data = json.loads(subprocess.run(["node", "-e", js], cwd=HERE, capture_output=True, text=True, check=True).stdout)
    return {k: {f: v[f] for f in SIM_FIELDS if f in v} for k, v in data.items()}


def handler_text(version="v1"):
    core = open(os.path.join(HERE, "traffic_core.py"), encoding="utf-8").read()
    tail = open(os.path.join(HERE, "handler_tail_traffic.py"), encoding="utf-8").read()
    levels = "LEVELS = " + json.dumps(levels_from_browser(), sort_keys=True).replace("true", "True").replace("false", "False").replace("null", "None") + NL
    head = NL + levels + "HANDLER_VERSION = %s%s" % (json.dumps("traffic " + version), NL)
    body = core + head + tail
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    text = core + head + "HANDLER_SHA = " + json.dumps(sha) + NL + tail
    assert chr(92) not in text and "'" * 3 not in text, "handler must have no backslashes or triple single quotes"
    return text, sha


def registrar(version="v1"):
    text, sha = handler_text(version)
    name = "demo_register_traffic_" + version
    code = ('$extens("include.py")' + NL + 'include("import os", [])' + NL + NL + "def %s() -> dict:" % name + NL +
            "    import disnet" + NL + "    handler_code = '''" + text + "'''" + NL +
            '    d = disnet.Disnet(url="https://disnet.extella.ai")' + NL +
            '    envelope = {"filtered_source_code": "", "func_name": "", "args": None, "kwargs": None, "cspl": "traffic", "response_format": None}' + NL +
            '    d.container(code=handler_code, func_name="traffic", container_path="traffic", args=None, kwargs=envelope, cspl_type="fython", push=False)' + NL +
            '    return {"status": "success", "registered": "traffic", "version": %s, "sha": %s, "bytes": len(handler_code)}' % (json.dumps(version), json.dumps(sha)) + NL)
    return name, code, sha


if __name__ == "__main__":
    name, code, sha = registrar()
    open(os.path.join(HERE, "extella", name + ".fython"), "w", encoding="utf-8").write(code)
    open(os.path.join(HERE, "traffic_handler_v1.py"), "w", encoding="utf-8").write(handler_text()[0])
    print(name, sha)
