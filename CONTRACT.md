# Episode contract

What every episode must provide. The CI (`tools/check_episodes.py`) checks the starred items automatically.

## Files

```
episodes/<id>/
  episode.json   * id, title {en, ru}, summary, authors, license, tests, contract (see below)
  sim.py         * class Game
  replay.py      * function replay
  README.md        what the profession is, how to play, how to recheck
  test_*.py      * your own tests, listed in episode.json "tests"
  (world data with source tags, web/ page, model runs, PREDICTIONS.md: optional but welcome)
```

## Simulator

```python
g = Game(seed, **settings)
while not g.done():
    obs = g.observe()          # only what the player knows now
    rej = g.decide(dec)        # list of rejections {field, code, ru, en}; accepted parts apply, rejected do not
    g.step()                   # one step of the world; a report is appended to g.journal
g.score()                      # {"score", "parts", "counts"}

replay(seed, settings, [[step, decision], ...]) -> {"score", ...}   # raises ValueError on anything that is not a decision
```

Rules:
1. * **One seed, one world.** Everything random is built from the seed before the first decision and does not depend on decisions. Same seed and same decisions give the same journal byte for byte.
2. * **Hidden stays hidden.** List hidden fields in `contract.hidden_keys`; they must never appear in `observe()`.
3. * **Replay.** The decision log a page records (each accepted decision with its step number) replays to the same score. Leaderboards accept only replayed scores.
4. **Rejections explain the rule** in Russian and English: "Departure is at 10:03:00, it is 10:01:12: you cannot leave early."
5. **Browser port, if you make a page:** no `random`, `round`, `pow`, `exp` in the step loop; your own PRNG (mulberry32 with FNV-1a substreams); same order of operations; a parity test against Python.
6. **Sources.** Every real-world number carries a tag: P primary source (agency, standard, operator), R retelling (press, Wikipedia), E our estimate. If you found nothing, say so.

## `contract` in episode.json

```json
"contract": {"settings": {"line_id": "ch_gotthard"}, "seeds": [1, 2], "driver": "drivers:full", "hidden_keys": ["adhesion_factor"]}
```

`driver` is a simple non-AI player `module:function(obs, game) -> decision or None` used to exercise the contract.

## Model runs (optional)

If you race models: write the prediction before the run, store prompts and raw answers, recompute scores with your own `verify.py`, and include a model that decides during the run with feedback, not only a plan written in advance. A plan that runs blind is easy to dismiss as an unfair comparison.
