"""Собирает game.html: шаблон game_src.html + sim.js + data.json в один файл (страница-артефакт без внешних файлов, кроме шрифтов)."""
import os
H = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(H, "game_src.html"), encoding="utf-8").read()
sim = open(os.path.join(H, "sim.js"), encoding="utf-8").read()
data = open(os.path.join(H, "data.json"), encoding="utf-8").read().replace("</", "<\\/")
out = src.replace("/*SIM*/", sim).replace("/*DATA*/", data)
open(os.path.join(H, "game.html"), "w", encoding="utf-8").write(out)
print(len(out) // 1024, "КБ")
# локальная копия для проверки в браузере: та же обёртка, что добавляет публикация артефакта
skel = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>'
open(os.path.join(H, "game_local.html"), "w", encoding="utf-8").write(skel + out + "</body></html>")
