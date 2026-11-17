# Rush hour

A cartoon city stuck in traffic. You are the mayor: decide what stands at every crossing and get everyone home before rush hour ends. There are more crossings than traffic lights, drivers block crossings they cannot leave, and on two levels an ambulance has to get through.

| level | crossings | lights | what it asks |
|---|---|---|---|
| `district` | 6 | 2 | where to put two lights, which street is the main one |
| `ambulance` | 9 | 3 | let an ambulance cross the city every 40 s along the middle street |
| `gridlock` | 12 | 4 | a Friday wave from the north, box junctions, two ambulances |

Each level has three goals (cars home, average wait, and either cars still stuck or the ambulance's time); a star for each. The city is a game, not a model of a real one: speeds, flows and goals are our own choices, and no number here comes from traffic data.

## The rules are a program

Your choices are a program in a small language called **traffic**. The buttons on the page write it; "Rules as text" shows it:

```
# a comment
A: light, north-south 12, east-west 8    a light with a fixed plan, green to each street in seconds
A: light, longest queue, min 5, max 25   green to the street with the longer queue
A: light, offset 4                       the plan starts 4 s later (green waves)
B: main north-south                      no light: north-south has the right of way
C: stop                                  no light: everyone stops and goes in the order they came
D: box                                   nobody drives in unless they can drive out
all: box                                 the same for every crossing
ambulance first                          lights turn green for an ambulance; signs let it through
```

Russian words work too («светофор», «главная север-юг», «стоп», «вафельная разметка», «пропускать скорую»). The handler checks the program before anything runs: a green shorter than 3 s, a cycle longer than 70 s, more lights than the city has, or a plan that gives green to only one street is refused, with the reason in words. Then it runs rush hour by the rules, car by car, with a fixed 0.1 s step and seeded random numbers, so the same rules always give the same day.

On extella.dev the same handler is registered as a language on an Extella device. "Confirm on the server" saves your rules as an expert in the traffic language and the device replays the day; the page compares the server's fingerprint of the result with its own, and the server's result goes into the table of mayors.

## Play

Open `web/play.html` in a browser. The page draws the city with Three.js from a CDN, so it needs a network connection; the simulation itself runs in the page. "Confirm on the server" and "Best mayors" talk to the extella.dev server and show an error when the page is opened from disk. To play with them, use [extella.dev/traffic](https://extella.dev/traffic/).

## As an episode

The whole game is one decision taken before the first step: the rules.

```python
from sim import Game
g = Game(None, level="district")      # None: the day played on extella.dev (seeds 41, 53, 67); any other seed is another day
g.decide({"rules": "A: light, ns 12, ew 8\nall: box"})   # [] or rejections with the handler's reason
g.step()                               # the whole rush hour
g.score()                              # {"score": stars 0..3, "parts": {...}, "sha": the result's fingerprint, "rank_key": ...}
```

The table of mayors orders results by stars, then shorter average wait, then more cars home; `rank_key` carries the same order. Hidden from `observe()`: the seed of the cars' random draws, a duck family that crosses one street, and the Friday wave on `gridlock`. You meet them on the street, as players on the page do.

Simple non-AI players are in `drivers.py`: `keep` writes nothing, `plan` is a rule of thumb (lights in the middle, the busier axis as the main street, box junctions everywhere). Neither earns more than one star on the live days, which is the point of the game.

## Recheck

```bash
python3 test_sim.py   # seed, replay, hidden state, refusals, browser = handler, the handler rebuilt byte for byte
python3 verify.py     # the published comparison: 450 rule sets, browser vs handler, 0 differences (~1-2 min, needs Node)
```

The page says the browser and the server were compared on 450 sets of rules, from mistakes to whole city plans, with not a single difference. `conformance.py` draws those 450 sets from a fixed seed (300 valid city plans and 150 random, often broken, rule sets), runs each in Python and in Node and compares the refusals and every number of the result; `conformance_result.json` is the published run: 450 sets, 156 refused, 294 full rush hours, 0 mismatches. `verify.py` reruns it and compares.

No AI model plays this episode yet: there are no recorded model runs. A model that writes rules for a level and reads the refusals and the result back would be a fair first race.

## Files

`traffic_core.py` the language and the simulation in Python (the handler's body), `traffic_handler_v1.py` the handler as registered (core + levels taken from the browser's file + `handler_tail_traffic.py`), `build_traffic.py` rebuilds it, `conformance.py` the browser vs handler check, `sim.py` / `replay.py` / `drivers.py` the episode wrapper, `web/` the page (`traffic_core.js` the same language and simulation in JavaScript, `app.js` the 3D city, `build_play.py` makes `play.html`, `parity.mjs` used by the tests), `extella/` the Extella side: `demo_register_traffic_v1.fython` registers the handler on a device, `setup_traffic.py` saves and runs it (reads the key, agent and device ids from environment variables), `traffic_api.py` the server endpoints for confirming a result and the table of mayors.

---

# Час пик

Мультяшный город в пробках. Ты мэр: решаешь, что стоит на каждом перекрёстке, и разводишь всех по домам до конца часа пик. Перекрёстков больше, чем светофоров, водители запирают перекрёстки, а на двух уровнях через город едет скорая.

Правила города это программа на маленьком языке traffic. Обработчик сначала проверяет её и словами объясняет, что не так, потом прогоняет час пик машина за машиной; одни и те же правила всегда дают один и тот же день. Открой `web/play.html` (город рисуется через Three.js из сети; кнопки сервера работают только на extella.dev/traffic). Перепроверка: `python3 test_sim.py` и `python3 verify.py` (450 наборов правил, браузер против обработчика, 0 расхождений). Записанных прогонов моделей в этом эпизоде пока нет.
