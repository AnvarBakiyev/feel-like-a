"""Собирает game.html: шаблон game_src.html + sim.js + data.json в один файл (страница-артефакт без внешних файлов).

    python3 build_data.py && python3 build_page.py
"""
import os
H = os.path.dirname(os.path.abspath(__file__))
rd = lambda f: open(os.path.join(H, f), encoding="utf-8").read()
out = rd("game_src.html").replace("/*SIM*/", rd("sim.js")).replace("/*AUDIO*/", rd("audio.js")).replace("/*DATA*/", rd("data.json").replace("</", "<\\/"))
assert "/*SIM*/" not in out and "/*DATA*/" not in out and "/*AUDIO*/" not in out
open(os.path.join(H, "game.html"), "w", encoding="utf-8").write(out)
print(len(out) // 1024, "КБ")
