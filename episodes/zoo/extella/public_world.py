"""Открытые цифры зоопарка для эксперта: то же, что игрок видит на странице правил. Скрытого (исходы, шум, дни событий) здесь нет."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))


def public_world(name="ny"):
    W = json.load(open(os.path.join(HERE, "..", "world_" + name + ".json"), encoding="utf-8"))
    return {k: v for k, v in W.items() if k not in ("scenarios",) and not k.startswith("_")}
