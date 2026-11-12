"""Собирает один файл эксперта train_plan.py из sim.py + poezdka.py + данных участков и поездов.
Первая функция файла train_plan (платформа вызывает первую функцию)."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

def body(path, drop_imports):
    s = open(os.path.join(ROOT, path), encoding="utf-8").read()
    s = re.sub(r'^""".*?"""\n', "", s, count=1, flags=re.S)
    out = []
    for line in s.splitlines():
        if any(line.startswith(x) for x in drop_imports):
            continue
        out.append(line)
    return "\n".join(out)

data = {"lines": {}, "trains": {}}
for k in ("lines", "trains"):
    for f in sorted(os.listdir(os.path.join(ROOT, k))):
        if f.endswith(".json"):
            data[k][f[:-5]] = json.load(open(os.path.join(ROOT, k, f), encoding="utf-8"))

head = '''def train_plan(text, seed, line_id, mode="check"):
    """Эпизод «машинист»: Проверка плана на языке поездки (mode=check) или рейс по плану в мире зерна (mode=run)."""
    if mode == "check":
        ok, errs, fc, plan = check(text, Game(seed, line_id))
        return {"ok": ok, "errors": errs, "forecast": fc}
    g = run(text, seed, line_id)
    return {"score": g.score(), "journal": g.journal, "decisions": g.decisions, "world": g.W}


import json, math, re
'''
sim_src = body("sim.py", ("import json, math, os",))
sim_src = sim_src.replace('HERE = os.path.dirname(os.path.abspath(__file__))\n', "")
sim_src = re.sub(r"def load\(kind, name\):\n    return json.load\(open\(os.path.join\(HERE, kind, name \+ \".json\"\), encoding=\"utf-8\"\)\)",
                 "def load(kind, name):\n    return json.loads(json.dumps(DATA[kind][name]))", sim_src)
pz = body("poezdka.py", ("import re", "import sim"))
pz = pz.replace("sim.Game", "Game").replace("sim.G", "G").replace("sim.DT", "DT").replace("sim.clock", "clock")
src = head + "\nDATA = json.loads(" + repr(json.dumps(data, ensure_ascii=False)) + ")\n\n" + sim_src + "\n\n" + pz + "\n"
open(os.path.join(HERE, "train_plan.py"), "w", encoding="utf-8").write(src)
print(len(src), "bytes")
