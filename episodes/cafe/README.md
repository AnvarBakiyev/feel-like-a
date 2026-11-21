# A Month at the Café

You own a small coffee shop in Brooklyn for 30 days. Every evening you decide for tomorrow:

- **orders** to three suppliers, each with its own delivery days and minimums: the dairy (milk, Mon/Wed/Fri), the roaster (beans and cups, Tue/Fri), the bakery (croissants, every day; they do not keep overnight);
- **shifts**: how many baristas and shift leads work the morning (7-11), midday (11-15) and evening (15-19); hire (starts in 3 days, $500) or let go;
- **prices and discounts** for latte, cold brew, drip, tea and croissant;
- **investments**: a second espresso machine ($3,500) or an ad campaign ($1,500);
- **event cards**: a health inspection, an equipment breakdown, a blogger, sidewalk repair, a catering order, a dairy price rise, a street fair, a blizzard, a competitor across the street.

Then the day plays out: guests come by part of the day, some leave when the queue is long, some cannot get what they want when an item runs out, milk expires, staff call in sick, a delivery may not arrive.

**Score** = profit for the month, minus $3 per guest who could not get their order, minus $5 per guest who left the queue, minus 10% of any loan. Leftover beans and cups and the second machine (at 80% of its price) count at the end. The whole month's rent is paid on day one, so every month starts in the red.

**Worlds**: 3 scenarios (calm October, January with a blizzard, October with a competitor opening nearby) x 3 streets (quiet side street, neighborhood, busy corridor) x 3 starting cash levels ($12k, $25k, $45k) = 27 worlds. A seed fixes everything random before the first decision: weather, events and their hidden outcomes, daily noise in demand. Same seed and same decisions give the same month byte for byte.

Wages, rent, supplier prices, card fees and weather come from public sources; every number in `city_ny.json` carries a tag (P primary source, R retelling, E our estimate). The list with links is `world/SOURCES.md`, the first sketch of the world `world/WORLD.md` (both in Russian).

## Play

Open `web/play.html` in a browser (English by default, Russian with one click). Three short lessons (an order, a shift, a card), then a month against the rivals below on the same world and seed. After each day you see their score for that day and, for the models, the reason they gave in their own words.

Or play in Extella: install the agent **Extella Cafe Month** from the Extella market as a new agent. Each evening you tell it in words what you want for tomorrow; the expert `cafe_month` (the same game and the same `cafe_game_plan` as in this folder) computes the exact orders and shifts and plays the day. The agent also checks a whole month log and returns its score. The agent and its experts are not in this repository; `extella/experts.lock.json` names the agent and the sha of every expert version the runs used.

| rival | sees | decides each evening | who writes the orders and shifts |
|---|---|---|---|
| Qwen 3.5 9B with Extella | the evening's view, like you, plus the expert's dollar estimates for each investment and card | an intent in a short plan language: stock lean/normal/safe, staff lean/normal/safe, price changes of -10..+10%, evening discount, what to buy, card answers | the expert `cafe_game_plan` on Extella turns the intent into exact orders and shifts; the game's check can reject with a reason and the model corrects |
| Qwen 3.5 9B alone | the same evening text | the full decision: every order, every shift, prices, cards | the model itself; on a rejection it gets the reason and tries again (up to 3 times), otherwise the evening passes with no new decision |
| Claude Opus 5 alone | the same evening text | the full decision, same JSON as Qwen alone | the model itself, playing evening by evening in a Claude Code session through `extella/play_cli.py` |
| simple programs (not AI) | the evening's view | careful: order by the forecast with a margin, shifts by the forecast; plenty, thrifty, bare: the same with one thing changed | the program |

Both Qwen 3.5 9B players are the same model (`qwen/qwen3.5-9b` on OpenRouter, providers DeepInfra and Parasail, temperature 0) with the same evening text; the difference is who computes the orders and shifts. The evening text and the rules the models get are in Russian. Claude Opus 5 played 11 of the 27 worlds (all nine at $25k, plus two more on the neighborhood street). Two of its months were set aside after signs that the agent had read the simulator's source; both were played again with opening the source forbidden, and only the replays are published.

## Results (seed 1)

All 27 worlds:

| player | average score | ahead of Qwen 3.5 9B with Extella |
|---|---|---|
| **Qwen 3.5 9B with Extella** | **$5,092** | |
| careful program | $2,225 | 0 of 27 |
| plenty program | $1,088 | 3 of 27 |
| thrifty program | $1,046 | 0 of 27 |
| bare program | -$3,148 | 0 of 27 |
| Qwen 3.5 9B alone | -$60,676 | 0 of 27 (best month -$44,367, worst -$88,455) |

What happened to Qwen 3.5 9B alone, in the recorded counts: of about 6,790 guests a month it served 2,371 on average; 4,809 could not get their order. Its average stockout penalty was -$14,428 and its wages -$34,756, against -$384 and -$18,857 with Extella. It needed 1.8 model calls per evening and fell back to no new decision on 21 of 810 evenings. With Extella the same model made 1.0 call per evening and the expert 2.0.

The 11 worlds Claude Opus 5 played:

| world | Qwen 3.5 9B with Extella | Claude Opus 5 | Qwen 3.5 9B alone | careful |
|---|---|---|---|---|
| calm, corridor, $25k | $7,641 | $6,947 | -$77,152 | $2,176 |
| calm, neighborhood, $45k | $11,432 | $7,904 | -$59,177 | $8,191 |
| calm, neighborhood, $12k | $8,230 | $8,255 | -$58,369 | $8,191 |
| calm, neighborhood, $25k | $11,439 | $7,679 | -$60,525 | $8,191 |
| calm, quiet, $25k | $4,446 | $1,260 | -$53,307 | $2,935 |
| competitor, corridor, $25k | $5,143 | $4,412 | -$74,331 | $2,866 |
| competitor, neighborhood, $25k | $8,206 | $5,871 | -$52,963 | $5,077 |
| competitor, quiet, $25k | -$2,800 | $350 | -$49,450 | -$4,030 |
| winter, corridor, $25k | $7,675 | $4,692 | -$75,589 | $4,100 |
| winter, neighborhood, $25k | $8,789 | $7,768 | -$50,086 | $5,651 |
| winter, quiet, $25k | $2,620 | -$3,395 | -$49,085 | $777 |
| **average** | **$6,620** | **$4,704** | **-$60,003** | **$4,011** |

Qwen 3.5 9B with Extella scored higher than Claude Opus 5 in 9 of 11 worlds. This is one seed per world: read it as a recorded race, not as a measure of the spread.

## Recheck everything

```bash
python3 test_sim.py        # simulator: seed, hidden state, rules, all 27 worlds, recorded runs replay
python3 test_replay.py     # a decision log replays to the same score; forgeries are rejected
python3 web/make_parity.py && node web/parity.mjs   # browser sim.js equals sim.py to the last digit (84 traces)
python3 verify.py          # every published number recomputed from recorded decisions (~1 min)
python3 verify.py --extella   # plus the expert checks, through the episode's agent on Extella
```

`verify.py` needs no keys or network. It replays every recorded month and compares the score and every day's score with the run file and with `web/data.json` (what the page shows). It also checks where each decision came from. For Qwen 3.5 9B with Extella, `verify.py --extella` asks the expert `cafe_game_plan` in the agent **Extella Cafe Month** (install it from the Extella market as a new agent, set `EXTELLA_TOKEN_FILE` and `EXTELLA_AGENT`, see `extella/expert_json.py`) to turn each recorded intent into a decision and compares it with the recorded one (810 of 810 evenings). The expert code is not in this repository; `extella/experts.lock.json` keeps the sha of the version the runs used. For Qwen 3.5 9B alone, each recorded prompt is rebuilt from the game and each decision is rebuilt from the recorded raw answer (810 of 810). The simple programs are recomputed from `policies.py`.

## Files

- `sim.py` simulator (`Game`, `observe`, `decide`, `step`, `score`, `replay`), `city_ny.json` the city with source tags, `cards_ny.json` event card texts, `policies.py` and `drivers.py` simple programs, `replay.py` score from a decision log.
- `web/` the browser game: `sim.js` port of the simulator, `game_src.html` page, `build_data.py` builds `data.json` from the recorded runs, `build_page.py` joins them into one page, `play.html` the ready page.
- `extella/runs/g14` Qwen 3.5 9B with Extella: per evening the prompt, the raw model answers, the intent, the expert's estimates and decision. `extella/runs/m_qwen` Qwen 3.5 9B alone: prompt, raw answers, decision. `extella/runs/m_opus` Claude Opus 5: decision and its stated reason per evening (the evening text is what `play_cli.py` prints and can be rebuilt by replay; the task text the agent got is not stored).
- `extella/experts.lock.json` the experts of the market agent by sha: `cafe_game_plan` (`4a9db5d491b0`, as recorded in every g14 run) and `cafe_month`, the whole game in one expert; `expert_json.py` calls them on Extella, `player.py` the player with Extella, `player_bare.py` the player without, `play_cli.py` evening-by-evening play for an agent, `llm.py` model calls (Ollama or OpenRouter; key from `OPENROUTER_API_KEY`), `extella_call.py` the call to Extella (key and agent from `EXTELLA_TOKEN_FILE`, `EXTELLA_AGENT`). Comments in these files are in Russian and sometimes point to our internal measurement log, which is not published.

---

# Месяц кофейни

Ты владелец маленькой кофейни в Бруклине на 30 дней: каждый вечер заказы трём поставщикам, смены, цены, вложения и ответы на карточки событий. Счёт: прибыль минус $3 за гостя без позиции, $5 за ушедшего из очереди и 10 % займа. Открой `web/play.html`: три коротких урока, потом месяц против Qwen 3.5 9B с Extella, Claude Opus 5 и Qwen 3.5 9B без Extella на том же мире. На 27 мирах Qwen 3.5 9B с Extella в среднем $5 092, без Extella -$60 676; на 11 мирах, сыгранных Claude Opus 5, $6 620 против $4 704. Всё перепроверяется без ключей и сети: `python3 verify.py` пересчитывает каждое опубликованное число из записанных решений. Источники цифр: `world/SOURCES.md`.
