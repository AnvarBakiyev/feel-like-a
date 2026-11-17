"""Открытые цифры города для эксперта: то же, что игрок видит на странице правил. Скрытого (исходы событий, шум) здесь нет."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP = ("scenarios", "weather", "holidays", "events", "streets", "money", "_tags")


def public_city(street, city="ny"):
    C = json.load(open(os.path.join(HERE, "..", "city_%s.json" % city), encoding="utf-8"))
    P = {k: v for k, v in C.items() if k not in SKIP and not k.startswith("_")}
    P["rent_month"] = C["streets"][street]["rent_month"]
    return P
