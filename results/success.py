"""Counts the successes in the short results table (RESULTS.md) from the recorded runs. No keys, no network.

python3 results/success.py

A success is defined per game, the same way for every player:
  cafe   the month ends with a positive score (money made)          episodes/cafe/extella/runs/{g14,m_qwen,m_opus}
  zoo    the month ends with a positive score                       episodes/zoo/extella/runs/ny2-page, bench/runs/ny2{small,opus}
  drone  the shift ends with no forced landing and no lost drone    episodes/drone/extella/{runs4b,noext/small_*,noext/big_*}
  train  the train reaches the end of the line (unfinished == 0)    episodes/train/extella/{runs_v2,noext/small_*,noext/big_*}
Scores in the run files are recomputed from their decision logs by each episode's verify.py.
"""
import glob, json, os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "episodes")
RUN = re.compile(r"_s\d+(_cxs)?\.json$")


def runs(pattern):
    fs = sorted(f for f in glob.glob(os.path.join(ROOT, pattern)) if RUN.search(f))
    return [json.load(open(f, encoding="utf-8"))["score"] for f in fs]


GAMES = [
    ("cafe", "month in profit", lambda s: s["score"] > 0,
     {"Qwen 3.5 9B alone": "cafe/extella/runs/m_qwen/*.json", "Qwen 3.5 9B + Extella": "cafe/extella/runs/g14/*.json",
      "Claude Opus 5": "cafe/extella/runs/m_opus/*.json"}),
    ("zoo", "month in profit", lambda s: s["score"] > 0,
     {"Qwen 3.5 9B alone": "zoo/bench/runs/ny2small_*.json", "Qwen 3.5 9B + Extella": "zoo/extella/runs/ny2-page/*.json",
      "Claude Opus 5.5": "zoo/bench/runs/ny2opus_*.json"}),
    ("drone", "shift with no forced landing and no lost drone", lambda s: s["counts"]["forced"] == 0 and s["counts"]["lost"] == 0,
     {"Qwen 3.5 9B alone": "drone/extella/noext/small_*.json", "Qwen 3.5 9B + Extella": "drone/extella/runs4b/*.json",
      "Claude Opus 5": "drone/extella/noext/big_*.json"}),
    ("train", "train reached the end of the line", lambda s: s["parts"]["unfinished"] == 0,
     {"Qwen 3.5 9B alone": "train/extella/noext/small_*.json", "Qwen 3.5 9B + Extella": "train/extella/runs_v2/*.json",
      "Claude Opus 5": "train/extella/noext/big_*.json"}),
]

if __name__ == "__main__":
    for game, what, ok, who in GAMES:
        cells = []
        for name, pat in who.items():
            S = runs(pat)
            cells.append("%s %d/%d" % (name, sum(ok(s) for s in S), len(S)))
        print("%-6s %-48s %s" % (game, what, " | ".join(cells)))
