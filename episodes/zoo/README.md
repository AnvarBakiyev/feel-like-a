# A Month at the Zoo

You manage a small zoo in Brooklyn for 30 days. Five sections (sea lion pool, snow leopards, bird house, contact yard, tropical house), a gate, a kiosk, a freezer and a team of keepers on salary. Every evening you decide tomorrow:

- keepers per section for the morning and the afternoon, cashiers and kiosk staff;
- public sea lion feedings (0, 1 or 2 a day; each needs 4 keepers in the pool);
- how much fish and meat to thaw (thawed feed lives one day), what to order (frozen feed Mon and Thu in 10 kg cases, hay on Wednesday in 20 kg bales, produce daily);
- ticket price, free Wednesday afternoon, hiring (a new keeper starts after 7 days), a vet visit (at least two a month);
- answers to event cards: heat advisory, bird flu, snow leopard cubs, a broken pool pump, a sea lion off food, an inspection, a school group, a donor tour, a power cut, a supplier that does not come.

Before the month you pick three settings: scenario (hot July, spring with a cub, bird flu in October), place (quiet park, waterfront, by the subway; this sets how many people come) and team (9, 12 or 15 keepers). That is 27 months; one seed gives one world (weather, events, visitors), whatever you decide.

The rulebook check rejects what a real zoo may not do and says why, in English and Russian: one keeper alone in the snow leopard enclosure, nobody at the pool, a sea lion off food left to wait (9 CFR 3.105), marine mammals outside in a heat advisory without shade (9 CFR 3.103), an order the supplier does not take tomorrow.

**Score** = revenue minus costs, minus $5,000 for each section-day with underfed animals or below the care minimum, minus $15,000 per violation found by an inspection, minus $100,000 for an animal's death, minus $5 per visitor who left the queue. Fixed costs and the city grant are not in the game.

Every real-world number carries a source tag in `world_ny2.json` and `istochniki.md` (Russian letters): И primary source (BLS wages, NOAA Central Park normals, USDA prices, EIA electricity, 9 CFR rules), П retelling, О our estimate. Copies of the downloaded sources are in `sources/`. What we did not find is listed at the end of `istochniki.md`.

## Play

Open `web/play.html` in a browser. Three short lessons (a shift the rulebook rejects, thawing too little, the bird flu card), then a month. A live map shows animals, visitors and keepers; after each day you see the places and profit and loss against your rivals on the same month:

| rival | sees each evening | decides | who turns it into the decision |
|---|---|---|---|
| Qwen 3.5 9B with Extella | a shorter evening text plus the expert's estimates in dollars (price options for tomorrow, card options, keepers needed) | a short plan: feed stock and staffing, each lean, normal or safe | the expert `zoo_game_plan` on Extella computes thaw, orders, shifts and hiring, and itself chooses the ticket price for each day, free Wednesday, public feedings and card answers |
| Claude Opus 5.5 without Extella | the same evening text a person sees, no estimates | the whole decision in the game's JSON | itself; played in Claude Code through `bench/closed.py`, with reasoning |
| Qwen 3.5 9B without Extella | the same evening text | the whole decision in the game's JSON | itself, without reasoning |
| Python program (not AI) | the observation | staffs to the care minimum, thaws the exact ration, orders feed up to the next delivery plus a buffer, two public feedings, vet twice, base price | itself (`policies.careful`) |

The three models play under the same rulebook check; a rejected decision goes back with the reason, up to two corrections an evening.

## Results

27 months (3 scenarios x 3 places x 3 teams), world `ny2`, seed 1, as on [extella.dev/zoo](https://extella.dev/zoo/):

| player | mean score per month | median | first places | places 1 / 2 / 3 / 4 |
|---|---|---|---|---|
| Qwen 3.5 9B with Extella | **$311,671** | $293,612 | **27 of 27** | 27 / 0 / 0 / 0 |
| Python program (no AI) | $263,043 | $260,681 | 0 | 0 / 19 / 8 / 0 |
| Claude Opus 5.5 without Extella | $232,054 | $228,270 | 0 | 0 / 8 / 19 / 0 |
| Qwen 3.5 9B without Extella | -$45,782 | $30,760 | 0 | 0 / 0 / 0 / 27 |

Qwen 3.5 9B with Extella scored above Claude Opus 5.5 in all 27 months, by $79,617 a month on average.

| mean per month | Qwen + Extella | Python | Claude Opus 5.5 | Qwen alone |
|---|---|---|---|---|
| revenue | $613,523 | $522,679 | $491,327 | $427,874 |
| care penalties | -$13,889 | -$17,222 | -$27,778 | -$190,556 |
| inspection | $0 | -$5,000 | -$7,778 | -$63,889 |
| animal deaths | $0 | $0 | $0 | $0 |

Model calls over the 810 evenings: Qwen 3.5 9B with Extella 821 (the expert ran 1,631 times besides); Claude Opus 5.5 861 (760 evenings accepted at once, 49 after one correction, 1 after two); Qwen 3.5 9B without Extella 1,724, and in 185 evenings it gave no valid JSON three times in a row, so nothing changed that evening. The expert set the ticket to $6.48 (50 % below the base $12.95) in 722 evenings and to $25.90 (the top of the allowed range, +100 %) in 65.

Limits of this comparison: one seed per month; Claude Opus 5.5 reasoned before every answer, Qwen did not; the repeat noise of Claude Opus 5.5 was not measured. Predictions written before the runs and the full notes, misses included, are in `PREDSKAZANIYA.md` (Russian).

## Recheck everything

```bash
python3 test_sim.py        # one seed, one month to the byte; hidden state stays hidden; rules and law reject
python3 test_replay.py     # decision logs replay to the recorded score; bad logs raise ValueError; Python 3.12+
python3 web/make_parity.py ny2 && node web/parity.mjs   # browser sim.js equals sim.py to the last digit
python3 verify.py          # every published number from the recorded runs (a few seconds)
```

`verify.py` needs no keys or network. For every evening of every month it rebuilds the prompt each model saw and compares it with the recorded one, turns the recorded answer into the decision again (for Extella: the model's plan goes through the expert code `extella/plan_expert.py`, run locally, and gives exactly the decision the expert returned on Extella), replays all four players to their scores, and checks the table above and the data inside `web/play.html`.

To play new months against real models: `run_ny2_all.py` (Qwen 3.5 9B through OpenRouter, keys from environment variables, see `extella/llm.py` and `extella/extella_call.py`), `bench/opus.sh` (a model in Claude Code plays through `bench/closed.py start|act|result`).

## Files

`sim.py` simulator (`det.py` shared generator), `replay.py` score from a decision log, `policies.py` and `drivers.py` simple programs, `world_ny2.json` the world of the published runs (`world_ny.json` the earlier balance), `cards_ny.json` event card texts, `verify.py` full recheck, `web/` browser game (`sim.js` port, `scene.js` live map, `audio.js`, `build_data.py` and `build_page.py` rebuild the page data and a one-file page), `extella/` Extella side (`plan_expert.py` the expert, `player.py` the evening loop, `runs/ny2-page/` the 27 recorded months with prompts and raw answers), `bench/` rivals without Extella (`common.py` the evening text, `closed.py` the Claude Code harness, `noext.py` the small model, `runs/` their 54 recorded months).

---

# Месяц зоопарка

Тридцать дней управляешь небольшим зоопарком в Бруклине: смотрители по секциям, разморозка и заказ кормов, цена билета, бесплатная среда, найм, ветеринар, карточки событий. Проверка отказывает с причиной, как отказал бы закон и устав настоящего зоопарка. Открой `web/play.html`: три урока, потом месяц против Qwen 3.5 9B с Extella, Claude Opus 5.5, Qwen 3.5 9B без Extella и программы на Python на том же зерне.

На 27 месяцах Qwen 3.5 9B с Extella первый во всех 27: в среднем $311 671 за месяц, программа на Python $263 043, Claude Opus 5.5 без Extella $232 054, Qwen 3.5 9B без Extella −$45 782. `python3 verify.py` пересчитывает всё это из записанных решений без ключей и сети. Предсказания до прогонов и итоги: `PREDSKAZANIYA.md`, источники цифр: `istochniki.md`.
