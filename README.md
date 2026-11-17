# Feel like a…

Short games where you do a real profession by its real rules, and race AI drivers, operators and planners on exactly the same situation. Each game ("episode") is a deterministic simulator with open data, a browser page, and recorded AI runs that anyone can recompute.

Extella is an extensible software environment that connects AI models, software tools and devices into working systems. Its core lets you configure and change how each module runs, from document processing to controlling sensors and robots.

| episode | play online | what you do |
|---|---|---|
| [Feel like a train driver](episodes/train/) | [extella.dev/train](https://extella.dev/train/) | drive real line profiles in Germany, Switzerland and Japan |
| [A Month at the Café](episodes/cafe/) | [extella.dev/cafe](https://extella.dev/cafe/) | run a Brooklyn coffee shop for 30 days: orders, shifts, prices |
| [A Month at the Zoo](episodes/zoo/) | [extella.dev/zoo](https://extella.dev/zoo/) | run a small Brooklyn zoo for 30 days: keepers, feed, visitors |
| [Feel like a drone courier](episodes/drone/) | [extella.dev/drone](https://extella.dev/drone/) | fly a shift of deliveries on a real map |
| [Rush hour](episodes/traffic/) | [extella.dev/traffic](https://extella.dev/traffic/) | write rules for a city's traffic lights in a small language, Extella checks them and plays the rush hour |
| [Template: water tower operator](episodes/_template/) | | copy it to start your own |

Every episode folder has the simulator, the browser page (`web/play.html`), the Extella side (expert or handler code), and `verify.py`, which recomputes every published number on your machine, without keys or network. The train, café, zoo and drone episodes also have the recorded AI runs with prompts and model answers; Rush hour has no AI players, its published check is browser against Extella on 450 rule sets.

## Why

Claims about AI agents are easy to make and hard to check. Here every claim comes with the decisions that produced it and a script that recomputes the score on your machine, without keys or network. The train driver episode shows a small local model with [Extella](https://extella.dev) beating a large cloud model that drives with feedback in 6 of 9 runs, with 1 to 2 model calls instead of 61. Run `python3 episodes/train/verify.py` and see for yourself.

## Add your own episode

See `CONTRIBUTING.md` and `CONTRACT.md`. Every pull request runs all episodes' tests, so new games cannot break existing ones; each episode folder has its own code owner.

## License

Code: MIT (`LICENSE`). Texts and data: CC BY 4.0 (`LICENSE-DATA.md`).

---

# Почувствуй себя…

Короткие игры, где ты работаешь по-настоящему, по правилам профессии, и соревнуешься с ИИ на той же самой ситуации. Каждый эпизод: детерминированный симулятор с открытыми данными, страница в браузере и записанные прогоны ИИ, которые любой может пересчитать у себя. Эпизоды: машинист, кофейня, зоопарк, курьер дронов, час пик. Свой эпизод добавляется по `CONTRIBUTING.md`.
