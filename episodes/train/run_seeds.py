"""Тестовые машинисты на 20 зёрнах каждого участка: средний счёт и его части."""
import json, sys
import sim, drivers

def run(n=20):
    out = {}
    for lid in sim.LINES:
        for name in ("full", "careful"):
            rows = []
            for seed in range(1, n + 1):
                g = sim.play(seed, lid, getattr(drivers, name))
                s = g.score(); s["weather"] = g.W["weather"]; s["seed"] = seed
                rows.append(s)
            avg = lambda k: round(sum(r["parts"][k] for r in rows) / n, 1)
            out[lid + "/" + name] = {"score": round(sum(r["score"] for r in rows) / n, 1), "min": min(r["score"] for r in rows), "max": max(r["score"] for r in rows),
                                     "parts": {k: avg(k) for k in rows[0]["parts"]}, "kwh": round(sum(r["kwh"] for r in rows) / n),
                                     "by_weather": {w: round(sum(r["score"] for r in rows if r["weather"] == w) / max(1, sum(1 for r in rows if r["weather"] == w))) for w in ("dry", "wet", "leaves")}}
    return out

if __name__ == "__main__":
    R = run(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
    for k, v in R.items():
        print(k.ljust(22), "счёт %7.1f (%6.1f…%6.1f)" % (v["score"], v["min"], v["max"]), "кВт·ч", v["kwh"], "погода", v["by_weather"])
        print(" " * 22, v["parts"])
    json.dump(R, open("run_seeds_20.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
