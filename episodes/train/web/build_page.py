"""Собирает game.html: шаблон game_src.html + sim.js + data.json в один файл (страница-артефакт без внешних файлов)."""
import os
H = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(H, "game_src.html"), encoding="utf-8").read()
sim = open(os.path.join(H, "sim.js"), encoding="utf-8").read()
scene = open(os.path.join(H, "scene.js"), encoding="utf-8").read()
cab = open(os.path.join(H, "cab.js"), encoding="utf-8").read()
data = open(os.path.join(H, "data.json"), encoding="utf-8").read().replace("</", "<\\/")
three = open(os.path.join(H, "vendor", "three.min.js"), encoding="utf-8").read()
t3 = open(os.path.join(H, "train3d.js"), encoding="utf-8").read()
d3 = open(os.path.join(H, "data3d.json"), encoding="utf-8").read()
import base64
au = open(os.path.join(H, "audio.js"), encoding="utf-8").read()
mus = base64.b64encode(open(os.path.join(H, "audio", "music_loop.mp3"), "rb").read()).decode()
out = src.replace("/*AUDIO*/", au).replace("/*MUSIC*/", mus).replace("/*THREE*/", three).replace("/*TRAIN3D*/", t3).replace("/*DATA3D*/", d3).replace("/*SIM*/", sim).replace("/*SCENE*/", scene).replace("/*CAB*/", cab).replace("/*DATA*/", data)
open(os.path.join(H, "game.html"), "w", encoding="utf-8").write(out)
print(len(out) // 1024, "КБ")
