"""Общее для бенчмарка зоопарка: набор месяцев, текст вечера без эксперта, решение в формате игры.

Модели без Extella видят то же, что человек на странице: счёт, вчерашний день, прогноз, склад, поставщиков,
штат и смены, минимум ухода, цену, карточки. Оценок эксперта в долларах здесь нет: в этом и состоит сравнение.
Дни считаются с нуля, как в журнале призрака, чтобы тексты совпадали по смыслу.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import sim  # noqa: E402

# мир: "ny" прежний, "ny2" с балансом 15.11 (теснота, эластичность 0,6, сильная бесплатная среда)
WORLD = os.environ.get("ZOO_WORLD", "ny")
W_PUB = sim.load_world(WORLD)

EP = json.load(open(os.path.join(ROOT, "episode.json"), encoding="utf-8"))
CARDS = json.load(open(os.path.join(ROOT, "cards_ny.json"), encoding="utf-8"))
WD = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
WX = {"clear": "ясно", "rain": "дождь", "hot": "жара от 90 °F", "advisory": "Heat Advisory"}
SEC = {"pool": "бассейн", "cats": "барсы", "birds": "птичий дом", "yard": "контактный двор", "tropic": "тропический дом"}
SUP = {"frozen": "мороженые корма", "hay": "сено", "produce": "овощи и фрукты"}
NOTE = {"advisory": "Heat Advisory", "closed_midday": "уличные вольеры закрыты днём", "cubs": "котята",
        "hpai": "птичий грипп", "pool_closed_pm": "бассейн закрыт днём", "tropic_closed": "тропический дом закрыт",
        "cubs_lost": "котят потеряли"}

SYSTEM = """Ты управляющий небольшого зоопарка в Бруклине на 30 дней. Каждый вечер ты сам решаешь, что будет завтра: смены по секциям, разморозка, заказы кормов, цена билета, кормления при публике, найм, ветеринар, ответы на карточки событий. Правила проверяет Проверка игры: решение, нарушающее правило, отклоняется с причиной.
Счёт = выручка минус расходы, минус $5 000 за каждый день секции, где животные недокормлены или без минимума ухода, минус $15 000 за нарушение инспекции, минус $100 000 за гибель животного, минус $5 за посетителя, ушедшего из очереди. Благополучие животных важнее денег.
Как устроен зоопарк: пять секций, у каждой свой минимум ухода на утро и день, он показан в вечере. В вольер снежных барсов входят вдвоём, поэтому утром там нужны двое. В бассейне и контактном дворе кто-то нужен всегда. На кассе нужен хотя бы один человек, иначе зоопарк не откроется. В одной секции не больше 6 смотрителей в половину дня. Смотрители на окладе 40 часов в неделю: лишние часы оплачиваются в полтора раза, а недобранные всё равно оплачиваются.
Рыба и мясо мороженые: размораживать надо накануне, размороженное живёт сутки, остаток выбрасывается. Мороженые корма возят по понедельникам и четвергам коробками по 10 кг, минимум на $300, морозилка на 600 кг. Сено возят по средам тюками по 20 кг, минимум 500 кг. Овощи и фрукты возят каждый день, минимум 10 кг, живут 3 дня.
Кормление морских львов при публике держат двое: в бассейне в эту половину дня нужно 4 смотрителя. Кормление поднимает пожертвования и репутацию. Репутация множит число посетителей.
Ветеринар должен приехать не меньше двух раз за месяц. Нанятый смотритель выходит через 7 дней.
Ответ: только JSON такого вида (любое поле можно опустить, опущенное остаётся прежним):
{"schedule": {"0": {"keepers": {"pool": [3,3], "cats": [2,1], "birds": [2,1], "yard": [2,2], "tropic": [1,1]}, "cashiers": [2,2], "kiosk": [2,2], "shows": 2}}, "thaw": {"fish": 34.4, "meat": 2.7}, "orders": {"frozen": {"fish": 210, "meat": 20}, "hay": {"hay": 500}, "produce": {"produce": 40}}, "price": 12.95, "free_wed": false, "hire": 0, "vet_visit": false, "choices": {"pump_7": "repair_now"}, "why_ru": "...", "why_en": "..."}
schedule: раскладка по дням недели, ключ это номер дня недели от 0 (пн) до 6 (вс). Достаточно прислать тот день, который завтра: остальные дни останутся как есть. Два числа в каждом поле это утро и день.
thaw: сколько килограммов достать из морозилки на завтра.
orders: заказ на завтра. Ключ это поставщик (frozen, hay, produce), значение это объект «товар: килограммы». У frozen товары fish и meat, у hay товар hay, у produce товар produce: {"hay": {"hay": 500}} значит 500 кг сена. Поставщик примет заказ, только если возит завтра.
price: цена взрослого билета в долларах. free_wed: бесплатный вход в среду днём.
hire: нанять от 0 до 3 смотрителей. vet_visit: вызвать ветеринара на завтра.
choices: ответ на открытые карточки. Ключ это id карточки из списка ниже, в квадратных скобках, значение это вариант оттуда же. Без ответа сработает вариант по умолчанию; вариант, запрещённый законом, Проверка отклонит.
why_ru и why_en: одна короткая фраза до 12 слов о главном решении вечера."""

if W_PUB.get("crowding"):
    _cr = W_PUB["crowding"]; _fw = W_PUB["free_wed"]
    SYSTEM += ("\nЦена и толпа: дешевле билет, больше людей; дороже, меньше людей, но каждый платит больше. "
               "Без толчеи зоопарк вмещает %d человек в половину дня. Сверх этого люди тратят на еду и сувениры меньше "
               "(до %d %%) и репутация падает. Бесплатный вход в среду после 14:00 приводит примерно в %.1f раза больше людей, "
               "билетов они не покупают, а жертвуют в %d раза больше. Вечером в тексте показана ожидаемая заполненность завтрашнего дня."
               % (_cr["comfort_per_half"], int(_cr["spend_drop_max"] * 100), _fw["afternoon_mult"], int(_fw.get("donation_mult", 1)))).replace("в 2.2 раза", "в 2,2 раза")


def money(x):
    return ("−$" if x < 0 else "$") + "{:,}".format(int(abs(x) + 0.5)).replace(",", " ")


def kg(x):
    return ("%.1f" % x).rstrip("0").rstrip(".")


def card_text(c):
    K = CARDS[c["kind"]]
    t = K["ru"]["text"].replace("{day2}", str(c["day"] + 1)).replace("{day}", str(c["day"]))
    opts = ["%s = %s" % (o, K["options"][o]["ru"]) for o in c["options"]]
    ch = " Уже выбрано: %s." % c["chosen"] if c.get("chosen") else ""
    return "[%s] %s. %s Варианты: %s. По умолчанию %s. Решить до вечера дня %d.%s" % (
        c["id"], K["ru"]["title"], t, "; ".join(opts), c["default"], c["decide_by_evening_of"], ch)


def evening_text(g, obs):
    t = obs["day"]; y = obs["yesterday"]
    L = ["Вечер перед днём %d из %d. Завтра %s, %s." % (t, obs["days_total"], WD[obs["wd"]], WX[obs["forecast"][0]["weather"]])]
    L.append("Счёт месяца сейчас %s. Репутация %.2f. Дней секций с нарушением ухода за месяц: %d. Ветеринар был %d раз из %d обязательных." % (
        money(g.score()["score"]), obs["reputation"], obs["counts"]["section_violation_days"], obs["vet_visits"], obs["vet_visits_min"]))
    if y:
        v = ", ".join("%s: %s" % (SEC[s], ", ".join(y["violations"][s])) for s in y["violations"]) if y.get("violations") else ""
        L.append("Сегодня: пришло %d, ушли из очереди %d, выручка %s, кормлений при публике %d%s." % (
            y["visitors"], y["queue_lost"], money(y["revenue"]), y["shows"], (". Нарушения ухода: " + v) if v else ""))
        fed = ", ".join("%s %.0f %%" % (SEC[s], 100 * y["fed"][s]) for s in sim.SECTIONS if y["fed"][s] < 0.999)
        if fed:
            L.append("Накормлены не полностью: %s." % fed)
        if y.get("events"):
            L.append("События дня: %s." % ", ".join(y["events"]))
    fc = []
    for f in obs["forecast"]:
        n = ", ".join(NOTE.get(x, x) for x in f["notes"])
        fc.append("день %d (%s, %s%s): %d, разброс %d-%d" % (f["day"], WD[f["wd"]], WX[f["weather"]], (", " + n if n else ""),
                  sum(f["visitors"]), sum(f["low"]), sum(f["high"])))
    L.append("Прогноз посетителей: " + "; ".join(fc) + ".")
    if W_PUB.get("crowding"):
        f0 = obs["forecast"][0]; cap = W_PUB["crowding"]["comfort_per_half"]
        L.append("Заполненность завтра при нынешней цене: утро %d %%, день %d %% от вместимости." % (
            round((f0["low"][0] + f0["high"][0]) / 2 / cap * 100), round((f0["low"][1] + f0["high"][1]) / 2 / cap * 100)))
    st = obs["stock"]; nd = obs["need_kg_per_day"]
    L.append("Склад: в морозилке рыбы %s кг, мяса %s кг; разморожено на завтра рыбы %s кг, мяса %s кг; сена %s кг; овощей и фруктов %s." % (
        kg(st["freezer"]["fish"]), kg(st["freezer"]["meat"]), kg(st["thawed_for_tomorrow"]["fish"]), kg(st["thawed_for_tomorrow"]["meat"]),
        kg(st["hay"]), ", ".join("%s кг годны до дня %d" % (kg(a), b) for a, b in st["produce"]) or "нет"))
    L.append("Норма на день: рыба %s кг, мясо %s кг, сено %s кг, овощи и фрукты %s кг. Морозилка вмещает %d кг, сенник %d кг." % (
        kg(nd["fish"]), kg(nd["meat"]), kg(nd["hay"]), kg(nd["produce"]), st["freezer_kg"], st["hay_store_kg"]))
    sup = []
    for s, S in obs["suppliers"].items():
        lim = []
        if S.get("min_order"):
            lim.append("минимум $%d" % S["min_order"])
        if S.get("min_kg"):
            lim.append("минимум %d кг" % S["min_kg"])
        if S.get("case_kg"):
            lim.append("коробки по %d кг" % S["case_kg"])
        if S.get("bale_kg"):
            lim.append("тюки по %d кг" % S["bale_kg"])
        sup.append("%s (%s): возит %s%s, %s" % (SUP.get(s, s), s, ", ".join(WD[d] for d in S["days"]),
                   ", завтра привезёт" if S["delivers_tomorrow"] else ", завтра не возит",
                   "; ".join("%s $%.2f за кг" % (k, v) for k, v in S["prices_kg"].items()) + ((", " + ", ".join(lim)) if lim else "")))
    L.append("Поставщики: " + ". ".join(sup) + ".")
    now = sum(1 for s in obs["staff"] if s["start"] <= t)
    soon = [s for s in obs["staff"] if s["start"] > t]
    L.append("Смотрителей в штате %d%s. Завтра болеет %d." % (
        now, (" (ещё %d выйдут с дня %d)" % (len(soon), min(s["start"] for s in soon))) if soon else "", obs["sick_tomorrow"]))
    L.append("Минимум ухода на завтра (утро/день): " + ", ".join("%s %d/%d" % (SEC[s], obs["min_tomorrow"][s][0], obs["min_tomorrow"][s][1]) for s in sim.SECTIONS) + ".")
    r = obs["schedule"][str(obs["wd"])]
    L.append("Сейчас на этот день недели стоит: " + ", ".join("%s %d/%d" % (SEC[s], r["keepers"][s][0], r["keepers"][s][1]) for s in sim.SECTIONS) +
             "; кассы %d/%d; киоски %d/%d; кормлений %d." % (r["cashiers"][0], r["cashiers"][1], r["kiosk"][0], r["kiosk"][1], r.get("shows", 0)))
    L.append("Билет взрослый сейчас $%.2f, бесплатная среда %s." % (obs["price"], "включена" if obs["free_wed"] else "выключена"))
    if obs["cards"]:
        L.append("Карточки событий:")
        for c in obs["cards"]:
            L.append("- " + card_text(c))
    else:
        L.append("Открытых карточек нет.")
    L.append("Ответь JSON.")
    return "\n".join(L)


def to_decision(p, obs=None):
    """Ответ модели -> решение для Проверки. Лишние поля отбрасываются, форму проверяет сама игра.

    Неполная раскладка смен достраивается до семи дней недели из той, что стоит сейчас: Проверка требует все семь,
    а игрок на странице правит только завтрашний день. Чужие дни при этом не меняются.
    """
    out = {}
    for k in ("schedule", "thaw", "orders", "choices"):
        if isinstance(p.get(k), dict):
            out[k] = p[k]
    if obs is not None and isinstance(out.get("schedule"), dict):
        full = json.loads(json.dumps(obs["schedule"]))
        for w, row in out["schedule"].items():
            if str(w) in full and isinstance(row, dict):
                full[str(w)] = row
        out["schedule"] = full
    if isinstance(p.get("price"), (int, float)) and not isinstance(p.get("price"), bool):
        out["price"] = p["price"]
    if isinstance(p.get("free_wed"), bool):
        out["free_wed"] = p["free_wed"]
    if isinstance(p.get("vet_visit"), bool):
        out["vet_visit"] = p["vet_visit"]
    for k in ("hire", "fire"):
        if isinstance(p.get(k), int) and not isinstance(p.get(k), bool):
            out[k] = p[k]
    return out


def bench_set():
    """Месяцы набора: (сценарий, место, команда, зерно)."""
    B = EP["bench"]
    return [(c["scenario"], c["place"], c["team"], s) for s in B["seeds"] for c in B["combos"]]
