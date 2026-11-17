# Feel like a drone courier

You dispatch a two-hour delivery shift (13:00 to 15:00) with three cargo octocopters from one depot. Orders of 2 to 30 kg appear during the shift, each due 25 to 50 minutes after it appears. For every flight you choose the drone, the orders (up to five stops), altitude (30, 60, 100 or 120 m), speed (eco 12 m/s or fast 18 m/s) and whether to stop at a charging pad. The flight itself is automatic. You answer for what a real dispatcher answers for: will the order arrive on time, and will the drone come back.

| city | what makes it hard |
|---|---|
| Almaty | frost down to −11 °C cuts battery capacity; points up to 2 300 m above sea level, in thin air |
| Dubai | up to 46 °C: the battery limits power and a heavy load cannot be lifted |
| Rotterdam | strong sea wind and gusts: easy on the way out, a headwind on the way back |

Each city has 10 real days of 2025 (seeds 1 to 10). The drone uses the published figures of a 95 kg cargo octocopter (DJI FlyCart 30 class, no brand in the game): 65 kg empty, up to 40 kg of cargo, 3 969 Wh, wind limit 12 m/s. Every number in `sim.py` and `world/` carries a source tag (И source, П recalculated from a source, О our estimate). Weather and terrain sources and their terms: `DATA-SOURCES.md`.

The player sees the map, the hourly wind forecast at 30, 60 and 120 m, the wind where the drones are, their charge and the orders that have already arrived. Hidden: the real wind (the forecast is off by up to ±18 % in strength and ±18° in direction) and gusts every 10 seconds. Score: 1000, +40 per delivered order, −1 per 10 s late, −60 per undelivered order, −250 per forced landing off a pad, −600 per lost drone, −10 per pad stop, ±2 per percent of energy against a reference flight.

## Play

Open `web/play.html` in a browser (no server needed). Five one-minute drills teach headwind, mountain pads, heat and two orders in one flight; then pick a city and a day. On the same shift (same weather, same orders) you can show the ghost of any rival or watch how Extella flies it.

| rival | sees | decides | who flies |
|---|---|---|---|
| Qwen 3.5 9B with Extella | the briefing: map, hourly forecast, drone figures, score rules | 1 to 4 times, all before the shift | the model writes an intent in a flight language (lines such as `speed fast`, `orders per flight 2`, `pad 3 if charge below 35`); Extella's handler checks it against the forecast and answers with errors or advice, then flies the shift and computes each round trip before take-off |
| Qwen 3.5 9B without Extella | the same briefing | once, before the shift | rules per point in JSON (altitude, speed, load limit, pad, skip), executed literally; nobody checks the charge |
| Claude Opus 5 without Extella | the same briefing | once, before the shift | the same kind of JSON rules, worked out from the briefing without a simulator or feedback, executed literally |
| careful program (not AI) | the live shift | every second | computes the round trip on the forecast and adds a pad stop when needed |
| simple program (not AI) | the live shift | every second | next order to the first free drone, fast, 60 m, ignores wind and charge |

Model ids as recorded in the run files: `qwen3.5:9b` (Ollama on a laptop, temperature 0, seed 7) and `claude-opus-5`. A large model deciding during the shift with feedback was not run for this episode.

## Results

30 shifts (10 days × 3 cities, 414 orders), the same weather and orders for everyone. Average score per city:

| rival | Almaty | Dubai | Rotterdam | delivered | forced landings off a pad | lost |
|---|---|---|---|---|---|---|
| Claude Opus 5 without Extella | 1138 | 779 | 952 | 242 of 414 | 4 | 0 |
| **Qwen 3.5 9B with Extella, stage 4** | **1084** | **803** | **975** | **242 of 414** | **0** | **0** |
| Qwen 3.5 9B with Extella, stage 3 | 1014 | 674 | 983 | 235 of 414 | 0 | 0 |
| Qwen 3.5 9B with Extella, stage 2 | 1014 | 599 | 983 | 235 of 414 | 3 | 0 |
| careful program | 918 | 440 | 600 | 221 of 414 | 15 | 0 |
| Qwen 3.5 9B with Extella, stage 1 | 665 | 577 | 708 | 189 of 414 | 5 | 0 |
| handler with an empty plan (not AI) | 559 | 447 | 567 | 154 of 414 | 7 | 0 |
| simple program | 246 | 399 | 853 | 222 of 414 | 48 | 0 |
| Qwen 3.5 9B without Extella | 53 | −38 | 640 | 199 of 414 | 66 | 0 |

The stages are four versions of the flight language and its check, each run on all 30 shifts with the same model:

1. The model writes the intent; the check refuses lines that lose points by the forecast. Qwen 3.5 9B wrote the same cautious intent in all 30 shifts (60 m, eco speed, one order per flight, reserve 20 %, a pad, no farther than 8 km; only the pad number and one line differed), and the check accepted it every time.
2. The check also names the line that would gain more than 60 points both on the forecast and on its worst edge (+18 % wind), and the model gets one more turn with that advice. The advice came in 27 shifts; in 24 the model's new intent scored higher by the forecast and was flown.
3. A wind reserve: if the forecast plus its declared error passes the 12 m/s limit in any hour of the shift, the handler does not fly that day. Exactly one shift changed (Dubai, 7 May 2025: −710 to 40).
4. Lines per point (`point 3 load up to 12 kg`, `skip point 5`) and advice as a chain of up to three lines. This is the version the page shows.

The same Qwen 3.5 9B with and without Extella at stage 1: +612 in Almaty, +615 in Dubai, +68 in Rotterdam. Gap to Claude Opus 5, sum of the three city averages: 918 at stage 1, 273 at stage 2, 198 at stage 3, 7 at stage 4. At stage 4, shift by shift, Extella scored higher than Claude Opus 5 in 12 shifts, lower in 13 and the same in 5. In Rotterdam on days 1, 7 and 9 the wind at the depot is above 12 m/s for the whole shift, every take-off is refused and all rivals score the same.

Predictions were written before the runs and kept with the misses: `POSTANOVKA.md` (D1 to D5, the setup before the runs) and `PREDSKAZANIYA.md` (results and later predictions), both in Russian.

## Recheck everything

```bash
python3 test_sim.py        # seed, hidden state, rejections with a reason, heat and wind, replay, plausibility against DJI figures
python3 test_polet.py      # flight language, check, the handler keeps the rules
python3 test_replay.py     # a decision log replays to the same score; forgeries are rejected
cd web && python3 make_parity.py && node parity.mjs   # browser sim.js equals sim.py to the last digit (45 traces)
node web/check_data.mjs    # every rival on the page, replayed in sim.js, gives its recorded score
python3 verify.py          # every published score recomputed from recorded decisions
```

No keys or network needed. `verify.py` replays all 150 recorded shifts, rebuilds the prompt each model saw from the world of its seed, runs each Extella plan through the exact expert version recorded in the run (by sha) and gets the same decisions, re-runs the stage 4 plan check of every model call (same verdict, errors and advice), executes the rules of the models without Extella literally, re-runs the programs, checks `web/data.json` and compares the table above number by number. `python3 verify.py --full` also re-runs the plan checks of stages 1 to 3.

## Files

- `sim.py` simulator (1 s step; hover power grows as mass^1.25 and with thinner air; forward flight curve; wind vector; frost and heat on the battery; `Game` and `replay`), `replay.py` strict replay for leaderboards, `drivers.py` the two programs, `polet.py` flight language, check and handler.
- `world/` 10 days of hourly weather per city and the city maps (depot, 10 points, pads, no-fly circles around airports, 250 m terrain grid). `pick_days.py` and `build_maps.py` rebuild them from downloaded ERA5 and Copernicus DEM files (`geo/`, not included; `build_maps.py` needs numpy and Pillow).
- `web/` browser game: `sim.js` port of `sim.py`, `game_src.html` the page, `audio.js` synthesized sound, `data.json` worlds and rivals (`build_data.py`), `build_page.py` builds `game.html`, `play.html` the same page as a standalone file.
- `extella/` model runs and the code that produced them: `player.py` (Extella rival), `noext.py` (rivals without Extella), `run30.py`, `drone_plan.py` the expert that ran on Extella (one file that `build_expert.py` builds from `sim.py`, `polet.py` and `world/`), `experts/` its earlier versions used at stages 1 to 3, `runs/`, `runs2/`, `runs3/`, `runs4b/` stages 1 to 4 (prompt, raw answers, check verdicts and advice, decisions, score), `noext/` the runs without Extella (`briefings.json` the exact prompt of Claude Opus 5, `big_plans.json` its answers; its system prompt is an earlier wording of `noext.SYSTEM`, without the example line "for another city, do not copy the numbers", which by the run timestamps was added before the Qwen 3.5 9B run), `extella_call.py` calls Extella with ids and key from environment variables. The per-second world report is left out of the run files; replay rebuilds it. A first stage 4 run, replaced by `runs4b`, is not included.

Code MIT, data and texts CC BY 4.0, third-party data under their own terms (`DATA-SOURCES.md`).

---

# Почувствуй себя курьером дронов

Двухчасовая смена доставки тремя грузовыми дронами в Алматы, Дубае или Роттердаме на настоящей погоде 2025 года: встречный ветер на обратном пути, мороз, разреженный воздух в горах и жара 46 °C. Открой `web/play.html`: пять коротких тренировок, потом смена против Qwen 3.5 9B с Extella, Claude Opus 5 и Qwen 3.5 9B без Extella. Всё перепроверяется без ключей и сети: `python3 verify.py` пересчитывает все опубликованные счета из записанных решений. Постановка и предсказания до прогонов: `POSTANOVKA.md`, итоги: `PREDSKAZANIYA.md`. Погода ERA5 (Copernicus) через Open-Meteo, рельеф Copernicus DEM, условия в `DATA-SOURCES.md`.
