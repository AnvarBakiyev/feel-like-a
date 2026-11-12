# Adding your episode

1. Fork the repository.
2. `cp -r episodes/_template episodes/<your-id>` and build your profession inside that folder only. Read `CONTRACT.md`.
3. Add one line to `.github/CODEOWNERS`: `/episodes/<your-id>/  @<your-github-login>`. From then on changes to your folder need your approval.
4. Run `python3 tools/check_episodes.py` until it prints "all episodes pass".
5. Open a pull request. CI runs every episode's tests; a change that breaks any episode cannot be merged.

Rules: your own mechanics (do not copy existing games), no real company brands, no personal data, sources for every real number, Russian and English texts. Code under MIT, texts and data under CC BY 4.0 (see `LICENSE`, `LICENSE-DATA.md`).

---

# Как добавить свой эпизод

Сделай копию репозитория (fork), скопируй `episodes/_template` в `episodes/<твой-id>` и строй свою профессию только внутри этой папки по `CONTRACT.md`. Допиши строку про свою папку в `.github/CODEOWNERS`. Запусти `python3 tools/check_episodes.py` до «all episodes pass» и пришли запрос на слияние (pull request). Робот прогонит тесты всех эпизодов: правка, которая ломает чужую игру, не сольётся. Механика своя, без чужих игр и брендов, у каждой цифры источник, тексты на русском и английском.
