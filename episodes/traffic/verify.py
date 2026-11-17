"""Rechecks the published number of Rush hour: "the browser and the server compared on 450 sets of rules, not a single difference".

Reruns conformance.py 450 (the same 450 rule sets, drawn from a fixed seed) and compares with conformance_result.json:
cases, refused, ran, the stars of every run, and zero mismatches. The published file is kept as it was. Needs Node. ~1-2 min.
python3 verify.py
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "conformance_result.json")
KEYS = ("cases", "levels", "mismatches", "refused", "ran", "stars")


def main():
    published = open(PATH, encoding="utf-8").read()
    want = json.loads(published)
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "conformance.py"), str(want["cases"])], cwd=HERE, check=True, capture_output=True, text=True)
        got = json.load(open(PATH, encoding="utf-8"))
    finally:
        open(PATH, "w", encoding="utf-8").write(published)
    bad = [k for k in KEYS if json.dumps(want[k], sort_keys=True) != json.dumps(got[k], sort_keys=True)]
    for k in KEYS:
        print("%-10s published %-40s recomputed %s" % (k, json.dumps(want[k]), json.dumps(got[k])))
    assert got["mismatches"] == 0, "the browser and the handler differ on %d rule sets" % got["mismatches"]
    assert not bad, "differs from the published result: " + ", ".join(bad)
    print("verified: %d rule sets, %d ran a full rush hour, browser = handler on every one" % (got["cases"], got["ran"]))


if __name__ == "__main__":
    main()
