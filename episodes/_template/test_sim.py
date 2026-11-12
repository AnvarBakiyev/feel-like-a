"""Episode's own tests: python3 test_sim.py"""
import json, sim, drivers

def run(seed):
    g = sim.Game(seed)
    while not g.done():
        g.decide(drivers.simple(g.observe(), g)); g.step()
    return g

assert json.dumps(run(1).journal) == json.dumps(run(1).journal)
assert run(1).score() != run(2).score()
assert sim.Game(1).decide({"pump": 500})[0]["code"] == "range"
print("ok", run(1).score())
