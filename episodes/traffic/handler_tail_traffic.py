

def traffic(code="", filtered_source_code="", func_name="", **extra):
    import platform, socket, time
    params = dict(extra)
    inner = extra.get("kwargs")
    if isinstance(inner, dict):
        params.update(inner)
    level = str(params.get("level") or "district")
    base = {"language": "traffic", "expert": func_name, "handler_version": HANDLER_VERSION, "handler_sha": HANDLER_SHA,
            "host": socket.gethostname(), "os": platform.system() + " " + platform.machine(), "model_calls": 0, "level": level}
    if level not in LEVELS:
        return dict(base, status="rejected", problems=["there is no level %s; the levels are %s" % (level, ", ".join(sorted(LEVELS)))])
    t0 = time.time()
    out = simulate(level, code or filtered_source_code or "")
    if out["problems"]:
        return dict(base, status="rejected", problems=out["problems"][:6])
    return dict(base, status="success", problems=[], result=out["result"], seconds_simulating=round(time.time() - t0, 2))
