"""Checks every episode in episodes/. Run before a pull request; CI runs the same.

python3 tools/check_episodes.py            # manifest, contract and each episode's tests
python3 tools/check_episodes.py --verify   # plus each episode's full re-verification of published results (slow)
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import contract

REQUIRED = ["id", "title", "summary", "authors", "license", "tests", "contract"]


def main():
    verify = "--verify" in sys.argv
    failed = []
    eps = sorted(d for d in os.listdir(os.path.join(ROOT, "episodes")) if os.path.isdir(os.path.join(ROOT, "episodes", d)))
    for ep in eps:
        folder = os.path.join(ROOT, "episodes", ep)
        print("==", ep)
        try:
            man = json.load(open(os.path.join(folder, "episode.json"), encoding="utf-8"))
            missing = [k for k in REQUIRED if k not in man]
            assert not missing, "episode.json is missing: %s" % ", ".join(missing)
            assert man["id"] == ep, "episode.json id must equal the folder name"
            assert {"en", "ru"} <= set(man["title"]), "title needs en and ru"
            for line in contract.check(folder, man["contract"]):
                print("   contract:", line)
            cmds = list(man["tests"]) + (list(man.get("verify", [])) if verify else [])
            for cmd in cmds:
                print("   $", cmd)
                r = subprocess.run(cmd, shell=True, cwd=folder, capture_output=True, text=True)
                tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
                for t in tail:
                    print("     ", t)
                assert r.returncode == 0, "command failed: " + cmd
        except Exception as e:
            print("   FAILED:", e)
            failed.append(ep)
    print()
    print("all episodes pass" if not failed else "failed: " + ", ".join(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
