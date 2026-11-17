// The browser's rush hour for a list of cases, to compare with the Python handler: node web/parity.mjs cases.json
// A case is [level, seed or null, rules]; seed null is the level's own day (the one extella.dev/traffic plays).
import { LEVELS, simulate } from "./traffic_core.js";
import { readFileSync } from "fs";
const cases = JSON.parse(readFileSync(process.argv[2], "utf8"));
const out = cases.map(([level, seed, rules]) => {
  const own = LEVELS[level].seed;
  if (seed !== null) LEVELS[level].seed = seed;
  try {
    const o = simulate(level, rules, { record: false });
    return { problems: o.problems, result: o.result || null };
  } finally { LEVELS[level].seed = own; }
});
process.stdout.write(JSON.stringify(out));
