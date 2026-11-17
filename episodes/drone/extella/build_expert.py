"""Собирает один файл эксперта drone_plan.py из sim.py + polet.py + миров городов.
Первая функция файла drone_plan (платформа вызывает первую функцию). Обратной косой черты в файле быть не должно:
с ней регистрация обработчика падает («'str' object is not callable»)."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def body(path, drop):
    s = open(os.path.join(ROOT, path), encoding="utf-8").read()
    s = re.sub(r'^""".*?"""' + chr(10), "", s, count=1, flags=re.S)
    return chr(10).join(l for l in s.splitlines() if not any(l.startswith(x) for x in drop))


data = {}
for city in ("almaty", "dubai", "rotterdam"):
    w = json.load(open(os.path.join(ROOT, "world", city + ".json"), encoding="utf-8"))
    m = json.load(open(os.path.join(ROOT, "world", city + "_map.json"), encoding="utf-8"))
    m["terrain"]["z"] = [round(z, 1) for z in m["terrain"]["z"]]
    data[city] = [w, m]

head = '''def drone_plan(text="", seed=1, city="rotterdam", mode="check"):
    """Эпизод «курьер дронов»: Проверка замысла на языке полёта (mode=check) или смена по замыслу в мире зерна (mode=run)."""
    if mode == "check":
        ok, errs, fc, plan = check(text, Game(seed, city))
        return {"ok": ok, "errors": errs, "forecast": fc}
    g, disp, decisions = run(text, seed, city)
    return {"score": g.score(), "journal": g.journal, "events": g.events, "decisions": decisions,
            "refusals": disp.refusals, "flights": disp.launched, "day": g.W["day"]}


import json, math, re
'''

sim_src = body("sim.py", ("import json, math, os",))
sim_src = sim_src.replace('H = os.path.dirname(os.path.abspath(__file__))' + chr(10), "")
old = chr(10).join([
    'def load(city):',
    '    w = json.load(open(os.path.join(H, "world", city + ".json"), encoding="utf-8"))',
    '    m = json.load(open(os.path.join(H, "world", city + "_map.json"), encoding="utf-8"))',
    '    return w, m'])
new = chr(10).join([
    'def load(city):',
    '    w, m = DATA[city]',
    '    return json.loads(json.dumps(w)), json.loads(json.dumps(m))'])
assert old in sim_src, "не нашёл load() в sim.py"
sim_src = sim_src.replace(old, new)

pz = body("polet.py", ("import math", "import re", "import sim"))
for a, b in (("sim.Game", "Game"), ("sim.ALTS", "ALTS"), ("sim.SPEEDS", "SPEEDS"), ("sim.CITIES", "CITIES"), ("sim.SHIFT_S", "SHIFT_S"),
             ("sim.CRUISE_A", "CRUISE_A"), ("sim.CRUISE_B", "CRUISE_B"), ("sim.Rng", "Rng"), ("sim.fnv", "fnv"), ("sim.D", "D")):
    pz = pz.replace(a, b)
assert "sim." not in pz, [l for l in pz.splitlines() if "sim." in l][:3]

src = head + chr(10) + "DATA = json.loads(" + repr(json.dumps(data, ensure_ascii=False)) + ")" + chr(10) * 2 + sim_src + chr(10) * 2 + pz + chr(10)
assert chr(92) not in src, "в файле есть обратная косая черта"
open(os.path.join(HERE, "drone_plan.py"), "w", encoding="utf-8").write(src)
print(len(src), "знаков,", len(src.encode()), "байт")
