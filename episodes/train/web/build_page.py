"""Собирает game.html: шаблон game_src.html + sim.js + data.json в один файл (страница-артефакт без внешних файлов)."""
import os
H = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(H, "game_src.html"), encoding="utf-8").read()
sim = open(os.path.join(H, "sim.js"), encoding="utf-8").read()
scene = open(os.path.join(H, "scene.js"), encoding="utf-8").read()
cab = open(os.path.join(H, "cab.js"), encoding="utf-8").read()
data = open(os.path.join(H, "data.json"), encoding="utf-8").read().replace("</", "<\\/")
out = src.replace("/*SIM*/", sim).replace("/*SCENE*/", scene).replace("/*CAB*/", cab).replace("/*DATA*/", data)
open(os.path.join(H, "game.html"), "w", encoding="utf-8").write(out)
print(len(out) // 1024, "КБ")
