# Feel like a…

Short games where you do a real profession by its real rules, and race AI drivers, operators and planners on exactly the same situation. Each game ("episode") is a deterministic simulator with open data, a browser page, and recorded AI runs that anyone can recompute.

| episode | status |
|---|---|
| [Feel like a train driver](episodes/train/) | playable, AI runs recorded, fully recheckable |
| [Template: water tower operator](episodes/_template/) | copy it to start your own |

## Why

Claims about AI agents are easy to make and hard to check. Here every claim comes with the decisions that produced it and a script that recomputes the score on your machine, without keys or network. The train driver episode shows a small local model with [Extella](https://extella.dev) beating a large cloud model that drives with feedback in 6 of 9 runs, with 1 to 2 model calls instead of 61. Run `python3 episodes/train/verify.py` and see for yourself.

## Add your own episode

See `CONTRIBUTING.md` and `CONTRACT.md`. Every pull request runs all episodes' tests, so new games cannot break existing ones; each episode folder has its own code owner.

## License

Code: MIT (`LICENSE`). Texts and data: CC BY 4.0 (`LICENSE-DATA.md`).

---

# Почувствуй себя…

Короткие игры, где ты работаешь по-настоящему, по правилам профессии, и соревнуешься с ИИ на той же самой ситуации. Каждый эпизод: детерминированный симулятор с открытыми данными, страница в браузере и записанные прогоны ИИ, которые любой может пересчитать у себя. Первый эпизод: машинист. Свой эпизод добавляется по `CONTRIBUTING.md`.
