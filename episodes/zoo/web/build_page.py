"""Собирает game.html: шаблон game_src.html + det.js + sim.js + scene.js (живая карта) + data.json в один файл (страница-артефакт без внешних файлов, кроме шрифтов)."""
import os
H = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(H, "game_src.html"), encoding="utf-8").read()
js = ""
for name in ("det.js", "sim.js"):
    p = os.path.join(H, name)
    if os.path.exists(p):
        js += "\n/* --- " + name + " --- */\n" + open(p, encoding="utf-8").read()
data = open(os.path.join(H, "data.json"), encoding="utf-8").read().replace("</", "<\\/")
scene = open(os.path.join(H, "scene.js"), encoding="utf-8").read()
out = src.replace("/*SIM*/", js).replace("/*SCENE*/", scene).replace("/*AUDIO*/", open(os.path.join(H, "audio.js"), encoding="utf-8").read()).replace("/*DATA*/", data)
open(os.path.join(H, "game.html"), "w", encoding="utf-8").write(out)
print(len(out) // 1024, "КБ")
# локальная копия для проверки в браузере: та же обёртка, что добавляет публикация артефакта
skel = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>'
open(os.path.join(H, "game_local.html"), "w", encoding="utf-8").write(skel + out + "</body></html>")
