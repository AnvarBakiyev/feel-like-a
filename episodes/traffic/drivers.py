"""Simple players, not AI. A driver is driver(obs, game) -> decision or None; here the only decision is the rules.

keep: writes nothing, every crossing keeps what the level starts with (stops, a few lights).
plan: a rule of thumb from what the player sees: lights where streets meet in the middle, the busier axis as the main
      street elsewhere, box junctions everywhere, ambulance first when ambulances come.
"""


def keep(obs, game):
    return {"rules": ""} if obs["step"] == 0 else None


def plan(obs, game):
    if obs["step"] != 0:
        return None
    cols, rows, names = obs["cols"], obs["rows"], obs["crossings"]
    f = obs["flows"]
    main = "east-west" if f.get("W", 0) + f.get("E", 0) >= f.get("N", 0) + f.get("S", 0) else "north-south"
    # crossings nearest the middle of the grid first
    cx, cy = (cols - 1) / 2, (rows - 1) / 2
    order = sorted(range(len(names)), key=lambda k: (abs(k % cols - cx) + abs(k // cols - cy), k))
    lit = set(names[k] for k in order[:obs["lights"]])
    lines = ["# rule of thumb"]
    for n in names:
        if n in lit:
            lines.append("%s: light, longest queue, min 5, max 20, box" % n)
        else:
            lines.append("%s: main %s, box" % (n, main))
    if obs["ambulances"]:
        lines.append("ambulance first")
    return {"rules": "\n".join(lines) + "\n"}
