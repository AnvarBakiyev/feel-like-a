# Feel like a train driver

Three real line profiles, three trains, one controller:

| line | train | what it teaches |
|---|---|---|
| Germany, Cologne – Frankfurt Airport (high-speed line) | ICE 3 type, 470 t, 300 km/h | coasting and energy on 40 ‰ grades |
| Switzerland, Gotthard mountain line, Erstfeld – Biasca | Re 6/6 + 900 t freight | adhesion on 25 ‰ climbs, sand, banking engine |
| Japan, Tokaido Shinkansen, Tokyo – Nagoya | N700S type, 285 km/h | punctuality and stopping at the mark |

Every number has a source tag in `lines/` and `trains/` (`_tag`, `_sources`): P primary source, R retelling, E our estimate. Station distances, speed limits and train data come from public sources; where we found nothing (e.g. exact location of 40 ‰ grades, service brake rates) the value is an estimate and marked so.

## Play

Open `web/play.html` in a browser. Five short drills teach the controls; then pick a line and a run. Your rivals on the same run (same weather, track work, delay and train ahead):

| rival | sees | decides | who drives |
|---|---|---|---|
| Extella | the briefing | 1 to 3 times before departure | Extella's handler: a small model (Qwen 9B, on a laptop) writes intent in a trip language, the handler checks it by simulation and drives |
| small model without Extella | the briefing | once | the plan runs literally |
| large model without Extella | the briefing | once | the plan runs literally |
| large model with feedback | the cab, like you | during the run, about 61 times | itself |
| simple program (not AI) | the cab | every half second | itself |

Result on the same 9 runs: Extella won 6 of 9 against the large model with feedback, 554 points on average against 253, with 1 to 2 model calls instead of 61; protection never stepped in for Extella, 18 times for the large model. All 30-run averages and their limits are in `PROVERKA.md`.

## Recheck everything

```bash
python3 test_sim.py        # simulator: seed, hidden state, rules, timetable, trip language
python3 test_replay.py     # a decision log replays to the same score; forgeries are rejected
python3 web/make_parity.py && node web/parity.mjs   # browser sim.js equals sim.py to the last digit
python3 verify.py          # every published score recomputed from recorded decisions (~10 min)
```

No keys or network needed: model answers are stored in `extella/`, scores are recomputed. Predictions were written before every run and kept with the misses: `PREDSKAZANIYA.md` (Russian). How the large model was prompted: `extella/noext/PROMPTS.md`.

## Files

`sim.py` simulator (0.5 s step, Davis/Strahl resistance, adhesion, ETCS-like braking curves with grade), `drivers.py` simple programs, `poezdka.py` trip language and handler, `replay.py` score from a decision log, `verify.py` full recheck, `web/` browser game (`sim.js`, `scene.js` side view, `cab.js` cab view and display), `extella/` model runs and the code that produced them (`extella_call.py` reads ids and key from environment variables).

---

# Почувствуй себя машинистом

Три настоящих профиля участков, три поезда, один контроллер. Открой `web/play.html`: пять коротких тренировок, потом рейс против Extella и других ИИ-машинистов на том же рейсе. Всё перепроверяется без ключей и сети: `python3 verify.py` пересчитывает все опубликованные счета из записанных решений. Подробно по-русски: `PROVERKA.md`, предсказания и итоги: `PREDSKAZANIYA.md`.
